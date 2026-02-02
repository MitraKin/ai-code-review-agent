"""
FastAPI Application - Main entry point.

Handles:
- GitHub webhook endpoints
- Manual review triggers
- Health checks
- API documentation
"""

from fastapi import FastAPI, Request, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse
from typing import Optional, List
from datetime import datetime
import structlog
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

from .core.config import get_settings
from .core.logging import setup_logging, get_logger
from .services.github_service import GitHubService
from .agents.orchestrator import ReviewOrchestrator

# Initialize logging
setup_logging()
logger = get_logger(__name__)

# Create FastAPI app
app = FastAPI(
    title="AI Code Review Agent",
    description="Automated code review using LLM-powered agents",
    version="0.1.0"
)

# Initialize services
github_service = GitHubService()
orchestrator = ReviewOrchestrator()

# In-memory storage for review results (in production, use Redis or database)
review_results: dict = {}


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "version": "0.1.0"}


@app.post("/webhook/github")
async def github_webhook(request: Request, background_tasks: BackgroundTasks):
    """
    GitHub webhook endpoint.
    
    Receives PR events and triggers reviews.
    
    TODO: Implement proper webhook handling
    """
    # Get headers
    event_type = request.headers.get("X-GitHub-Event")
    signature = request.headers.get("X-Hub-Signature-256", "")
    
    # Get payload
    payload = await request.body()
    
    # Verify signature
    if not github_service.verify_webhook_signature(payload, signature):
        logger.warning("Invalid webhook signature")
        raise HTTPException(status_code=401, detail="Invalid signature")
    
    # Parse payload
    data = await request.json()
    
    # Handle PR events
    if event_type == "pull_request":
        action = data.get("action")
        
        if action in ["opened", "synchronize", "reopened"]:
            # Trigger review in background
            background_tasks.add_task(
                process_pr_review,
                repo=data["repository"]["full_name"],
                pr_number=data["pull_request"]["number"]
            )
            
            return {"status": "review_queued"}
    
    return {"status": "ignored", "event": event_type}


async def process_pr_review(repo: str, pr_number: int):
    """
    Process a PR review in the background.
    
    TODO: Add error handling and retries
    """
    review_key = f"{repo}#{pr_number}"
    
    try:
        logger.info("Starting PR review", repo=repo, pr=pr_number)
        
        # Update status to processing
        review_results[review_key] = {
            "repo": repo,
            "pr_number": pr_number,
            "status": "processing",
            "started_at": datetime.now().isoformat(),
            "result": None,
            "error": None
        }
        
        # Fetch PR data
        pr_data = await github_service.get_pr(repo, pr_number)
        
        # Run the review orchestrator
        review = await orchestrator.review_pr(pr_data)
        
        # Format and post the review
        formatted = orchestrator.reviewer.format_for_github(review)
        await github_service.post_review(repo, pr_number, formatted)
        
        # Store the result
        review_results[review_key] = {
            "repo": repo,
            "pr_number": pr_number,
            "status": "completed",
            "started_at": review_results[review_key]["started_at"],
            "completed_at": datetime.now().isoformat(),
            "result": {
                "summary": review.get("summary", ""),
                "recommendation": review.get("approval_recommendation", "comment"),
                "comments": review.get("comments", []),
                "stats": review.get("stats", {})
            },
            "error": None
        }
        
        logger.info("Completed PR review", repo=repo, pr=pr_number)
        
    except Exception as e:
        error_msg = str(e)
        logger.error("PR review failed", repo=repo, pr=pr_number, error=error_msg)
        
        # Store the error
        review_results[review_key] = {
            "repo": repo,
            "pr_number": pr_number,
            "status": "failed",
            "started_at": review_results.get(review_key, {}).get("started_at", datetime.now().isoformat()),
            "completed_at": datetime.now().isoformat(),
            "result": None,
            "error": error_msg
        }


@app.post("/review")
async def manual_review(repo: str, pr_number: int, background_tasks: BackgroundTasks):
    """
    Manually trigger a PR review.
    
    Useful for testing or re-reviewing PRs.
    """
    background_tasks.add_task(process_pr_review, repo=repo, pr_number=pr_number)
    return {"status": "review_queued", "repo": repo, "pr": pr_number}


@app.get("/review/status")
async def get_review_status(repo: str, pr_number: int):
    """
    Get the status of a PR review.
    
    Returns the current status and results if available.
    """
    review_key = f"{repo}#{pr_number}"
    
    if review_key not in review_results:
        return {
            "status": "not_found",
            "repo": repo,
            "pr_number": pr_number,
            "message": "No review found for this PR. Trigger a review first."
        }
    
    return review_results[review_key]


@app.get("/reviews")
async def list_reviews():
    """
    List all reviews (most recent first).
    """
    reviews = list(review_results.values())
    # Sort by completed_at or started_at, most recent first
    reviews.sort(
        key=lambda x: x.get("completed_at") or x.get("started_at", ""),
        reverse=True
    )
    return {"reviews": reviews, "total": len(reviews)}


@app.get("/")
async def root():
    """Root endpoint with API info."""
    return {
        "name": "AI Code Review Agent",
        "version": "0.1.0",
        "docs": "/docs",
        "health": "/health"
    }


if __name__ == "__main__":
    import uvicorn
    settings = get_settings()
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.environment == "development"
    )
