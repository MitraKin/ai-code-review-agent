"""
Tests for Reviewer Agent
"""
import pytest
from dotenv import load_dotenv

# Load environment variables before importing agents
load_dotenv()

from app.agents.reviewer import ReviewerAgent, ReviewComment, ReviewResult


class TestReviewerAgent:
    """Test cases for ReviewerAgent."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.agent = ReviewerAgent()
    
    # ==================== Comment Formatting Tests ====================
    
    def test_format_comment_body_critical(self):
        """Test formatting critical comments."""
        comment: ReviewComment = {
            "file_path": "test.py",
            "line_number": 10,
            "side": "RIGHT",
            "comment": "SQL injection vulnerability detected",
            "severity": "critical",
            "category": "security",
            "suggested_code": None
        }
        
        body = self.agent._format_comment_body(comment)
        
        assert "🚨" in body
        assert "Security" in body
        assert "SQL injection" in body
    
    def test_format_comment_body_warning(self):
        """Test formatting warning comments."""
        comment: ReviewComment = {
            "file_path": "test.py",
            "line_number": 20,
            "side": "RIGHT",
            "comment": "This loop could be optimized",
            "severity": "warning",
            "category": "performance",
            "suggested_code": None
        }
        
        body = self.agent._format_comment_body(comment)
        
        assert "⚠️" in body
        assert "Performance" in body
    
    def test_format_comment_body_suggestion(self):
        """Test formatting suggestion comments."""
        comment: ReviewComment = {
            "file_path": "test.py",
            "line_number": 30,
            "side": "RIGHT",
            "comment": "Consider using a more descriptive name",
            "severity": "suggestion",
            "category": "style",
            "suggested_code": None
        }
        
        body = self.agent._format_comment_body(comment)
        
        assert "💡" in body
        assert "Style" in body
    
    def test_format_comment_body_with_suggestion(self):
        """Test formatting comments with code suggestions."""
        comment: ReviewComment = {
            "file_path": "test.py",
            "line_number": 10,
            "side": "RIGHT",
            "comment": "Use f-string instead of concatenation",
            "severity": "suggestion",
            "category": "style",
            "suggested_code": 'greeting = f"Hello {name}"'
        }
        
        body = self.agent._format_comment_body(comment)
        
        assert "💡" in body
        assert "```suggestion" in body
        assert 'f"Hello {name}"' in body
    
    # ==================== GitHub Formatting Tests ====================
    
    def test_format_for_github_approve(self):
        """Test formatting an approval review for GitHub."""
        review: ReviewResult = {
            "pr_number": 1,
            "overall_assessment": "Code looks good",
            "approval_recommendation": "approve",
            "comments": [],
            "summary": "No issues found",
            "stats": {"critical": 0, "warning": 0, "suggestion": 0, "total": 0}
        }
        
        github_format = self.agent.format_for_github(review)
        
        assert github_format["event"] == "APPROVE"
        assert "AI Code Review" in github_format["body"]
        assert github_format["comments"] == []
    
    def test_format_for_github_request_changes(self):
        """Test formatting a request changes review for GitHub."""
        review: ReviewResult = {
            "pr_number": 1,
            "overall_assessment": "Critical issues found",
            "approval_recommendation": "request_changes",
            "comments": [
                {
                    "file_path": "test.py",
                    "line_number": 10,
                    "side": "RIGHT",
                    "comment": "Security issue",
                    "severity": "critical",
                    "category": "security",
                    "suggested_code": None
                }
            ],
            "summary": "Fix security issues",
            "stats": {"critical": 1, "warning": 0, "suggestion": 0, "total": 1}
        }
        
        github_format = self.agent.format_for_github(review)
        
        assert github_format["event"] == "REQUEST_CHANGES"
        assert len(github_format["comments"]) == 1
        assert github_format["comments"][0]["path"] == "test.py"
        assert github_format["comments"][0]["line"] == 10
    
    def test_format_for_github_skips_general_comments(self):
        """Test that comments without line numbers are not included."""
        review: ReviewResult = {
            "pr_number": 1,
            "overall_assessment": "Some issues",
            "approval_recommendation": "comment",
            "comments": [
                {
                    "file_path": "test.py",
                    "line_number": 0,  # General comment
                    "side": "RIGHT",
                    "comment": "General feedback",
                    "severity": "suggestion",
                    "category": "style",
                    "suggested_code": None
                }
            ],
            "summary": "General feedback",
            "stats": {"critical": 0, "warning": 0, "suggestion": 1, "total": 1}
        }
        
        github_format = self.agent.format_for_github(review)
        
        # General comments (line 0) should not be in line comments
        assert len(github_format["comments"]) == 0
    
    # ==================== Security Review Detection Tests ====================
    
    def test_needs_security_review_auth_file(self):
        """Test that auth-related files need security review."""
        change = {"file_path": "auth/login.py", "language": "python", "diff": ""}
        assert self.agent._needs_security_review(change) is True
    
    def test_needs_security_review_password_in_diff(self):
        """Test that diffs with password handling need security review."""
        change = {
            "file_path": "user.py", 
            "language": "python", 
            "diff": "password = request.form['password']"
        }
        assert self.agent._needs_security_review(change) is True
    
    def test_needs_security_review_sql_in_diff(self):
        """Test that diffs with SQL need security review."""
        change = {
            "file_path": "service.py", 
            "language": "python", 
            "diff": "query = f\"SELECT * FROM users WHERE id = {user_id}\""
        }
        assert self.agent._needs_security_review(change) is True
    
    def test_no_security_review_simple_change(self):
        """Test that simple changes don't need security review."""
        change = {
            "file_path": "utils/helpers.py", 
            "language": "python", 
            "diff": "def format_date(d): return d.strftime('%Y-%m-%d')"
        }
        assert self.agent._needs_security_review(change) is False
    
    # ==================== Performance Review Detection Tests ====================
    
    def test_needs_performance_review_model_file(self):
        """Test that model files need performance review."""
        change = {"file_path": "models/user.py", "language": "python", "diff": "", "additions": 10}
        assert self.agent._needs_performance_review(change) is True
    
    def test_needs_performance_review_loop_in_diff(self):
        """Test that diffs with loops need performance review."""
        change = {
            "file_path": "service.py", 
            "language": "python", 
            "diff": "for item in items:",
            "additions": 10
        }
        assert self.agent._needs_performance_review(change) is True
    
    def test_needs_performance_review_large_change(self):
        """Test that large changes need performance review."""
        change = {
            "file_path": "utils.py", 
            "language": "python", 
            "diff": "simple code",
            "additions": 150
        }
        assert self.agent._needs_performance_review(change) is True
    
    # ==================== Deduplication Tests ====================
    
    def test_deduplicate_comments(self):
        """Test that duplicate comments are removed."""
        comments = [
            {
                "file_path": "test.py",
                "line_number": 10,
                "category": "style",
                "comment": "Use descriptive names",
                "severity": "suggestion",
                "side": "RIGHT",
                "suggested_code": None
            },
            {
                "file_path": "test.py",
                "line_number": 10,
                "category": "style",
                "comment": "Use descriptive names",  # Duplicate
                "severity": "suggestion",
                "side": "RIGHT",
                "suggested_code": None
            },
            {
                "file_path": "test.py",
                "line_number": 20,  # Different line
                "category": "style",
                "comment": "Use descriptive names",
                "severity": "suggestion",
                "side": "RIGHT",
                "suggested_code": None
            }
        ]
        
        unique = self.agent._deduplicate_comments(comments)
        
        assert len(unique) == 2  # Only 2 unique comments
    
    # ==================== JSON Parsing Tests ====================
    
    def test_parse_json_response_direct(self):
        """Test parsing direct JSON response."""
        content = '{"comments": [], "overall_assessment": "Good"}'
        result = self.agent._parse_json_response(content)
        
        assert result["comments"] == []
        assert result["overall_assessment"] == "Good"
    
    def test_parse_json_response_markdown(self):
        """Test parsing JSON in markdown code block."""
        content = '''Here's my analysis:

```json
{"comments": [], "overall_assessment": "Good"}
```

Hope this helps!'''
        
        result = self.agent._parse_json_response(content)
        
        assert result["comments"] == []
        assert result["overall_assessment"] == "Good"
    
    def test_parse_json_response_embedded(self):
        """Test parsing embedded JSON in text."""
        content = 'The result is {"comments": [], "overall_assessment": "Good"} as shown.'
        result = self.agent._parse_json_response(content)
        
        assert result["comments"] == []
        assert result["overall_assessment"] == "Good"
