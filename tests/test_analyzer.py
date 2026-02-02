"""
Tests for Analyzer Agent
"""
import pytest
from unittest.mock import MagicMock
from app.agents.analyzer import AnalyzerAgent, CodeChange, DiffHunk


class TestAnalyzerAgent:
    """Test cases for AnalyzerAgent."""
    
    def setup_method(self):
        """Set up test fixtures."""
        # Create agent with a mock LLM to avoid needing API key
        mock_llm = MagicMock()
        self.agent = AnalyzerAgent(llm=mock_llm)
    
    # ==================== Language Detection Tests ====================
    
    def test_detect_language_python(self):
        """Test Python language detection."""
        assert self.agent._detect_language("test.py") == "python"
        assert self.agent._detect_language("path/to/file.py") == "python"
        assert self.agent._detect_language("UPPERCASE.PY") == "python"
    
    def test_detect_language_javascript(self):
        """Test JavaScript language detection."""
        assert self.agent._detect_language("app.js") == "javascript"
        assert self.agent._detect_language("component.jsx") == "javascript"
    
    def test_detect_language_typescript(self):
        """Test TypeScript language detection."""
        assert self.agent._detect_language("service.ts") == "typescript"
        assert self.agent._detect_language("component.tsx") == "typescript"
    
    def test_detect_language_dockerfile(self):
        """Test Dockerfile detection."""
        assert self.agent._detect_language("Dockerfile") == "dockerfile"
        assert self.agent._detect_language("path/to/Dockerfile") == "dockerfile"
        assert self.agent._detect_language("Dockerfile.prod") == "dockerfile"
    
    def test_detect_language_unknown(self):
        """Test unknown language detection."""
        assert self.agent._detect_language("file.xyz") == "unknown"
        assert self.agent._detect_language("README") == "unknown"
        assert self.agent._detect_language("Makefile") == "unknown"
    
    # ==================== Diff Parsing Tests ====================
    
    def test_parse_diff_hunks_empty(self):
        """Test parsing empty diff."""
        hunks = self.agent.parse_diff_hunks("")
        assert hunks == []
    
    def test_parse_diff_hunks_single(self):
        """Test parsing a single hunk."""
        diff = """@@ -1,3 +1,4 @@
 line1
-old line
+new line
+added line
 line3"""
        
        hunks = self.agent.parse_diff_hunks(diff)
        
        assert len(hunks) == 1
        assert hunks[0]["old_start"] == 1
        assert hunks[0]["old_count"] == 3
        assert hunks[0]["new_start"] == 1
        assert hunks[0]["new_count"] == 4
        assert "old line" in hunks[0]["removed_lines"]
        assert "new line" in hunks[0]["added_lines"]
        assert "added line" in hunks[0]["added_lines"]
    
    def test_parse_diff_hunks_multiple(self):
        """Test parsing multiple hunks."""
        diff = """@@ -1,3 +1,3 @@
 line1
-old1
+new1
 line3
@@ -10,3 +10,4 @@
 line10
-old10
+new10
+added10
 line12"""
        
        hunks = self.agent.parse_diff_hunks(diff)
        
        assert len(hunks) == 2
        assert hunks[0]["old_start"] == 1
        assert hunks[1]["old_start"] == 10
        assert hunks[1]["new_count"] == 4
    
    def test_parse_diff_hunks_with_context(self):
        """Test parsing hunks with function context."""
        diff = """@@ -5,6 +5,7 @@ def my_function():
     existing_code()
+    new_code()
     more_code()"""
        
        hunks = self.agent.parse_diff_hunks(diff)
        
        assert len(hunks) == 1
        assert hunks[0]["header"] == "def my_function():"
    
    # ==================== Skip Analysis Tests ====================
    
    def test_should_skip_analysis_lock_files(self):
        """Test that lock files are skipped."""
        assert self.agent._should_skip_analysis("package-lock.json", "json") is True
        assert self.agent._should_skip_analysis("yarn.lock", "unknown") is True
        assert self.agent._should_skip_analysis("poetry.lock", "unknown") is True
    
    def test_should_skip_analysis_minified(self):
        """Test that minified files are skipped."""
        assert self.agent._should_skip_analysis("app.min.js", "javascript") is True
        assert self.agent._should_skip_analysis("styles.min.css", "css") is True
    
    def test_should_skip_analysis_images(self):
        """Test that image files are skipped."""
        assert self.agent._should_skip_analysis("logo.png", "unknown") is True
        assert self.agent._should_skip_analysis("photo.jpg", "unknown") is True
        assert self.agent._should_skip_analysis("icon.svg", "unknown") is True
    
    def test_should_skip_analysis_non_code_files(self):
        """Test that documentation and config files are skipped."""
        assert self.agent._should_skip_analysis("README.md", "markdown") is True
        assert self.agent._should_skip_analysis("docs/guide.md", "markdown") is True
        assert self.agent._should_skip_analysis("config.yaml", "yaml") is True
        assert self.agent._should_skip_analysis("config.json", "json") is True
        assert self.agent._should_skip_analysis("styles.css", "css") is True
    
    def test_should_not_skip_source_files(self):
        """Test that source files are not skipped."""
        assert self.agent._should_skip_analysis("app.py", "python") is False
        assert self.agent._should_skip_analysis("service.ts", "typescript") is False
        assert self.agent._should_skip_analysis("main.go", "go") is False
        assert self.agent._should_skip_analysis("app.js", "javascript") is False
        assert self.agent._should_skip_analysis("Main.java", "java") is False
        assert self.agent._should_skip_analysis("lib.rs", "rust") is False


class TestAnalyzerAgentAsync:
    """Async test cases for AnalyzerAgent."""
    
    @pytest.fixture
    def agent(self):
        mock_llm = MagicMock()
        return AnalyzerAgent(llm=mock_llm)
    
    @pytest.mark.asyncio
    async def test_analyze_pr_empty(self, agent):
        """Test analyzing PR with no files."""
        pr_data = {
            "number": 1,
            "title": "Test PR",
            "files": []
        }
        
        result = await agent.analyze_pr(pr_data)
        
        assert result["pr_number"] == 1
        assert result["total_files_changed"] == 0
        assert result["changes"] == []
    
    @pytest.mark.asyncio
    async def test_analyze_file_change_basic(self, agent):
        """Test analyzing a single file change."""
        file_data = {
            "filename": "test.py",
            "status": "modified",
            "additions": 5,
            "deletions": 2,
            "patch": "@@ -1,3 +1,6 @@\n+import os\n+\n def main():\n-    pass\n+    print('hello')\n+    return 0"
        }
        
        change = await agent._analyze_file_change(file_data)
        
        assert change["file_path"] == "test.py"
        assert change["language"] == "python"
        assert change["change_type"] == "modified"
        assert change["additions"] == 5
        assert change["deletions"] == 2
        assert len(change["hunks"]) == 1
