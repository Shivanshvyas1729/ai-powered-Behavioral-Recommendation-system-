import os
from dotenv import load_dotenv
load_dotenv()

import math
import httpx
import logging
import time
from typing import List, Dict, Any

logger = logging.getLogger("smartreco.vector_store")

MESH_API_KEY = os.getenv("MESH_API_KEY", "")
MESH_BASE_URL = os.getenv("MESHAPI_BASE_URL", "https://api.meshapi.ai/v1")
if not MESH_BASE_URL.endswith("/v1"):
    MESH_BASE_URL = f"{MESH_BASE_URL.rstrip('/')}/v1"

# ChromaDB Persistent Storage Initialization
CHROMA_AVAILABLE = False
chroma_collection = None
COLLECTION_NAME = "smartreco_products"

try:
    import chromadb
    CHROMA_DIR = os.getenv("CHROMA_DB_DIR", "./chroma_db")
    chroma_client = chromadb.PersistentClient(path=CHROMA_DIR)
    chroma_collection = chroma_client.get_or_create_collection(
        name=COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"}
    )
    CHROMA_AVAILABLE = True
    logger.info(f"ChromaDB Vector Store active & persisting to '{CHROMA_DIR}'")
except Exception as err:
    logger.warning(f"ChromaDB initialization fallback mode: {err}")

# Fallback In-Memory cache for speed
_VECTOR_STORE: Dict[int, Dict[str, Any]] = {}



def get_embedding(text: str) -> List[float]:
    """Fetches a single dense vector embedding from Mesh API Gateway."""
    if MESH_API_KEY:
        try:
            headers = {
                "Authorization": f"Bearer {MESH_API_KEY}",
                "Content-Type": "application/json",
                "x-mesh-router": "lowest-latency",
                "x-mesh-fallback": "auto"
            }
            res = httpx.post(
                f"{MESH_BASE_URL}/embeddings",
                headers=headers,
                json={
                    "model": os.getenv("MESH_EMBEDDING_MODEL", "openai/text-embedding-3-small"),
                    "input": text
                },
                timeout=12.0
            )
            if res.status_code == 200:
                data = res.json()
                return data["data"][0]["embedding"]
            else:
                logger.error(f"Mesh API Embedding non-200 status {res.status_code}: {res.text}")
                raise Exception(f"Mesh API returned {res.status_code}")
        except Exception as e:
            logger.error(f"Mesh API embedding request failed: {e}")
            raise e
    else:
        raise Exception("MESH_API_KEY is not set.")

def get_embeddings_batch(texts: List[str]) -> List[List[float]]:
    """Fetches dense vector embeddings for a batch of texts in a SINGLE API call."""
    if not texts:
        return []
    
    if MESH_API_KEY:
        try:
            headers = {
                "Authorization": f"Bearer {MESH_API_KEY}",
                "Content-Type": "application/json",
                "x-mesh-router": "lowest-latency",
                "x-mesh-fallback": "auto"
            }
            t0 = time.time()
            res = httpx.post(
                f"{MESH_BASE_URL}/embeddings",
                headers=headers,
                json={
                    "model": os.getenv("MESH_EMBEDDING_MODEL", "openai/text-embedding-3-small"),
                    "input": texts  # Pass list directly — OpenAI-compatible batch endpoint
                },
                timeout=30.0  # Longer timeout for large batches
            )
            t1 = time.time()
            if res.status_code == 200:
                data = res.json()
                # API returns results sorted by index
                sorted_data = sorted(data["data"], key=lambda x: x["index"])
                logger.info(f"[API Latency] Batch embedding ({len(texts)} texts) completed in {(t1 - t0) * 1000:.2f} ms")
                return [item["embedding"] for item in sorted_data]
            else:
                logger.error(f"Mesh Batch Embedding non-200 status {res.status_code}: {res.text}")
                raise Exception(f"Mesh API returned {res.status_code}")
        except Exception as e:
            logger.error(f"Mesh batch embedding request failed: {e}")
            raise e
    else:
        raise Exception("MESH_API_KEY is not set.")

def cosine_similarity(vec1: List[float], vec2: List[float]) -> float:
    if not vec1 or not vec2:
        return 0.0
    dot = sum(a * b for a, b in zip(vec1, vec2))
    norm1 = math.sqrt(sum(a * a for a in vec1)) or 1.0
    norm2 = math.sqrt(sum(b * b for b in vec2)) or 1.0
    return dot / (norm1 * norm2)

class VectorStoreManager:
    """
    Dual-Write & Semantic Retrieval Manager powered by ChromaDB.
    Persists dense vectors to disk in `./chroma_db` and synchronizes SQL DB CRUD actions.
    """

    @classmethod
    def sync_product(
        cls,
        product_id: int, 
        title: str, 
        description: str, 
        category: str, 
        price: float,
        level: str = "ADVANCED",
        what_you_will_learn: str = "",
        what_you_will_build: str = "",
        technologies: str = "",
        silent: bool = False
    ) -> str:
        global chroma_collection

        # Structured Composite Chunk for Vector Embedding & RAG Search
        text_payload = (
            f"Title: {title}. Category: {category}. Level: {level}. Price: ${price:.2f}. "
            f"Description: {description}. "
            f"Technologies: {technologies}. "
            f"What You Will Learn: {what_you_will_learn}. "
            f"What You'll Build: {what_you_will_build}."
        )
        vector = get_embedding(text_payload)
        doc_id = f"product_{product_id}"

        # 1. Dual-Write to ChromaDB (Disk Persistence — only real dense embeddings, not 64-dim fallbacks)
        if CHROMA_AVAILABLE and chroma_collection and len(vector) > 64:
            try:
                chroma_collection.upsert(
                    ids=[doc_id],
                    embeddings=[vector],
                    documents=[text_payload],
                    metadatas=[{
                        "product_id": product_id,
                        "title": title,
                        "category": category,
                        "price": float(price),
                        "level": level
                    }]
                )
                if not silent:
                    logger.info(f"Product #{product_id} Dual-Written & Persisted to ChromaDB ({doc_id})")
            except Exception as e:
                logger.error(f"ChromaDB dual-write upsert failed for product #{product_id}: {e}")

        # 2. In-Memory Store Sync
        _VECTOR_STORE[product_id] = {
            "id": product_id,
            "title": title,
            "description": description,
            "category": category,
            "price": price,
            "level": level,
            "vector": vector,
            "payload": text_payload
        }

        return doc_id

    @staticmethod
    def delete_product(product_id: int):
        doc_id = f"product_{product_id}"

        # 1. Dual-Write Delete from ChromaDB
        if CHROMA_AVAILABLE and chroma_collection:
            try:
                chroma_collection.delete(ids=[doc_id])
                logger.info(f"Product #{product_id} removed from ChromaDB ({doc_id})")
            except Exception as e:
                logger.error(f"ChromaDB delete failed for product #{product_id}: {e}")

        # 2. In-Memory Store Cleanup
        if product_id in _VECTOR_STORE:
            del _VECTOR_STORE[product_id]

    @staticmethod
    def search_similar_products(query: str, top_k: int = 3, products_catalog: List[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        # --- Batch cold-start: embed ALL products in a SINGLE API call ---
        if not _VECTOR_STORE and products_catalog:
            texts = []
            products_to_sync = []
            for p in products_catalog:
                text_payload = (
                    f"Title: {p['title']}. Category: {p['category']}. Level: {p.get('level', 'ADVANCED')}. "
                    f"Price: ${float(p['price']):.2f}. Description: {p['description']}. "
                    f"Technologies: {p.get('technologies', '')}. "
                    f"What You Will Learn: {p.get('what_you_will_learn', '')}. "
                    f"What You'll Build: {p.get('what_you_will_build', '')}."
                )
                texts.append(text_payload)
                products_to_sync.append((p, text_payload))

            logger.info(f"[Batch Embed] Cold-start: embedding {len(texts)} products in 1 API call")
            vectors = get_embeddings_batch(texts)

            chroma_ids, chroma_embeddings, chroma_docs, chroma_metas = [], [], [], []
            for (p, text_payload), vector in zip(products_to_sync, vectors):
                doc_id = f"product_{p['id']}"
                _VECTOR_STORE[p["id"]] = {
                    "id": p["id"], "title": p["title"], "description": p["description"],
                    "category": p["category"], "price": float(p["price"]),
                    "level": p.get("level", "ADVANCED"), "vector": vector, "payload": text_payload
                }
                if len(vector) > 64:
                    chroma_ids.append(doc_id)
                    chroma_embeddings.append(vector)
                    chroma_docs.append(text_payload)
                    chroma_metas.append({
                        "product_id": p["id"], "title": p["title"],
                        "category": p["category"], "price": float(p["price"]),
                        "level": p.get("level", "ADVANCED")
                    })

            if CHROMA_AVAILABLE and chroma_collection and chroma_ids:
                try:
                    chroma_collection.upsert(
                        ids=chroma_ids, embeddings=chroma_embeddings,
                        documents=chroma_docs, metadatas=chroma_metas
                    )
                    logger.info(f"[Batch Embed] {len(chroma_ids)} products upserted to ChromaDB in one shot")
                except Exception as e:
                    logger.error(f"ChromaDB batch upsert failed: {e}")

        query_vec = get_embedding(query)

        catalog_map = {p["id"]: p for p in (products_catalog or [])}

        # 1. Try ChromaDB Semantic Vector Search (only if embedding dimension matches)
        if CHROMA_AVAILABLE and chroma_collection and len(query_vec) > 64:
            try:
                # Query ChromaDB collection
                results = chroma_collection.query(
                    query_embeddings=[query_vec],
                    n_results=min(top_k, len(catalog_map) or top_k)
                )
                if results and results.get("metadatas") and len(results["metadatas"][0]) > 0:
                    matched_products = []
                    for meta in results["metadatas"][0]:
                        pid = meta.get("product_id")
                        if pid:
                            if pid in _VECTOR_STORE:
                                matched_products.append(_VECTOR_STORE[pid])
                            elif pid in catalog_map:
                                matched_products.append(catalog_map[pid])
                    if matched_products:
                        return matched_products
            except Exception as e:
                logger.warning(f"ChromaDB query failed, executing fallback similarity: {e}")

        # 2. Fallback Cosine Search against _VECTOR_STORE
        scored_items = []
        for p_id, p_data in _VECTOR_STORE.items():
            sim = cosine_similarity(query_vec, p_data["vector"])
            text_lower = p_data["payload"].lower()
            query_terms = query.lower().split()
            kw_match = sum(0.15 for term in query_terms if len(term) > 2 and term in text_lower)
            
            final_score = sim + kw_match
            scored_items.append({"product": p_data, "score": final_score})

        if scored_items:
            scored_items.sort(key=lambda x: x["score"], reverse=True)
            return [item["product"] for item in scored_items[:top_k]]
        
        # 3. Last Resort: return candidates from available catalog
        return (products_catalog or [])[:top_k]
