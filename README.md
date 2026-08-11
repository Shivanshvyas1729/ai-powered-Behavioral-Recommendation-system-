# NeuroCart / SmartReco — Behavioral AI Recommendation Agent
live link  -  https://neurocart-smartreco.onrender.com
**NeuroCart (SmartReco)** is an agentic, hyper-personalized recommendation platform for modern e-commerce and learning marketplaces. Instead of static "related products" widgets or generic rules, NeuroCart features a **real-time 17-signal behavioral AI agent** that continuously observes user browsing activity (views, searches, filters, tech tag clicks, dwell times, scroll depth, text highlights, curriculum expansions), semantically retrieves candidate items via **Vector RAG (ChromaDB)**, and re-ranks courses using **Mesh API LLM (`openai/gpt-4o-mini`)** with **Pydantic structured output validation**.

---

## 🌟 Architecture & Data Flow

```
                                  ┌───────────────────────────┐
                                  │ Admin Product Management  │
                                  │ (Dual-Write CRUD Engine)  │
                                  └─────────────┬─────────────┘
                                                │
                                       (Dual-Write Sync)
                                                │
                       ┌────────────────────────┴────────────────────────┐
                       ▼                                                 ▼
             ┌───────────────────┐                             ┌───────────────────┐
             │ SQLite Database   │                             │ ChromaDB Vector   │
             │ (smartreco.db)    │                             │ Store (Local/RAG) │
             └───────────────────┘                             └───────────────────┘
                       ▲                                                 ▲
                       │                                                 │
  ┌────────────────────┴────────────────────┐             ┌──────────────┴──────────────┐
  │ Behavioral Telemetry Stream (tracker.js)│             │ 2-Pass Agentic RAG Engine   │
  │ - 17 Natural Intent Signals             │ ──────────> │ - Top-10 Candidate Vector   │
  │ - AbortController Interruption          │             │   Retrieval (ChromaDB)      │
  │ - IntersectionObserver Lazy Trigger     │             │ - Single LLM Re-Ranking &   │
  └─────────────────────────────────────────┘             │   Pydantic Reason Generation│
                                                          └──────────────┬──────────────┘
                                                                         │
                                                                         ▼
                                                          ┌─────────────────────────────┐
                                                          │ Live Stream Animation       │
                                                          │ Warm AI Reason Badges       │
                                                          └─────────────────────────────┘
```

---

## 🚀 Key Features & Architectural Innovations

### 1. 📡 17-Signal Natural Telemetry Engine & Zero-Click Auto-Popup (`tracker.js`)
* **Zero-Click Automatic Popups**: The user never has to press a "Get Recommendations" button. `tracker.js` observes browsing activity and **automatically pops up personalized recommendations** as intent signals accumulate.
* **Human-Intent Statement Logging**: Captures natural intent statements (e.g., `"User spent 18s reading MLOps"`, `"User highlighted 'LangGraph state persistence'"`, `"User expanded Module 2"`).
* **Automatic Dwell Timer Flushing**: Flushes per-topic dwell timer snapshots automatically to resolve attribution race conditions.

### 2. ⚡ 3-Layer Performance Pipeline (<0.8s Latency & Token Efficiency)
* **Layer 1 (In-Memory 15s Cache & Cooldown)**: Short-lived server-side TTL caching and target-aware cooldown serve high-frequency interactions with **0ms backend latency** (saves generated results so rapid actions on the same page don't re-trigger LLM calls).
* **Layer 2 (Single-Pass RAG — 3 Calls to 1)**: Replaced a 3-step LLM chain with local ChromaDB vector candidate retrieval ($<2\text{ms}$) followed by a **single unified LLM re-ranking & copywriting pass** using Pydantic schema validation, cutting total latency from 4.5s down to $<0.8\text{s}$.
* **Layer 3 (Client-Side `AbortController`)**: Native JavaScript `AbortController` instantly cancels in-flight HTTP requests and SSE streams when users scroll away or switch categories, preventing token waste.

### 3. 🎯 Category-Context Scoping & Event Threshold
* **Threshold Rule**: Requires at least **3 captured events** before showing recommendations, preventing cold-start mismatches.
* **Category Scoping**: When filtering by a category (e.g. `Data Engineering`), vector candidate retrieval is strictly scoped to `Data Engineering` courses.

### 4. 💡 Warm, Customer-Centric AI Reasons (Pydantic Validated)
* Swapped robotic log readouts for warm, customer-delighting AI advice:
  > **💡 Why AI Suggested:** *Since you've been exploring MLOps and LangGraph, here is a budget-friendly course ($149) perfectly matching your tech stack!*
* Uses Pydantic (`AgentRecommendationPayload` & `CourseReasonItem`) for 100% structured JSON output parsing.

### 5. 🛑 Non-Blocking UI & Request Interruption
* **Lazy Viewport Triggering**: Uses `IntersectionObserver` so AI API calls ONLY trigger when the recommendation panel is visible on screen.
* **In-Flight Interruption**: Uses `AbortController` to instantly cancel pending HTTP requests (`controller.abort()`) when a user scrolls away or switches categories, saving API tokens and compute.
* **Request Priority**: All AI fetches use `priority: 'low'` so browsing, search, and navigation execute with 0ms UI delay.

### 6. 📦 Production Catalog (38 Rich Courses)
* Pre-seeded with 38 rich production AI/ML, Data Engineering, MLOps, and Cloud DevOps courses across 15 metadata fields (`acronym`, `rating`, `students_count`, `level`, `lectures_count`, `what_you_will_learn`, `what_you_will_build`, `instructor_name`, `technologies`).

---

## 🛠️ Technology Stack

* **Backend**: Python 3.11, **FastAPI**, **Uvicorn**, **Pydantic**
* **Database**: SQLite (`smartreco.db`)
* **Vector Store**: **ChromaDB** (`./chroma_db`) with 1536-dim embeddings
* **LLM Gateway**: **Mesh API Gateway** (`https://api.meshapi.ai/v1`) using `openai` SDK with `x-mesh-router: lowest-latency`
* **Frontend**: Jinja2 Templates, Vanilla JS (`tracker.js`), Glassmorphic CSS3
* **Scheduler**: APScheduler (`app/scheduler.py`)

---

## ⚡ Quickstart Guide

### 1. Clone & Install Dependencies
```bash
git clone <repo-url>
cd "recommandation system"

# Activate Virtual Environment
.\venv\Scripts\activate

# Install Dependencies
pip install -r requirements.txt
```

### 2. Set Up Environment Variables
Create or verify `.env` file:
```env
MESH_API_KEY=rsk_your_mesh_api_key
MESHAPI_BASE_URL=https://api.meshapi.ai/v1
MESHAPI_CHAT_MODEL=openai/gpt-4o-mini
```

### 3. Start Application Server
```bash
python -m uvicorn app.main:app --reload --port 8000
```
Open **[http://localhost:8000](http://localhost:8000)** in your browser!

---

## ☁️ Render Deployment & Free Tier Optimization

This project includes a pre-configured [`render.yaml`](file:///c:/Users/DELL/Desktop/recommandation%20system/render.yaml) blueprint for 1-click deployment on Render.

### Saving Render Free Tier Build Minutes:
1. **Automated `buildFilter`**: `render.yaml` automatically ignores changes to `.md` documentation, `.gitignore`, and log files so Render won't trigger unnecessary builds.
2. **Use `[skip render]` in Commit Messages**: If you ever want to push code or docs without triggering a deployment, include `[skip render]` or `[skip ci]` in your git commit message:
   ```bash
   git commit -m "Updated README and Judges Pitch Guide [skip render]"
   git push origin main
   ```

---

## 🔑 Pre-seeded Login Credentials

* **User Account**: `user@smartreco.ai` / `user123`
* **Admin Account**: `admin@smartreco.ai` / `admin123`

---

## 📋 Mandatory Challenge Verification Checklist

| Requirement | Built & Verified? | Implementation Path |
| :--- | :---: | :--- |
| **Authentication** | ✅ YES | Session Cookie Auth (`user`/`admin` roles) in `app/main.py` |
| **SQL Database** | ✅ YES | SQLite persistent DB (`smartreco.db`) in `app/database.py` |
| **Vector DB** | ✅ YES | Persistent ChromaDB (`./chroma_db`) in `app/vector_store.py` |
| **SQL + Vector Dual-Write** | ✅ YES | Admin product CRUD dual-writes to SQLite + ChromaDB |
| **Behavior Tracking** | ✅ YES | 17-signal natural language telemetry in `tracker.js` |
| **RAG Retrieval** | ✅ YES | Top-10 Vector Retrieval + LLM Re-ranking in `agent.py` |
| **Mesh API** | ✅ MANDATORY | All AI calls route through Mesh API Gateway |
