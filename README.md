<div align="center">

# 🤖 AI Code Review Agent

[![Python 3.11+](https://img.shields.io/badge/Python-3.11+-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-009688?style=for-the-badge&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![LangGraph](https://img.shields.io/badge/LangGraph-FF6B6B?style=for-the-badge&logo=langchain&logoColor=white)](https://langchain.com)
[![Docker](https://img.shields.io/badge/Docker-2496ED?style=for-the-badge&logo=docker&logoColor=white)](https://docker.com)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg?style=for-the-badge)](https://opensource.org/licenses/MIT)

**An intelligent, agentic code review system powered by LLMs and LangGraph.**

*Automatically reviews pull requests, learns from feedback, and provides context-aware suggestions.*

[Features](#-features) •
[Quick Start](#-quick-start) •
[Architecture](#-architecture) •
[Configuration](#-configuration) •
[Deployment](#-deployment)

</div>

---

## ✨ Features

<table>
<tr>
<td width="50%">

### 🧠 Intelligent Analysis
- **Multi-Agent Architecture** — Specialized agents for analysis, context retrieval, and review generation
- **RAG-Powered Context** — Learns from past reviews and coding standards using vector search
- **Smart File Detection** — Automatically identifies and reviews code files (Python, JavaScript, TypeScript, Go, Rust, and more)

</td>
<td width="50%">

### ⚡ Production Ready
- **LangGraph Orchestration** — Stateful, graph-based workflow management
- **GitHub Integration** — Webhook-driven automatic PR reviews
- **Docker Ready** — One-command deployment with Docker Compose
- **Extensible Design** — Easy to add new agents or review rules

</td>
</tr>
</table>

---

## 🚀 Quick Start

### Prerequisites

- Python 3.11+
- Docker & Docker Compose (optional)
- OpenAI API key
- GitHub Personal Access Token

### Installation

```bash
# Clone the repository
git clone https://github.com/MitraKin/ai-code-review-agent.git
cd ai-code-review-agent

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Linux/macOS
# venv\Scripts\activate   # Windows

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your API keys
```

### Running the Application

<table>
<tr>
<td width="50%">

#### 🖥️ Backend API

```bash
uvicorn app.main:app --reload
```
Access API docs at: http://localhost:8000/docs

</td>
<td width="50%">

#### 🎨 Streamlit Frontend

```bash
streamlit run app/frontend/streamlit_app.py
```
Access frontend at: http://localhost:8501

</td>
</tr>
</table>

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        GitHub Webhook                           │
└─────────────────────────────────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│                      FastAPI Application                        │
└─────────────────────────────────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Review Orchestrator                          │
│                 (LangGraph State Machine)                       │
│                                                                 │
│   ┌──────────┐    ┌──────────┐    ┌──────────┐                │
│   │ Analyzer │───▶│ Context  │───▶│ Reviewer │                │
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

### 📁 Project Structure

```
ai-code-review-agent/
├── 📂 app/
│   ├── 📂 agents/
│   │   ├── analyzer.py      # Parses and analyzes code diffs
│   │   ├── context.py       # RAG-based context retrieval
│   │   ├── reviewer.py      # Generates review comments
│   │   └── orchestrator.py  # LangGraph workflow coordination
│   ├── 📂 core/
│   │   ├── config.py        # Pydantic settings
│   │   └── logging.py       # Structured logging
│   ├── 📂 services/
│   │   └── github_service.py # GitHub API interactions
│   ├── 📂 frontend/
│   │   └── streamlit_app.py  # Streamlit UI
│   └── main.py              # FastAPI application
├── 📂 tests/                # Test suite
├── 🐳 Dockerfile
├── 🐳 docker-compose.yml
├── 📋 requirements.txt
└── 📖 README.md
```

---

## 🔧 Configuration

### Environment Variables

| Variable | Description | Required |
|:---------|:------------|:--------:|
| `OPENAI_API_KEY` | OpenAI API key for LLM calls | ✅ |
| `GITHUB_TOKEN` | GitHub Personal Access Token | ✅ |
| `GITHUB_APP_ID` | GitHub App ID (alternative auth) | ❌ |
| `GITHUB_WEBHOOK_SECRET` | Secret for webhook verification | ⚠️ |
| `DATABASE_URL` | PostgreSQL connection string | ✅ |

### GitHub Webhook Setup

1. Navigate to **Repository Settings → Webhooks**
2. Click **Add webhook** and configure:
   - **Payload URL:** `https://your-domain.com/webhook/github`
   - **Content type:** `application/json`
   - **Secret:** Your `GITHUB_WEBHOOK_SECRET`
   - **Events:** Select `Pull requests`

---

## 🐳 Deployment

### Docker Compose (Recommended)

```bash
# Configure environment
cp .env.example .env
# Edit .env with your API keys

# Build and run
docker-compose up --build
```

**Access Points:**
- 🌐 API: http://localhost:8000
- 📚 Docs: http://localhost:8000/docs
- 🗄️ pgAdmin: http://localhost:5050

### Cloud Deployment

<details>
<summary><b>☁️ AWS (ECS + Fargate)</b></summary>

```bash
# Build and push to ECR
aws ecr get-login-password | docker login --username AWS --password-stdin <account>.dkr.ecr.<region>.amazonaws.com
docker build -t ai-code-review .
docker tag ai-code-review:latest <account>.dkr.ecr.<region>.amazonaws.com/ai-code-review:latest
docker push <account>.dkr.ecr.<region>.amazonaws.com/ai-code-review:latest
```

</details>

<details>
<summary><b>☁️ GCP (Cloud Run)</b></summary>

```bash
# Deploy to Cloud Run
gcloud run deploy ai-code-review \
  --image gcr.io/<project>/ai-code-review \
  --platform managed \
  --allow-unauthenticated
```

</details>

---

## 🧪 Testing

```bash
# Run all tests
pytest

# Run with coverage report
pytest --cov=app tests/

# Run specific test file
pytest tests/test_analyzer.py -v
```

---

## 💡 Key Technologies

<table>
<tr>
<td align="center" width="20%">
<img src="https://raw.githubusercontent.com/devicons/devicon/master/icons/python/python-original.svg" width="48" height="48" alt="Python" />
<br><b>Python</b>
<br><sub>Core Language</sub>
</td>
<td align="center" width="20%">
<img src="https://raw.githubusercontent.com/devicons/devicon/master/icons/fastapi/fastapi-original.svg" width="48" height="48" alt="FastAPI" />
<br><b>FastAPI</b>
<br><sub>API Framework</sub>
</td>
<td align="center" width="20%">
<img src="https://raw.githubusercontent.com/devicons/devicon/master/icons/docker/docker-original.svg" width="48" height="48" alt="Docker" />
<br><b>Docker</b>
<br><sub>Containerization</sub>
</td>
<td align="center" width="20%">
<img src="https://raw.githubusercontent.com/devicons/devicon/master/icons/postgresql/postgresql-original.svg" width="48" height="48" alt="PostgreSQL" />
<br><b>PostgreSQL</b>
<br><sub>Database</sub>
</td>
<td align="center" width="20%">
<img src="https://raw.githubusercontent.com/devicons/devicon/master/icons/github/github-original.svg" width="48" height="48" alt="GitHub" />
<br><b>GitHub</b>
<br><sub>Integration</sub>
</td>
</tr>
</table>

**Additional:** LangGraph • LangChain • OpenAI GPT-4 • ChromaDB • Streamlit • Pydantic

---

## 🤝 Contributing

Contributions are welcome! Here's how you can help:

1. 🍴 Fork the repository
2. 🌿 Create a feature branch (`git checkout -b feature/amazing-feature`)
3. 💻 Make your changes
4. ✅ Run tests (`pytest`)
5. 📝 Commit your changes (`git commit -m 'Add amazing feature'`)
6. 🚀 Push to the branch (`git push origin feature/amazing-feature`)
7. 🔃 Open a Pull Request

---

## 📄 License

This project is licensed under the **MIT License** - see the [LICENSE](LICENSE) file for details.

---

<div align="center">

**⭐ Star this repo if you find it helpful!**

Made with ❤️ by [MitraKin](https://github.com/MitraKin)

</div>
