# AI Code Review Agent 🤖

An intelligent, agentic code review system powered by LLMs and LangGraph. Automatically reviews pull requests, learns from feedback, and provides context-aware suggestions.

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        GitHub Webhook                           │
└─────────────────────────────────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│                      FastAPI Application                        │
│                        (app/main.py)                            │
└─────────────────────────────────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Review Orchestrator                          │
│                 (LangGraph State Machine)                       │
│                                                                 │
│   ┌──────────┐    ┌──────────┐    ┌──────────┐                │
│   │ Analyzer │ -> │ Context  │ -> │ Reviewer │                │
│   │  Agent   │    │  Agent   │    │  Agent   │                │
│   └──────────┘    └──────────┘    └──────────┘                │
│        │               │               │                        │
│        ▼               ▼               ▼                        │
│   Parse Diffs    RAG Retrieval   Generate Review               │
└─────────────────────────────────────────────────────────────────┘
                               │
              ┌────────────────┼────────────────┐
              ▼                ▼                ▼
        ┌──────────┐    ┌──────────┐    ┌──────────┐
        │ ChromaDB │    │ Postgres │    │  GitHub  │
        │ (Vector) │    │  (Data)  │    │   API    │
        └──────────┘    └──────────┘    └──────────┘
```

## 🚀 Features

- **Multi-Agent Architecture**: Specialized agents for analysis, context retrieval, and review
- **RAG-Powered Context**: Learns from past reviews and coding standards
- **LangGraph Orchestration**: Stateful, graph-based workflow management
- **GitHub Integration**: Webhook-driven automatic PR reviews
- **Docker Ready**: One-command deployment with Docker Compose
- **Extensible**: Easy to add new agents or review rules

## 📁 Project Structure

```
ai-code-review-agent/
├── app/
│   ├── agents/
│   │   ├── __init__.py
│   │   ├── analyzer.py      # Parses and analyzes code diffs
│   │   ├── context.py       # RAG-based context retrieval
│   │   ├── reviewer.py      # Generates review comments
│   │   └── orchestrator.py  # LangGraph workflow coordination
│   ├── api/
│   │   └── __init__.py
│   ├── core/
│   │   ├── __init__.py
│   │   ├── config.py        # Pydantic settings
│   │   └── logging.py       # Structured logging
│   ├── services/
│   │   ├── __init__.py
│   │   └── github_service.py # GitHub API interactions
│   ├── db/
│   │   └── __init__.py
│   ├── utils/
│   │   └── __init__.py
│   ├── __init__.py
│   └── main.py              # FastAPI application
├── tests/
├── docs/
├── scripts/
├── .env.example
├── .gitignore
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
└── README.md
```

## 🛠️ Setup

### Prerequisites

- Python 3.11+
- Docker & Docker Compose
- OpenAI API key
- GitHub Personal Access Token (or GitHub App)

### Local Development

1. **Clone and setup environment**:
   ```bash
   cd D:\ai-code-review-agent
   python -m venv venv
   venv\Scripts\activate  # Windows
   pip install -r requirements.txt
   ```

2. **Configure environment**:
   ```bash
   copy .env.example .env
   # Edit .env with your API keys
   ```

3. **Run the Backend API**:
   ```bash
   uvicorn app.main:app --reload
   ```

4. **Run the Streamlit Frontend** (in a separate terminal):
   ```bash
   streamlit run app/frontend/streamlit_app.py
   ```
   
   Access the frontend at: http://localhost:8501

### Docker Deployment

1. **Configure environment**:
   ```bash
   copy .env.example .env
   # Edit .env with your API keys
   ```

2. **Build and run**:
   ```bash
   docker-compose up --build
   ```

3. **Access**:
   - API: http://localhost:8000
   - Docs: http://localhost:8000/docs
   - pgAdmin: http://localhost:5050 (if enabled)

## 🔧 Configuration

### Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `OPENAI_API_KEY` | OpenAI API key for LLM calls | Yes |
| `GITHUB_TOKEN` | GitHub Personal Access Token | Yes* |
| `GITHUB_APP_ID` | GitHub App ID (alternative auth) | No |
| `GITHUB_WEBHOOK_SECRET` | Secret for webhook verification | Recommended |
| `DATABASE_URL` | PostgreSQL connection string | Yes |

### GitHub Webhook Setup

1. Go to your repository Settings → Webhooks
2. Add webhook:
   - Payload URL: `https://your-domain.com/webhook/github`
   - Content type: `application/json`
   - Secret: Your `GITHUB_WEBHOOK_SECRET`
   - Events: Select "Pull requests"

## 📚 Implementation Guide

### Step 1: Complete the Analyzer Agent
Start with `app/agents/analyzer.py`:
- [ ] Implement `parse_diff_hunks()` for parsing unified diffs
- [ ] Complete `_analyze_file_change()` with LLM categorization
- [ ] Add language-specific analysis logic

### Step 2: Implement RAG in Context Agent
Work on `app/agents/context.py`:
- [ ] Initialize ChromaDB collections
- [ ] Implement embedding generation
- [ ] Complete similarity search methods
- [ ] Add context summarization

### Step 3: Build Review Generation
Finish `app/agents/reviewer.py`:
- [ ] Implement `_review_file()` with LLM calls
- [ ] Add security and performance review passes
- [ ] Complete `_generate_overall_assessment()`

### Step 4: Wire Up the Orchestrator
Complete `app/agents/orchestrator.py`:
- [ ] Add conditional edges for error handling
- [ ] Implement retry logic
- [ ] Add parallel processing for multiple files

### Step 5: Cloud Deployment
- [ ] Set up AWS ECS / GCP Cloud Run / Azure Container Apps
- [ ] Configure secrets management
- [ ] Set up monitoring and logging
- [ ] Configure auto-scaling

## 🧪 Testing

```bash
# Run tests
pytest

# With coverage
pytest --cov=app tests/
```

## 🚢 Cloud Deployment Options

### AWS (ECS + Fargate)
```bash
# Build and push to ECR
aws ecr get-login-password | docker login --username AWS --password-stdin <account>.dkr.ecr.<region>.amazonaws.com
docker build -t ai-code-review .
docker tag ai-code-review:latest <account>.dkr.ecr.<region>.amazonaws.com/ai-code-review:latest
docker push <account>.dkr.ecr.<region>.amazonaws.com/ai-code-review:latest
```

### GCP (Cloud Run)
```bash
# Deploy to Cloud Run
gcloud run deploy ai-code-review \
  --image gcr.io/<project>/ai-code-review \
  --platform managed \
  --allow-unauthenticated
```

## 📈 What This Project Demonstrates

- **Agentic AI**: Multi-agent system with specialized roles
- **LangGraph**: State machine orchestration for complex workflows
- **RAG**: Retrieval-augmented generation for context-aware responses
- **Production Architecture**: Docker, async Python, structured logging
- **API Design**: RESTful endpoints, webhook handling
- **DevOps**: Containerization, environment configuration

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

## 📄 License

MIT License - feel free to use this for your portfolio!

---

**Built as a portfolio project to demonstrate AI engineering expertise.**
