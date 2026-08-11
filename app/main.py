import os
from dotenv import load_dotenv
load_dotenv()

import asyncio
import re
import traceback
from contextlib import asynccontextmanager
from typing import List, Dict, Any, Optional

from fastapi import FastAPI, Request, Form, Response, Cookie, HTTPException, status, Query
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
import time
import threading
import json as _json

from app.logger import logger
from app.database import (
    init_db, get_user_by_email, get_user_by_id, create_user, hash_password,
    get_all_products, get_product_by_id, insert_product, update_product_db, delete_product_db,
    record_events_batch, get_all_live_events_stream, clear_all_behavioral_events,
    get_project_curriculum_modules, get_allowed_trigger_events, set_allowed_trigger_events
)
from app.vector_store import VectorStoreManager, CHROMA_AVAILABLE, chroma_collection
from app.agent import SmartRecoAgent, TRACE_LOGS, TRACES_LOCK
from app.scheduler import start_scheduler, stop_scheduler

async def background_vector_sync():
    try:
        products = get_all_products()
        synced = 0
        for p in products:
            doc_id = f"product_{p['id']}"
            needs_sync = True
            
            if p.get("vector_id") and p["vector_id"] != "pending":
                if CHROMA_AVAILABLE and chroma_collection:
                    res = chroma_collection.get(ids=[doc_id])
                    if res and res.get('ids'):
                        # Already exists in ChromaDB, no need to re-embed
                        needs_sync = False
            
            if needs_sync:
                VectorStoreManager.sync_product(
                    product_id=p["id"],
                    title=p["title"],
                    description=p["description"],
                    category=p["category"],
                    price=float(p["price"]),
                    silent=True
                )
                synced += 1
        logger.info(f"Successfully dual-written and synced {synced}/{len(products)} products to ChromaDB.")
    except Exception as e:
        logger.warning(f"Background vector sync error: {e}")

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Initializing NeuroCart / SmartReco database...")
    init_db()
    
    # Launch background vector sync asynchronously so web server accepts traffic instantly
    task = asyncio.create_task(background_vector_sync())
    
    try:
        start_scheduler()
    except Exception as e:
        logger.warning(f"Scheduler start skipped: {e}")

    try:
        yield
    except asyncio.CancelledError:
        pass
    finally:
        task.cancel()
        try:
            stop_scheduler()
        except Exception:
            pass

app = FastAPI(title="NeuroCart / SmartReco — Behavioral AI Recommendation Agent", lifespan=lifespan)

from starlette.exceptions import HTTPException as StarletteHTTPException

@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    if exc.status_code == 404:
        accept = request.headers.get("accept", "")
        if "text/html" in accept:
            return HTMLResponse(
                content=f"""
                <!DOCTYPE html>
                <html>
                <head>
                    <title>404 Not Found — NeuroCart</title>
                    <style>
                        body {{ background: #0b0c14; color: #f3f4f6; font-family: sans-serif; padding: 2rem; text-align: center; margin-top: 10vh; }}
                        h1 {{ color: #a78bfa; font-size: 4rem; margin-bottom: 0.5rem; }}
                        p {{ color: #94a3b8; font-size: 1.1rem; margin-bottom: 2rem; }}
                        .btn {{ display: inline-block; background: #8b5cf6; color: #fff; padding: 0.8rem 1.5rem; text-decoration: none; border-radius: 8px; font-weight: 600; transition: background 0.2s; }}
                        .btn:hover {{ background: #7c3aed; }}
                    </style>
                </head>
                <body>
                    <h1>404</h1>
                    <p>Oops! We couldn't find the page or course you're looking for.</p>
                    <a href="/" class="btn">Explore Catalog</a>
                </body>
                </html>
                """,
                status_code=404
            )
    return JSONResponse({"detail": exc.detail}, status_code=exc.status_code)

# Global Exception Handler Middleware to capture and log any unhandled runtime error
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    error_trace = traceback.format_exc()
    logger.error(f"Unhandled Exception on {request.method} {request.url.path}:\n{error_trace}")
    
    # If client accepts HTML, render a detailed clean error page
    accept = request.headers.get("accept", "")
    if "text/html" in accept:
        return HTMLResponse(
            content=f"""
            <!DOCTYPE html>
            <html>
            <head>
                <title>500 Internal Server Error — SmartReco</title>
                <style>
                    body {{ background: #0b0c14; color: #f3f4f6; font-family: sans-serif; padding: 2rem; }}
                    .error-card {{ background: #161826; border: 1px solid #ef4444; border-radius: 12px; padding: 2rem; max-width: 900px; margin: 0 auto; }}
                    h1 {{ color: #ef4444; margin-top: 0; }}
                    pre {{ background: #0b0c14; padding: 1rem; border-radius: 8px; overflow-x: auto; color: #fca5a5; font-size: 0.85rem; }}
                    .btn {{ display: inline-block; background: #8b5cf6; color: #fff; padding: 0.6rem 1.2rem; text-decoration: none; border-radius: 999px; margin-top: 1rem; font-weight: 600; }}
                </style>
            </head>
            <body>
                <div class="error-card">
                    <h1>⚡ 500 Internal Server Error</h1>
                    <p>An unexpected exception occurred while processing <code>{request.method} {request.url.path}</code>.</p>
                    <p><strong>Error:</strong> <code>{str(exc)}</code></p>
                    <h3>Detailed Exception Traceback (Logged to smartreco.log):</h3>
                    <pre>{error_trace}</pre>
                    <a href="/" class="btn">&larr; Return to Home Page</a>
                </div>
            </body>
            </html>
            """,
            status_code=500
        )
    
    return JSONResponse(
        status_code=500,
        content={
            "status": "error",
            "error": str(exc),
            "path": request.url.path,
            "traceback": error_trace.splitlines()
        }
    )

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
app.mount("/static", StaticFiles(directory=os.path.join(BASE_DIR, "static")), name="static")
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))

def render_template(request: Request, name: str, context: dict, status_code: int = 200) -> HTMLResponse:
    """Helper to render templates compatibly across all Starlette/FastAPI versions."""
    ctx = {"request": request, **context}
    try:
        # Starlette 0.27+ standard signature
        return templates.TemplateResponse(request=request, name=name, context=ctx, status_code=status_code)
    except TypeError:
        # Legacy fallback
        return templates.TemplateResponse(name, ctx, status_code=status_code)

import hmac
import hashlib

def sign_user_id(user_id: str) -> str:
    secret = os.getenv("SECRET_KEY", "smartreco_secret_fallback").encode('utf-8')
    signature = hmac.new(secret, str(user_id).encode('utf-8'), hashlib.sha256).hexdigest()
    return f"{user_id}.{signature}"

def verify_user_id(cookie_val: str) -> Optional[str]:
    if not cookie_val or "." not in cookie_val:
        return None
    user_id, signature = cookie_val.split(".", 1)
    secret = os.getenv("SECRET_KEY", "smartreco_secret_fallback").encode('utf-8')
    expected_sig = hmac.new(secret, str(user_id).encode('utf-8'), hashlib.sha256).hexdigest()
    if hmac.compare_digest(signature, expected_sig):
        return user_id
    return None

def get_current_user(session_user_id: Optional[str] = Cookie(None)) -> Optional[Dict[str, Any]]:
    uid = verify_user_id(session_user_id)
    if uid:
        try:
            return get_user_by_id(int(uid))
        except (ValueError, TypeError):
            return None
    return None

def ensure_session(session_user_id: Optional[str], response: Optional[Response] = None) -> tuple[str, bool]:
    verified = verify_user_id(session_user_id)
    if verified:
        return session_user_id, False
    import random
    random_id = str(random.randint(100000, 999999999))
    try:
        uid = create_user(f"anon_{random_id}@smartreco.local", "nopass", "guest")
    except Exception:
        uid = random_id
    new_cookie = sign_user_id(str(uid))
    if response:
        response.set_cookie(key="session_user_id", value=new_cookie, max_age=31536000)
    return new_cookie, True

class EventItem(BaseModel):
    event_type: str
    target_id: Optional[str] = ""
    metadata: Optional[Dict[str, Any]] = {}
    timestamp: Optional[str] = None

class EventBatchRequest(BaseModel):
    events: List[EventItem]

# --- PLATFORM ROUTES ---

@app.get("/", response_class=HTMLResponse)
async def catalog_page(
    request: Request, 
    category: Optional[str] = Query("All"), 
    session_user_id: Optional[str] = Cookie(None)
):
    session_user_id, new_session = ensure_session(session_user_id)

    logger.info(f"Rendering catalog page instantly. Category filter: {category}")
    user = get_current_user(session_user_id)
    products = get_all_products() # Fetch ALL products so client-side filter works dynamically without blank screens!
    categories = ["All"] + sorted(list(set(p['category'] for p in products)))
    
    # Fast instant HTML render — signal widget populates asynchronously via JS
    resp = render_template(
        request=request,
        name="catalog.html",
        context={
            "user": user,
            "products": products,
            "categories": categories,
            "selected_category": category,
            "current_page": "catalog"
        }
    )
    if new_session:
        resp.set_cookie(key="session_user_id", value=session_user_id, max_age=31536000)
    return resp

@app.get("/product/{product_id}", response_class=HTMLResponse)
async def product_detail_page(product_id: int, request: Request, session_user_id: Optional[str] = Cookie(None)):
    session_user_id, new_session = ensure_session(session_user_id)

    user = get_current_user(session_user_id)
    product = get_product_by_id(product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Course not found")
        
    all_products = get_all_products()
    related_products = [p for p in all_products if p["id"] != product_id][:3]
    curriculum_modules = get_project_curriculum_modules(product)

    # Fast instant HTML render
    resp = render_template(
        request=request,
        name="product.html",
        context={
            "user": user,
            "product": product,
            "curriculum_modules": curriculum_modules,
            "related_products": related_products,
            "current_page": "catalog"
        }
    )
    if new_session:
        resp.set_cookie(key="session_user_id", value=session_user_id, max_age=31536000)
    return resp

@app.get("/recommendations", response_class=HTMLResponse)
async def recommendations_page(request: Request, session_user_id: Optional[str] = Cookie(None)):
    user = get_current_user(session_user_id)
    if not user:
        return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)

    # Fast 0ms instant HTML render — client JS populates live narrative asynchronously
    initial_products = get_all_products()[:3]
    return render_template(
        request=request,
        name="recommendations.html",
        context={
            "user": user,
            "initial_products": initial_products,
            "current_page": "recommendations"
        }
    )

@app.post("/recommendations/refresh")
async def refresh_recommendation(session_user_id: Optional[str] = Cookie(None)):
    user = get_current_user(session_user_id)
    if not user:
        return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)

    agent = SmartRecoAgent(user["id"])
    agent.generate_recommendation(force_refresh=True)
    return RedirectResponse(url="/recommendations", status_code=status.HTTP_303_SEE_OTHER)

# --- PEEK INSIDE THE ENGINE VIEW ---

@app.get("/engine", response_class=HTMLResponse)
async def engine_peek_page(request: Request, session_user_id: Optional[str] = Cookie(None)):
    user = get_current_user(session_user_id)
    live_events = get_all_live_events_stream(limit=40)
    return render_template(
        request=request,
        name="engine.html",
        context={
            "user": user,
            "live_events": live_events,
            "mesh_model": os.getenv("MESHAPI_CHAT_MODEL", "tencent/hy3"),
            "current_page": "engine"
        }
    )

@app.get("/api/engine/stream")
async def get_engine_stream_api():
    events = get_all_live_events_stream(limit=40)
    return {"events": events}

@app.post("/api/engine/clear")
async def clear_engine_stream_api():
    clear_all_behavioral_events()
    return {"status": "success", "message": "Live event stream cleared."}

# --- LIVE AGENT & EVENT TRACKING API ---

@app.post("/api/events/batch")
async def track_events_batch(batch_req: EventBatchRequest, response: Response, session_user_id: Optional[str] = Cookie(None)):
    session_user_id, _ = ensure_session(session_user_id, response)

    user = get_current_user(session_user_id)
    user_id = user["id"] if user else int(verify_user_id(session_user_id) or 0)
    
    if batch_req.events:
        events_dicts = [ev.model_dump() for ev in batch_req.events]
        record_events_batch(user_id, events_dicts)

    return {"status": "success", "processed_count": len(batch_req.events)}

@app.get("/api/agent/narrative-stream")
async def agent_narrative_stream(
    request: Request,
    category: Optional[str] = Query("All"),
    session_user_id: Optional[str] = Cookie(None)
):
    """SSE endpoint: streams a rich 6-7 sentence mentor narrative in real-time via LLM streaming."""
    session_user_id, _ = ensure_session(session_user_id)

    user = get_current_user(session_user_id)
    user_id = user["id"] if user else int(verify_user_id(session_user_id) or 2)

    loop = asyncio.get_running_loop()
    queue: asyncio.Queue = asyncio.Queue()

    def run_stream():
        """Run sync LLM streaming in a background thread, push chunks to asyncio queue."""
        try:
            agent = SmartRecoAgent(user_id)
            for chunk in agent.stream_narrative(category_context=category):
                asyncio.run_coroutine_threadsafe(queue.put(chunk), loop).result(timeout=5)
        except Exception as e:
            logger.warning(f"[Narrative SSE Thread] Error: {e}")
        finally:
            asyncio.run_coroutine_threadsafe(queue.put(None), loop).result(timeout=5)  # sentinel

    threading.Thread(target=run_stream, daemon=True).start()

    async def event_generator():
        while True:
            if await request.is_disconnected():
                break
            try:
                item = await asyncio.wait_for(queue.get(), timeout=30.0)
                if item is None:                          # stream finished
                    yield f"data: {_json.dumps({'done': True})}\n\n"
                    break
                if item == "__INACTIVE__":               # not enough signals yet
                    yield f"data: {_json.dumps({'inactive': True, 'done': True})}\n\n"
                    break
                yield f"data: {_json.dumps({'token': item})}\n\n"
            except asyncio.TimeoutError:
                yield f"data: {_json.dumps({'done': True})}\n\n"
                break

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        }
    )

@app.get("/api/agent/live-signal")
def get_live_agent_signal(response: Response, category: Optional[str] = Query(None), session_user_id: Optional[str] = Cookie(None)):
    """Returns course card recommendations only. Narrative is delivered separately via /api/agent/narrative-stream."""
    session_user_id, _ = ensure_session(session_user_id, response)

    user = get_current_user(session_user_id)
    user_id = user["id"] if user else int(verify_user_id(session_user_id) or 0)

    agent = SmartRecoAgent(user_id)
    rec_data = agent.generate_recommendation(category_context=category, force_refresh=False)
    return {
        "active": rec_data.get("active", False if rec_data.get("active") is False else True),
        "invisible": rec_data.get("invisible", False),
        "signal_pills": rec_data.get("signal_pills", []),
        "narrative": "",   # narrative comes from /api/agent/narrative-stream now
        "recommended_products": rec_data.get("recommended_products", []),
        "trace_id": rec_data.get("trace_id")
    }

# --- ADMIN DUAL-WRITE PRODUCT MANAGEMENT ROUTES ---

@app.get("/admin", response_class=HTMLResponse)
async def admin_page(request: Request, session_user_id: Optional[str] = Cookie(None)):
    user = get_current_user(session_user_id)
    if not user or user["role"] != "admin":
        return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)

    products = get_all_products()
    allowed_trigger_events = get_allowed_trigger_events()
    return render_template(
        request=request,
        name="admin.html",
        context={
            "user": user, 
            "products": products, 
            "allowed_trigger_events": allowed_trigger_events,
            "current_page": "admin"
        }
    )

@app.post("/admin/triggers/update")
async def update_admin_triggers(
    request: Request,
    session_user_id: Optional[str] = Cookie(None)
):
    user = get_current_user(session_user_id)
    if not user or user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")

    form_data = await request.form()
    allowed = form_data.getlist("allowed_triggers")
    set_allowed_trigger_events(allowed)
    return RedirectResponse(url="/admin", status_code=status.HTTP_303_SEE_OTHER)

@app.post("/admin/product/add")
async def admin_add_product(
    title: str = Form(...),
    description: str = Form(...),
    category: str = Form(...),
    price: float = Form(...),
    rating: float = Form(4.8),
    students_count: str = Form("1.0k"),
    level: str = Form("ADVANCED"),
    lectures_count: str = Form("22 lectures"),
    what_you_will_learn: str = Form(""),
    what_you_will_build: str = Form(""),
    instructor_name: str = Form("Sudhanshu"),
    instructor_exp: str = Form("4+ YEARS EXP"),
    instructor_linkedin: str = Form("https://linkedin.com"),
    technologies: str = Form("LangGraph, Keycloak, OPA, OpenMetadata, Streamlit"),
    session_user_id: Optional[str] = Cookie(None)
):
    user = get_current_user(session_user_id)
    if not user or user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")

    acronym = "".join([w[0] for w in title.split()[:3]]).upper() or "CRS"
    product_id = insert_product(
        title=title, 
        description=description, 
        category=category, 
        price=price, 
        acronym=acronym, 
        vector_id="pending",
        rating=rating,
        students_count=students_count,
        level=level,
        lectures_count=lectures_count,
        what_you_will_learn=what_you_will_learn,
        what_you_will_build=what_you_will_build,
        instructor_name=instructor_name,
        instructor_exp=instructor_exp,
        instructor_linkedin=instructor_linkedin,
        technologies=technologies
    )
    vector_id = VectorStoreManager.sync_product(
        product_id=product_id, 
        title=title, 
        description=description, 
        category=category, 
        price=price,
        level=level,
        what_you_will_learn=what_you_will_learn,
        what_you_will_build=what_you_will_build,
        technologies=technologies
    )
    update_product_db(
        product_id=product_id, 
        title=title, 
        description=description, 
        category=category, 
        price=price, 
        vector_id=vector_id,
        rating=rating,
        students_count=students_count,
        level=level,
        lectures_count=lectures_count,
        what_you_will_learn=what_you_will_learn,
        what_you_will_build=what_you_will_build,
        instructor_name=instructor_name,
        instructor_exp=instructor_exp,
        instructor_linkedin=instructor_linkedin,
        technologies=technologies
    )

    return RedirectResponse(url="/admin", status_code=status.HTTP_303_SEE_OTHER)

@app.post("/admin/product/edit/{product_id}")
async def admin_edit_product(
    product_id: int,
    title: str = Form(...),
    description: str = Form(...),
    category: str = Form(...),
    price: float = Form(...),
    rating: float = Form(4.8),
    students_count: str = Form("1.0k"),
    level: str = Form("ADVANCED"),
    lectures_count: str = Form("22 lectures"),
    what_you_will_learn: str = Form(""),
    what_you_will_build: str = Form(""),
    instructor_name: str = Form("Sudhanshu"),
    instructor_exp: str = Form("4+ YEARS EXP"),
    instructor_linkedin: str = Form("https://linkedin.com"),
    technologies: str = Form("LangGraph, Keycloak, OPA, OpenMetadata, Streamlit"),
    session_user_id: Optional[str] = Cookie(None)
):
    user = get_current_user(session_user_id)
    if not user or user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")

    # 1. Dual-Write: Sync updated vector embedding in Vector Store
    vector_id = VectorStoreManager.sync_product(
        product_id=product_id,
        title=title,
        description=description,
        category=category,
        price=price,
        level=level,
        what_you_will_learn=what_you_will_learn,
        what_you_will_build=what_you_will_build,
        technologies=technologies
    )

    # 2. Dual-Write: Update relational SQL database
    update_product_db(
        product_id=product_id,
        title=title,
        description=description,
        category=category,
        price=price,
        vector_id=vector_id,
        rating=rating,
        students_count=students_count,
        level=level,
        lectures_count=lectures_count,
        what_you_will_learn=what_you_will_learn,
        what_you_will_build=what_you_will_build,
        instructor_name=instructor_name,
        instructor_exp=instructor_exp,
        instructor_linkedin=instructor_linkedin,
        technologies=technologies
    )

    logger.info(f"Dual-Write EDIT completed for product #{product_id}: SQL & Vector DB updated.")
    return RedirectResponse(url="/admin", status_code=status.HTTP_303_SEE_OTHER)

@app.post("/admin/product/delete/{product_id}")
async def admin_delete_product(product_id: int, session_user_id: Optional[str] = Cookie(None)):
    user = get_current_user(session_user_id)
    if not user or user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")

    VectorStoreManager.delete_product(product_id)
    delete_product_db(product_id)
    logger.info(f"Dual-Write DELETE completed for product #{product_id}: Removed from SQL & Vector DB.")
    return RedirectResponse(url="/admin", status_code=status.HTTP_303_SEE_OTHER)

# --- AUTHENTICATION ROUTES ---

@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return render_template(request=request, name="auth.html", context={"mode": "login", "user": None})

@app.post("/login")
async def login_action(request: Request, response: Response, email: str = Form(...), password: str = Form(...)):
    user = get_user_by_email(email)
    if not user or user["password_hash"] != hash_password(password):
        return render_template(
            request=request,
            name="auth.html",
            context={"mode": "login", "error": "Invalid email or password", "user": None}
        )

    res = RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)
    res.set_cookie(key="session_user_id", value=sign_user_id(str(user["id"])), httponly=True)
    return res

@app.get("/register", response_class=HTMLResponse)
async def register_page(request: Request):
    return render_template(request=request, name="auth.html", context={"mode": "register", "user": None})

@app.post("/register")
async def register_action(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    role: str = Form("user")
):
    existing = get_user_by_email(email)
    if existing:
        return render_template(
            request=request,
            name="auth.html",
            context={"mode": "register", "error": "Email is already registered", "user": None}
        )

    user_id = create_user(email, hash_password(password), role=role)
    res = RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)
    res.set_cookie(key="session_user_id", value=sign_user_id(str(user_id)), httponly=True)
    return res

@app.get("/logout")
async def logout_action():
    res = RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)
    res.delete_cookie("session_user_id")
    return res

@app.get("/api/agent/traces")
async def get_agent_traces():
    """Returns the last 5 agentic execution flow traces."""
    with TRACES_LOCK:
        traces = [t.model_dump() for t in TRACE_LOGS]
    return JSONResponse({
        "traces": traces,
        "total_traces": len(traces),
        "server_time": time.time()
    })

@app.get("/api/agent/traces/{trace_id}")
async def get_agent_trace(trace_id: str):
    """Returns detailed view of a single trace."""
    with TRACES_LOCK:
        for t in TRACE_LOGS:
            if t.trace_id == trace_id:
                return JSONResponse(t.model_dump())
    raise HTTPException(status_code=404, detail="Trace not found")
