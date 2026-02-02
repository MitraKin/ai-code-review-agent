"""
Demo Review Data

Sample review data for testing and demonstration.
"""

SAMPLE_PR_DATA = {
    "number": 42,
    "title": "Add user authentication feature",
    "body": "This PR adds user authentication with JWT tokens.",
    "state": "open",
    "base": "main",
    "head": "feature/auth",
    "user": "developer123",
    "files": [
        {
            "filename": "src/auth/login.py",
            "status": "added",
            "additions": 85,
            "deletions": 0,
            "changes": 85,
            "patch": """@@ -0,0 +1,85 @@
+from fastapi import APIRouter, Depends, HTTPException
+from pydantic import BaseModel
+import jwt
+import hashlib
+
+router = APIRouter()
+SECRET_KEY = "hardcoded-secret-key"  # TODO: Move to env
+
+class LoginRequest(BaseModel):
+    username: str
+    password: str
+
+@router.post("/login")
+async def login(request: LoginRequest):
+    # Check credentials
+    user = get_user(request.username)
+    if not user:
+        raise HTTPException(status_code=401)
+    
+    if user.password == hashlib.md5(request.password.encode()).hexdigest():
+        token = jwt.encode({"user_id": user.id}, SECRET_KEY)
+        return {"token": token}
+    
+    raise HTTPException(status_code=401)"""
        },
        {
            "filename": "src/auth/middleware.py",
            "status": "added",
            "additions": 45,
            "deletions": 0,
            "changes": 45,
            "patch": """@@ -0,0 +1,45 @@
+from fastapi import Request
+import jwt
+
+SECRET_KEY = "hardcoded-secret-key"
+
+async def auth_middleware(request: Request, call_next):
+    token = request.headers.get("Authorization")
+    if token:
+        try:
+            payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
+            request.state.user_id = payload["user_id"]
+        except:
+            pass
+    return await call_next(request)"""
        },
        {
            "filename": "tests/test_auth.py",
            "status": "added",
            "additions": 25,
            "deletions": 0,
            "changes": 25,
            "patch": """@@ -0,0 +1,25 @@
+import pytest
+from src.auth.login import login
+
+def test_login_success():
+    # TODO: Add test implementation
+    pass
+
+def test_login_failure():
+    pass"""
        }
    ],
    "commits": 3,
    "additions": 155,
    "deletions": 0
}


SAMPLE_ANALYSIS_RESULT = {
    "pr_number": 42,
    "title": "Add user authentication feature",
    "total_files_changed": 3,
    "total_additions": 155,
    "total_deletions": 0,
    "summary": "This PR implements user authentication with JWT tokens, including login endpoint and middleware for token validation.",
    "risk_level": "high",
    "categories": ["feature", "security"],
    "changes": [
        {
            "file_path": "src/auth/login.py",
            "change_type": "added",
            "language": "python",
            "additions": 85,
            "deletions": 0,
            "analysis": {
                "categories": ["feature", "security"],
                "risk_level": "high",
                "summary": "New authentication endpoint with JWT token generation",
                "key_changes": ["Login endpoint", "JWT token generation", "Password hashing"],
                "potential_issues": ["Hardcoded secret key", "MD5 password hashing is insecure"]
            }
        },
        {
            "file_path": "src/auth/middleware.py",
            "change_type": "added",
            "language": "python",
            "additions": 45,
            "deletions": 0,
            "analysis": {
                "categories": ["feature", "security"],
                "risk_level": "medium",
                "summary": "Authentication middleware for request processing",
                "key_changes": ["JWT token validation middleware"],
                "potential_issues": ["Silent exception handling"]
            }
        },
        {
            "file_path": "tests/test_auth.py",
            "change_type": "added",
            "language": "python",
            "additions": 25,
            "deletions": 0,
            "analysis": {
                "categories": ["test"],
                "risk_level": "low",
                "summary": "Test file for authentication",
                "key_changes": ["Test stubs for login"],
                "potential_issues": ["Tests not implemented"]
            }
        }
    ]
}


SAMPLE_REVIEW_RESULT = {
    "pr_number": 42,
    "overall_assessment": "This PR implements authentication functionality but has several critical security issues that must be addressed before merging. The use of hardcoded secrets and weak hashing algorithms poses significant security risks.",
    "approval_recommendation": "request_changes",
    "summary": "The authentication implementation works but has critical security vulnerabilities. Please address the hardcoded secrets and password hashing before merging.",
    "stats": {
        "total_comments": 6,
        "critical_count": 2,
        "warning_count": 2,
        "suggestion_count": 2
    },
    "comments": [
        {
            "file_path": "src/auth/login.py",
            "line_number": 7,
            "side": "RIGHT",
            "comment": "**Critical Security Issue**: The secret key is hardcoded in the source code. This is a major security vulnerability as anyone with access to the code can forge JWT tokens. Move this to environment variables and use a cryptographically secure random key.",
            "severity": "critical",
            "category": "security",
            "suggested_code": """import os

SECRET_KEY = os.getenv("JWT_SECRET_KEY")
if not SECRET_KEY:
    raise ValueError("JWT_SECRET_KEY environment variable is required")"""
        },
        {
            "file_path": "src/auth/login.py",
            "line_number": 20,
            "side": "RIGHT",
            "comment": "**Critical Security Issue**: MD5 is cryptographically broken and should never be used for password hashing. Use a proper password hashing algorithm like bcrypt, scrypt, or Argon2 which include salting and are designed to be slow.",
            "severity": "critical",
            "category": "security",
            "suggested_code": """import bcrypt

# When storing password:
hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt())

# When verifying:
if bcrypt.checkpw(request.password.encode(), user.password_hash):
    # Password matches"""
        },
        {
            "file_path": "src/auth/login.py",
            "line_number": 17,
            "side": "RIGHT",
            "comment": "**Security Warning**: The error response doesn't differentiate between 'user not found' and 'wrong password'. This is actually good for security (prevents user enumeration), but the error message could be more descriptive for the client.",
            "severity": "suggestion",
            "category": "security",
            "suggested_code": """raise HTTPException(
    status_code=401,
    detail="Invalid credentials"
)"""
        },
        {
            "file_path": "src/auth/middleware.py",
            "line_number": 13,
            "side": "RIGHT",
            "comment": "**Warning**: Silent exception handling can hide bugs. If token validation fails, you should at least log the error. Consider using proper error handling and logging.",
            "severity": "warning",
            "category": "bug",
            "suggested_code": """import logging
logger = logging.getLogger(__name__)

try:
    payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
    request.state.user_id = payload["user_id"]
except jwt.ExpiredSignatureError:
    logger.warning("Expired token received")
except jwt.InvalidTokenError as e:
    logger.warning(f"Invalid token: {e}")"""
        },
        {
            "file_path": "src/auth/middleware.py",
            "line_number": 4,
            "side": "RIGHT",
            "comment": "**Warning**: The secret key is duplicated here. This violates DRY principle and makes key rotation harder. Create a shared configuration module for secrets.",
            "severity": "warning",
            "category": "maintainability"
        },
        {
            "file_path": "tests/test_auth.py",
            "line_number": 5,
            "side": "RIGHT",
            "comment": "**Suggestion**: The tests are not implemented. Please add actual test assertions. At minimum, test successful login, failed login with wrong password, and login with non-existent user.",
            "severity": "suggestion",
            "category": "test"
        }
    ]
}


def get_sample_data():
    """Return all sample data."""
    return {
        "pr_data": SAMPLE_PR_DATA,
        "analysis": SAMPLE_ANALYSIS_RESULT,
        "review": SAMPLE_REVIEW_RESULT
    }
