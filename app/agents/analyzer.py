"""
Analyzer Agent - Parses code diffs and identifies changes.

This agent is responsible for:
1. Parsing GitHub PR diffs
2. Identifying what changed (files, functions, classes)
3. Categorizing changes (bugfix, feature, refactor, etc.)
4. Extracting context around changes
"""

import re
import json
from typing import TypedDict, List, Optional
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate

from ..core.logging import get_logger

logger = get_logger(__name__)


class DiffHunk(TypedDict):
    """Represents a single hunk in a diff."""
    old_start: int
    old_count: int
    new_start: int
    new_count: int
    header: str
    content: str
    added_lines: List[str]
    removed_lines: List[str]


class CodeChange(TypedDict):
    """Represents a single code change."""
    file_path: str
    change_type: str  # added, modified, deleted, renamed
    diff: str
    language: str
    hunks: List[DiffHunk]
    additions: int
    deletions: int
    analysis: Optional[dict]  # LLM analysis results


class AnalysisResult(TypedDict):
    """Result of analyzing a PR."""
    pr_number: int
    title: str
    total_files_changed: int
    total_additions: int
    total_deletions: int
    changes: List[CodeChange]
    summary: str
    risk_level: str  # low, medium, high
    categories: List[str]  # bugfix, feature, refactor, etc.


class AnalyzerAgent:
    """
    Agent responsible for analyzing code changes in a pull request.
    
    This agent parses diffs, understands what changed, and prepares
    structured data for the Context and Reviewer agents.
    """
    
    def __init__(self, llm: Optional[ChatOpenAI] = None):
        self.llm = llm or ChatOpenAI(model="gpt-4-turbo-preview", temperature=0)
        self._init_prompts()
    
    def _init_prompts(self):
        """Initialize prompt templates."""
        
        # Prompt for analyzing a single file's changes
        self.analyze_file_prompt = ChatPromptTemplate.from_messages([
            ("system", """You are a code analysis expert. Analyze the following code diff and provide:

1. **categories**: List of change types (choose from: bugfix, feature, refactor, documentation, test, config, dependency, security, performance)
2. **risk_level**: Assessment of risk (low, medium, high) based on:
   - low: Simple changes, documentation, tests, config
   - medium: New features, moderate refactors
   - high: Security changes, core logic changes, complex refactors, database changes
3. **summary**: Brief 1-2 sentence description of what changed
4. **key_changes**: List of specific changes (functions/classes added, modified, removed)
5. **potential_issues**: Any concerns or things to look out for

Respond ONLY with valid JSON in this exact format:
{{
    "categories": ["category1", "category2"],
    "risk_level": "low|medium|high",
    "summary": "Brief description",
    "key_changes": ["change1", "change2"],
    "potential_issues": ["issue1", "issue2"]
}}"""),
            ("user", """File: {file_path}
Language: {language}
Change type: {change_type}
Additions: {additions}
Deletions: {deletions}

Diff:
```
{diff}
```""")
        ])
        
        # Prompt for overall PR summary
        self.summarize_pr_prompt = ChatPromptTemplate.from_messages([
            ("system", """You are a code analysis expert. Given the analysis of individual files in a pull request, provide an overall summary.

Include:
1. **summary**: 2-3 sentence overview of the entire PR
2. **risk_level**: Overall risk (low, medium, high) - take the highest risk from individual files
3. **categories**: Aggregated categories from all files (deduplicated)
4. **review_focus**: What reviewers should pay attention to

Respond ONLY with valid JSON:
{{
    "summary": "Overall PR description",
    "risk_level": "low|medium|high",
    "categories": ["category1", "category2"],
    "review_focus": ["focus1", "focus2"]
}}"""),
            ("user", """PR Title: {title}
Total files: {total_files}
Total additions: {additions}
Total deletions: {deletions}

Individual file analyses:
{file_analyses}""")
        ])
    
    async def analyze_pr(self, pr_data: dict) -> AnalysisResult:
        """
        Analyze a pull request and return structured results.
        
        Args:
            pr_data: Dictionary containing PR information from GitHub API
            
        Returns:
            AnalysisResult with categorized and analyzed changes
        """
        logger.info("Starting PR analysis", pr=pr_data.get("number"))
        
        changes: List[CodeChange] = []
        file_analyses = []
        
        # Process each file's diff
        for file in pr_data.get("files", []):
            change = await self._analyze_file_change(file)
            changes.append(change)
            
            if change.get("analysis"):
                file_analyses.append({
                    "file": change["file_path"],
                    "analysis": change["analysis"]
                })
        
        # Calculate totals
        total_additions = sum(c.get("additions", 0) for c in changes)
        total_deletions = sum(c.get("deletions", 0) for c in changes)
        
        # Generate overall summary
        overall = await self._generate_overall_summary(
            pr_data.get("title", ""),
            len(changes),
            total_additions,
            total_deletions,
            file_analyses
        )
        
        # Aggregate categories and determine risk
        all_categories = set()
        max_risk = "low"
        risk_order = {"low": 0, "medium": 1, "high": 2}
        
        for change in changes:
            if change.get("analysis"):
                all_categories.update(change["analysis"].get("categories", []))
                change_risk = change["analysis"].get("risk_level", "low")
                if risk_order.get(change_risk, 0) > risk_order.get(max_risk, 0):
                    max_risk = change_risk
        
        result: AnalysisResult = {
            "pr_number": pr_data.get("number", 0),
            "title": pr_data.get("title", ""),
            "total_files_changed": len(changes),
            "total_additions": total_additions,
            "total_deletions": total_deletions,
            "changes": changes,
            "summary": overall.get("summary", ""),
            "risk_level": max_risk,
            "categories": list(all_categories)
        }
        
        logger.info("PR analysis complete", 
                   pr=pr_data.get("number"), 
                   files=len(changes),
                   risk=max_risk)
        
        return result
    
    async def _analyze_file_change(self, file_data: dict) -> CodeChange:
        """
        Analyze a single file's changes.
        """
        file_path = file_data.get("filename", "")
        language = self._detect_language(file_path)
        diff = file_data.get("patch", "")
        
        # Parse diff into hunks
        hunks = self.parse_diff_hunks(diff)
        
        # Count additions and deletions
        additions = file_data.get("additions", 0)
        deletions = file_data.get("deletions", 0)
        
        change: CodeChange = {
            "file_path": file_path,
            "change_type": file_data.get("status", "modified"),
            "diff": diff,
            "language": language,
            "hunks": hunks,
            "additions": additions,
            "deletions": deletions,
            "analysis": None
        }
        
        # Skip analysis for certain files
        if self._should_skip_analysis(file_path, language):
            logger.debug("Skipping analysis for file", file=file_path)
            return change
        
        # Use LLM to analyze the change
        try:
            analysis = await self._llm_analyze_file(change)
            change["analysis"] = analysis
        except Exception as e:
            logger.error("LLM analysis failed", file=file_path, error=str(e))
        
        return change
    
    async def _llm_analyze_file(self, change: CodeChange) -> dict:
        """Use LLM to analyze a file change."""
        messages = self.analyze_file_prompt.format_messages(
            file_path=change["file_path"],
            language=change["language"],
            change_type=change["change_type"],
            additions=change["additions"],
            deletions=change["deletions"],
            diff=change["diff"][:8000]  # Truncate very long diffs
        )
        
        response = await self.llm.ainvoke(messages)
        
        # Parse JSON response
        try:
            # Extract JSON from response (handle markdown code blocks)
            content = response.content
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
            elif "```" in content:
                content = content.split("```")[1].split("```")[0]
            
            return json.loads(content.strip())
        except json.JSONDecodeError as e:
            logger.warning("Failed to parse LLM response as JSON", error=str(e))
            return {
                "categories": ["unknown"],
                "risk_level": "medium",
                "summary": "Could not analyze changes",
                "key_changes": [],
                "potential_issues": []
            }
    
    async def _generate_overall_summary(
        self, 
        title: str, 
        total_files: int,
        additions: int,
        deletions: int,
        file_analyses: List[dict]
    ) -> dict:
        """Generate overall PR summary using LLM."""
        if not file_analyses:
            return {
                "summary": "No analyzable changes found.",
                "risk_level": "low",
                "categories": [],
                "review_focus": []
            }
        
        # Format file analyses for prompt
        analyses_text = "\n".join([
            f"- {fa['file']}: {fa['analysis'].get('summary', 'N/A')}"
            for fa in file_analyses
        ])
        
        messages = self.summarize_pr_prompt.format_messages(
            title=title,
            total_files=total_files,
            additions=additions,
            deletions=deletions,
            file_analyses=analyses_text
        )
        
        response = await self.llm.ainvoke(messages)
        
        try:
            content = response.content
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
            elif "```" in content:
                content = content.split("```")[1].split("```")[0]
            
            return json.loads(content.strip())
        except json.JSONDecodeError:
            return {
                "summary": f"PR with {total_files} files changed.",
                "risk_level": "medium",
                "categories": [],
                "review_focus": []
            }
    
    def _should_skip_analysis(self, file_path: str, language: str) -> bool:
        """Determine if a file should skip LLM analysis."""
        # Languages that should be reviewed (actual code files)
        reviewable_languages = {
            "python", "javascript", "typescript", "java", "go", "rust",
            "cpp", "c", "csharp", "fsharp", "ruby", "php", "swift",
            "kotlin", "scala", "sql", "bash", "zsh", "powershell",
            "dockerfile", "terraform", "hcl", "vue", "svelte",
            "r", "julia", "elixir", "erlang", "clojure", "lisp", "lua", "perl"
        }
        
        # Skip binary files, lock files, generated files
        skip_patterns = [
            r'\.lock$',
            r'package-lock\.json$',
            r'yarn\.lock$',
            r'\.min\.js$',
            r'\.min\.css$',
            r'\.map$',
            r'\.svg$',
            r'\.png$',
            r'\.jpg$',
            r'\.jpeg$',
            r'\.gif$',
            r'\.ico$',
            r'\.woff',
            r'\.ttf$',
            r'\.eot$',
            r'__pycache__',
            r'\.pyc$',
            r'node_modules/',
            r'vendor/',
            r'\.generated\.',
        ]
        
        for pattern in skip_patterns:
            if re.search(pattern, file_path, re.IGNORECASE):
                return True
        
        # Only review actual code files, skip documentation, config, and style files
        return language not in reviewable_languages
    
    def _detect_language(self, file_path: str) -> str:
        """Detect programming language from file extension."""
        extension_map = {
            ".py": "python",
            ".js": "javascript",
            ".ts": "typescript",
            ".jsx": "javascript",
            ".tsx": "typescript",
            ".java": "java",
            ".go": "go",
            ".rs": "rust",
            ".cpp": "cpp",
            ".cc": "cpp",
            ".cxx": "cpp",
            ".c": "c",
            ".h": "c",
            ".hpp": "cpp",
            ".rb": "ruby",
            ".php": "php",
            ".swift": "swift",
            ".kt": "kotlin",
            ".kts": "kotlin",
            ".scala": "scala",
            ".cs": "csharp",
            ".fs": "fsharp",
            ".sql": "sql",
            ".sh": "bash",
            ".bash": "bash",
            ".zsh": "zsh",
            ".ps1": "powershell",
            ".yaml": "yaml",
            ".yml": "yaml",
            ".json": "json",
            ".xml": "xml",
            ".html": "html",
            ".htm": "html",
            ".css": "css",
            ".scss": "scss",
            ".sass": "sass",
            ".less": "less",
            ".md": "markdown",
            ".markdown": "markdown",
            ".rst": "restructuredtext",
            ".txt": "text",
            ".dockerfile": "dockerfile",
            ".tf": "terraform",
            ".hcl": "hcl",
            ".vue": "vue",
            ".svelte": "svelte",
            ".r": "r",
            ".R": "r",
            ".jl": "julia",
            ".ex": "elixir",
            ".exs": "elixir",
            ".erl": "erlang",
            ".clj": "clojure",
            ".lisp": "lisp",
            ".lua": "lua",
            ".pl": "perl",
            ".pm": "perl",
        }
        
        # Handle Dockerfile without extension
        if file_path.lower().endswith("dockerfile") or "dockerfile" in file_path.lower():
            return "dockerfile"
        
        for ext, lang in extension_map.items():
            if file_path.lower().endswith(ext):
                return lang
        
        return "unknown"
    
    def parse_diff_hunks(self, diff: str) -> List[DiffHunk]:
        """
        Parse a unified diff into individual hunks.
        
        Unified diff format:
        @@ -old_start,old_count +new_start,new_count @@ optional context
        """
        if not diff:
            return []
        
        hunks: List[DiffHunk] = []
        
        # Regex to match hunk headers
        # Format: @@ -start,count +start,count @@ optional_context
        hunk_header_pattern = re.compile(
            r'^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@(.*)$',
            re.MULTILINE
        )
        
        # Find all hunk headers and their positions
        matches = list(hunk_header_pattern.finditer(diff))
        
        for i, match in enumerate(matches):
            old_start = int(match.group(1))
            old_count = int(match.group(2)) if match.group(2) else 1
            new_start = int(match.group(3))
            new_count = int(match.group(4)) if match.group(4) else 1
            header_context = match.group(5).strip()
            
            # Get the content until the next hunk or end of diff
            start_pos = match.end()
            if i + 1 < len(matches):
                end_pos = matches[i + 1].start()
            else:
                end_pos = len(diff)
            
            content = diff[start_pos:end_pos].strip()
            
            # Parse added and removed lines
            added_lines = []
            removed_lines = []
            
            for line in content.split('\n'):
                if line.startswith('+') and not line.startswith('+++'):
                    added_lines.append(line[1:])
                elif line.startswith('-') and not line.startswith('---'):
                    removed_lines.append(line[1:])
            
            hunk: DiffHunk = {
                "old_start": old_start,
                "old_count": old_count,
                "new_start": new_start,
                "new_count": new_count,
                "header": header_context,
                "content": content,
                "added_lines": added_lines,
                "removed_lines": removed_lines
            }
            
            hunks.append(hunk)
        
        return hunks
