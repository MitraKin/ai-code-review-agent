"""
Streamlit Frontend for AI Code Review Agent

A beautiful, interactive UI for:
- Viewing application status
- Triggering PR reviews manually
- Viewing review results
- Exploring review history
- Configuration management
"""

import streamlit as st
import requests
import asyncio
import json
from datetime import datetime
from typing import Optional
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from dotenv import load_dotenv
load_dotenv()

# Page config - must be first Streamlit command
st.set_page_config(
    page_title="AI Code Review Agent",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Constants
API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")

# Custom CSS
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: 700;
        color: #1f77b4;
        margin-bottom: 1rem;
    }
    .sub-header {
        font-size: 1.2rem;
        color: #666;
        margin-bottom: 2rem;
    }
    .metric-card {
        background-color: #f0f2f6;
        border-radius: 10px;
        padding: 20px;
        text-align: center;
    }
    .status-healthy {
        color: #28a745;
        font-weight: bold;
    }
    .status-unhealthy {
        color: #dc3545;
        font-weight: bold;
    }
    .review-card {
        background-color: #ffffff;
        border: 1px solid #e0e0e0;
        border-radius: 8px;
        padding: 16px;
        margin-bottom: 12px;
    }
    .severity-critical {
        background-color: #ffebee;
        border-left: 4px solid #f44336;
    }
    .severity-warning {
        background-color: #fff3e0;
        border-left: 4px solid #ff9800;
    }
    .severity-suggestion {
        background-color: #e3f2fd;
        border-left: 4px solid #2196f3;
    }
    .code-block {
        background-color: #1e1e1e;
        color: #d4d4d4;
        padding: 12px;
        border-radius: 6px;
        font-family: 'Consolas', monospace;
        font-size: 0.85rem;
        overflow-x: auto;
    }
</style>
""", unsafe_allow_html=True)


# ============ Helper Functions ============

def check_api_health() -> dict:
    """Check if the backend API is healthy."""
    try:
        response = requests.get(f"{API_BASE_URL}/health", timeout=5)
        if response.status_code == 200:
            return {"status": "healthy", "data": response.json()}
        return {"status": "unhealthy", "error": f"Status code: {response.status_code}"}
    except requests.exceptions.ConnectionError:
        return {"status": "unhealthy", "error": "Cannot connect to API server"}
    except Exception as e:
        return {"status": "unhealthy", "error": str(e)}


def trigger_review(repo: str, pr_number: int) -> dict:
    """Trigger a PR review via the API."""
    try:
        response = requests.post(
            f"{API_BASE_URL}/review",
            params={"repo": repo, "pr_number": pr_number},
            timeout=30
        )
        if response.status_code == 200:
            return {"success": True, "data": response.json()}
        return {"success": False, "error": response.text}
    except Exception as e:
        return {"success": False, "error": str(e)}


def get_api_info() -> dict:
    """Get API information."""
    try:
        response = requests.get(f"{API_BASE_URL}/", timeout=5)
        if response.status_code == 200:
            return response.json()
        return {}
    except:
        return {}


def get_review_status(repo: str, pr_number: int) -> dict:
    """Get the status of a specific review."""
    try:
        response = requests.get(
            f"{API_BASE_URL}/review/status",
            params={"repo": repo, "pr_number": pr_number},
            timeout=10
        )
        if response.status_code == 200:
            return response.json()
        return {"status": "error", "error": response.text}
    except Exception as e:
        return {"status": "error", "error": str(e)}


def get_all_reviews() -> list:
    """Get all reviews from the backend."""
    try:
        response = requests.get(f"{API_BASE_URL}/reviews", timeout=10)
        if response.status_code == 200:
            data = response.json()
            return data.get("reviews", [])
        return []
    except:
        return []


# ============ Session State Initialization ============

if 'review_history' not in st.session_state:
    st.session_state.review_history = []

if 'current_review' not in st.session_state:
    st.session_state.current_review = None


# ============ Sidebar ============

with st.sidebar:
    st.image("https://raw.githubusercontent.com/github/explore/main/topics/github/github.png", width=60)
    st.title("🤖 AI Code Review")
    st.markdown("---")
    
    # Navigation
    page = st.radio(
        "Navigation",
        ["🏠 Dashboard", "🔍 Review PR", "📊 History", "⚙️ Settings"],
        label_visibility="collapsed"
    )
    
    st.markdown("---")
    
    # Quick Stats
    st.subheader("📈 Quick Stats")
    col1, col2 = st.columns(2)
    with col1:
        st.metric("Reviews", len(st.session_state.review_history))
    with col2:
        health = check_api_health()
        status_emoji = "🟢" if health["status"] == "healthy" else "🔴"
        st.metric("API", status_emoji)
    
    st.markdown("---")
    st.caption("Built with ❤️ using LangGraph & Streamlit")


# ============ Page: Dashboard ============

if page == "🏠 Dashboard":
    st.markdown('<p class="main-header">🤖 AI Code Review Agent</p>', unsafe_allow_html=True)
    st.markdown('<p class="sub-header">Automated, intelligent code reviews powered by LLMs</p>', unsafe_allow_html=True)
    
    # Status Cards
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        health = check_api_health()
        status_class = "status-healthy" if health["status"] == "healthy" else "status-unhealthy"
        st.markdown(f"""
        <div class="metric-card">
            <h3>API Status</h3>
            <p class="{status_class}" style="font-size: 1.5rem;">
                {"✅ Online" if health["status"] == "healthy" else "❌ Offline"}
            </p>
        </div>
        """, unsafe_allow_html=True)
    
    with col2:
        api_info = get_api_info()
        st.markdown(f"""
        <div class="metric-card">
            <h3>Version</h3>
            <p style="font-size: 1.5rem; color: #1f77b4;">{api_info.get('version', 'N/A')}</p>
        </div>
        """, unsafe_allow_html=True)
    
    with col3:
        st.markdown(f"""
        <div class="metric-card">
            <h3>Reviews Today</h3>
            <p style="font-size: 1.5rem; color: #1f77b4;">{len(st.session_state.review_history)}</p>
        </div>
        """, unsafe_allow_html=True)
    
    with col4:
        st.markdown(f"""
        <div class="metric-card">
            <h3>Model</h3>
            <p style="font-size: 1.5rem; color: #1f77b4;">GPT-4 Turbo</p>
        </div>
        """, unsafe_allow_html=True)
    
    st.markdown("---")
    
    # Architecture Overview
    st.subheader("🏗️ System Architecture")
    
    st.markdown("""
    ```
    ┌─────────────────────────────────────────────────────────────────┐
    │                     Streamlit Frontend (You are here!)          │
    └─────────────────────────────────────────────────────────────────┘
                                   │
                                   ▼
    ┌─────────────────────────────────────────────────────────────────┐
    │                      FastAPI Backend                            │
    └─────────────────────────────────────────────────────────────────┘
                                   │
                                   ▼
    ┌─────────────────────────────────────────────────────────────────┐
    │                    Review Orchestrator (LangGraph)              │
    │                                                                 │
    │   ┌──────────┐    ┌──────────┐    ┌──────────┐                │
    │   │ Analyzer │ -> │ Context  │ -> │ Reviewer │                │
    │   │  Agent   │    │  Agent   │    │  Agent   │                │
    │   └──────────┘    └──────────┘    └──────────┘                │
    └─────────────────────────────────────────────────────────────────┘
    ```
    """)
    
    # Features
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("✨ Features")
        st.markdown("""
        - 🔍 **Intelligent Analysis**: Deep understanding of code changes
        - 🛡️ **Security Scanning**: Detect vulnerabilities automatically
        - ⚡ **Performance Tips**: Identify optimization opportunities
        - 📝 **Clear Feedback**: Actionable, constructive suggestions
        - 🔄 **Auto-Learning**: Improves from past reviews
        """)
    
    with col2:
        st.subheader("🚀 Quick Start")
        st.markdown("""
        1. Navigate to **Review PR** in the sidebar
        2. Enter your repository name (e.g., `owner/repo`)
        3. Enter the PR number to review
        4. Click **Start Review** and wait for magic! ✨
        """)


# ============ Page: Review PR ============

elif page == "🔍 Review PR":
    st.header("🔍 Review a Pull Request")
    st.markdown("Trigger an AI-powered code review for any GitHub pull request.")
    
    st.markdown("---")
    
    # Input Form
    col1, col2 = st.columns([2, 1])
    
    with col1:
        repo_input = st.text_input(
            "Repository",
            placeholder="owner/repository",
            help="Enter the full repository name in 'owner/repo' format"
        )
        
        pr_number = st.number_input(
            "Pull Request Number",
            min_value=1,
            step=1,
            help="Enter the PR number to review"
        )
        
        # Advanced options
        with st.expander("⚙️ Advanced Options"):
            review_depth = st.select_slider(
                "Review Depth",
                options=["Quick", "Standard", "Thorough"],
                value="Standard"
            )
            
            focus_areas = st.multiselect(
                "Focus Areas",
                ["Security", "Performance", "Style", "Documentation", "Testing", "All"],
                default=["All"]
            )
            
            include_suggestions = st.checkbox("Include code suggestions", value=True)
    
    with col2:
        st.markdown("### 📋 Review Settings")
        st.info(f"""
        **Repository:** {repo_input or 'Not set'}  
        **PR Number:** {pr_number}  
        **Depth:** {review_depth if 'review_depth' in dir() else 'Standard'}
        """)
    
    st.markdown("---")
    
    # Review Button
    if st.button("🚀 Start Review", type="primary", use_container_width=True):
        if not repo_input:
            st.error("Please enter a repository name")
        elif not pr_number:
            st.error("Please enter a PR number")
        else:
            with st.spinner(f"🔍 Analyzing PR #{pr_number} in {repo_input}..."):
                # Trigger actual review
                result = trigger_review(repo_input, pr_number)
                
                if result["success"]:
                    st.info(f"⏳ Review started for {repo_input}#{pr_number}. Polling for results...")
                    
                    # Poll for results
                    import time
                    progress = st.progress(0)
                    status_text = st.empty()
                    
                    max_attempts = 120  # 2 minutes max
                    attempt = 0
                    review_result = None
                    
                    while attempt < max_attempts:
                        status = get_review_status(repo_input, pr_number)
                        
                        if status.get("status") == "completed":
                            review_result = status
                            progress.progress(100)
                            status_text.text("Review completed!")
                            break
                        elif status.get("status") == "failed":
                            st.error(f"❌ Review failed: {status.get('error', 'Unknown error')}")
                            break
                        elif status.get("status") == "processing":
                            progress.progress(min(attempt * 2, 90))
                            status_text.text(f"Processing... ({attempt}s)")
                        
                        time.sleep(1)
                        attempt += 1
                    
                    if review_result:
                        st.success(f"✅ Review completed for {repo_input}#{pr_number}")
                        
                        # Add to history with full results
                        st.session_state.review_history.append({
                            "repo": repo_input,
                            "pr_number": pr_number,
                            "timestamp": review_result.get("completed_at", datetime.now().isoformat()),
                            "status": "completed",
                            "result": review_result.get("result", {})
                        })
                        
                        # Show quick summary
                        result_data = review_result.get("result", {})
                        rec = result_data.get("recommendation", "comment")
                        rec_emoji = {"approve": "✅", "request_changes": "🔴", "comment": "💬"}.get(rec, "❓")
                        
                        st.markdown(f"### {rec_emoji} Recommendation: **{rec.replace('_', ' ').title()}**")
                        
                        if result_data.get("summary"):
                            st.info(result_data["summary"])
                        
                        stats = result_data.get("stats", {})
                        if stats:
                            col1, col2, col3 = st.columns(3)
                            with col1:
                                st.metric("🚨 Critical", stats.get("critical", 0))
                            with col2:
                                st.metric("⚠️ Warnings", stats.get("warning", 0))
                            with col3:
                                st.metric("💡 Suggestions", stats.get("suggestion", 0))
                        
                        st.balloons()
                    elif attempt >= max_attempts:
                        st.warning("⏰ Review is taking longer than expected. Check the History tab for results.")
                        st.session_state.review_history.append({
                            "repo": repo_input,
                            "pr_number": pr_number,
                            "timestamp": datetime.now().isoformat(),
                            "status": "processing"
                        })
                else:
                    st.error(f"❌ Failed to start review: {result.get('error', 'Unknown error')}")
    
    # Recent Reviews
    st.markdown("---")
    st.subheader("📜 Recent Reviews")
    
    if st.session_state.review_history:
        for review in reversed(st.session_state.review_history[-5:]):
            col1, col2, col3 = st.columns([3, 2, 1])
            with col1:
                st.markdown(f"**{review['repo']}** #{review['pr_number']}")
            with col2:
                st.caption(review['timestamp'][:19])
            with col3:
                status_color = "🟢" if review['status'] == 'completed' else "🟡"
                st.markdown(f"{status_color} {review['status']}")
    else:
        st.info("No reviews yet. Start your first review above!")


# ============ Page: History ============

elif page == "📊 History":
    st.header("📊 Review History")
    st.markdown("View and analyze past code reviews.")
    
    # Refresh button to fetch from backend
    col1, col2 = st.columns([1, 4])
    with col1:
        if st.button("🔄 Refresh"):
            backend_reviews = get_all_reviews()
            if backend_reviews:
                # Merge with session state, avoiding duplicates
                existing_keys = {f"{r['repo']}#{r['pr_number']}" for r in st.session_state.review_history}
                for review in backend_reviews:
                    key = f"{review['repo']}#{review['pr_number']}"
                    if key not in existing_keys:
                        st.session_state.review_history.append({
                            "repo": review["repo"],
                            "pr_number": review["pr_number"],
                            "timestamp": review.get("completed_at") or review.get("started_at", ""),
                            "status": review["status"],
                            "result": review.get("result")
                        })
                st.success(f"Loaded {len(backend_reviews)} reviews from backend")
                st.rerun()
    
    st.markdown("---")
    
    if st.session_state.review_history:
        # Stats
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Total Reviews", len(st.session_state.review_history))
        with col2:
            unique_repos = len(set(r['repo'] for r in st.session_state.review_history))
            st.metric("Unique Repos", unique_repos)
        with col3:
            st.metric("Today's Reviews", len(st.session_state.review_history))
        
        st.markdown("---")
        
        # Filter
        filter_repo = st.selectbox(
            "Filter by Repository",
            ["All"] + list(set(r['repo'] for r in st.session_state.review_history))
        )
        
        # History Table
        st.subheader("📋 Review Log")
        
        for review in reversed(st.session_state.review_history):
            if filter_repo != "All" and review['repo'] != filter_repo:
                continue
                
            with st.container():
                col1, col2, col3, col4 = st.columns([3, 1, 2, 1])
                with col1:
                    st.markdown(f"**{review['repo']}** PR #{review['pr_number']}")
                with col2:
                    status_emoji = {"queued": "🟡", "completed": "🟢", "failed": "🔴"}.get(review['status'], "⚪")
                    st.markdown(f"{status_emoji} {review['status'].title()}")
                with col3:
                    st.caption(review['timestamp'][:19])
                with col4:
                    if st.button("View", key=f"view_{review['timestamp']}"):
                        st.session_state.current_review = review
                st.markdown("---")
        
        # Display selected review details
        if st.session_state.current_review:
            st.markdown("---")
            st.subheader("📄 Review Details")
            
            review = st.session_state.current_review
            
            # Review header
            col1, col2 = st.columns([3, 1])
            with col1:
                st.markdown(f"### {review['repo']} - PR #{review['pr_number']}")
            with col2:
                if st.button("✖ Close", key="close_review"):
                    st.session_state.current_review = None
                    st.rerun()
            
            # Review metadata
            col1, col2, col3 = st.columns(3)
            with col1:
                st.markdown(f"**Status:** {review['status'].title()}")
            with col2:
                st.markdown(f"**Reviewed:** {review['timestamp'][:19]}")
            with col3:
                st.markdown(f"**PR Link:** [View on GitHub](https://github.com/{review['repo']}/pull/{review['pr_number']})")
            
            st.markdown("---")
            
            # Check if there are detailed results
            if 'result' in review and review['result']:
                result = review['result']
                
                # Overall recommendation
                recommendation = result.get('recommendation', 'comment')
                rec_color = {"approve": "🟢", "request_changes": "🔴", "comment": "🟡"}.get(recommendation, "⚪")
                st.markdown(f"### {rec_color} Recommendation: **{recommendation.replace('_', ' ').title()}**")
                
                # Summary
                if 'summary' in result:
                    st.markdown("#### 📝 Summary")
                    st.info(result['summary'])
                
                # Comments
                if 'comments' in result and result['comments']:
                    st.markdown("#### 💬 Review Comments")
                    for i, comment in enumerate(result['comments']):
                        severity = comment.get('severity', 'info')
                        severity_icon = {"critical": "🚨", "warning": "⚠️", "suggestion": "💡", "info": "ℹ️"}.get(severity, "💬")
                        
                        with st.expander(f"{severity_icon} {comment.get('category', 'General')} - Line {comment.get('line_number', 'N/A')}", expanded=(i < 3)):
                            st.markdown(f"**File:** `{comment.get('file_path', 'Unknown')}`")
                            st.markdown(f"**Message:** {comment.get('message', 'No message')}")
                            if comment.get('suggestion'):
                                st.markdown("**Suggested Fix:**")
                                st.code(comment['suggestion'], language="python")
                else:
                    st.info("No detailed comments available for this review.")
            else:
                # No detailed results, show basic info
                st.info(f"""
                **Review Status:** {review['status'].title()}
                
                This review was queued but detailed results are not available yet.
                
                If the review was recently submitted, it may still be processing.
                Check the backend logs for more information.
                """)
                
                # Show link to check manually
                st.markdown(f"[🔗 View PR on GitHub](https://github.com/{review['repo']}/pull/{review['pr_number']})")
                
    else:
        st.info("📭 No review history yet. Go to 'Review PR' to start your first review!")
        
        # Sample data option
        if st.button("Load Sample Data"):
            st.session_state.review_history = [
                {
                    "repo": "example/repo1", 
                    "pr_number": 42, 
                    "timestamp": "2026-01-30T10:30:00", 
                    "status": "completed",
                    "result": {
                        "recommendation": "approve",
                        "summary": "This PR adds a new utility function with good error handling and documentation. Minor style improvements suggested.",
                        "comments": [
                            {
                                "file_path": "src/utils.py",
                                "line_number": 15,
                                "severity": "suggestion",
                                "category": "Style",
                                "message": "Consider using f-strings for better readability",
                                "suggestion": 'message = f"User {user_id} logged in"'
                            },
                            {
                                "file_path": "src/utils.py",
                                "line_number": 28,
                                "severity": "warning",
                                "category": "Performance",
                                "message": "This list comprehension could be replaced with a generator for memory efficiency",
                                "suggestion": "results = (process(item) for item in items)"
                            }
                        ]
                    }
                },
                {
                    "repo": "example/repo1", 
                    "pr_number": 43, 
                    "timestamp": "2026-01-30T11:15:00", 
                    "status": "completed",
                    "result": {
                        "recommendation": "request_changes",
                        "summary": "Security issues detected. Please address the SQL injection vulnerability before merging.",
                        "comments": [
                            {
                                "file_path": "src/database.py",
                                "line_number": 45,
                                "severity": "critical",
                                "category": "Security",
                                "message": "SQL Injection vulnerability! User input is directly concatenated into SQL query.",
                                "suggestion": 'cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))'
                            }
                        ]
                    }
                },
                {
                    "repo": "example/repo2", 
                    "pr_number": 17, 
                    "timestamp": "2026-01-30T14:00:00", 
                    "status": "queued"
                },
            ]
            st.rerun()


# ============ Page: Settings ============

elif page == "⚙️ Settings":
    st.header("⚙️ Settings")
    st.markdown("Configure your AI Code Review Agent.")
    
    st.markdown("---")
    
    # API Configuration
    st.subheader("🔗 API Configuration")
    
    col1, col2 = st.columns(2)
    with col1:
        api_url = st.text_input("API Base URL", value=API_BASE_URL)
        
    with col2:
        # Test connection
        if st.button("Test Connection"):
            health = check_api_health()
            if health["status"] == "healthy":
                st.success("✅ Connected successfully!")
            else:
                st.error(f"❌ Connection failed: {health.get('error', 'Unknown')}")
    
    st.markdown("---")
    
    # GitHub Configuration
    st.subheader("🐙 GitHub Configuration")
    
    github_token = st.text_input(
        "GitHub Token",
        type="password",
        help="Your GitHub Personal Access Token",
        placeholder="ghp_xxxxxxxxxxxxxxxxxxxx"
    )
    
    webhook_secret = st.text_input(
        "Webhook Secret",
        type="password",
        help="Secret for webhook signature verification"
    )
    
    st.markdown("---")
    
    # LLM Configuration
    st.subheader("🧠 LLM Configuration")
    
    col1, col2 = st.columns(2)
    with col1:
        model = st.selectbox(
            "Model",
            ["gpt-4-turbo-preview", "gpt-4", "gpt-3.5-turbo"],
            index=0
        )
    
    with col2:
        temperature = st.slider("Temperature", 0.0, 1.0, 0.2, 0.1)
    
    st.markdown("---")
    
    # Review Preferences
    st.subheader("📝 Review Preferences")
    
    col1, col2 = st.columns(2)
    with col1:
        st.checkbox("Auto-approve minor changes", value=False)
        st.checkbox("Include performance analysis", value=True)
        st.checkbox("Security-first review", value=True)
    
    with col2:
        st.checkbox("Generate code suggestions", value=True)
        st.checkbox("Include documentation checks", value=True)
        st.checkbox("Verbose explanations", value=False)
    
    st.markdown("---")
    
    # Save Settings
    col1, col2 = st.columns([1, 4])
    with col1:
        if st.button("💾 Save Settings", type="primary"):
            st.success("Settings saved successfully!")
    with col2:
        if st.button("🔄 Reset to Defaults"):
            st.info("Settings reset to defaults")


# ============ Footer ============

st.markdown("---")
st.markdown(
    """
    <div style="text-align: center; color: #888; padding: 20px;">
        <p>AI Code Review Agent v0.1.0 | Built with LangGraph & Streamlit</p>
        <p>
            <a href="/docs" target="_blank">API Docs</a> |
            <a href="https://github.com" target="_blank">GitHub</a>
        </p>
    </div>
    """,
    unsafe_allow_html=True
)
