# System Architecture & Technical Explanation — SmartReco / NeuroCart

This document provides a comprehensive technical overview of **SmartReco / NeuroCart**, explaining how every layer of the system is built, how data flows end-to-end, and how behavioral AI recommendations are generated using **FastAPI**, **SQLite**, **Vector RAG**, and **Mesh API** (`https://api.meshapi.ai/v1`).

---

## 1. System Overview & Architecture Diagram

```
                                  ┌───────────────────────────┐
                                  │ Admin Product Management  │
                                  └─────────────┬─────────────┘
                                                │
                                  (Dual-Write Synchronization)
                                                │
                       ┌────────────────────────┴────────────────────────┐
                       ▼                                                 ▼
             ┌───────────────────┐                             ┌───────────────────┐
             │ SQLite Database   │                             │ Vector Store      │
             │ (Products Table)  │                             │ (Dense Embeddings)│
             └───────────────────┘                             └───────────────────┘
                       ▲                                                 ▲
                       │                                                 │
  ┌────────────────────┴────────────────────┐             ┌──────────────┴──────────────┐
  │ Frontend Tracking Engine                │             │ Agentic Recommendation      │
  │ (Non-blocking tracker.js + sendBeacon)  │ ──────────> │ Engine (Mesh API Gateway)   │
  └─────────────────────────────────────────┘             └──────────────┬──────────────┘
                                                                         │
                                                                         ▼
                                                          ┌─────────────────────────────┐
                                                          │ Storefront Signal Widget,   │
                                                          │ Telemetry Stream & Digest   │
                                                          └─────────────────────────────┘
```

---

## 2. Component-by-Component Deep Dive

### A. Web Platform & API Server (`app/main.py`)
- **Framework:** FastAPI with Uvicorn.
- **Routes & Responsibilities:**
  - `GET /`: Main storefront catalog page with live category filters and hero signal widget.
  - `GET /product/{id}`: Detailed course view page with dwell time tracking.
  - `POST /api/events/batch`: Non-blocking endpoint accepting batched frontend events.
  - `GET /api/agent/live-signal`: Asynchronous polling endpoint for updating the floating "Your Signal" widget.
  - `GET /recommendations` & `POST /recommendations/refresh`: Dedicated user recommendation feed.
  - `GET /engine` & `GET /api/engine/stream`: Telemetry view showing real-time event logs and multi-model router stats.
  - `GET/POST /admin/product/*`: Admin Dual-Write CRUD operations.
  - `GET/POST /login`, `/register`, `/logout`: Authentication routes with HTTP-only cookies.
- **Global Error Handling & Compatibility:** Uses `render_template` to ensure cross-version Starlette `TemplateResponse` compatibility and `@app.exception_handler(Exception)` for persistent log tracebacks.

---

### B. Relational Database Layer (`app/database.py`)
- **Database:** SQLite (`smartreco.db`).
- **Tables & Schemas:**
  1. `users`: Stores `id`, `email`, `password_hash`, `role` (`user` | `admin`), `created_at`.
  2. `products`: Stores `id`, `title`, `acronym` (e.g. `BPR`, `AWL`), `description`, `category`, `price`, `rating`, `students_count`, `vector_id`, `updated_at`.
  3. `behavioral_events`: Stores `id`, `user_id`, `event_type` (`view`, `search`, `click`, `time_on_page`), `target_id`, `metadata_json`, `timestamp`.
  4. `recommendations`: Stores `id`, `user_id`, `narrative`, `recommended_product_ids`, `trigger_reason`, `created_at`.
- **Pre-seeding:** Initializes admin/user credentials, course catalog items, and telemetry event streams on startup.

---

### C. Vector Store & Dual-Write Manager (`app/vector_store.py`)
- **Dual-Write Mechanism:** When an admin adds, updates, or deletes a course:
  1. The record is written to the SQLite relational table.
  2. Dense vector embeddings are generated via Mesh API (`/v1/embeddings` text-embedding-3-small) or fallback vectorizer.
  3. The vector and metadata payload are stored in the vector store manager.
  4. The returned `vector_id` reference is updated in the SQL product record.
- **Semantic Retrieval:** Executes cosine similarity vector search over the product catalog, augmented with keyword matching boost for precise query relevance.

---

### D. Agentic Recommendation Engine (`app/agent.py`)
Executes an explicit 3-step reasoning workflow:

1. **Step 1: Signal Analysis:** Parses recent behavioral events into live signal pills (e.g., `Viewed · MLOps for Real Teams`, `Dwell · 3s on Agentic AI`, `Searched · "Airflow"`).
2. **Step 2: Semantic RAG Retrieval:** Converts signal pills text into a query vector and retrieves top matching catalog products from `VectorStoreManager`.
3. **Step 3: Persuasive Copy Generation (Mesh API):** Points standard OpenAI SDK to Mesh API Gateway (`https://api.meshapi.ai/v1`) using `MESH_API_KEY` (`rsk_...`) and model specified in `MESHAPI_CHAT_MODEL` (`tencent/hy3`, `openai/gpt-4o-mini`). Generates persuasive narratives connecting user curiosity directly to course benefits.
- **Caching Layer:** Includes in-memory recommendation caching based on event hashes to eliminate redundant LLM calls.

---

### E. Frontend Tracking Engine (`app/static/js/tracker.js`)
- **Non-Blocking Architecture:** Listens to user actions (page views, course clicks, search queries, page dwell duration).
- **Batching & Throttling:** Buffers events into an in-memory queue (`eventQueue`) and flushes every 3 seconds or when queue size reaches 6.
- **Beacon Transport:** Transmits payload via `navigator.sendBeacon('/api/events/batch')` or async `fetch` keepalive so page navigation is never frozen.
- **Real-Time UI Updates:** Immediately injects signal pills into the UI and triggers asynchronous agent recommendation updates.

---

### F. UI Design System & Templates (`app/static/css/style.css` & `app/templates/`)
- **Theme:** Dark mode palette (`#0b0c14`), vibrant purple gradients (`#8b5cf6`, `#6366f1`), glassmorphism cards, and pulsating green streaming dots.
- **Templates:**
  - `base.html`: Header, search bar, MeshAPI Console link, category navigation bar.
  - `catalog.html`: Hero grid, floating "Your Signal" widget, course cards with acronym badges (`BPR`, `AWL`).
  - `product.html`: Course detail view, dwell tracking, related course recommendations.
  - `recommendations.html`: Dedicated recommendation feed with observed signal stream and AI narrative.
  - `engine.html`: Live telemetry stream table (`TIME`, `USER`, `EVENT`, `DETAIL`) and Mesh API Router stats.
  - `admin.html`: Dual-write catalog management dashboard.
  - `auth.html`: User login and registration interface.

---

### G. Background Scheduler (`app/scheduler.py`)
- **Library:** `APScheduler`.
- **Functionality:** Periodically iterates over active platform users, executing the agentic recommendation engine in the background to simulate daily email/Telegram digests.

---

### H. Centralized Logging Service (`app/logger.py`)
- **Service:** Formats logs with timestamps, file names, line numbers, and log levels.
- **Outputs:** Streams to `stdout` and appends to persistent log file `smartreco.log` for debugging and observability.

---

## 3. End-to-End User Interaction Flow

```
1. USER ACTION: User searches "LangGraph" or views "Agentic Workflows".
       │
       ▼
2. FRONTEND TRACKER: tracker.js captures search/view event & renders live pill.
       │
       ▼
3. BEACON FLUSH: Batch sent asynchronously to POST /api/events/batch.
       │
       ▼
4. SQL RECORD: Event stored in behavioral_events table.
       │
       ▼
5. AGENT REASONING: SmartRecoAgent parses events -> Queries Vector Store -> Calls Mesh API Gateway.
       │
       ▼
6. UI REFRESH: Live Signal Widget displays updated persuasive copy & recommended course cards!
```
