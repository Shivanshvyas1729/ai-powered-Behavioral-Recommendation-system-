# Project Reference Guide — SmartReco: Behavioral AI Recommendation Agent

This reference guide synthesizes the official hackathon challenge specifications, system architecture, automated check setup, and **MeshAPI** (`https://developers.meshapi.ai`) integration patterns tailored for **SmartReco**.

> 🚨 **Workflow Notice:** The token issue in the automated checks has been resolved. Download the latest workflow file from `https://careerapi-production.krishnaik.in/api/ci/hackathons/smartreco-build-challenge-2026/workflow.yml` and place it at `.github/workflows/smartreco-checks.yml`.

---

## 1. Executive Summary & Challenge Brief

**SmartReco** is an agentic recommendation platform for an online learning/product marketplace. Instead of static "related products" widgets, SmartReco features an agentic backend recommendation system: a continuous AI observer that tracks user behavior (clicks, views, searches, dwell time), reasons over behavioral patterns, semantically retrieves matching catalog items, and generates personalized, persuasive recommendations that update dynamically as user actions change.

### The End-to-End Story
1. **User Exploration:** User browses courses, searches terms, clicks items, and spends time on specific pages.
2. **Behavioral Tracking:** Every action is tracked asynchronously and non-blockingly on the frontend.
3. **Agent Reasoning & RAG Retrieval:** The AI agent analyzes aggregated activity, queries the vector database for relevant catalog products, and reasons about why these match the user's intent.
4. **Persuasive Messaging:** The agent generates a tailored narrative explaining *why* these courses matter to the user, followed by specific product recommendations.
5. **Dynamic UI & Proactive Delivery:** Recommendations display on the platform UI and refresh with new behavior. Proactive daily digests can be sent via Email/Telegram.

---

## 2. System Architecture & Requirements Breakdown

```
                                  ┌───────────────────────────┐
                                  │ Admin Product Management  │
                                  └─────────────┬─────────────┘
                                                │
                                       (Dual-Write Sync)
                                                │
                       ┌────────────────────────┴────────────────────────┐
                       ▼                                                 ▼
             ┌───────────────────┐                             ┌───────────────────┐
             │ SQL Database      │                             │ Vector Store /    │
             │ (SQLite / Postgres)│                             │ MeshAPI Managed RAG│
             └───────────────────┘                             └───────────────────┘
                       ▲                                                 ▲
                       │                                                 │
  ┌────────────────────┴────────────────────┐             ┌──────────────┴──────────────┐
  │ Behavioral Event Tracking API           │             │ Agentic Recommendation      │
  │ (Non-blocking batched frontend JS)      │ ──────────> │ Engine (MeshAPI LLM + RAG)  │
  └─────────────────────────────────────────┘             └──────────────┬──────────────┘
                                                                         │
                                                                         ▼
                                                          ┌─────────────────────────────┐
                                                          │ Dynamic Frontend Display &  │
                                                          │ Proactive Email / Telegram  │
                                                          └─────────────────────────────┘
```

### Core Requirements
1. **Platform Foundation:** Web application built with Python (Flask/FastAPI), email/password login, SQLite/PostgreSQL database, Jinja2 templates + JS frontend, and two user roles (`user` & `admin`).
2. **Product Management with Dual-Write:** Admin CRUD actions for products must write synchronously/consistently to both the relational SQL database and a vector database (e.g. Chroma, FAISS, Pinecone, Qdrant, or MeshAPI Managed RAG).
3. **Non-Blocking Behavioral Event Tracking:** Efficient frontend event capture (page views, searches, clicks, time spent) using batching, throttling, and non-blocking transports (`navigator.sendBeacon` or async batched `/api/events/batch`).
4. **Agentic Recommendation Engine:** Backend agent consuming user behavior, executing RAG semantic search over the vector store to retrieve grounded products, and generating persuasive copy.
5. **Efficiency & Production Thinking:** Intelligent LLM call triggers (throttling/debounce, change detection, caching) to prevent firing LLM calls on every raw user event.

### Highlighted Bonus Features ⭐
- **Structured Agent Framework:** LangGraph workflow nodes (Analyze activity -> Decide retrieval -> Evaluate retrieval quality -> Refine -> Generate copy).
- **Scheduled Proactive Delivery:** Background scheduler (APScheduler / Celery Beat) sending daily personalized recommendation digests via Email or Telegram.
- **Observability:** LangSmith tracing for end-to-end agent workflow monitoring.
- **Retrieval Polish:** Advanced RAG techniques (re-ranking, metadata filtering, chunking optimization).

---

## 3. Useful Mesh API Integration & Capabilities

All LLM/AI calls in SmartReco **must** go through **Mesh API** (`https://api.meshapi.ai/v1`). Mesh API is an OpenAI-compatible gateway providing single-key (`rsk_...`) access to 1000+ models.

### A. Quickstart & Gateway Setup
```python
import os
from openai import OpenAI

# Initialize standard OpenAI client pointing to Mesh API
client = OpenAI(
    base_url="https://api.meshapi.ai/v1",
    api_key=os.getenv("MESH_API_KEY")  # Starts with rsk_
)

# Chat completion via Mesh API
response = client.chat.completions.create(
    model="openai/gpt-4o",  # Provider/Model syntax
    messages=[
        {"role": "system", "content": "You are a persuasive recommendation agent for SmartReco."},
        {"role": "user", "content": "User viewed agentic AI courses twice and searched for 'LangChain'."}
    ]
)
print(response.choices[0].message.content)
```

---

### B. Mesh API Features Tailored for SmartReco

| Mesh API Feature | Endpoint / Mechanism | Primary Use Case in SmartReco |
| :--- | :--- | :--- |
| **Managed RAG (`/v1/files`)** | `POST /v1/files`<br>`POST /v1/files/search` | Can serve as the project's vector store for dual-write catalog sync and semantic search without setting up external vector infrastructure. |
| **Mesh Memory API (`/v1/memories`)** | `POST /v1/memories`<br>`Header: x-mem-id` | Automatically inject per-user behavioral facts, guardrails, and preferences into LLM recommendation calls without bloating system prompts manually. |
| **Model Tiering & Auto-Routing** | `POST /v1/auto-router/router-select` | Route high-frequency activity parsing to fast/cheap models (`openai/gpt-4o-mini`), and persuasive narrative generation to smart models (`openai/gpt-4o` or `anthropic/claude-3.5-sonnet`). |
| **Embeddings API (`/v1/embeddings`)** | `POST /v1/embeddings` | Unified embedding generation across 44+ embedding models if storing vectors in Chroma, Pinecone, FAISS, or Qdrant. |
| **Prompt Templates API (`/v1/templates`)** | `POST /v1/templates` | Manage versioned persuasive copy templates directly on Mesh dashboard with variable substitution. |
| **Batch API (`/v1/batch`)** | `POST /v1/batch` | Offload scheduled daily email/Telegram digest recommendation generation to batch jobs at 50% cost reduction. |
| **Content Moderation (`/v1/moderations`)** | `POST /v1/moderations` | Screen search queries and generated persuasive recommendations for safety and prompt injection. |
| **Response Caching** | Gateway header controls | Cache identical recommendation queries to avoid redundant LLM invocations. |
| **Spend Caps & Monitoring** | `GET /v1/usage` | Enforce hard spend caps per key to protect against run-away tracking calls. |

---

### C. Specific Mesh API Code Snippets for SmartReco

#### 1. Dual-Write & Retrieval via Mesh Managed RAG (`/v1/files`)
Mesh provides a managed RAG service where product catalog files or JSON documents are uploaded, automatically embedded, and semantically searched with metadata filtering.

```python
import httpx

API = "https://api.meshapi.ai/v1"
HEADERS = {"Authorization": f"Bearer {os.getenv('MESH_API_KEY')}", "Content-Type": "application/json"}

# Dual-Write: Upload Product Catalog Document to Mesh RAG
def sync_product_to_mesh_rag(product_data: dict):
    init_res = httpx.post(f"{API}/files", headers=HEADERS, json={
        "file_name": f"product_{product_data['id']}.json",
        "mime_type": "application/json",
        "embed": True,
        "metadata": {"category": product_data["category"], "price": str(product_data["price"])}
    }).json()
    
    # Upload binary content to signed URL
    httpx.put(init_res["signed_url"], content=str(product_data).encode("utf-8"), headers={"Content-Type": "application/json"})
    return init_res["file_id"]

# Semantic Search for Products matching user intent
def retrieve_products_mesh_rag(user_intent_query: str, category_filter: str = None):
    payload = {"query": user_intent_query, "top_k": 5}
    if category_filter:
        payload["filter"] = {"category": category_filter}
    
    search_res = httpx.post(f"{API}/files/search", headers=HEADERS, json=payload).json()
    return search_res.get("results", [])
```

#### 2. Automatic Context Injection via Mesh Memory API (`x-mem-id`)
Store behavioral signals as `facts` under a user's memory slug (`mem_user_{id}`). At recommendation time, passing `x-mem-id: mem_user_{id}` automatically retrieves and prepends relevant behavioral facts to the prompt.

```python
import httpx

# 1. Initialize Memory Bucket for User (if not created)
def create_user_memory(user_id: int):
    httpx.post(f"{API}/memories", headers=HEADERS, json={
        "slug": f"mem_user_{user_id}",
        "name": f"User {user_id} Behavior Memory",
        "description": "Stores user browsing preferences and activity facts."
    })

# 2. Store Tracked Behavioral Signal as a Memory Fact
def record_behavior_fact(user_id: int, activity_summary: str):
    httpx.post(f"{API}/memories/mem_user_{user_id}/items", headers=HEADERS, json={
        "item_type": "fact",
        "content": activity_summary  # e.g., "User viewed Advanced Agentic AI 3 times and spent 240 seconds"
    })

# 3. Generate Persuasive Copy with Attached Memory Header
def generate_recommendation_with_memory(user_id: int, prompt_text: str):
    headers_with_mem = HEADERS.copy()
    headers_with_mem["x-mem-id"] = f"mem_user_{user_id}"
    
    res = httpx.post(f"{API}/chat/completions", headers=headers_with_mem, json={
        "model": "openai/gpt-4o",
        "messages": [
            {"role": "system", "content": "You are SmartReco AI. Generate a short, persuasive recommendation narrative based on the user's recent facts."},
            {"role": "user", "content": prompt_text}
        ]
    }).json()
    
    return res["choices"][0]["message"]["content"]
```

---

## 4. Data Schemas & Event Tracking Specifications

### SQL Relational Database Schemas

```sql
-- Users Table
CREATE TABLE users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    role VARCHAR(50) DEFAULT 'user', -- 'user' or 'admin'
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Products Table
CREATE TABLE products (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title VARCHAR(255) NOT NULL,
    description TEXT NOT NULL,
    category VARCHAR(100) NOT NULL,
    price DECIMAL(10, 2) NOT NULL,
    vector_id VARCHAR(255), -- Reference ID in vector store / Mesh RAG file_id
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Behavioral Events Table
CREATE TABLE behavioral_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    event_type VARCHAR(50) NOT NULL, -- 'view', 'search', 'click', 'dwell_time'
    target_id VARCHAR(255), -- product_id or search_query
    metadata_json TEXT, -- extra context like dwell duration in seconds
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id)
);

-- Stored Recommendations Table
CREATE TABLE recommendations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    narrative TEXT NOT NULL, -- AI-generated persuasive message
    recommended_product_ids TEXT NOT NULL, -- JSON array of product IDs
    trigger_reason VARCHAR(255), -- e.g., 'heavy_search_interest'
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id)
);
```

### Frontend Event Tracking Strategy
- **Batching & Throttling:** Buffer events in JavaScript memory (`eventQueue`) and flush every 5 seconds or when buffer reaches 10 events.
- **Beacon API Transport:** Use `navigator.sendBeacon('/api/events/batch', data)` or async `fetch` calls so page navigation is never interrupted.

---

## 5. Automated CI/CD Setup & Repository Checklist

### GitHub Repository Setup Requirements
1. **Source Code:** Complete Python project free of syntax errors.
2. **`requirements.txt` / `pyproject.toml`:** Must list:
   - Web framework (`flask` or `fastapi`)
   - LLM client library (`openai` or `httpx` for Mesh API)
3. **`README.md`:** Explaining project architecture, feature breakdown, setup steps, and implemented bonus features.
4. **`.gitignore`:** Must include `.env` (secrets must never be committed).
5. **GitHub Actions Workflow File:** Located at `.github/workflows/smartreco-checks.yml`, downloaded from:
   `https://careerapi-production.krishnaik.in/api/ci/hackathons/smartreco-build-challenge-2026/workflow.yml`

### GitHub Repository Secrets Required (Settings → Secrets and variables → Actions)
- **`MESH_API_KEY`:** Mandatory Mesh API Key (starts with `rsk_`).
- **`SUBMISSION_TOKEN`:** Token shown on hackathon dashboard registration.

### Evaluation Automated Checks Summary
- **Critical Checks (Must Pass):** Syntax validation across all `.py` files; presence of web framework & LLM client dependencies in `requirements.txt`.
- **Advisory Checks:** Valid `.gitignore` ignoring `.env`, presence of `README.md`, absence of hardcoded keys in repo.
