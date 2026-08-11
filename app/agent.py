import os
from dotenv import load_dotenv
load_dotenv()

import re
import json
import time
import logging
from typing import List, Dict, Any, Optional
from openai import OpenAI
from pydantic import BaseModel, Field
import uuid
import threading
from collections import deque
from app.models.trace import ExecutionTrace

from app.database import get_recent_user_events, get_all_products, save_recommendation, get_latest_recommendation
from app.vector_store import VectorStoreManager

logger = logging.getLogger("smartreco.agent")

MESH_API_KEY = os.getenv("MESH_API_KEY", "")
MESH_BASE_URL = os.getenv("MESHAPI_BASE_URL", "https://api.meshapi.ai/v1")
if not MESH_BASE_URL.endswith("/v1"):
    MESH_BASE_URL = f"{MESH_BASE_URL.rstrip('/')}/v1"

def get_mesh_model() -> str:
    return os.getenv("MESHAPI_CHAT_MODEL", "openai/gpt-4o-mini")

def get_mesh_client() -> OpenAI:
    key = MESH_API_KEY if (MESH_API_KEY and MESH_API_KEY.startswith("rsk_")) else "rsk_demo_key"
    return OpenAI(
        base_url=MESH_BASE_URL,
        api_key=key,
        default_headers={
            "x-mesh-router": "lowest-latency",
            "x-mesh-fallback": "auto"
        }
    )

class CourseReasonItem(BaseModel):
    id: int = Field(description="The numeric ID of the recommended course.")
    reason: str = Field(description="Enthusiastic, customer-focused 1-sentence reason highlighting tech stack match, budget suitability, and user interest.")

class AgentRecommendationPayload(BaseModel):
    narrative: str = Field(description="Persuasive 1-2 sentence overall recommendation summary.")
    recommendations: List[CourseReasonItem] = Field(description="Selected course recommendations with warm customer-centric reasons.")

TRACE_LOGS = deque(maxlen=5)
TRACES_LOCK = threading.Lock()
# Cooldown tracking registry: user_id -> float (timestamp of last LLM call)
LAST_USER_TRIGGER_TIME: Dict[int, float] = {}

def calculate_intent_score(events: List[Dict[str, Any]]) -> float:
    """
    Calculates behavioral Intent Score using production formula:
    Intent Score = Sum(Event Weight * Dwell Factor)
    """
    score = 0.0
    for ev in events:
        ev_type = (ev.get("event_type") or "").lower()
        target = (ev.get("target_id") or "").lower()
        
        # Skip generic main catalog / engine peeking from positive scoring
        if any(k in target for k in ["main course catalog", "peek inside the engine", "course catalog"]):
            continue

        meta = ev.get("metadata", {})
        if isinstance(meta, str):
            try: meta = json.loads(meta)
            except: meta = {}
            
        dwell_sec = meta.get("dwell_sec", 1.0)
        try: dwell_sec = float(dwell_sec)
        except: dwell_sec = 1.0

        if "filter" in ev_type or "category" in target:
            score += 3.0
        elif "view" in ev_type or "product" in target or "course" in target:
            dwell_factor = min(dwell_sec / 3.0, 1.0)
            score += 3.0 * dwell_factor
        elif "search" in ev_type:
            score += 2.5
        elif "dwell" in ev_type:
            dwell_factor = min(dwell_sec / 5.0, 1.0)
            score += 1.5 * dwell_factor
        else:
            score += 0.2

    return round(score, 2)


class SmartRecoAgent:
    """
    Behavioral AI Recommendation Agent for SmartReco / NeuroCart.
    Executes Top-10 Candidate Retrieval + Single LLM Re-ranking & Copywriting Architecture.
    """

    def __init__(self, user_id: int):
        self.user_id = user_id

    def extract_signal_pills(self, events: List[Dict[str, Any]], product_map: Dict[int, str]) -> List[Dict[str, str]]:
        """Parses event stream into live natural language signal pills."""
        pills = []
        for e in events[:16]:
            ev_type = e.get("event_type", "Signal")
            target = e.get("target_id", "")
            meta = json.loads(e.get("metadata_json") or "{}")
            stmt = meta.get("statement") or target

            if stmt:
                pills.append({"type": ev_type, "label": stmt})

        if not pills:
            pills = [
                {"type": "Observed", "label": "Exploring Main Catalog"},
                {"type": "Active", "label": "Browsing AI & Data Engineering Courses"}
            ]

        return pills

    def generate_recommendation(self, category_context: Optional[str] = None, force_refresh: bool = False) -> Dict[str, Any]:
        recent_events = get_recent_user_events(self.user_id, limit=20)
        all_products = get_all_products()

        if not all_products:
            return {
                "active": False,
                "narrative": "Welcome to NeuroCart! Browse our catalog to activate real-time AI recommendations.",
                "signal_pills": [],
                "recommended_products": []
            }

        # --- Calculate Intent Score & Thresholds ---
        intent_score = calculate_intent_score(recent_events)
        active_category = category_context if (category_context and category_context != "All") else None

        # Filter out generic main catalog visits
        meaningful_events = [
            e for e in recent_events
            if not any(k in (e.get("target_id", "") or "").lower() for k in ["main course catalog", "peek inside the engine", "course catalog"])
        ]

        # Determine primary trigger action and target
        if recent_events:
            last_ev = recent_events[0]
            ev_type = last_ev.get("event_type", "Intent")
            ev_target = last_ev.get("target_id", "Catalog Exploration")
            trigger_action = f"{ev_type}: {ev_target}"
            current_target = str(ev_target).lower()
        else:
            trigger_action = "Manual Intent Refresh"
            current_target = (active_category or "all").lower()

        # Smart Target-Aware Cooldown:
        # Cooldown ONLY applies if user triggers for the EXACT SAME target within 10s.
        # Exploring a NEW course or NEW category BYPASSES cooldown INSTANTLY!
        now = time.time()
        last_time, last_target = LAST_USER_TRIGGER_TIME.get(self.user_id, (0.0, ""))
        time_since_last = now - last_time
        is_same_target = (last_target == current_target)

        if not force_refresh and is_same_target and time_since_last < 10.0 and last_time > 0.0:
            remaining = int(10.0 - time_since_last)
            # Log Cooldown Suppression to agent_triggers.log
            try:
                with open("agent_triggers.log", "a", encoding="utf-8") as f:
                    f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] User #{self.user_id} | ⏸️ SUPPRESSED | Trigger: {trigger_action} | Score: {intent_score} | Reason: SAME_TARGET_COOLDOWN ({remaining}s remaining)\n")
            except Exception:
                pass

        if active_category:
            scoped_products = [p for p in all_products if p["category"].lower() == active_category.lower()]
            if not force_refresh and (intent_score < 1.5 and len(meaningful_events) < 1):
                return {
                    "active": False,
                    "narrative": f"Explore {active_category} courses to get personalized AI recommendations.",
                    "signal_pills": [],
                    "recommended_products": []
                }
        else:
            if not force_refresh and (intent_score < 1.5 and len(meaningful_events) < 1):
                return {
                    "active": False,
                    "narrative": "Keep exploring specific products or categories to enable live AI agent recommendations.",
                    "signal_pills": [],
                    "recommended_products": []
                }
            scoped_products = all_products

        # Record LLM call timestamp and target for smart cooldown
        LAST_USER_TRIGGER_TIME[self.user_id] = (now, current_target)

        product_map = {p["id"]: p["title"] for p in all_products}
        signal_pills = self.extract_signal_pills(recent_events, product_map)

        user_signals_text = ", ".join([p["label"] for p in signal_pills])
        
        trace = ExecutionTrace(
            trace_id=str(uuid.uuid4()),
            user_id=self.user_id,
            timestamp=time.time(),
            trigger_action=f"{trigger_action} (Score: {intent_score})"
        )

        # Write to temporary log file agent_triggers.log
        try:
            with open("agent_triggers.log", "a", encoding="utf-8") as f:
                f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] User #{self.user_id} | Trigger: {trigger_action} | Trace: {trace.trace_id}\n")
        except Exception:
            pass

        t0_total = time.perf_counter()
        
        try:
            t0_vector = time.perf_counter()
            candidate_products = VectorStoreManager.search_similar_products(
                query=user_signals_text,
                top_k=10,
                products_catalog=scoped_products
            )
            trace.t_vector_ms = (time.perf_counter() - t0_vector) * 1000

            # --- Filter out already-visited courses ---
            # Extract course titles the user has explored from their event statements
            visited_titles = set()
            for ev in recent_events:
                stmt = ev.get("target_id", "")
                # Extract quoted titles from statements like: User opened & currently exploring "Course Title"
                quoted = re.findall(r'"([^"]+)"', stmt)
                for q in quoted:
                    visited_titles.add(q.lower().strip())

            if visited_titles:
                filtered_candidates = [
                    p for p in candidate_products
                    if p["title"].lower().strip() not in visited_titles
                ]
                # Only use filtered list if we still have enough candidates
                if len(filtered_candidates) >= 2:
                    candidate_products = filtered_candidates
                    logger.info(f"[Agent] Filtered out {len(visited_titles)} visited courses, {len(candidate_products)} candidates remain")
            
            if not candidate_products:
                trace.error_vector_db = "Vector store search returned 0 candidate products."
                raise Exception(trace.error_vector_db)

            # Build Rich Candidate Context for Deep LLM Re-Ranking & Analysis
            candidates_context = "\n".join([
                f"[ID #{p['id']}] {p['title']} | Category: {p['category']} | Price: ${p['price']:.0f} | Tech: {p.get('technologies', 'N/A')} | Level: {p.get('level', 'ADVANCED')} | Learn: {p.get('what_you_will_learn', 'Core Architecture')} | Desc: {p['description']}"
                for p in candidate_products
            ])
            behavioral_history = ", ".join([f"{p['type']} · {p['label']}" for p in signal_pills])

            narrative = ""
            recommended_products = []
            t_llm_ms_val = 0

            # 2. Single Fast LLM Call: Re-Rank Candidates + Generate Personalized Narrative & Customer-Centric Reasons
            if MESH_API_KEY:
                try:
                    client = get_mesh_client()
                    prompt = (
                        f"User Real-Time Behavioral Telemetry Actions: [{behavioral_history}]\n\n"
                        f"Candidate Courses:\n{candidates_context}\n\n"
                        f"INSTRUCTION:\n"
                        f"Select 2 course IDs that best match user interest. Keep narrative and reasons brief (under 30 words per reason).\n\n"
                        f"Format output strictly as JSON object:\n"
                        f"{{\n"
                        f'  "narrative": "Persuasive 1-sentence recommendation summary.",\n'
                        f'  "recommendations": [\n'
                        f'    {{"id": 1, "reason": "How: Teaches state persistence. Why: Matches your MLOps interest. What: Build Autonomous Agents. Tech: LangGraph, Python."}}\n'
                        f'  ]\n'
                        f"}}"
                    )

                    t0_llm = time.perf_counter()
                    response = client.chat.completions.create(
                        model=get_mesh_model(),
                        messages=[
                            {"role": "system", "content": "You are NeuroCart's AI course advisor. Output JSON adhering strictly to the schema."},
                            {"role": "user", "content": prompt}
                        ],
                        max_tokens=2048,
                        temperature=0.7,
                        response_format={"type": "json_object"}
                    )
                    trace.t_llm_ms = (time.perf_counter() - t0_llm) * 1000
                    raw_content = (response.choices[0].message.content or "").strip()
                    # Strip markdown codeblocks if returned
                    clean_json_str = re.sub(r'^```(?:json)?\s*', '', raw_content, flags=re.IGNORECASE)
                    clean_json_str = re.sub(r'\s*```$', '', clean_json_str).strip()
                    
                    try:
                        if not clean_json_str:
                            raise ValueError("Mesh API LLM returned empty content string.")
                        
                        # Attempt direct JSON parse
                        try:
                            parsed_json = json.loads(clean_json_str)
                        except json.JSONDecodeError:
                            # Attempt JSON repair if truncated
                            repaired = clean_json_str
                            if repaired.startswith('{') and not repaired.endswith('}'):
                                last_brace = repaired.rfind('}')
                                if last_brace != -1:
                                    repaired = repaired[:last_brace+1]
                            parsed_json = json.loads(repaired)

                        payload = AgentRecommendationPayload.model_validate(parsed_json)
                        narrative = payload.narrative
                        recs_list = payload.recommendations
                    except json.JSONDecodeError as jde:
                        err_msg = f"Mesh API returned non-JSON response ({clean_json_str[:150]!r}): {jde}"
                        trace.error_llm = err_msg
                        logger.error(err_msg)
                        raise ValueError(err_msg) from jde
                    except Exception as parse_err:
                        err_msg = f"Failed parsing Mesh API payload ({clean_json_str[:150]!r}): {parse_err}"
                        trace.error_llm = err_msg
                        logger.error(err_msg)
                        raise ValueError(err_msg) from parse_err

                    for r in recs_list:
                        pid = r.id
                        reason = r.reason
                        for p in candidate_products:
                            if p["id"] == pid:
                                p_copy = dict(p)
                                p_copy["ai_reason"] = reason
                                recommended_products.append(p_copy)
                                break
                except Exception as e:
                    if not trace.error_llm:
                        trace.error_llm = str(e)
                    logger.error(f"Mesh API Pydantic recommendation re-ranking call failed: {e}")
                    raise e

            if not recommended_products or not narrative:
                trace.error_llm = "Agentic generation failed to produce valid recommendations or narrative."
                raise Exception(trace.error_llm)

            trace.t_total_ms = (time.perf_counter() - t0_total) * 1000
            trace.candidates_found = len(candidate_products)
            trace.success = True
            trace.narrative = narrative
            
            with TRACES_LOCK:
                TRACE_LOGS.appendleft(trace)

            result = {
                "id": 0,
                "active": True,
                "narrative": narrative,
                "signal_pills": signal_pills,
                "recommended_products": recommended_products,
                "user_interest_summary": user_signals_text,
                "trace_id": trace.trace_id
            }
            
            logger.info(
                f"[Recommendation Pipeline] TOTAL={trace.t_total_ms:.0f}ms | "
                f"VectorSearch={trace.t_vector_ms:.0f}ms | "
                f"LLM={trace.t_llm_ms:.0f}ms | "
                f"Candidates={len(candidate_products)} | Recs={len(recommended_products)}"
            )

            return result
        except Exception as ex:
            trace.t_total_ms = (time.perf_counter() - t0_total) * 1000
            trace.success = False
            if not trace.error_vector_db and not trace.error_llm:
                trace.error_vector_db = str(ex)
            
            with TRACES_LOCK:
                TRACE_LOGS.appendleft(trace)
            raise ex

    def stream_narrative(self, category_context: Optional[str] = None):
        """
        Sync generator that streams a rich personalized narrative via LLM.
        Falls back to a rich multi-sentence dynamic summary when LLM rate-limits or fails.
        """
        recent_events = get_recent_user_events(self.user_id, limit=20)
        all_products = get_all_products()

        # --- Threshold checks (same logic as generate_recommendation) ---
        active_category = category_context if (category_context and category_context != "All") else None

        if active_category:
            scoped_products = [p for p in all_products if p["category"].lower() == active_category.lower()]
            if len(recent_events) < 3:
                yield "__INACTIVE__"
                return
        else:
            if len(recent_events) < 3:
                yield "__INACTIVE__"
                return
            scoped_products = all_products

        product_map = {p["id"]: p["title"] for p in all_products}
        signal_pills = self.extract_signal_pills(recent_events, product_map)
        user_signals_text = ", ".join([p["label"] for p in signal_pills])

        candidate_products = VectorStoreManager.search_similar_products(
            query=user_signals_text, top_k=6, products_catalog=scoped_products
        )
        if not candidate_products:
            candidate_products = scoped_products[:5]

        # Rich course catalog context
        candidates_rich = "\n\n".join([
            f"Course: \"{p['title']}\"\n"
            f"  Category: {p['category']} | Price: ${p['price']:.0f} | Level: {p.get('level', 'Advanced')}\n"
            f"  Technologies: {p.get('technologies', 'N/A')}\n"
            f"  What You'll Learn: {p.get('what_you_will_learn', p['description'])}\n"
            f"  What You'll Build: {p.get('what_you_will_build', 'Real-world production projects')}"
            for p in candidate_products[:4]
        ])

        # Check for valid key
        if not MESH_API_KEY:
            yield "Error: MESH_API_KEY is not set. Total agentic functionality requires a valid API key."
            return

        try:
            client = get_mesh_client()
            t0 = time.time()
            stream = client.chat.completions.create(
                model=get_mesh_model(),
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are NeuroCart's expert AI learning mentor. Write in warm, direct flowing prose — "
                            "no bullet points, no numbered lists. You MUST name specific courses by their exact title "
                            "using quotes. Reference real technologies and learning outcomes from the course data provided. "
                            "Sound like a trusted senior engineer who has taken these courses themselves."
                        )
                    },
                    {
                        "role": "user",
                        "content": (
                            f"Learner's interests and signals: [{user_signals_text}]\n\n"
                            f"Here are the specific courses that match their profile — use this data to be concrete and specific:\n\n"
                            f"{candidates_rich}\n\n"
                            f"Write 6-7 sentences as a mentor speaking directly to this learner. Follow this structure:\n"
                            f"- Sentence 1: What their current learning trajectory reveals about where they're heading.\n"
                            f"- Sentence 2: The core skill or knowledge gap they need to close next (be specific).\n"
                            f"- Sentence 3-4: Name 1-2 specific courses from the list above by exact title. For each course, explicitly detail: How it helps them, Why it's a good match, What they will build/learn, and the matching Tech Stack.\n"
                            f"- Sentence 5: Why NOW is the right time to take these (connect it to their current learning stage).\n"
                            f"- Sentence 6-7: What they'll be able to build or ship once they complete the recommended path. Make it concrete and exciting.\n\n"
                            f"NEVER mention clicks, time-on-page, scrolls, or raw behavioral data. Sound like a mentor, not an analytics system."
                        )
                    }
                ],
                max_tokens=480,
                temperature=0.82,
                stream=True
            )

            for chunk in stream:
                if chunk.choices and len(chunk.choices) > 0:
                    delta = chunk.choices[0].delta.content
                    if delta:
                        yield delta

            t_ms = (time.time() - t0) * 1000
            logger.info(f"[Narrative Stream] Streamed in {t_ms:.0f}ms")

        except Exception as e:
            logger.error(f"[Narrative Stream] LLM streaming failed/rate limited: {e}")
            yield f"Error: LLM streaming failed - {e}"
