"""
Review Visualization Components

Provides rich visualization for code review results.
"""

import streamlit as st
from typing import List, Dict, Any, Optional


def render_severity_badge(severity: str) -> str:
    """Render a severity badge with appropriate styling."""
    colors = {
        "critical": ("#f44336", "🚨"),
        "warning": ("#ff9800", "⚠️"),
        "suggestion": ("#2196f3", "💡")
    }
    color, emoji = colors.get(severity.lower(), ("#9e9e9e", "ℹ️"))
    return f"{emoji} {severity.title()}"


def render_category_badge(category: str) -> str:
    """Render a category badge."""
    icons = {
        "security": "🛡️",
        "bug": "🐛",
        "performance": "⚡",
        "style": "🎨",
        "documentation": "📝",
        "test": "🧪",
        "maintainability": "🔧"
    }
    icon = icons.get(category.lower(), "📌")
    return f"{icon} {category.title()}"


def render_comment_card(comment: Dict[str, Any]):
    """Render a single review comment as a card."""
    severity = comment.get("severity", "suggestion")
    category = comment.get("category", "general")
    
    # Determine card styling based on severity
    border_colors = {
        "critical": "#f44336",
        "warning": "#ff9800",
        "suggestion": "#2196f3"
    }
    bg_colors = {
        "critical": "#ffebee",
        "warning": "#fff3e0",
        "suggestion": "#e3f2fd"
    }
    
    border_color = border_colors.get(severity, "#e0e0e0")
    bg_color = bg_colors.get(severity, "#fafafa")
    
    st.markdown(f"""
    <div style="
        background-color: {bg_color};
        border-left: 4px solid {border_color};
        border-radius: 8px;
        padding: 16px;
        margin-bottom: 12px;
    ">
        <div style="display: flex; justify-content: space-between; margin-bottom: 8px;">
            <span>{render_severity_badge(severity)}</span>
            <span>{render_category_badge(category)}</span>
        </div>
        <p style="margin: 0 0 8px 0; color: #666; font-size: 0.9rem;">
            📁 <code>{comment.get('file_path', 'Unknown file')}</code>
            {f" • Line {comment.get('line_number')}" if comment.get('line_number') else ""}
        </p>
        <p style="margin: 0; color: #333;">
            {comment.get('comment', '')}
        </p>
    </div>
    """, unsafe_allow_html=True)
    
    # Show suggested code if available
    if comment.get("suggested_code"):
        with st.expander("💡 Suggested Fix"):
            st.code(comment["suggested_code"], language="python")


def render_review_summary(review: Dict[str, Any]):
    """Render a complete review summary."""
    st.subheader("📋 Review Summary")
    
    # Overall assessment
    st.markdown(f"**Overall Assessment:** {review.get('overall_assessment', 'No assessment available')}")
    
    # Recommendation badge
    recommendation = review.get("approval_recommendation", "comment")
    rec_colors = {
        "approve": ("🟢", "#28a745", "Approved"),
        "request_changes": ("🔴", "#dc3545", "Changes Requested"),
        "comment": ("🟡", "#ffc107", "Comment")
    }
    emoji, color, text = rec_colors.get(recommendation, ("⚪", "#6c757d", "Unknown"))
    
    st.markdown(f"""
    <div style="
        display: inline-block;
        background-color: {color}20;
        border: 2px solid {color};
        border-radius: 20px;
        padding: 8px 16px;
        margin: 12px 0;
    ">
        <span style="color: {color}; font-weight: bold;">
            {emoji} {text}
        </span>
    </div>
    """, unsafe_allow_html=True)
    
    # Stats
    if review.get("stats"):
        stats = review["stats"]
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Comments", stats.get("total_comments", 0))
        with col2:
            st.metric("Critical", stats.get("critical_count", 0))
        with col3:
            st.metric("Warnings", stats.get("warning_count", 0))
        with col4:
            st.metric("Suggestions", stats.get("suggestion_count", 0))


def render_file_tree(files: List[Dict[str, Any]]):
    """Render a file tree of changes."""
    st.subheader("📁 Changed Files")
    
    for file in files:
        status_icons = {
            "added": "🟢",
            "modified": "🟡",
            "deleted": "🔴",
            "renamed": "🔄"
        }
        status = file.get("status", "modified")
        icon = status_icons.get(status, "📄")
        
        additions = file.get("additions", 0)
        deletions = file.get("deletions", 0)
        
        st.markdown(f"""
        <div style="
            display: flex;
            justify-content: space-between;
            padding: 8px;
            border-bottom: 1px solid #eee;
        ">
            <span>{icon} {file.get('filename', 'Unknown')}</span>
            <span>
                <span style="color: #28a745;">+{additions}</span>
                <span style="color: #dc3545;">-{deletions}</span>
            </span>
        </div>
        """, unsafe_allow_html=True)


def render_diff_viewer(diff: str, filename: str):
    """Render a diff with syntax highlighting."""
    st.markdown(f"### 📄 {filename}")
    
    lines = diff.split('\n')
    html_lines = []
    
    for line in lines:
        if line.startswith('+') and not line.startswith('+++'):
            html_lines.append(f'<div style="background-color: #e6ffed; color: #22863a;">{line}</div>')
        elif line.startswith('-') and not line.startswith('---'):
            html_lines.append(f'<div style="background-color: #ffeef0; color: #b31d28;">{line}</div>')
        elif line.startswith('@@'):
            html_lines.append(f'<div style="background-color: #f1f8ff; color: #032f62;">{line}</div>')
        else:
            html_lines.append(f'<div style="color: #6a737d;">{line}</div>')
    
    st.markdown(f"""
    <div style="
        font-family: 'Consolas', 'Monaco', monospace;
        font-size: 0.85rem;
        background-color: #fafbfc;
        border: 1px solid #e1e4e8;
        border-radius: 6px;
        padding: 12px;
        overflow-x: auto;
        white-space: pre;
    ">
        {''.join(html_lines)}
    </div>
    """, unsafe_allow_html=True)


def render_risk_indicator(risk_level: str):
    """Render a risk level indicator."""
    risk_config = {
        "low": ("🟢", "#28a745", "Low Risk"),
        "medium": ("🟡", "#ffc107", "Medium Risk"),
        "high": ("🔴", "#dc3545", "High Risk")
    }
    
    emoji, color, text = risk_config.get(risk_level.lower(), ("⚪", "#6c757d", "Unknown"))
    
    return f"""
    <span style="
        display: inline-block;
        background-color: {color}20;
        color: {color};
        padding: 4px 12px;
        border-radius: 12px;
        font-weight: bold;
        font-size: 0.9rem;
    ">
        {emoji} {text}
    </span>
    """
