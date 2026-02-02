"""
GitHub Service - Handles all GitHub API interactions.

Responsibilities:
- Fetch PR details and diffs
- Post review comments
- Handle webhook events
- Manage GitHub App authentication

TODO: Implement full GitHub integration
"""

from typing import Optional, List
from github import Github, GithubIntegration
from github.PullRequest import PullRequest

from ..core.config import get_settings
from ..core.logging import get_logger

logger = get_logger(__name__)


class GitHubService:
    """
    Service for interacting with GitHub API.
    
    Supports both:
    - Personal Access Token (simple, for testing)
    - GitHub App (production, for multiple repos)
    """
    
    def __init__(self):
        self.settings = get_settings()
        self._client: Optional[Github] = None
    
    @property
    def client(self) -> Github:
        """Get or create GitHub client."""
        if self._client is None:
            self._client = self._create_client()
        return self._client
    
    def _create_client(self) -> Github:
        """
        Create GitHub client using available credentials.
        
        TODO: Implement GitHub App authentication for production
        """
        if self.settings.github_token:
            logger.info("Using GitHub Personal Access Token")
            return Github(self.settings.github_token)
        
        # TODO: Implement GitHub App authentication
        # if self.settings.github_app_id and self.settings.github_private_key_path:
        #     logger.info("Using GitHub App authentication")
        #     with open(self.settings.github_private_key_path, 'r') as f:
        #         private_key = f.read()
        #     integration = GithubIntegration(
        #         self.settings.github_app_id,
        #         private_key
        #     )
        #     # Get installation token...
        
        raise ValueError("No GitHub credentials configured")
    
    async def get_pr(self, repo_full_name: str, pr_number: int) -> dict:
        """
        Fetch pull request details.
        
        Args:
            repo_full_name: "owner/repo" format
            pr_number: Pull request number
            
        Returns:
            Dict with PR data including files and diffs
            
        TODO: Implement full PR data fetching
        """
        try:
            repo = self.client.get_repo(repo_full_name)
            pr = repo.get_pull(pr_number)
            
            # Get files changed
            files = []
            for file in pr.get_files():
                files.append({
                    "filename": file.filename,
                    "status": file.status,
                    "additions": file.additions,
                    "deletions": file.deletions,
                    "changes": file.changes,
                    "patch": file.patch or "",
                })
            
            return {
                "number": pr.number,
                "title": pr.title,
                "body": pr.body or "",
                "state": pr.state,
                "base": pr.base.ref,
                "head": pr.head.ref,
                "user": pr.user.login,
                "files": files,
                "commits": pr.commits,
                "additions": pr.additions,
                "deletions": pr.deletions,
            }
            
        except Exception as e:
            logger.error("Failed to fetch PR", repo=repo_full_name, pr=pr_number, error=str(e))
            raise
    
    async def post_review(
        self, 
        repo_full_name: str, 
        pr_number: int, 
        review: dict
    ):
        """
        Post a review to a pull request.
        
        Args:
            repo_full_name: "owner/repo" format
            pr_number: Pull request number
            review: Formatted review from ReviewerAgent
            
        TODO: Implement review posting
        """
        try:
            repo = self.client.get_repo(repo_full_name)
            pr = repo.get_pull(pr_number)
            
            # Filter comments to only include those with valid line numbers
            # GitHub only accepts comments on lines that are part of the diff
            valid_comments = []
            for c in review.get("comments", []):
                line = c.get("line", 0)
                # Skip comments with invalid line numbers (0 or negative)
                if line and line > 0:
                    valid_comments.append({
                        "path": c["path"],
                        "line": line,
                        "body": c["body"]
                    })
                else:
                    # Add as general comment in the body
                    logger.debug("Skipping inline comment with invalid line", path=c.get("path"), line=line)
            
            # Post the review
            # If there are valid inline comments, include them
            # Otherwise, just post the body
            try:
                pr.create_review(
                    body=review.get("body", ""),
                    event=review.get("event", "COMMENT"),
                    comments=valid_comments
                )
                logger.info("Posted review with inline comments", repo=repo_full_name, pr=pr_number, comments=len(valid_comments))
            except Exception as inline_error:
                # If inline comments fail, try posting just the body
                logger.warning("Inline comments failed, posting body only", error=str(inline_error))
                pr.create_review(
                    body=review.get("body", ""),
                    event=review.get("event", "COMMENT")
                )
                logger.info("Posted review without inline comments", repo=repo_full_name, pr=pr_number)
            
        except Exception as e:
            logger.error("Failed to post review", repo=repo_full_name, pr=pr_number, error=str(e))
            raise
    
    def verify_webhook_signature(self, payload: bytes, signature: str) -> bool:
        """
        Verify GitHub webhook signature.
        
        TODO: Implement HMAC verification for security
        """
        import hmac
        import hashlib
        
        if not self.settings.github_webhook_secret:
            logger.warning("Webhook secret not configured, skipping verification")
            return True
        
        expected = hmac.new(
            self.settings.github_webhook_secret.encode(),
            payload,
            hashlib.sha256
        ).hexdigest()
        
        return hmac.compare_digest(f"sha256={expected}", signature)
