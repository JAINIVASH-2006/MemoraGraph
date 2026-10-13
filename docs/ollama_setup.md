# MemoraGraph – Local LLM Setup with Ollama

> **Phase**: Phase 1 complete (integration prepared).  
> **Phase 2** (pull & run Qwen3 4B) should be started **only when ≥ 8 GB RAM is available**.

---

## Overview

MemoraGraph supports four LLM providers:

| Provider | Env value | Requires API key? |
|---|---|---|
| OpenAI | `openai` | ✅ |
| Google Gemini | `google` | ✅ |
| Anthropic Claude | `anthropic` | ✅ |
| **Ollama (local)** | **`ollama`** | ❌ |

Switching to Ollama replaces cloud API calls with a local inference server running on your machine.

---

## Architecture

```
Frontend → FastAPI Backend
         → Intent Classification
         → Qdrant Vector Retrieval
         → Neo4j Directional Graph Traversal
         → Context Validation
         → LLM Generation   ←── Ollama (local) / Gemini / OpenAI
```

When `LLM_PROVIDER=ollama`, the `OllamaProvider` inside
`backend/app/llm/provider.py` sends requests to `OLLAMA_BASE_URL/api/chat`
using the Ollama REST API.

---

## Phase 1: Files Changed (already done)

| File | Change |
|---|---|
| `backend/app/config.py` | Added `ollama_base_url` setting |
| `backend/app/llm/provider.py` | `OllamaProvider` class + factory updated |
| `backend/app/api/health.py` | Ollama added to `/api/health` as optional service |
| `docker-compose.yml` | `ollama` service, `ollama_data` volume, `OLLAMA_BASE_URL` env var |
| `.env` | `OLLAMA_BASE_URL=http://localhost:11434` documented |
| `.env.example` | Same |

---

## Phase 2: Start Ollama and Pull Qwen3 4B

> WARNING: Qwen3 4B (Q4 quantized) needs ~4 GB RAM free.
> Verify with Task Manager before proceeding.

### Option A: Native (Windows)

1. **Install Ollama**
   Download from https://ollama.com/download and run the installer.

2. **Pull the model**
   ```powershell
   ollama pull qwen3:4b
   ```

3. **Verify it runs**
   ```powershell
   ollama run qwen3:4b "Hello, what is MemoraGraph?"
   ```

4. **Update `.env`**
   ```env
   LLM_PROVIDER=ollama
   LLM_MODEL=qwen3:4b
   LLM_API_KEY=
   OLLAMA_BASE_URL=http://localhost:11434
   ```

5. **Restart the backend**
   ```powershell
   docker compose restart backend
   ```

6. **Test**
   ```powershell
   curl http://localhost:8000/api/health
   # "ollama": {"status": "up", "optional": true}
   ```

---

### Option B: Dockerized Ollama (all-in-one)

The `docker-compose.yml` already includes the Ollama service.

```powershell
# Start all services including Ollama
docker compose up -d

# Pull the model inside the container
docker exec memoragraph-ollama-1 ollama pull qwen3:4b

# Verify
docker exec memoragraph-ollama-1 ollama list
```

The backend will automatically reach Ollama at `http://ollama:11434`
(Docker internal hostname set via `OLLAMA_BASE_URL`).

---

## Recommended Models (by RAM budget)

| Model | RAM needed | Command |
|---|---|---|
| Qwen3 1.7B | ~2 GB | `ollama pull qwen3:1.7b` |
| **Qwen3 4B** (recommended) | ~4 GB | `ollama pull qwen3:4b` |
| Llama3.2 3B | ~3 GB | `ollama pull llama3.2:3b` |
| Mistral 7B | ~6 GB | `ollama pull mistral:7b` |
| Qwen3 8B | ~6 GB | `ollama pull qwen3:8b` |

---

## Switching Back to Gemini/OpenAI

```env
LLM_PROVIDER=google
LLM_API_KEY=<your-key>
LLM_MODEL=gemini-3.6-flash
```

Then restart the backend. No code changes needed.

---

## Troubleshooting

| Problem | Fix |
|---|---|
| `ollama: unavailable` in health | Ollama not running — OK when using cloud providers |
| OOM / model crashes | Use Qwen3 1.7B or close other apps |
| Slow first inference | Model loading on cold start — normal |
| JSON mode issues | Qwen3 supports `format: json` natively |
