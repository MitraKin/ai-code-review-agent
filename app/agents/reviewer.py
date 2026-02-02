"""
Reviewer Agent - Generates code review comments.

This agent is responsible for:
1. Taking analyzed code and context
2. Generating helpful, specific review comments
3. Suggesting improvements with code examples
4. Formatting comments for GitHub API
"""

import json
from typing import List, Optional, TypedDict
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate

from ..core.logging import get_logger

logger = get_logger(__name__)


class ReviewComment(TypedDict):
    """A single review comment."""
    file_path: str
    line_number: int
    side: str  # LEFT (old code) or RIGHT (new code)
    comment: str
    severity: str  # suggestion, warning, critical
    category: str  # style, bug, security, performance, etc.
    suggested_code: Optional[str]


class ReviewResult(TypedDict):
    """Complete review result for a PR."""
    pr_number: int
    overall_assessment: str
    approval_recommendation: str  # approve, request_changes, comment
    comments: List[ReviewComment]
    summary: str
    stats: dict


class ReviewerAgent:
    """
    Agent responsible for generating code review feedback.
    
    Takes the analysis from AnalyzerAgent and context from ContextAgent
    to produce helpful, actionable code review comments.
    """
    
    def __init__(self, llm: Optional[ChatOpenAI] = None):
        self.llm = llm or ChatOpenAI(model="gpt-4-turbo-preview", temperature=0.2)
        self._init_prompts()
    
    def _init_prompts(self):
        """Initialize prompt templates for different review aspects."""
        
        # Main review prompt
        self.review_prompt = ChatPromptTemplate.from_messages([
            ("system", """You are an expert code reviewer with deep knowledge of software engineering best practices, security, and performance optimization.

Your job is to provide helpful, constructive, and specific feedback on code changes.

**Review Guidelines:**
1. **Be specific**: Point to exact lines when possible, explain the issue clearly
2. **Explain why**: Don't just say something is wrong - explain the impact
3. **Provide solutions**: When pointing out issues, suggest how to fix them
4. **Prioritize**: Focus on important issues (security > bugs > performance > style)
5. **Be constructive**: Phrase feedback positively, focus on the code not the person
6. **Don't nitpick**: Skip trivial style issues if the code works and is readable
7. **Acknowledge good work**: If something is done well, say so

**Severity Levels:**
- `critical`: Security vulnerabilities, data loss risks, breaking bugs
- `warning`: Potential bugs, performance issues, bad practices
- `suggestion`: Style improvements, minor optimizations, nice-to-haves

**Categories:**
- `security`: Security vulnerabilities, auth issues, injection risks
- `bug`: Logic errors, edge cases, potential crashes
- `performance`: N+1 queries, memory leaks, inefficient algorithms
- `style`: Naming, formatting, code organization
- `documentation`: Missing or incorrect docs/comments
- `test`: Missing tests, test quality issues
- `maintainability`: Complex code, duplication, tight coupling

**Response Format:**
Respond with a JSON object containing your review:
{{
    "comments": [
        {{
            "line_number": <int or null if general comment>,
            "side": "RIGHT",
            "comment": "<your detailed feedback>",
            "severity": "critical|warning|suggestion",
            "category": "security|bug|performance|style|documentation|test|maintainability",
            "suggested_code": "<optional: corrected code snippet>"
        }}
    ],
    "overall_assessment": "<2-3 sentence summary of the changes>",
    "approval_recommendation": "approve|request_changes|comment",
    "positive_notes": ["<things done well>"]
}}

If there are no issues, return an empty comments array and recommend approval."""),
            ("user", """**File:** {file_path}
**Language:** {language}
**Change Type:** {change_type}

**Code Diff:**
```{language}
{diff}
```

**Analysis Summary:**
{analysis_summary}

**Context from Past Reviews & Standards:**
{context}

Please review this code change and provide your feedback.""")
        ])
        
        # Security-focused review prompt
        self.security_prompt = ChatPromptTemplate.from_messages([
            ("system", """You are a security expert reviewing code for vulnerabilities.

Focus ONLY on security issues. Look for:
- SQL injection vulnerabilities
- XSS (Cross-Site Scripting)
- CSRF vulnerabilities
- Authentication/authorization flaws
- Secrets/credentials in code
- Insecure deserialization
- Path traversal
- Command injection
- Insecure cryptography
- Missing input validation
- Information disclosure
- OWASP Top 10 vulnerabilities

**Response Format:**
Respond with JSON:
{{
    "security_issues": [
        {{
            "line_number": <int or null>,
            "vulnerability_type": "<type of vulnerability>",
            "description": "<detailed explanation>",
            "severity": "critical|warning",
            "remediation": "<how to fix>"
        }}
    ],
    "security_score": "<low_risk|medium_risk|high_risk|critical_risk>"
}}

If no security issues are found, return empty security_issues array and "low_risk" score."""),
            ("user", """Review this code for security vulnerabilities:

**File:** {file_path}
**Language:** {language}

```{language}
{diff}
```""")
        ])
        
        # Performance review prompt
        self.performance_prompt = ChatPromptTemplate.from_messages([
            ("system", """You are a performance optimization expert reviewing code for efficiency issues.

Focus ONLY on performance problems. Look for:
- N+1 query patterns
- Missing database indexes (if schema changes)
- Unnecessary loops or iterations
- Memory leaks or excessive memory usage
- Blocking operations in async code
- Missing caching opportunities
- Inefficient data structures
- Redundant computations
- Large payload sizes
- Missing pagination

**Response Format:**
Respond with JSON:
{{
    "performance_issues": [
        {{
            "line_number": <int or null>,
            "issue_type": "<type of performance issue>",
            "description": "<detailed explanation>",
            "impact": "<estimated impact: low|medium|high>",
            "suggestion": "<how to improve>"
        }}
    ]
}}

Only report significant issues, not micro-optimizations. If no issues, return empty array."""),
            ("user", """Review this code for performance issues:

**File:** {file_path}
**Language:** {language}

```{language}
{diff}
```""")
        ])
        
        # Summary prompt for overall PR review
        self.summary_prompt = ChatPromptTemplate.from_messages([
            ("system", """You are summarizing code review findings for a pull request.

Given the individual file reviews, create a cohesive summary that:
1. Highlights the most important findings
2. Groups related issues
3. Provides an overall recommendation
4. Acknowledges positive aspects

Keep it concise but comprehensive. This will be posted as the main review comment."""),
            ("user", """**PR Title:** {pr_title}
**Files Changed:** {file_count}
**Total Additions:** {additions}
**Total Deletions:** {deletions}
**Risk Level:** {risk_level}

**Individual File Reviews:**
{file_reviews}

**Statistics:**
- Critical issues: {critical_count}
- Warnings: {warning_count}
- Suggestions: {suggestion_count}

Create a summary for this pull request review.""")
        ])
    
    async def review(
        self, 
        analysis: dict, 
        context: dict
    ) -> ReviewResult:
        """
        Generate a complete code review.
        
        Args:
            analysis: Output from AnalyzerAgent
            context: Output from ContextAgent
            
        Returns:
            ReviewResult with all comments and recommendations
        """
        logger.info("Starting review generation", pr=analysis.get("pr_number"))
        
        all_comments: List[ReviewComment] = []
        file_reviews = []
        
        # Review each changed file
        for change in analysis.get("changes", []):
            # Skip files without diffs (e.g., binary files)
            if not change.get("diff"):
                continue
            
            logger.debug("Reviewing file", file=change.get("file_path"))
            
            # Main review
            file_result = await self._review_file(change, context)
            
            # Security review for sensitive file types
            if self._needs_security_review(change):
                security_issues = await self._security_review(change)
                file_result["comments"].extend(security_issues)
            
            # Performance review for certain changes
            if self._needs_performance_review(change):
                perf_issues = await self._performance_review(change)
                file_result["comments"].extend(perf_issues)
            
            # Add file path to all comments
            for comment in file_result["comments"]:
                comment["file_path"] = change.get("file_path", "")
            
            all_comments.extend(file_result["comments"])
            file_reviews.append({
                "file": change.get("file_path"),
                "assessment": file_result.get("overall_assessment", ""),
                "comment_count": len(file_result["comments"])
            })
        
        # Deduplicate comments
        all_comments = self._deduplicate_comments(all_comments)
        
        # Generate overall assessment
        overall = await self._generate_overall_assessment(
            analysis, all_comments, file_reviews
        )
        
        # Calculate stats
        stats = {
            "critical": sum(1 for c in all_comments if c.get("severity") == "critical"),
            "warning": sum(1 for c in all_comments if c.get("severity") == "warning"),
            "suggestion": sum(1 for c in all_comments if c.get("severity") == "suggestion"),
            "total": len(all_comments)
        }
        
        result: ReviewResult = {
            "pr_number": analysis.get("pr_number", 0),
            "overall_assessment": overall.get("assessment", ""),
            "approval_recommendation": overall.get("recommendation", "comment"),
            "comments": all_comments,
            "summary": overall.get("summary", ""),
            "stats": stats
        }
        
        logger.info("Review complete", 
                   pr=analysis.get("pr_number"),
                   comments=len(all_comments),
                   recommendation=result["approval_recommendation"])
        
        return result
    
    async def _review_file(
        self, 
        change: dict, 
        context: dict
    ) -> dict:
        """Review a single file's changes."""
        # Prepare context summary
        context_summary = context.get("summary", "No additional context available.")
        
        # Prepare analysis summary
        analysis_summary = "No analysis available."
        if change.get("analysis"):
            analysis_summary = change["analysis"].get("summary", analysis_summary)
        
        messages = self.review_prompt.format_messages(
            file_path=change.get("file_path", "unknown"),
            language=change.get("language", "unknown"),
            change_type=change.get("change_type", "modified"),
            diff=change.get("diff", "")[:12000],  # Truncate very long diffs
            analysis_summary=analysis_summary,
            context=context_summary[:3000]
        )
        
        try:
            response = await self.llm.ainvoke(messages)
            result = self._parse_review_response(response.content)
            return result
        except Exception as e:
            logger.error("File review failed", file=change.get("file_path"), error=str(e))
            return {
                "comments": [],
                "overall_assessment": "Review could not be completed.",
                "approval_recommendation": "comment"
            }
    
    async def _security_review(self, change: dict) -> List[ReviewComment]:
        """Run security-focused review."""
        messages = self.security_prompt.format_messages(
            file_path=change.get("file_path", "unknown"),
            language=change.get("language", "unknown"),
            diff=change.get("diff", "")[:10000]
        )
        
        try:
            response = await self.llm.ainvoke(messages)
            result = self._parse_json_response(response.content)
            
            comments = []
            for issue in result.get("security_issues", []):
                comments.append({
                    "file_path": change.get("file_path", ""),
                    "line_number": issue.get("line_number") or 0,
                    "side": "RIGHT",
                    "comment": f"**Security: {issue.get('vulnerability_type', 'Issue')}**\n\n{issue.get('description', '')}\n\n**Remediation:** {issue.get('remediation', 'N/A')}",
                    "severity": issue.get("severity", "warning"),
                    "category": "security",
                    "suggested_code": None
                })
            
            return comments
            
        except Exception as e:
            logger.error("Security review failed", file=change.get("file_path"), error=str(e))
            return []
    
    async def _performance_review(self, change: dict) -> List[ReviewComment]:
        """Run performance-focused review."""
        messages = self.performance_prompt.format_messages(
            file_path=change.get("file_path", "unknown"),
            language=change.get("language", "unknown"),
            diff=change.get("diff", "")[:10000]
        )
        
        try:
            response = await self.llm.ainvoke(messages)
            result = self._parse_json_response(response.content)
            
            comments = []
            for issue in result.get("performance_issues", []):
                comments.append({
                    "file_path": change.get("file_path", ""),
                    "line_number": issue.get("line_number") or 0,
                    "side": "RIGHT",
                    "comment": f"**Performance: {issue.get('issue_type', 'Issue')}**\n\n{issue.get('description', '')}\n\n**Suggestion:** {issue.get('suggestion', 'N/A')}",
                    "severity": "warning" if issue.get("impact") == "high" else "suggestion",
                    "category": "performance",
                    "suggested_code": None
                })
            
            return comments
            
        except Exception as e:
            logger.error("Performance review failed", file=change.get("file_path"), error=str(e))
            return []
    
    def _needs_security_review(self, change: dict) -> bool:
        """Determine if a file needs security review."""
        file_path = change.get("file_path", "").lower()
        language = change.get("language", "")
        
        # Always review these
        security_sensitive_patterns = [
            "auth", "login", "password", "credential", "secret",
            "token", "api", "key", "cert", "ssl", "tls",
            "session", "cookie", "jwt", "oauth",
            "sql", "query", "database", "db",
            "input", "form", "upload", "download",
            "admin", "user", "permission", "role"
        ]
        
        for pattern in security_sensitive_patterns:
            if pattern in file_path:
                return True
        
        # Review certain languages more carefully
        security_languages = ["python", "javascript", "typescript", "php", "java", "go", "ruby"]
        if language in security_languages:
            # Check if diff contains sensitive patterns
            diff = change.get("diff", "").lower()
            sensitive_in_diff = [
                "password", "exec(", "eval(", "system(", "query(",
                "innerhtml", "document.write", "createelement",
                "sql", "select ", "insert ", "update ", "delete ",
                "http", "request", "response", "cookie"
            ]
            for pattern in sensitive_in_diff:
                if pattern in diff:
                    return True
        
        return False
    
    def _needs_performance_review(self, change: dict) -> bool:
        """Determine if a file needs performance review."""
        file_path = change.get("file_path", "").lower()
        language = change.get("language", "")
        diff = change.get("diff", "").lower()
        
        # Database-related files
        if any(p in file_path for p in ["model", "repository", "dao", "query", "database", "migration"]):
            return True
        
        # Files with loops or data processing
        performance_patterns = [
            "for ", "while ", "foreach", ".map(", ".filter(", ".reduce(",
            "select ", "join ", "where ", "query",
            "async", "await", "promise",
            "cache", "redis", "memcache"
        ]
        
        for pattern in performance_patterns:
            if pattern in diff:
                return True
        
        # Large changes might have performance implications
        if change.get("additions", 0) > 100:
            return True
        
        return False
    
    async def _generate_overall_assessment(
        self, 
        analysis: dict, 
        comments: List[ReviewComment],
        file_reviews: List[dict]
    ) -> dict:
        """Generate an overall assessment of the PR."""
        # Count issues by severity
        critical_count = sum(1 for c in comments if c.get("severity") == "critical")
        warning_count = sum(1 for c in comments if c.get("severity") == "warning")
        suggestion_count = sum(1 for c in comments if c.get("severity") == "suggestion")
        
        # Determine recommendation based on issues found
        if critical_count > 0:
            recommendation = "request_changes"
        elif warning_count > 3:
            recommendation = "request_changes"
        elif warning_count > 0:
            recommendation = "comment"
        else:
            recommendation = "approve"
        
        # Format file reviews for summary
        file_reviews_text = "\n".join([
            f"- **{fr['file']}**: {fr['assessment']} ({fr['comment_count']} comments)"
            for fr in file_reviews
        ]) or "No files reviewed."
        
        messages = self.summary_prompt.format_messages(
            pr_title=analysis.get("title", "Untitled PR"),
            file_count=analysis.get("total_files_changed", 0),
            additions=analysis.get("total_additions", 0),
            deletions=analysis.get("total_deletions", 0),
            risk_level=analysis.get("risk_level", "unknown"),
            file_reviews=file_reviews_text,
            critical_count=critical_count,
            warning_count=warning_count,
            suggestion_count=suggestion_count
        )
        
        try:
            response = await self.llm.ainvoke(messages)
            summary = response.content
        except Exception as e:
            logger.error("Summary generation failed", error=str(e))
            summary = f"Review completed with {len(comments)} comments."
        
        # Create assessment
        if recommendation == "approve":
            assessment = "This PR looks good and is ready to merge."
        elif recommendation == "request_changes":
            assessment = f"This PR has {critical_count} critical and {warning_count} warning issues that should be addressed before merging."
        else:
            assessment = f"This PR has some suggestions for improvement but no blocking issues."
        
        return {
            "assessment": assessment,
            "recommendation": recommendation,
            "summary": summary
        }
    
    def _parse_review_response(self, content: str) -> dict:
        """Parse the LLM review response."""
        result = self._parse_json_response(content)
        
        # Convert to our internal format
        comments = []
        for c in result.get("comments", []):
            comments.append({
                "file_path": "",  # Will be set by caller
                "line_number": c.get("line_number") or 0,
                "side": c.get("side", "RIGHT"),
                "comment": c.get("comment", ""),
                "severity": c.get("severity", "suggestion"),
                "category": c.get("category", "general"),
                "suggested_code": c.get("suggested_code")
            })
        
        return {
            "comments": comments,
            "overall_assessment": result.get("overall_assessment", ""),
            "approval_recommendation": result.get("approval_recommendation", "comment"),
            "positive_notes": result.get("positive_notes", [])
        }
    
    def _parse_json_response(self, content: str) -> dict:
        """Extract and parse JSON from LLM response."""
        try:
            # Try direct parse first
            parsed = json.loads(content)
            # Ensure we always return a dict, not a list
            if isinstance(parsed, list):
                return {"items": parsed}
            return parsed
        except json.JSONDecodeError:
            pass
        
        # Try to extract JSON from markdown code block
        if "```json" in content:
            try:
                json_str = content.split("```json")[1].split("```")[0]
                parsed = json.loads(json_str.strip())
                if isinstance(parsed, list):
                    return {"items": parsed}
                return parsed
            except (IndexError, json.JSONDecodeError):
                pass
        
        if "```" in content:
            try:
                json_str = content.split("```")[1].split("```")[0]
                parsed = json.loads(json_str.strip())
                if isinstance(parsed, list):
                    return {"items": parsed}
                return parsed
            except (IndexError, json.JSONDecodeError):
                pass
        
        # Try to find JSON object in content
        try:
            start = content.find("{")
            end = content.rfind("}") + 1
            if start != -1 and end != 0:
                parsed = json.loads(content[start:end])
                if isinstance(parsed, list):
                    return {"items": parsed}
                return parsed
        except json.JSONDecodeError:
            pass
        
        # Try to find JSON array in content
        try:
            start = content.find("[")
            end = content.rfind("]") + 1
            if start != -1 and end != 0:
                parsed = json.loads(content[start:end])
                if isinstance(parsed, list):
                    return {"items": parsed}
                return parsed
        except json.JSONDecodeError:
            pass
        
        logger.warning("Could not parse JSON from response")
        return {}
    
    def _deduplicate_comments(self, comments: List[ReviewComment]) -> List[ReviewComment]:
        """Remove duplicate comments."""
        seen = set()
        unique = []
        
        for comment in comments:
            # Create a key for deduplication
            key = (
                comment.get("file_path", ""),
                comment.get("line_number", 0),
                comment.get("category", ""),
                comment.get("comment", "")[:100]  # First 100 chars
            )
            
            if key not in seen:
                seen.add(key)
                unique.append(comment)
        
        return unique
    
    def format_for_github(self, review: ReviewResult) -> dict:
        """
        Format review result for GitHub PR Review API.
        
        GitHub API expects:
        {
            "body": "Overall comment",
            "event": "APPROVE" | "REQUEST_CHANGES" | "COMMENT",
            "comments": [
                {
                    "path": "file.py",
                    "line": 10,
                    "side": "RIGHT",
                    "body": "Comment text"
                }
            ]
        }
        """
        event_map = {
            "approve": "APPROVE",
            "request_changes": "REQUEST_CHANGES",
            "comment": "COMMENT"
        }
        
        # Format summary with stats
        stats = review.get("stats", {})
        summary_header = f"""## 🤖 AI Code Review

**Recommendation:** {review['approval_recommendation'].replace('_', ' ').title()}

**Summary:** {review['overall_assessment']}

**Statistics:**
- 🚨 Critical: {stats.get('critical', 0)}
- ⚠️ Warnings: {stats.get('warning', 0)}
- 💡 Suggestions: {stats.get('suggestion', 0)}

---

{review['summary']}
"""
        
        # Format individual comments
        github_comments = []
        for c in review["comments"]:
            if c.get("line_number", 0) > 0:  # Only include line-specific comments
                github_comments.append({
                    "path": c["file_path"],
                    "line": c["line_number"],
                    "side": c.get("side", "RIGHT"),
                    "body": self._format_comment_body(c)
                })
        
        github_format = {
            "body": summary_header,
            "event": event_map.get(review["approval_recommendation"], "COMMENT"),
            "comments": github_comments
        }
        
        return github_format
    
    def _format_comment_body(self, comment: ReviewComment) -> str:
        """Format a single comment for GitHub."""
        severity_emoji = {
            "critical": "🚨",
            "warning": "⚠️",
            "suggestion": "💡"
        }
        
        emoji = severity_emoji.get(comment.get("severity", ""), "💬")
        category = comment.get("category", "general").title()
        
        body = f"{emoji} **{category}**\n\n{comment.get('comment', '')}"
        
        if comment.get("suggested_code"):
            body += f"\n\n**Suggested fix:**\n```suggestion\n{comment['suggested_code']}\n```"
        
        return body
