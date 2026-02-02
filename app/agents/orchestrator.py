"""
Review Orchestrator - LangGraph-based agent orchestration.

This is the brain of the system. It coordinates:
1. AnalyzerAgent → Parses and understands the PR
2. ContextAgent → Retrieves relevant context
3. ReviewerAgent → Generates review feedback

Uses LangGraph for stateful, graph-based agent orchestration.
"""

from typing import TypedDict, Annotated, Literal, Any
import operator
import asyncio

from langgraph.graph import StateGraph, END

from .analyzer import AnalyzerAgent, AnalysisResult
from .context import ContextAgent, RetrievedContext
from .reviewer import ReviewerAgent, ReviewResult

from ..core.logging import get_logger

logger = get_logger(__name__)


class ReviewState(TypedDict):
    """
    State that flows through the review graph.
    
    This is the central data structure that accumulates results
    as the workflow progresses through each node.
    """
    # Input
    pr_data: dict
    
    # Intermediate results
    analysis: AnalysisResult | None
    context: dict[str, RetrievedContext]  # file_path -> context
    
    # Output
    review: ReviewResult | None
    
    # Control flow
    errors: Annotated[list[str], operator.add]  # Accumulates errors
    status: str
    retry_count: int


class ReviewOrchestrator:
    """
    Orchestrates the code review process using LangGraph.
    
    The graph flow:
    
    ┌─────────┐
    │  Start  │
    └────┬────┘
         │
         ▼
    ┌─────────────┐
    │  Analyze PR │ ──────────────────┐
    └──────┬──────┘                   │
           │                          │ (on error)
           ▼                          ▼
    ┌──────────────────┐        ┌─────────────┐
    │  Check Analysis  │───────►│ Handle Error│
    └────────┬─────────┘        └──────┬──────┘
             │ (success)               │
             ▼                         │
    ┌─────────────────┐                │
    │  Get Context    │                │
    │  (parallel)     │                │
    └────────┬────────┘                │
             │                         │
             ▼                         │
    ┌─────────────────┐                │
    │ Generate Review │                │
    └────────┬────────┘                │
             │                         │
             ▼                         │
    ┌─────────────────┐                │
    │  Store Feedback │◄───────────────┘
    │   (learning)    │
    └────────┬────────┘
             │
             ▼
    ┌─────────┐
    │   END   │
    └─────────┘
    """
    
    def __init__(self):
        self.analyzer = AnalyzerAgent()
        self.context_agent = ContextAgent()
        self.reviewer = ReviewerAgent()
        
        self.graph = self._build_graph()
        
        logger.info("ReviewOrchestrator initialized")
    
    def _build_graph(self) -> StateGraph:
        """
        Build the LangGraph workflow.
        
        LangGraph uses a state machine approach where:
        - Nodes are processing functions
        - Edges define the flow between nodes
        - State is passed and accumulated through the graph
        """
        # Create the graph with our state schema
        workflow = StateGraph(ReviewState)
        
        # Add nodes (processing steps)
        workflow.add_node("analyze", self._analyze_node)
        workflow.add_node("get_context", self._context_node)
        workflow.add_node("generate_review", self._review_node)
        workflow.add_node("store_learning", self._store_learning_node)
        workflow.add_node("handle_error", self._error_node)
        
        # Set the entry point
        workflow.set_entry_point("analyze")
        
        # Add conditional edge after analysis
        workflow.add_conditional_edges(
            "analyze",
            self._should_continue_after_analysis,
            {
                "continue": "get_context",
                "error": "handle_error"
            }
        )
        
        # Add conditional edge after context retrieval
        workflow.add_conditional_edges(
            "get_context",
            self._should_continue_after_context,
            {
                "continue": "generate_review",
                "error": "handle_error"
            }
        )
        
        # Add conditional edge after review generation
        workflow.add_conditional_edges(
            "generate_review",
            self._should_continue_after_review,
            {
                "continue": "store_learning",
                "error": "handle_error"
            }
        )
        
        # Final edges
        workflow.add_edge("store_learning", END)
        workflow.add_edge("handle_error", END)
        
        # Compile the graph
        compiled = workflow.compile()
        
        logger.debug("LangGraph workflow compiled successfully")
        return compiled
    
    # ==================== Node Functions ====================
    
    async def _analyze_node(self, state: ReviewState) -> dict:
        """
        Node: Analyze the PR.
        
        This is the first processing step. It parses the PR diff,
        categorizes changes, and prepares structured data.
        """
        logger.info("Executing analyze node", pr=state["pr_data"].get("number"))
        
        try:
            analysis = await self.analyzer.analyze_pr(state["pr_data"])
            
            return {
                "analysis": analysis,
                "status": "analyzed"
            }
            
        except Exception as e:
            logger.error("Analysis failed", error=str(e))
            return {
                "errors": [f"Analysis failed: {str(e)}"],
                "status": "error"
            }
    
    async def _context_node(self, state: ReviewState) -> dict:
        """
        Node: Retrieve context for each changed file.
        
        Runs context retrieval in parallel for all files to speed up processing.
        """
        logger.info("Executing context node")
        
        try:
            changes = state["analysis"].get("changes", [])
            
            if not changes:
                return {
                    "context": {},
                    "status": "context_retrieved"
                }
            
            # Retrieve context for all files in parallel
            async def get_file_context(change):
                try:
                    ctx = await self.context_agent.get_context(change)
                    return (change.get("file_path", ""), ctx)
                except Exception as e:
                    logger.warning("Context retrieval failed for file", 
                                 file=change.get("file_path"), error=str(e))
                    return (change.get("file_path", ""), {
                        "similar_reviews": [],
                        "coding_standards": [],
                        "documentation": [],
                        "summary": "Context retrieval failed."
                    })
            
            # Run parallel retrieval (limit concurrency to avoid rate limits)
            semaphore = asyncio.Semaphore(3)  # Max 3 concurrent requests
            
            async def bounded_get_context(change):
                async with semaphore:
                    return await get_file_context(change)
            
            results = await asyncio.gather(
                *[bounded_get_context(change) for change in changes]
            )
            
            # Convert to dict
            context_dict = {file_path: ctx for file_path, ctx in results}
            
            logger.info("Context retrieved", files=len(context_dict))
            
            return {
                "context": context_dict,
                "status": "context_retrieved"
            }
            
        except Exception as e:
            logger.error("Context retrieval failed", error=str(e))
            return {
                "errors": [f"Context retrieval failed: {str(e)}"],
                "status": "error"
            }
    
    async def _review_node(self, state: ReviewState) -> dict:
        """
        Node: Generate the review.
        
        Uses the analysis and context to generate review comments.
        """
        logger.info("Executing review node")
        
        try:
            # Merge context into a single context object
            # The reviewer expects a single context, so we merge all file contexts
            merged_context = self._merge_contexts(state.get("context", {}))
            
            review = await self.reviewer.review(
                state["analysis"],
                merged_context
            )
            
            return {
                "review": review,
                "status": "reviewed"
            }
            
        except Exception as e:
            logger.error("Review generation failed", error=str(e))
            return {
                "errors": [f"Review generation failed: {str(e)}"],
                "status": "error"
            }
    
    async def _store_learning_node(self, state: ReviewState) -> dict:
        """
        Node: Store feedback for future learning.
        
        This enables the system to learn from its reviews over time.
        """
        logger.info("Executing store_learning node")
        
        try:
            # Store each reviewed file for future reference
            for change in state["analysis"].get("changes", []):
                # Find comments for this file
                file_comments = [
                    c for c in state["review"].get("comments", [])
                    if c.get("file_path") == change.get("file_path")
                ]
                
                if file_comments:
                    await self.context_agent.store_review({
                        "code": change.get("diff", "")[:2000],
                        "feedback": "\n".join([c.get("comment", "") for c in file_comments]),
                        "file_path": change.get("file_path", ""),
                        "language": change.get("language", "unknown"),
                        "outcome": "pending"  # Updated when review is accepted/rejected
                    })
            
            return {
                "status": "completed"
            }
            
        except Exception as e:
            # Don't fail the whole review if learning storage fails
            logger.warning("Failed to store learning", error=str(e))
            return {
                "status": "completed"
            }
    
    async def _error_node(self, state: ReviewState) -> dict:
        """
        Node: Handle errors gracefully.
        
        Creates a fallback review when processing fails.
        """
        logger.warning("Executing error handler", errors=state.get("errors", []))
        
        # Determine what information we have
        pr_number = state["pr_data"].get("number", 0)
        errors = state.get("errors", ["Unknown error occurred"])
        
        # Check if we can do a partial review
        if state.get("analysis") and state.get("status") == "context_retrieved":
            # We have analysis, just context or review failed
            # Try a simplified review without context
            try:
                logger.info("Attempting simplified review without context")
                review = await self.reviewer.review(
                    state["analysis"],
                    {"summary": "Context unavailable - reviewing without historical context."}
                )
                return {
                    "review": review,
                    "status": "completed_with_errors"
                }
            except Exception as e:
                logger.error("Simplified review also failed", error=str(e))
        
        # Create fallback review
        fallback_review: ReviewResult = {
            "pr_number": pr_number,
            "overall_assessment": "Automated review could not be completed due to errors.",
            "approval_recommendation": "comment",
            "comments": [],
            "summary": f"The automated code review encountered errors and could not complete:\n\n" + 
                      "\n".join([f"- {e}" for e in errors]) +
                      "\n\nPlease request a manual review.",
            "stats": {"critical": 0, "warning": 0, "suggestion": 0, "total": 0}
        }
        
        return {
            "review": fallback_review,
            "status": "failed"
        }
    
    # ==================== Routing Functions ====================
    
    def _should_continue_after_analysis(self, state: ReviewState) -> Literal["continue", "error"]:
        """Determine whether to continue after analysis."""
        if state.get("status") == "error" or not state.get("analysis"):
            return "error"
        
        # Check if there are any changes to review
        if not state["analysis"].get("changes"):
            logger.info("No changes to review")
            # Still continue - we'll create an empty review
        
        return "continue"
    
    def _should_continue_after_context(self, state: ReviewState) -> Literal["continue", "error"]:
        """Determine whether to continue after context retrieval."""
        if state.get("status") == "error":
            return "error"
        return "continue"
    
    def _should_continue_after_review(self, state: ReviewState) -> Literal["continue", "error"]:
        """Determine whether to continue after review generation."""
        if state.get("status") == "error" or not state.get("review"):
            return "error"
        return "continue"
    
    # ==================== Helper Methods ====================
    
    def _merge_contexts(self, contexts: dict[str, RetrievedContext]) -> dict:
        """Merge multiple file contexts into a single context object."""
        if not contexts:
            return {
                "similar_reviews": [],
                "coding_standards": [],
                "documentation": [],
                "summary": "No context available."
            }
        
        # Aggregate all context items
        all_reviews = []
        all_standards = []
        all_docs = []
        summaries = []
        
        for file_path, ctx in contexts.items():
            all_reviews.extend(ctx.get("similar_reviews", []))
            all_standards.extend(ctx.get("coding_standards", []))
            all_docs.extend(ctx.get("documentation", []))
            if ctx.get("summary"):
                summaries.append(f"**{file_path}:** {ctx['summary']}")
        
        # Deduplicate by content
        def dedupe(items):
            seen = set()
            unique = []
            for item in items:
                content = item.get("content", "")[:100]
                if content not in seen:
                    seen.add(content)
                    unique.append(item)
            return unique
        
        return {
            "similar_reviews": dedupe(all_reviews)[:10],  # Limit to top 10
            "coding_standards": dedupe(all_standards)[:5],
            "documentation": dedupe(all_docs)[:5],
            "summary": "\n\n".join(summaries) if summaries else "No context available."
        }
    
    # ==================== Public API ====================
    
    async def review_pr(self, pr_data: dict) -> ReviewResult:
        """
        Main entry point: Review a pull request.
        
        Args:
            pr_data: PR data from GitHub API, expected format:
                {
                    "number": int,
                    "title": str,
                    "body": str,
                    "files": [
                        {
                            "filename": str,
                            "status": str,
                            "additions": int,
                            "deletions": int,
                            "patch": str
                        }
                    ]
                }
            
        Returns:
            ReviewResult with comments and recommendations
        """
        logger.info("Starting PR review", pr=pr_data.get("number"))
        
        # Initial state
        initial_state: ReviewState = {
            "pr_data": pr_data,
            "analysis": None,
            "context": {},
            "review": None,
            "errors": [],
            "status": "started",
            "retry_count": 0
        }
        
        # Run the graph
        try:
            final_state = await self.graph.ainvoke(initial_state)
            
            logger.info("PR review completed", 
                       pr=pr_data.get("number"),
                       status=final_state.get("status"))
            
            return final_state["review"]
            
        except Exception as e:
            logger.error("Graph execution failed", error=str(e))
            
            # Return fallback review
            return {
                "pr_number": pr_data.get("number", 0),
                "overall_assessment": "Review failed due to an unexpected error.",
                "approval_recommendation": "comment",
                "comments": [],
                "summary": f"An unexpected error occurred: {str(e)}",
                "stats": {"critical": 0, "warning": 0, "suggestion": 0, "total": 0}
            }
    
    async def update_feedback(self, pr_number: int, outcome: str):
        """
        Update feedback outcome after a review is accepted or rejected.
        
        This helps the system learn which reviews were helpful.
        
        Args:
            pr_number: The PR number
            outcome: "accepted", "rejected", or "partial"
        """
        # This would update the stored reviews in ChromaDB
        # For now, this is a placeholder for future enhancement
        logger.info("Feedback received", pr=pr_number, outcome=outcome)
    
    async def seed_knowledge_base(self):
        """
        Seed the context agent with default coding standards.
        
        Call this once during initial setup.
        """
        await self.context_agent.seed_default_standards()
        logger.info("Knowledge base seeded with default standards")
