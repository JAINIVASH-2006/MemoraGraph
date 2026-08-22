# MemoraGraph

**AI-Powered Organizational Memory Retrieval using Intent-Routed Graph RAG**

MemoraGraph transforms organizational documents into a searchable knowledge system using Knowledge Graphs, Vector Retrieval, Semantic Intent Classification, Directed Edge-Routing, and LLM-powered answer generation.

---

## Final Architecture

The complete system architecture diagram can be found at [`docs/memoragraph_final_architecture.mmd`](docs/memoragraph_final_architecture.mmd).

```
User Query
    ↓
Semantic Intent Classification
    ↓
Relevant Entity / Vector Entry Points
    ↓
Directed Edge-Routing (Intent-Constrained Graph Traversal)
    ↓
Context Validation & Evidence Assembly
    ↓
LLM Generation (Grounded Answer + Sources + Citations)
```

### Key Innovation: Intent-Routed Graph RAG

Unlike standard Graph RAG which expands all neighbors from an entity, MemoraGraph first classifies the **semantic intent** of the query, then constrains graph traversal to only follow **relevant relationship types**. This reduces irrelevant context, suppresses noise, and significantly improves retrieval precision.

---

## Technology Stack

| Layer | Technology |
|-------|-----------|
| Frontend | React, TypeScript, Vite, Tailwind CSS v4 |
| Backend | Python, FastAPI, Pydantic, Uvicorn |
| Knowledge Graph | Neo4j |
| Vector Database | Qdrant |
| Relational DB | PostgreSQL |
| AI/NLP | Sentence Transformers (`BAAI/bge-small-en-v1.5`), Configurable LLM |
| Auth | JWT, Role-Based Access Control |
| Deployment | Docker, docker-compose |

---

## System Requirements

- **OS:** Windows 10/11 (with WSL 2 enabled)
- **Python:** v3.13.x
- **Node.js:** v22.x
- **npm:** v10.x
- **Docker / WSL 2:** Ubuntu distribution running WSL 2 kernel

---

## Installation & Setup

### 1. Clone & Configure

Open **PowerShell** and run:
```powershell
git clone <repository-url>
cd MemoraGraph
Copy-Item .env.example .env
# Edit .env with your configuration if needed
```

### 2. WSL Docker Startup

Since the Docker daemon runs inside WSL 2 (Ubuntu), run the following commands in PowerShell to start the daemon and spin up the database services:
```powershell
# Ensure Docker service is running inside WSL
wsl -d Ubuntu -u root -- service docker start

# Spin up database containers
wsl -d Ubuntu -- sh -c "cd /mnt/c/MemoraGraph && docker-compose up -d postgres neo4j qdrant"
```

### 3. Backend Setup

From the root `MemoraGraph\` directory:
```powershell
cd backend
python -m venv venv
.\venv\Scripts\activate
pip install -r requirements.txt
cd ..
```

### 4. Database Seeding

To seed the Postgres, Neo4j, and Qdrant databases with synthetic evaluation documents:
```powershell
.\backend\venv\Scripts\python.exe scripts\seed_data.py
```

### 5. Running the Backend Server

To start the FastAPI server:
```powershell
cd backend
..\backend\venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

### 6. Frontend Setup & Run

To build and start the React app:
```powershell
cd frontend
npm install
npm run dev
```

---

## Verification & Testing

### Running Unit and Integration Tests

To run the full Pytest test suite (covers health, graph, vector search, intent classification, and RAG):
```powershell
.\backend\venv\Scripts\python.exe -m pytest
```

### Running Academic Evaluation

To run the evaluation framework and output the metric report (Precision@1, Precision@5, PathPrecision@K, AnswerRecall, Latency):
```powershell
.\backend\venv\Scripts\python.exe scripts\evaluate.py
```

### Reproducing All Results

To run the entire clean start, port check, database seed, testing, and evaluation pipeline in one command:
```powershell
powershell -ExecutionPolicy Bypass -File scripts/run_all_tests.ps1
```

---

## Access URLs

| Service | URL |
|---------|-----|
| Frontend App | http://localhost:5173 |
| Backend Server | http://localhost:8000 |
| Swagger API Docs | http://localhost:8000/api/docs |
| ReDoc API Docs | http://localhost:8000/api/redoc |

---

## Known Limitations

1. **WSL Idle Timeout:** WSL 2 terminates the active Linux environment if no interactive shells remain open, which can stop background docker containers. The reproduction script runs a keep-alive background daemon in WSL to prevent this.
2. **API Keys:** In the absence of OpenAI/Gemini API keys, the system falls back to a deterministic Mock LLM Provider to enable local evaluation and testing without API overhead.

---

## License

Academic project. All rights reserved.
