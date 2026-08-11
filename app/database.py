import sqlite3
import json
import hashlib
import os
from typing import List, Dict, Optional, Any

DB_PATH = os.getenv("SQLITE_DB_PATH", "smartreco.db")

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def hash_password(password: str) -> str:
    salt = "smartreco_salt_2026"
    return hashlib.sha256((password + salt).encode('utf-8')).hexdigest()

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()

    # 1. Users Table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        email VARCHAR(255) UNIQUE NOT NULL,
        password_hash VARCHAR(255) NOT NULL,
        role VARCHAR(50) DEFAULT 'user',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')

    # 2. Products Table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS products (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title VARCHAR(255) NOT NULL,
        acronym VARCHAR(10) NOT NULL,
        description TEXT NOT NULL,
        category VARCHAR(100) NOT NULL,
        price DECIMAL(10, 2) NOT NULL,
        rating DECIMAL(3, 1) DEFAULT 4.8,
        students_count VARCHAR(20) DEFAULT '2.4k',
        vector_id VARCHAR(255),
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')

    # Ensure schema has all advanced detail columns if upgrading
    cursor.execute("PRAGMA table_info(products)")
    columns = [row[1] for row in cursor.fetchall()]
    if "acronym" not in columns:
        cursor.execute("ALTER TABLE products ADD COLUMN acronym VARCHAR(10) DEFAULT 'CRS'")
    if "rating" not in columns:
        cursor.execute("ALTER TABLE products ADD COLUMN rating DECIMAL(3, 1) DEFAULT 4.8")
    if "students_count" not in columns:
        cursor.execute("ALTER TABLE products ADD COLUMN students_count VARCHAR(20) DEFAULT '2.4k'")
    if "level" not in columns:
        cursor.execute("ALTER TABLE products ADD COLUMN level VARCHAR(50) DEFAULT 'ADVANCED'")
    if "lectures_count" not in columns:
        cursor.execute("ALTER TABLE products ADD COLUMN lectures_count VARCHAR(50) DEFAULT '22 lectures'")
    if "what_you_will_learn" not in columns:
        cursor.execute("ALTER TABLE products ADD COLUMN what_you_will_learn TEXT DEFAULT ''")
    if "what_you_will_build" not in columns:
        cursor.execute("ALTER TABLE products ADD COLUMN what_you_will_build TEXT DEFAULT ''")
    if "instructor_name" not in columns:
        cursor.execute("ALTER TABLE products ADD COLUMN instructor_name VARCHAR(100) DEFAULT 'Sudhanshu'")
    if "instructor_exp" not in columns:
        cursor.execute("ALTER TABLE products ADD COLUMN instructor_exp VARCHAR(50) DEFAULT '4+ YEARS EXP'")
    if "instructor_linkedin" not in columns:
        cursor.execute("ALTER TABLE products ADD COLUMN instructor_linkedin VARCHAR(255) DEFAULT 'https://linkedin.com'")
    if "technologies" not in columns:
        cursor.execute("ALTER TABLE products ADD COLUMN technologies VARCHAR(255) DEFAULT 'LangGraph, Keycloak, OPA, OpenMetadata, Streamlit'")
    if "curriculum" not in columns:
        cursor.execute("ALTER TABLE products ADD COLUMN curriculum TEXT DEFAULT ''")

    # 3. System Settings Table (Admin Trigger Controls & System Config)
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS system_settings (
        setting_key VARCHAR(100) PRIMARY KEY,
        setting_value TEXT NOT NULL,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')

    # Seed default allowed trigger events if not set
    default_triggers = json.dumps(["Filter", "Viewed", "Searched", "Dwell", "CTA", "Clicked", "Tech"])
    cursor.execute(
        "INSERT OR IGNORE INTO system_settings (setting_key, setting_value) VALUES ('allowed_trigger_events', ?)",
        (default_triggers,)
    )

    # 4. Behavioral Events Table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS behavioral_events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        event_type VARCHAR(50) NOT NULL,
        target_id VARCHAR(255),
        metadata_json TEXT,
        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(id)
    )
    ''')

    # 5. Recommendations Table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS recommendations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        narrative TEXT NOT NULL,
        recommended_product_ids TEXT NOT NULL,
        trigger_reason VARCHAR(255),
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(id)
    )
    ''')

    conn.commit()

    # Seed Admin & Default Users (Guaranteed initialization)
    cursor.execute(
        "INSERT OR IGNORE INTO users (id, email, password_hash, role) VALUES (?, ?, ?, ?)",
        (1, "admin@smartreco.ai", hash_password("admin123"), "admin")
    )
    cursor.execute(
        "INSERT OR IGNORE INTO users (id, email, password_hash, role) VALUES (?, ?, ?, ?)",
        (2, "user@smartreco.ai", hash_password("user123"), "user")
    )
    cursor.execute(
        "INSERT OR IGNORE INTO users (id, email, password_hash, role) VALUES (?, ?, ?, ?)",
        (3, "mia.r@smartreco.ai", hash_password("user123"), "user")
    )
    cursor.execute(
        "INSERT OR IGNORE INTO users (id, email, password_hash, role) VALUES (?, ?, ?, ?)",
        (4, "priya.r@smartreco.ai", hash_password("user123"), "user")
    )
    conn.commit()

    # Seed 38 Products matching NeuroCart Production Catalog with 9 Distinct Domain Mentors
    cursor.execute("SELECT COUNT(DISTINCT instructor_name) FROM products")
    distinct_instructors = cursor.fetchone()[0]
    if cursor.execute("SELECT COUNT(*) FROM products").fetchone()[0] < 38 or distinct_instructors < 8:
        # Clear old seed to ensure complete 38 catalog populates with diverse 9 mentors
        cursor.execute("DELETE FROM products")
        
        initial_products = [
            # 1-8: Core AI/ML Products
            ("Building Production RAG Systems", "BPR", "Ship retrieval that actually holds up under real traffic. Master vector indexing, chunking strategies, and hybrid search.", "Generative AI", 189.00, 4.8, "3.2k", "ADVANCED", "22 lectures", "Vector DB indexing, hybrid retrieval, prompt compression, guardrails", "Production-grade RAG pipeline with ChromaDB and Mesh API", "Sudhanshu Kumar", "10+ YEARS EXP", "https://www.linkedin.com/in/sudhanshu-kumar-b79657155/", "LangGraph, Keycloak, OPA, OpenMetadata, Streamlit", "vec_bpr_01"),
            ("Agentic Workflows with LangGraph", "AWL", "Compose reliable multi-step agents without the chaos. Handle state persistence, human-in-the-loop, and cyclic graph control.", "Agentic AI", 219.00, 4.9, "2.2k", "INTERMEDIATE", "18 lectures", "StateGraph flow, memory state persistence, checkpointing, multi-agent dispatch", "Autonomous Research & Coding Agent with LangGraph", "Sudhanshu Kumar", "10+ YEARS EXP", "https://www.linkedin.com/in/sudhanshu-kumar-b79657155/", "LangGraph, Python, Tavily, FastAPI", "vec_awl_02"),
            ("MLOps for Real Teams", "MRT", "The pipeline, review and rollout habits mature ML orgs share. CI/CD for models, artifact registries, and automated testing.", "MLOps", 179.00, 4.7, "1.8k", "ADVANCED", "26 lectures", "Model registry, MLflow, DVC versioning, automated model deployment pipelines", "End-to-end MLOps pipeline on GitHub Actions", "Sunny Savita", "8+ YEARS EXP", "https://www.linkedin.com/in/sunnysavita/", "MLflow, Docker, DVC, Airflow, Prometheus", "vec_mrt_03"),
            ("Data Engineering with Airflow & Spark", "DEA", "Batch pipelines that survive schema drift and 3am reruns. PySpark transformations, DAG dependency resolution, and data quality checks.", "Data Engineering", 199.00, 4.8, "2.9k", "INTERMEDIATE", "30 lectures", "PySpark optimization, Airflow DAG design, Great Expectations validation", "Scalable ETL pipeline processing 100M+ records", "Shivan Kumar", "8+ YEARS EXP", "https://www.linkedin.com/in/shivan-kumar/", "Apache Airflow, PySpark, PostgreSQL, Docker", "vec_dea_04"),
            ("Prompt Engineering to Production", "PEP", "Go from clever prompt to reliable, tested, versioned feature. Systematic evaluation, few-shot optimization, and JSON schema outputs.", "Generative AI", 149.00, 4.5, "4.1k", "BEGINNER", "14 lectures", "Few-shot techniques, Pydantic structured output, prompt evaluation frameworks", "Production prompt management dashboard", "Krish Naik", "12+ YEARS EXP", "https://www.linkedin.com/in/naikkrish/", "Pydantic, OpenAI API, Mesh API, Streamlit", "vec_pep_05"),
            ("Agentic AI Bootcamp", "AAB", "Twelve weeks from 'wraps a prompt' to shipping real agents. Tool calling, browser subagents, memory architectures, and safety guardrails.", "Agentic AI", 499.00, 4.9, "0.9k", "ADVANCED", "45 lectures", "Tool execution, planning algorithms, subagent delegation, vector memory", "Full-stack Agentic AI enterprise assistant platform", "Krish Naik", "12+ YEARS EXP", "https://www.linkedin.com/in/naikkrish/", "LangGraph, CrewAI, AutoGen, ChromaDB, FastAPI", "vec_aab_06"),
            ("Evaluating LLM Applications", "ELA", "Stop shipping vibes — measure what your LLM apps actually do. Automated LLM-as-a-judge, hallucination metrics, and regression testing.", "MLOps", 149.00, 4.8, "1.5k", "INTERMEDIATE", "16 lectures", "RAG Triad metrics, Ragas evaluation framework, LLM-as-a-judge benchmarking", "Automated LLM continuous evaluation pipeline", "Ayush Singh", "6+ YEARS EXP", "https://www.linkedin.com/in/ayush-singh/", "Ragas, TruLens, Langfuse, Python", "vec_ela_07"),
            ("Cloud & DevOps for AI Workloads", "CDE", "Infrastructure, GPU clusters, and deployment pipelines for AI. Terraform provisioning, Kubernetes autoscaling, and vLLM serving.", "Cloud & DevOps", 229.00, 4.7, "1.4k", "ADVANCED", "24 lectures", "Kubernetes GPU scheduling, vLLM deployment, Terraform infrastructure code", "Auto-scaling LLM inference API cluster on AWS EKS", "Bapuji Vignesh", "7+ YEARS EXP", "https://www.linkedin.com/in/bapuji-vignesh/", "Kubernetes, Docker, Terraform, vLLM, AWS", "vec_cde_08"),

            # 9-18: Advanced AI & Data Science Courses
            ("Fine-Tuning LLMs with Unsloth & LLaMA-3", "FTL", "Superfast LoRA and QLoRA fine-tuning for custom domain LLMs. 5x faster training with 80% less VRAM usage.", "Generative AI", 249.00, 4.9, "1.9k", "ADVANCED", "20 lectures", "Unsloth optimization, QLoRA quantization, dataset curation, HuggingFace Hub", "Domain-adapted financial LLM fine-tuned on LLaMA-3 8B", "Sunny Savita", "8+ YEARS EXP", "https://www.linkedin.com/in/sunnysavita/", "Unsloth, PyTorch, HuggingFace, CUDA, Weights & Biases", "vec_ftl_09"),
            ("Multi-Agent Orchestration with AutoGen & CrewAI", "MAO", "Build collaborative multi-agent teams with role hierarchy, tool sharing, and task delegation.", "Agentic AI", 269.00, 4.8, "2.1k", "INTERMEDIATE", "22 lectures", "AutoGen conversational patterns, CrewAI task delegation, memory sharing", "Automated Software Development Crew with PM, Coder, and QA agents", "Sudhanshu Kumar", "10+ YEARS EXP", "https://www.linkedin.com/in/sudhanshu-kumar-b79657155/", "AutoGen, CrewAI, Python, LangChain", "vec_mao_10"),
            ("Feature Stores & Data Flywheels with Feast", "FSF", "Centralize feature engineering for real-time and batch ML models. Point-in-time joins and online low-latency retrieval.", "Data Engineering", 189.00, 4.7, "1.3k", "ADVANCED", "19 lectures", "Feast feature registry, Redis online store, Snowflake offline store, point-in-time correctness", "Real-time fraud detection feature store pipeline", "Shivan Kumar", "8+ YEARS EXP", "https://www.linkedin.com/in/shivan-kumar/", "Feast, Redis, Snowflake, PySpark", "vec_fsf_11"),
            ("Vector DB Deep Dive & Hybrid Search", "VDD", "Master vector indexing algorithms (HNSW, IVF, Flat) and combine BM25 sparse keyword search with dense embeddings.", "Generative AI", 179.00, 4.8, "2.8k", "INTERMEDIATE", "18 lectures", "HNSW tuning, Reciprocal Rank Fusion (RRF), hybrid search indexing, Qdrant/ChromaDB", "Ultra-fast hybrid enterprise search engine", "Rishabh Mishra", "6+ YEARS EXP", "https://www.linkedin.com/in/rishabh-mishra/", "ChromaDB, Qdrant, BM25, Python, FastEmbed", "vec_vdd_12"),
            ("LLM Observability with Langfuse & Arize", "LOA", "Trace prompt executions, monitor latency, calculate cost token metrics, and catch production LLM drift.", "MLOps", 159.00, 4.6, "1.7k", "INTERMEDIATE", "15 lectures", "Tracing open-telemetry spans, token cost calculation, latency breakdown, drift alerts", "Full-stack LLM observability dashboard", "Ayush Singh", "6+ YEARS EXP", "https://www.linkedin.com/in/ayush-singh/", "Langfuse, OpenTelemetry, Arize Phoenix, Grafana", "vec_loa_13"),
            ("Kubernetes for AI & GPU Workloads", "KAI", "Orchestrate multi-GPU training jobs and inference deployments with KServe, Ray, and NVIDIA GPU operator.", "Cloud & DevOps", 259.00, 4.9, "1.1k", "ADVANCED", "28 lectures", "NVIDIA GPU Operator, KServe autoscaling, Ray Cluster orchestration, Prometheus metrics", "Production Kubernetes GPU cluster for LLM serving", "Bapuji Vignesh", "7+ YEARS EXP", "https://www.linkedin.com/in/bapuji-vignesh/", "Kubernetes, Ray, KServe, Helm, NVIDIA CUDA", "vec_kai_14"),
            ("Multimodal AI & Vision Language Models", "MVL", "Build applications powered by GPT-4 Vision, LLaVA, and CLIP. Visual Q&A, document extraction, and image embeddings.", "Generative AI", 239.00, 4.8, "1.6k", "ADVANCED", "21 lectures", "CLIP visual embeddings, LLaVA fine-tuning, OCR-free document parsing", "Multimodal visual catalog search & image Q&A engine", "Nitish Singh", "9+ YEARS EXP", "https://www.linkedin.com/in/nitish-singh/", "PyTorch, CLIP, LLaVA, OpenCV, FastAPI", "vec_mvl_15"),
            ("Graph Neural Networks for Recommendation Engines", "GNN", "Model user-item interaction graphs using PyTorch Geometric and GraphSAGE for hyper-personalized recommendations.", "Data Science", 219.00, 4.7, "1.2k", "ADVANCED", "25 lectures", "PyTorch Geometric, GraphSAGE embeddings, link prediction, node classification", "Graph-based e-commerce recommendation system", "Sunny Savita", "8+ YEARS EXP", "https://www.linkedin.com/in/sunnysavita/", "PyTorch Geometric, NetworkX, DGL, Scikit-Learn", "vec_gnn_16"),
            ("AI Security, Guardrails & Red Teaming", "ASG", "Protect LLMs against prompt injection, jailbreaks, data leakage, and toxic outputs using NeMo Guardrails and Llama Guard.", "AI Security", 199.00, 4.9, "2.4k", "INTERMEDIATE", "20 lectures", "NeMo Guardrails, Llama Guard evaluation, prompt injection defenses, OWASP top 10 for LLMs", "Hardened enterprise LLM API gateway with security guardrails", "Ankit Sharma", "7+ YEARS EXP", "https://www.linkedin.com/in/ankit-sharma/", "NeMo Guardrails, Llama Guard, Presidio, FastAPI", "vec_asg_17"),
            ("Real-Time Data Streaming with Kafka & Flink", "RDS", "Stream processing architectures for real-time analytics and AI feature calculation using Apache Kafka and Flink.", "Data Engineering", 229.00, 4.8, "2.0k", "ADVANCED", "27 lectures", "Kafka event streaming, Flink windowed aggregations, Schema Registry, Kafka Connect", "Real-time user behavior analytics engine", "Shivan Kumar", "8+ YEARS EXP", "https://www.linkedin.com/in/shivan-kumar/", "Apache Kafka, Apache Flink, Schema Registry, Java/Python", "vec_rds_18"),

            # 19-28: Specialized AI & Systems Engineering Courses
            ("DSPy: Systemic Prompt Optimization & Pipelines", "DSP", "Stop writing manual prompts. Compile Declarative Language Models with automatic prompt optimization using DSPy.", "Generative AI", 169.00, 4.9, "1.5k", "INTERMEDIATE", "16 lectures", "DSPy signatures, teleprompters, BootstrapFewShot optimization, pipeline evaluation", "Automated DSPy reasoning pipeline for complex QA", "Ayush Singh", "6+ YEARS EXP", "https://www.linkedin.com/in/ayush-singh/", "DSPy, Python, Mesh API, OpenAI API", "vec_dsp_19"),
            ("Autonomous Coding Agents & Function Calling", "ACA", "Build AI agents capable of editing codebases, executing terminal commands, running tests, and opening GitHub PRs.", "Agentic AI", 289.00, 4.9, "1.8k", "ADVANCED", "32 lectures", "AST code parsing, terminal command execution, sandboxed Docker execution, function calling", "Autonomous AI Pair Programming Agent CLI", "Ayush Singh", "6+ YEARS EXP", "https://www.linkedin.com/in/ayush-singh/", "Python, Docker, Git, OpenAI Function Calling", "vec_aca_20"),
            ("Model Distillation & Quantization (GGML/vLLM)", "MDQ", "Compress 70B models down to 8B with minimal accuracy loss using AWQ, GPTQ, GGUF, and Knowledge Distillation.", "MLOps", 209.00, 4.7, "1.3k", "ADVANCED", "22 lectures", "AWQ quantization, GGUF conversion, llama.cpp integration, knowledge distillation loss", "Ultra-fast low-memory LLM deployment package", "Rishabh Mishra", "6+ YEARS EXP", "https://www.linkedin.com/in/rishabh-mishra/", "vLLM, llama.cpp, AutoAWQ, PyTorch", "vec_mdq_21"),
            ("Terraform & Infrastructure as Code for Machine Learning", "TAC", "Automate AWS, GCP, and Azure cloud resources for ML infrastructure with modular Terraform scripts.", "Cloud & DevOps", 189.00, 4.6, "1.5k", "INTERMEDIATE", "18 lectures", "Terraform state management, AWS S3/EC2/EKS provisioning, IAM permissions, CI/CD integration", "Automated cloud ML platform infrastructure deployment", "Bapuji Vignesh", "7+ YEARS EXP", "https://www.linkedin.com/in/bapuji-vignesh/", "Terraform, AWS, GCP, GitHub Actions", "vec_tac_22"),
            ("AI Ethics, Governance & Model Auditing", "AEG", "Frameworks for bias mitigation, explainable AI (SHAP/LIME), compliance with EU AI Act, and model auditing.", "AI Security", 139.00, 4.5, "1.0k", "BEGINNER", "14 lectures", "SHAP/LIME interpretability, EU AI Act compliance checklist, bias detection tools", "AI model compliance & fairness audit suite", "Ankit Sharma", "7+ YEARS EXP", "https://www.linkedin.com/in/ankit-sharma/", "SHAP, LIME, Fairlearn, Python", "vec_aeg_23"),
            ("PyTorch 2.0 Distributed Training at Scale", "PDT", "Scale model training across dozens of GPUs using torch.compile, FSDP (Fully Sharded Data Parallel), and DeepSpeed.", "Generative AI", 279.00, 4.8, "1.2k", "ADVANCED", "29 lectures", "torch.compile, DeepSpeed ZeRO-3, PyTorch FSDP, multi-node GPU cluster setup", "Distributed pre-training pipeline for LLMs", "Nitish Singh", "9+ YEARS EXP", "https://www.linkedin.com/in/nitish-singh/", "PyTorch 2.0, DeepSpeed, CUDA, NCCL", "vec_pdt_24"),
            ("Snowflake & Databricks Lakehouse Architecture", "SDL", "Design enterprise data lakes and delta lake tables combining SQL analytics with ML workloads.", "Data Engineering", 249.00, 4.8, "2.3k", "INTERMEDIATE", "25 lectures", "Delta Lake, dbt transformations, Snowflake Snowpark, Medallion Architecture (Bronze/Silver/Gold)", "Enterprise Lakehouse data warehouse", "Shivan Kumar", "8+ YEARS EXP", "https://www.linkedin.com/in/shivan-kumar/", "Databricks, Snowflake, dbt, SQL, PySpark", "vec_sdl_25"),
            ("Semantic Cache & Cost Optimization for LLMs", "SCC", "Cut your LLM API costs by up to 80% using Redis semantic caching, prompt truncation, and response batching.", "MLOps", 149.00, 4.9, "2.6k", "BEGINNER", "15 lectures", "Redis Vector Similarity Search (VSS) caching, exact vs semantic cache, token cost metrics", "High-performance LLM caching API middleware", "Rishabh Mishra", "6+ YEARS EXP", "https://www.linkedin.com/in/rishabh-mishra/", "Redis, GPTCache, Python, FastAPI", "vec_scc_26"),
            ("Building Search Engines with Elasticsearch & Hybrid Vector", "SEH", "Combine BM25 text relevance search with dense vector embeddings using Elasticsearch 8.x and Kibana.", "Data Science", 199.00, 4.7, "1.9k", "INTERMEDIATE", "21 lectures", "Elasticsearch dense vector fields, RRF hybrid scoring, Kibana dashboard analysis", "Production-grade e-commerce enterprise search engine", "Sunny Savita", "8+ YEARS EXP", "https://www.linkedin.com/in/sunnysavita/", "Elasticsearch, Kibana, Python, Docker", "vec_seh_27"),
            ("RAG Evaluation with Ragas & TruLens", "RER", "Quantify faithfulness, answer relevance, and context recall in your RAG pipeline using continuous evaluation tools.", "Generative AI", 159.00, 4.8, "1.8k", "INTERMEDIATE", "16 lectures", "Context relevance metrics, ground truth generation, TruLens feedback functions", "Automated RAG quality benchmarking suit", "Krish Naik", "12+ YEARS EXP", "https://www.linkedin.com/in/naikkrish/", "Ragas, TruLens, Python, Streamlit", "vec_rer_28"),

            # 29-38: Next-Gen Enterprise AI Courses
            ("Deploying Deep Learning on Edge & Embedded Devices", "DLE", "Optimize PyTorch models for mobile and edge deployment using ONNX Runtime, TensorRT, and CoreML.", "Cloud & DevOps", 239.00, 4.7, "0.9k", "ADVANCED", "22 lectures", "ONNX model conversion, TensorRT optimization, INT8 quantization, edge deployment", "Real-time edge computer vision application", "Bapuji Vignesh", "7+ YEARS EXP", "https://www.linkedin.com/in/bapuji-vignesh/", "ONNX, TensorRT, OpenCV, C++/Python", "vec_dle_29"),
            ("Reinforcement Learning from Human Feedback (RLHF)", "RLH", "Align LLM models with human preferences using PPO, DPO (Direct Preference Optimization), and TRL.", "Generative AI", 319.00, 4.9, "1.0k", "ADVANCED", "32 lectures", "Reward model training, DPO alignment, PPO policy optimization, TRL library", "Human preference-aligned assistant LLM", "Nitish Singh", "9+ YEARS EXP", "https://www.linkedin.com/in/nitish-singh/", "PyTorch, HuggingFace TRL, WandB, CUDA", "vec_rlh_30"),
            ("Enterprise Knowledge Graphs & Graph RAG", "EKG", "Supercharge RAG with Neo4j knowledge graphs to represent complex relational domain entities.", "Data Engineering", 229.00, 4.8, "1.4k", "ADVANCED", "24 lectures", "Neo4j Cypher queries, entity extraction, Graph RAG indexing, LangChain Neo4j integration", "Enterprise Graph RAG system for medical & legal domain", "Shivan Kumar", "8+ YEARS EXP", "https://www.linkedin.com/in/shivan-kumar/", "Neo4j, Cypher, Python, LangChain", "vec_ekg_31"),
            ("AI Agent Tool Use & API Integration Masterclass", "ATM", "Teach LLMs to interact cleanly with REST APIs, OpenAPI specs, and external databases.", "Agentic AI", 199.00, 4.7, "2.2k", "BEGINNER", "18 lectures", "OpenAPI spec parsing, dynamic tool generation, JSON schema validation, error handling", "Universal API Assistant Agent", "Krish Naik", "12+ YEARS EXP", "https://www.linkedin.com/in/naikkrish/", "Python, Pydantic, FastAPI, OpenAI Tools API", "vec_atm_32"),
            ("Trino & Iceberg Open Data Lakehouse", "TOD", "Build open-table format data lakes using Apache Iceberg, Apache Hive metastore, and Trino query engine.", "Data Engineering", 219.00, 4.6, "1.1k", "ADVANCED", "23 lectures", "Apache Iceberg table specs, Trino distributed SQL query optimization, MinIO S3 storage", "High-performance open lakehouse platform", "Shivan Kumar", "8+ YEARS EXP", "https://www.linkedin.com/in/shivan-kumar/", "Trino, Apache Iceberg, MinIO, Docker", "vec_tod_33"),
            ("Synthetic Data Generation for ML & Privacy", "SDG", "Generate realistic synthetic datasets while preserving user privacy using SDV and CTGAN.", "MLOps", 179.00, 4.7, "1.3k", "INTERMEDIATE", "17 lectures", "CTGAN synthetic generation, differential privacy, correlation validation", "Privacy-safe synthetic dataset generator", "Sunny Savita", "8+ YEARS EXP", "https://www.linkedin.com/in/sunnysavita/", "SDV, CTGAN, PyTorch, Pandas", "vec_sdg_34"),
            ("Voice AI & Real-Time Speech Agents with Whisper", "VSA", "Build sub-second latency conversational voice agents using OpenAI Whisper, ElevenLabs, and WebSockets.", "Generative AI", 249.00, 4.9, "1.7k", "INTERMEDIATE", "21 lectures", "Whisper streaming STT, ElevenLabs TTS, WebSocket bidirectional streaming, VAD detection", "Real-time AI voice phone agent", "Rishabh Mishra", "6+ YEARS EXP", "https://www.linkedin.com/in/rishabh-mishra/", "Whisper, WebSockets, ElevenLabs, Python", "vec_vsa_35"),
            ("ML System Architecture & System Design", "MSA", "Prepare for senior AI engineer interviews and design large-scale recommendation, search, and LLM architectures.", "MLOps", 299.00, 4.9, "3.1k", "ADVANCED", "35 lectures", "Latency SLAs, candidate generation + re-ranking, load balancing, caching strategies", "Complete ML System Design blueprint collection", "Sudhanshu Kumar", "10+ YEARS EXP", "https://www.linkedin.com/in/sudhanshu-kumar-b79657155/", "System Architecture, UML, Mermaid, System Design", "vec_msa_36"),
            ("Serverless AI Deployments on AWS Lambda & Modal", "SAD", "Deploy Python ML workloads and LLM functions with sub-second cold starts using Modal and AWS Lambda.", "Cloud & DevOps", 169.00, 4.8, "1.9k", "BEGINNER", "16 lectures", "Modal GPU functions, AWS Lambda container images, API Gateway integration", "Serverless image generation & text analysis API", "Bapuji Vignesh", "7+ YEARS EXP", "https://www.linkedin.com/in/bapuji-vignesh/", "Modal, AWS Lambda, Python, Docker", "vec_sad_37"),
            ("Zero Trust Security for AI Microservices & APIs", "ZTS", "Secure your AI microservices using OAuth2, OIDC, Keycloak authentication, and Open Policy Agent (OPA).", "AI Security", 209.00, 4.8, "1.4k", "ADVANCED", "20 lectures", "Keycloak OIDC integration, OPA policy enforcement, JWT validation, microservice security", "Zero Trust AI API gateway with fine-grained authorization", "Ankit Sharma", "7+ YEARS EXP", "https://www.linkedin.com/in/ankit-sharma/", "Keycloak, OPA, FastAPI, JWT, Docker", "vec_zts_38")
        ]
        
        cursor.executemany(
            "INSERT INTO products (title, acronym, description, category, price, rating, students_count, level, lectures_count, what_you_will_learn, what_you_will_build, instructor_name, instructor_exp, instructor_linkedin, technologies, vector_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            initial_products
        )
        conn.commit()

    # Pre-seed Initial Behavioral Events for Telemetry Stream
    cursor.execute("SELECT COUNT(*) FROM behavioral_events")
    if cursor.fetchone()[0] == 0:
        initial_events = [
            (2, "time_on_page", "96s · Building Production RAG Systems", json.dumps({"duration_seconds": 96})),
            (3, "viewed_product", "Data Engineering with Airflow & Spark", json.dumps({"text": "Data Engineering"})),
            (4, "searched", '"Airflow"', json.dumps({"text": '"Airflow"'})),
            (2, "added_to_cart", "Agentic Workflows with LangGraph", json.dumps({"text": "Agentic Workflows"})),
            (3, "searched", '"prompt tests"', json.dumps({"text": '"prompt tests"'})),
            (4, "added_to_cart", "Cloud & DevOps for AI Workloads", json.dumps({"text": "Cloud & DevOps"})),
            (2, "viewed_product", "Prompt Engineering to Production", json.dumps({"text": "Prompt Engineering"})),
            (3, "time_on_page", "105s · Evaluating LLM Apps", json.dumps({"duration_seconds": 105}))
        ]
        cursor.executemany(
            "INSERT INTO behavioral_events (user_id, event_type, target_id, metadata_json) VALUES (?, ?, ?, ?)",
            initial_events
        )
        conn.commit()

    conn.close()

# Helper Functions for Users
def get_user_by_email(email: str) -> Optional[Dict[str, Any]]:
    conn = get_db_connection()
    user = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
    conn.close()
    return dict(user) if user else None

def get_user_by_id(user_id: int) -> Optional[Dict[str, Any]]:
    conn = get_db_connection()
    user = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    conn.close()
    return dict(user) if user else None

def create_user(email: str, password_hash: str, role: str = "user") -> int:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO users (email, password_hash, role) VALUES (?, ?, ?)",
        (email, password_hash, role)
    )
    conn.commit()
    user_id = cursor.lastrowid
    conn.close()
    return user_id

def _hydrate_product_defaults(d: dict) -> dict:
    if d.get("level") is None:
        d["level"] = "ADVANCED"
    if d.get("lectures_count") is None:
        d["lectures_count"] = "22 lectures"
    if d.get("instructor_name") is None:
        d["instructor_name"] = "Sudhanshu"
    if d.get("instructor_exp") is None:
        d["instructor_exp"] = "4+ YEARS EXP"
    if d.get("instructor_linkedin") is None:
        d["instructor_linkedin"] = "https://linkedin.com"
    if d.get("technologies") is None:
        d["technologies"] = "LangGraph, Keycloak, OPA, OpenMetadata, MLflow, Langfuse, Streamlit"
    if d.get("what_you_will_learn") is None:
        d["what_you_will_learn"] = (
            "How real production controls work in practice\n"
            "How multi-agent orchestrators enforce security policies\n"
            "Identity Governance for Humans and AI Agents\n"
            "Data Governance, Model Governance & Operational Compliance"
        )
    if d.get("what_you_will_build") is None:
        d["what_you_will_build"] = (
            "A working multi-agent AI system backed by a real database with least-privilege roles.\n"
            "A full governance stack — Keycloak, OPA policy engine, OpenMetadata, MLflow, and Langfuse.\n"
            "A live Streamlit dashboard showing pass/fail status per request with log compliance generator."
        )
    return d

# Helper Functions for Products
def get_all_products(category_filter: Optional[str] = None) -> List[Dict[str, Any]]:
    conn = get_db_connection()
    if category_filter and category_filter != "All":
        products = conn.execute(
            "SELECT * FROM products WHERE category = ? ORDER BY id DESC",
            (category_filter,)
        ).fetchall()
    else:
        products = conn.execute("SELECT * FROM products ORDER BY id DESC").fetchall()
    conn.close()
    return [_hydrate_product_defaults(dict(p)) for p in products]

def get_product_by_id(product_id: int) -> Optional[Dict[str, Any]]:
    conn = get_db_connection()
    product = conn.execute("SELECT * FROM products WHERE id = ?", (product_id,)).fetchone()
    conn.close()
    if not product:
        return None
    return _hydrate_product_defaults(dict(product))

def insert_product(
    title: str, 
    description: str, 
    category: str, 
    price: float, 
    acronym: str = "NEW", 
    vector_id: str = "",
    rating: float = 4.8,
    students_count: str = "1.0k",
    level: str = "ADVANCED",
    lectures_count: str = "22 lectures",
    what_you_will_learn: str = "",
    what_you_will_build: str = "",
    instructor_name: str = "Sudhanshu",
    instructor_exp: str = "4+ YEARS EXP",
    instructor_linkedin: str = "https://linkedin.com",
    technologies: str = "LangGraph, Keycloak, OPA, OpenMetadata, Streamlit"
) -> int:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        '''
        INSERT INTO products (
            title, acronym, description, category, price, rating, students_count, vector_id,
            level, lectures_count, what_you_will_learn, what_you_will_build,
            instructor_name, instructor_exp, instructor_linkedin, technologies
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''',
        (
            title, acronym[:3].upper(), description, category, price, rating, students_count, vector_id,
            level, lectures_count, what_you_will_learn, what_you_will_build,
            instructor_name, instructor_exp, instructor_linkedin, technologies
        )
    )
    conn.commit()
    product_id = cursor.lastrowid
    conn.close()
    return product_id

def update_product_db(
    product_id: int, 
    title: str, 
    description: str, 
    category: str, 
    price: float, 
    vector_id: str,
    rating: float = 4.8,
    students_count: str = "1.0k",
    level: str = "ADVANCED",
    lectures_count: str = "22 lectures",
    what_you_will_learn: str = "",
    what_you_will_build: str = "",
    instructor_name: str = "Sudhanshu",
    instructor_exp: str = "4+ YEARS EXP",
    instructor_linkedin: str = "https://linkedin.com",
    technologies: str = "LangGraph, Keycloak, OPA, OpenMetadata, Streamlit"
):
    conn = get_db_connection()
    conn.execute(
        '''
        UPDATE products SET 
            title = ?, description = ?, category = ?, price = ?, vector_id = ?,
            rating = ?, students_count = ?, level = ?, lectures_count = ?, 
            what_you_will_learn = ?, what_you_will_build = ?,
            instructor_name = ?, instructor_exp = ?, instructor_linkedin = ?, technologies = ?,
            updated_at = CURRENT_TIMESTAMP 
        WHERE id = ?
        ''',
        (
            title, description, category, price, vector_id,
            rating, students_count, level, lectures_count, what_you_will_learn, what_you_will_build,
            instructor_name, instructor_exp, instructor_linkedin, technologies,
            product_id
        )
    )
    conn.commit()
    conn.close()

def delete_product_db(product_id: int):
    conn = get_db_connection()
    conn.execute("DELETE FROM products WHERE id = ?", (product_id,))
    conn.commit()
    conn.close()

# Helper Functions for Behavioral Events
def record_events_batch(user_id: int, events: List[Dict[str, Any]]):
    conn = get_db_connection()
    cursor = conn.cursor()
    for ev in events:
        event_type = ev.get("event_type", "view")
        target_id = str(ev.get("target_id", ""))
        metadata_json = json.dumps(ev.get("metadata", {}))
        cursor.execute(
            "INSERT INTO behavioral_events (user_id, event_type, target_id, metadata_json) VALUES (?, ?, ?, ?)",
            (user_id, event_type, target_id, metadata_json)
        )
    conn.commit()
    conn.close()

def get_recent_user_events(user_id: int, limit: int = 20) -> List[Dict[str, Any]]:
    conn = get_db_connection()
    events = conn.execute(
        "SELECT * FROM behavioral_events WHERE user_id = ? ORDER BY timestamp DESC LIMIT ?",
        (user_id, limit)
    ).fetchall()
    conn.close()
    return [dict(e) for e in events]

def get_all_live_events_stream(limit: int = 30) -> List[Dict[str, Any]]:
    """Fetches global live event stream across users for the Engine Peek view."""
    conn = get_db_connection()
    events = conn.execute(
        '''
        SELECT e.*, u.email 
        FROM behavioral_events e 
        LEFT JOIN users u ON e.user_id = u.id 
        ORDER BY e.timestamp DESC LIMIT ?
        ''',
        (limit,)
    ).fetchall()
    conn.close()
    
    result = []
    for row in events:
        d = dict(row)
        email = d.get("email") or "anonymous"
        user_label = email.split("@")[0] if "@" in email else email
        d["user_label"] = user_label
        result.append(d)
    return result

def clear_all_behavioral_events():
    """Clears all logged behavioral events for a fresh stream start."""
    conn = get_db_connection()
    conn.execute("DELETE FROM behavioral_events")
    conn.commit()
    conn.close()

# Helper Functions for Recommendations
def save_recommendation(user_id: int, narrative: str, recommended_product_ids: List[int], trigger_reason: str = "behavioral_update") -> int:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO recommendations (user_id, narrative, recommended_product_ids, trigger_reason) VALUES (?, ?, ?, ?)",
        (user_id, narrative, json.dumps(recommended_product_ids), trigger_reason)
    )
    conn.commit()
    rec_id = cursor.lastrowid
    conn.close()
    return rec_id

def get_latest_recommendation(user_id: int) -> Optional[Dict[str, Any]]:
    conn = get_db_connection()
    rec = conn.execute(
        "SELECT * FROM recommendations WHERE user_id = ? ORDER BY created_at DESC LIMIT 1",
        (user_id,)
    ).fetchone()
    conn.close()
    if rec:
        d = dict(rec)
        d["recommended_product_ids"] = json.loads(d["recommended_product_ids"])
        return d
    return None

# System Settings Helpers (Admin Trigger Event Control)
def get_setting(key: str, default_val: str = "") -> str:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT setting_value FROM system_settings WHERE setting_key = ?", (key,))
    row = cursor.fetchone()
    conn.close()
    return row[0] if row else default_val

def set_setting(key: str, val: str):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("INSERT OR REPLACE INTO system_settings (setting_key, setting_value) VALUES (?, ?)", (key, val))
    conn.commit()
    conn.close()

def get_allowed_trigger_events() -> List[str]:
    default_allowed = json.dumps(["Filter", "Viewed", "Searched", "Dwell", "CTA", "Clicked", "Tech"])
    raw = get_setting("allowed_trigger_events", default_allowed)
    try:
        return json.loads(raw)
    except Exception:
        return ["Filter", "Viewed", "Searched", "Dwell", "CTA", "Clicked", "Tech"]

def set_allowed_trigger_events(events: List[str]):
    set_setting("allowed_trigger_events", json.dumps(events))

# Dynamic Project-Specific Curriculum Module Generator
def get_project_curriculum_modules(product: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Generates unique, project-tailored curriculum modules matching the course title and tech stack."""
    if product.get("curriculum"):
        try:
            parsed = json.loads(product["curriculum"])
            if isinstance(parsed, list) and len(parsed) > 0:
                return parsed
        except Exception:
            pass

    title = product.get("title", "Project")
    techs = [t.strip() for t in product.get("technologies", "").split(",") if t.strip()]
    tech_primary = techs[0] if techs else "Core Tech"
    tech_secondary = techs[1] if len(techs) > 1 else "Architecture"
    tech_tertiary = techs[2] if len(techs) > 2 else "Production Deployment"

    return [
        {
            "module": "MODULE 1",
            "title": f"Architecture & {tech_primary} Foundations",
            "lectures": "4 lectures",
            "lectures_list": [
                f"Lecture 1.1: Project Setup & {title} Overview",
                f"Lecture 1.2: Core Architecture & {tech_primary} Environment",
                f"Lecture 1.3: Data Structures & State Schema Design",
                f"Lecture 1.4: Production Environment Guardrails"
            ]
        },
        {
            "module": "MODULE 2",
            "title": f"Deep Dive: {tech_secondary} & Engine Core",
            "lectures": "6 lectures",
            "lectures_list": [
                f"Lecture 2.1: {tech_secondary} Pipeline Implementation",
                f"Lecture 2.2: Advanced Routing & Error Resilience",
                f"Lecture 2.3: {title} Core Business Logic",
                f"Lecture 2.4: State Persistence & Memory Management",
                f"Lecture 2.5: Integration Testing & Mock Harnesses",
                f"Lecture 2.6: Performance Benchmarking & Optimization"
            ]
        },
        {
            "module": "MODULE 3",
            "title": f"Security, Policy & {tech_tertiary}",
            "lectures": "6 lectures",
            "lectures_list": [
                f"Lecture 3.1: Security Policy Enforcement & RBAC",
                f"Lecture 3.2: {tech_tertiary} Integration & Secrets Management",
                f"Lecture 3.3: Automated Telemetry & Observability Spans",
                f"Lecture 3.4: Real-time Event Streaming & Webhooks",
                f"Lecture 3.5: Failover Mechanisms & Rate Limiting",
                f"Lecture 3.6: Production Compliance Audit"
            ]
        },
        {
            "module": "MODULE 4",
            "title": f"Production Project: Capstone {title} Deployment",
            "lectures": "6 lectures",
            "lectures_list": [
                f"Lecture 4.1: Docker Containerization & Microservice Build",
                f"Lecture 4.2: CI/CD Pipeline on GitHub Actions",
                f"Lecture 4.3: Cloud Infrastructure Provisioning",
                f"Lecture 4.4: End-to-End System Testing & Stress Testing",
                f"Lecture 4.5: Monitoring & Alerting Setup",
                f"Lecture 4.6: Live Production Deployment & Graduation"
            ]
        }
    ]
