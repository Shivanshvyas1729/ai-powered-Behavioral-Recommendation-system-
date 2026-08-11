# NeuroCart / SmartReco — Behavioral AI Recommendation Agent

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

### 1. 📡 17-Signal Natural Behavioral Telemetry Engine (`tracker.js`)
* Real-time intent statement logging (e.g., `"User spent 18s reading MLOps"`, `"User highlighted 'LangGraph state persistence'"`, `"User expanded Module 2"`).
* Automatic cross-topic dwell time snapshot flushing to prevent attribution bugs.
* Scroll depth tracking (`25%`, `50%`, `75%`, `90%`) restricted to course detail pages.

### 2. ⚡ 2-Pass RAG Architecture (Top-10 Retrieval + LLM Re-ranking)
* **Pass 1 (Vector Search)**: Queries **ChromaDB (`./chroma_db`)** using candidate user signals to retrieve the Top 10 matching courses.
* **Pass 2 (Single Mesh API Call)**: Passes the 10 candidate courses + full behavioral actions to Mesh API (`openai/gpt-4o-mini`) to re-rank the top 2-3 matches and generate personalized narrative copy.

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
