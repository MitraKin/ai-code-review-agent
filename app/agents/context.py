"""
Context Agent - Retrieves relevant context using RAG.

This agent is responsible for:
1. Finding similar past code reviews
2. Retrieving coding standards and guidelines
3. Fetching related documentation
4. Providing historical context for better reviews
"""

import os
import hashlib
from typing import List, Optional, TypedDict
from datetime import datetime

from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_core.prompts import ChatPromptTemplate

from ..core.config import get_settings
from ..core.logging import get_logger

logger = get_logger(__name__)


class ContextItem(TypedDict):
    """A piece of retrieved context."""
    content: str
    source: str  # past_review, coding_standard, documentation
    relevance_score: float
    metadata: dict


class RetrievedContext(TypedDict):
    """All context retrieved for a code change."""
    similar_reviews: List[ContextItem]
    coding_standards: List[ContextItem]
    documentation: List[ContextItem]
    summary: str


class ContextAgent:
    """
    Agent responsible for retrieving relevant context for code reviews.
    
    Uses RAG (Retrieval-Augmented Generation) to find:
    - Similar past reviews and their feedback
    - Relevant coding standards and best practices
    - Documentation that might be helpful
    """
    
    def __init__(
        self, 
        llm: Optional[ChatOpenAI] = None,
        embeddings: Optional[OpenAIEmbeddings] = None,
    ):
        self.settings = get_settings()
        self.llm = llm or ChatOpenAI(model="gpt-4-turbo-preview", temperature=0)
        self.embeddings = embeddings or OpenAIEmbeddings()
        
        self._chroma_client = None
        self._collections_initialized = False
        
        self._init_prompts()
    
    def _get_chroma_client(self):
        """Lazy initialization of ChromaDB client."""
        if self._chroma_client is None:
            import chromadb
            
            persist_dir = self.settings.chroma_persist_directory
            os.makedirs(persist_dir, exist_ok=True)
            
            # Use the new ChromaDB client initialization (v0.4+)
            self._chroma_client = chromadb.PersistentClient(path=persist_dir)
            
            logger.info("ChromaDB client initialized", persist_dir=persist_dir)
        
        return self._chroma_client
    
    def _init_collections(self):
        """Initialize ChromaDB collections on first use."""
        if self._collections_initialized:
            return
        
        client = self._get_chroma_client()
        
        # Collection for past reviews
        self.reviews_collection = client.get_or_create_collection(
            name="past_reviews",
            metadata={"description": "Historical code reviews and feedback"}
        )
        
        # Collection for coding standards
        self.standards_collection = client.get_or_create_collection(
            name="coding_standards",
            metadata={"description": "Team coding standards and guidelines"}
        )
        
        # Collection for documentation
        self.docs_collection = client.get_or_create_collection(
            name="documentation",
            metadata={"description": "Relevant documentation and best practices"}
        )
        
        self._collections_initialized = True
        logger.info("ChromaDB collections initialized")
    
    def _init_prompts(self):
        """Initialize prompt templates."""
        
        self.summarize_context_prompt = ChatPromptTemplate.from_messages([
            ("system", """You are helping a code reviewer. Based on the retrieved context, provide a concise summary of relevant information that will help review this code change.

Focus on:
1. **Patterns from similar reviews**: What feedback was given before for similar code?
2. **Applicable standards**: What coding standards or guidelines apply here?
3. **Best practices**: What documentation or best practices are relevant?

Be specific and actionable. If there's no relevant context, say so briefly.

Keep your response under 500 words."""),
            ("user", """Code being reviewed:
File: {file_path}
Language: {language}
Summary: {code_summary}

Similar past reviews:
{past_reviews}

Relevant coding standards:
{coding_standards}

Relevant documentation:
{documentation}

Provide a summary of relevant context for reviewing this code.""")
        ])
    
    async def get_context(self, code_change: dict) -> RetrievedContext:
        """
        Retrieve all relevant context for a code change.
        
        Args:
            code_change: The analyzed code change from AnalyzerAgent
            
        Returns:
            RetrievedContext with similar reviews, standards, and docs
        """
        self._init_collections()
        
        file_path = code_change.get("file_path", "")
        language = code_change.get("language", "unknown")
        diff = code_change.get("diff", "")
        
        logger.info("Retrieving context", file=file_path, language=language)
        
        # Generate embedding for the code change
        code_text = f"File: {file_path}\nLanguage: {language}\n\n{diff}"
        embedding = await self._get_embedding(code_text)
        
        # Retrieve from each collection in parallel
        similar_reviews = await self._search_similar_reviews(
            embedding, language, file_path
        )
        coding_standards = await self._search_coding_standards(
            embedding, language
        )
        documentation = await self._search_documentation(
            embedding, language
        )
        
        # Generate summary of context
        summary = await self._summarize_context(
            code_change,
            similar_reviews,
            coding_standards,
            documentation
        )
        
        return {
            "similar_reviews": similar_reviews,
            "coding_standards": coding_standards,
            "documentation": documentation,
            "summary": summary
        }
    
    async def _get_embedding(self, text: str) -> List[float]:
        """Generate embedding for text using OpenAI."""
        # Truncate if too long (OpenAI embedding limit is ~8191 tokens)
        if len(text) > 30000:
            text = text[:30000]
        
        try:
            embedding = await self.embeddings.aembed_query(text)
            return embedding
        except Exception as e:
            logger.error("Failed to generate embedding", error=str(e))
            return []
    
    async def _search_similar_reviews(
        self, 
        embedding: List[float],
        language: str,
        file_path: str,
        k: int = 5
    ) -> List[ContextItem]:
        """Search for similar past code reviews."""
        if not embedding:
            return []
        
        try:
            # Build filter for language
            where_filter = None
            if language and language != "unknown":
                where_filter = {"language": language}
            
            results = self.reviews_collection.query(
                query_embeddings=[embedding],
                n_results=k,
                where=where_filter
            )
            
            items = []
            if results and results.get("documents"):
                for i, doc in enumerate(results["documents"][0]):
                    metadata = results["metadatas"][0][i] if results.get("metadatas") else {}
                    distance = results["distances"][0][i] if results.get("distances") else 0
                    
                    items.append({
                        "content": doc,
                        "source": "past_review",
                        "relevance_score": 1 - distance,  # Convert distance to similarity
                        "metadata": metadata
                    })
            
            logger.debug("Found similar reviews", count=len(items))
            return items
            
        except Exception as e:
            logger.error("Failed to search reviews", error=str(e))
            return []
    
    async def _search_coding_standards(
        self, 
        embedding: List[float],
        language: str,
        k: int = 3
    ) -> List[ContextItem]:
        """Search for relevant coding standards."""
        if not embedding:
            return []
        
        try:
            where_filter = None
            if language and language != "unknown":
                # Match either the specific language or "general" standards
                where_filter = {
                    "$or": [
                        {"language": language},
                        {"language": "general"}
                    ]
                }
            
            results = self.standards_collection.query(
                query_embeddings=[embedding],
                n_results=k,
                where=where_filter
            )
            
            items = []
            if results and results.get("documents"):
                for i, doc in enumerate(results["documents"][0]):
                    metadata = results["metadatas"][0][i] if results.get("metadatas") else {}
                    distance = results["distances"][0][i] if results.get("distances") else 0
                    
                    items.append({
                        "content": doc,
                        "source": "coding_standard",
                        "relevance_score": 1 - distance,
                        "metadata": metadata
                    })
            
            logger.debug("Found coding standards", count=len(items))
            return items
            
        except Exception as e:
            logger.error("Failed to search standards", error=str(e))
            return []
    
    async def _search_documentation(
        self, 
        embedding: List[float],
        language: str,
        k: int = 3
    ) -> List[ContextItem]:
        """Search for relevant documentation."""
        if not embedding:
            return []
        
        try:
            results = self.docs_collection.query(
                query_embeddings=[embedding],
                n_results=k
            )
            
            items = []
            if results and results.get("documents"):
                for i, doc in enumerate(results["documents"][0]):
                    metadata = results["metadatas"][0][i] if results.get("metadatas") else {}
                    distance = results["distances"][0][i] if results.get("distances") else 0
                    
                    items.append({
                        "content": doc,
                        "source": "documentation",
                        "relevance_score": 1 - distance,
                        "metadata": metadata
                    })
            
            logger.debug("Found documentation", count=len(items))
            return items
            
        except Exception as e:
            logger.error("Failed to search documentation", error=str(e))
            return []
    
    async def _summarize_context(
        self,
        code_change: dict,
        similar_reviews: List[ContextItem],
        coding_standards: List[ContextItem],
        documentation: List[ContextItem]
    ) -> str:
        """Generate a summary of all retrieved context."""
        # Check if we have any context to summarize
        if not similar_reviews and not coding_standards and not documentation:
            return "No relevant historical context found. This appears to be a new area without prior reviews or documented standards."
        
        # Format context items for the prompt
        reviews_text = self._format_context_items(similar_reviews, "No similar past reviews found.")
        standards_text = self._format_context_items(coding_standards, "No specific coding standards found.")
        docs_text = self._format_context_items(documentation, "No relevant documentation found.")
        
        # Get code summary from analysis
        code_summary = ""
        if code_change.get("analysis"):
            code_summary = code_change["analysis"].get("summary", "")
        
        messages = self.summarize_context_prompt.format_messages(
            file_path=code_change.get("file_path", "unknown"),
            language=code_change.get("language", "unknown"),
            code_summary=code_summary or "No summary available",
            past_reviews=reviews_text,
            coding_standards=standards_text,
            documentation=docs_text
        )
        
        try:
            response = await self.llm.ainvoke(messages)
            return response.content
        except Exception as e:
            logger.error("Failed to summarize context", error=str(e))
            return "Context summarization failed."
    
    def _format_context_items(self, items: List[ContextItem], default: str) -> str:
        """Format context items for the prompt."""
        if not items:
            return default
        
        formatted = []
        for i, item in enumerate(items, 1):
            score = item.get("relevance_score", 0)
            content = item.get("content", "")[:500]  # Truncate long content
            metadata = item.get("metadata", {})
            
            meta_str = ""
            if metadata:
                meta_parts = [f"{k}: {v}" for k, v in metadata.items() if k not in ["embedding"]]
                if meta_parts:
                    meta_str = f" ({', '.join(meta_parts[:3])})"
            
            formatted.append(f"{i}. [Score: {score:.2f}]{meta_str}\n{content}")
        
        return "\n\n".join(formatted)
    
    # ==================== Storage Methods ====================
    
    async def store_review(self, review_data: dict):
        """
        Store a completed review for future retrieval.
        
        This is how the system learns from past reviews.
        
        Args:
            review_data: Dict containing:
                - code: The code that was reviewed
                - feedback: The feedback given
                - file_path: Path of the reviewed file
                - language: Programming language
                - outcome: Was feedback accepted? (optional)
        """
        self._init_collections()
        
        code = review_data.get("code", "")
        feedback = review_data.get("feedback", "")
        file_path = review_data.get("file_path", "")
        language = review_data.get("language", "unknown")
        
        # Create document to store
        document = f"File: {file_path}\n\nCode:\n{code[:2000]}\n\nFeedback:\n{feedback}"
        
        # Generate embedding
        embedding = await self._get_embedding(document)
        if not embedding:
            logger.error("Failed to generate embedding for review storage")
            return
        
        # Generate unique ID
        doc_id = hashlib.md5(f"{file_path}:{code[:500]}:{feedback[:500]}".encode()).hexdigest()
        
        # Store in collection
        try:
            self.reviews_collection.add(
                documents=[document],
                embeddings=[embedding],
                metadatas=[{
                    "file_path": file_path,
                    "language": language,
                    "stored_at": datetime.utcnow().isoformat(),
                    "outcome": review_data.get("outcome", "unknown")
                }],
                ids=[doc_id]
            )
            
            # Note: PersistentClient auto-persists, no need to call persist()
            
            logger.info("Stored review for learning", file=file_path, id=doc_id)
            
        except Exception as e:
            logger.error("Failed to store review", error=str(e))
    
    async def store_coding_standard(self, standard: dict):
        """
        Store a coding standard/guideline.
        
        Args:
            standard: Dict containing:
                - title: Standard title
                - content: The standard text
                - language: Applicable language (or "general")
                - category: e.g., "naming", "error-handling", "security"
        """
        self._init_collections()
        
        title = standard.get("title", "Untitled Standard")
        content = standard.get("content", "")
        language = standard.get("language", "general")
        category = standard.get("category", "general")
        
        document = f"# {title}\n\n{content}"
        
        embedding = await self._get_embedding(document)
        if not embedding:
            logger.error("Failed to generate embedding for standard")
            return
        
        doc_id = hashlib.md5(f"{title}:{language}:{content[:500]}".encode()).hexdigest()
        
        try:
            self.standards_collection.add(
                documents=[document],
                embeddings=[embedding],
                metadatas=[{
                    "title": title,
                    "language": language,
                    "category": category,
                    "stored_at": datetime.utcnow().isoformat()
                }],
                ids=[doc_id]
            )
            
            # Note: PersistentClient auto-persists
            logger.info("Stored coding standard", title=title, language=language)
            
        except Exception as e:
            logger.error("Failed to store standard", error=str(e))
    
    async def store_documentation(self, doc: dict):
        """
        Store documentation for retrieval.
        
        Args:
            doc: Dict containing:
                - title: Doc title
                - content: The documentation text
                - source: Where this came from (e.g., "official_docs", "wiki")
                - url: Optional URL reference
        """
        self._init_collections()
        
        title = doc.get("title", "Untitled")
        content = doc.get("content", "")
        source = doc.get("source", "unknown")
        url = doc.get("url", "")
        
        # Chunk long documents
        chunks = self._chunk_text(content, chunk_size=1500, overlap=200)
        
        for i, chunk in enumerate(chunks):
            document = f"# {title}\n\n{chunk}"
            
            embedding = await self._get_embedding(document)
            if not embedding:
                continue
            
            doc_id = hashlib.md5(f"{title}:{i}:{chunk[:200]}".encode()).hexdigest()
            
            try:
                self.docs_collection.add(
                    documents=[document],
                    embeddings=[embedding],
                    metadatas=[{
                        "title": title,
                        "source": source,
                        "url": url,
                        "chunk_index": i,
                        "total_chunks": len(chunks),
                        "stored_at": datetime.utcnow().isoformat()
                    }],
                    ids=[doc_id]
                )
            except Exception as e:
                logger.error("Failed to store doc chunk", title=title, chunk=i, error=str(e))
        
        # Note: PersistentClient auto-persists
        logger.info("Stored documentation", title=title, chunks=len(chunks))
    
    def _chunk_text(self, text: str, chunk_size: int = 1500, overlap: int = 200) -> List[str]:
        """Split text into overlapping chunks."""
        if len(text) <= chunk_size:
            return [text]
        
        chunks = []
        start = 0
        
        while start < len(text):
            end = start + chunk_size
            
            # Try to break at a natural boundary (paragraph, sentence)
            if end < len(text):
                # Look for paragraph break
                newline_pos = text.rfind('\n\n', start, end)
                if newline_pos > start + chunk_size // 2:
                    end = newline_pos
                else:
                    # Look for sentence break
                    for sep in ['. ', '.\n', '! ', '? ']:
                        sep_pos = text.rfind(sep, start, end)
                        if sep_pos > start + chunk_size // 2:
                            end = sep_pos + len(sep)
                            break
            
            chunks.append(text[start:end].strip())
            start = end - overlap
        
        return chunks
    
    # ==================== Utility Methods ====================
    
    async def seed_default_standards(self):
        """Seed the database with common coding standards."""
        default_standards = [
            {
                "title": "Python: Use Type Hints",
                "content": """Always use type hints for function parameters and return values.
                
Good:
```python
def calculate_total(items: List[Item], tax_rate: float) -> Decimal:
    ...
```

Bad:
```python
def calculate_total(items, tax_rate):
    ...
```

Type hints improve code readability, enable better IDE support, and catch bugs early with tools like mypy.""",
                "language": "python",
                "category": "typing"
            },
            {
                "title": "Python: Handle Exceptions Specifically",
                "content": """Catch specific exceptions rather than using bare `except:` or `except Exception:`.

Good:
```python
try:
    user = get_user(user_id)
except UserNotFoundError:
    return None
except DatabaseConnectionError:
    logger.error("Database unavailable")
    raise ServiceUnavailableError()
```

Bad:
```python
try:
    user = get_user(user_id)
except:
    return None  # Swallows all errors including KeyboardInterrupt
```""",
                "language": "python",
                "category": "error-handling"
            },
            {
                "title": "General: No Secrets in Code",
                "content": """Never commit secrets, API keys, passwords, or tokens to version control.

Use environment variables or secret management services instead.

Bad:
```python
API_KEY = "sk-1234567890abcdef"
```

Good:
```python
import os
API_KEY = os.environ.get("API_KEY")
```

Use tools like git-secrets or pre-commit hooks to prevent accidental commits.""",
                "language": "general",
                "category": "security"
            },
            {
                "title": "JavaScript: Use Async/Await Over Callbacks",
                "content": """Prefer async/await over callbacks and raw promises for better readability.

Good:
```javascript
async function fetchUserData(userId) {
    try {
        const user = await api.getUser(userId);
        const posts = await api.getPosts(userId);
        return { user, posts };
    } catch (error) {
        logger.error('Failed to fetch user data', error);
        throw error;
    }
}
```

Avoid callback hell and promise chains when async/await is available.""",
                "language": "javascript",
                "category": "async"
            },
            {
                "title": "General: Write Self-Documenting Code",
                "content": """Choose descriptive names for variables, functions, and classes. 
Comments should explain WHY, not WHAT.

Bad:
```python
# Increment x by 1
x = x + 1

def p(d):
    return d * 0.1
```

Good:
```python
retry_count += 1

def calculate_discount(price: Decimal) -> Decimal:
    \"\"\"Apply the standard 10% member discount.\"\"\"
    return price * MEMBER_DISCOUNT_RATE
```""",
                "language": "general",
                "category": "readability"
            }
        ]
        
        for standard in default_standards:
            await self.store_coding_standard(standard)
        
        logger.info("Seeded default coding standards", count=len(default_standards))
