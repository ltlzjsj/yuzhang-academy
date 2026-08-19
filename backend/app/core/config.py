from functools import lru_cache
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "赣书院·智典"
    env: str = "dev"
    debug: bool = True
    db_echo: bool = False
    db_pool_size: int = 10
    db_max_overflow: int = 20
    db_pool_recycle_seconds: int = 3600

    db_host: str = "127.0.0.1"
    db_port: int = 3306
    db_user: str = "georag"
    db_password: str = "georag_pass"
    db_name: str = "georag"

    redis_url: str = "redis://127.0.0.1:6379/0"
    celery_broker_url: str = "redis://127.0.0.1:6379/1"
    celery_result_backend: str = "redis://127.0.0.1:6379/2"

    qdrant_url: str = "http://127.0.0.1:6333"
    qdrant_api_key: str | None = None

    ollama_base_url: str = "http://127.0.0.1:11434"
    embed_model: str = "bge-m3:latest"
    embedding_dim: int = 1024
    default_chat_model: str = "mimo-v2.5"

    # LLM provider: "mimo" (Xiaomi MiMo cloud, Anthropic Messages API) or
    # "ollama" (local). The geological-era code used Ollama; the 书院 build
    # defaults to MiMo and keeps the Ollama path behind this switch.
    llm_provider: str = "mimo"
    # MiMo (小米) multimodal LLM — Anthropic-compatible Messages API.
    # The API key MUST come from the MIMO_API_KEY environment variable; never
    # hard-code it. base_url is the host root; "/v1/messages" is appended.
    # NOTE: use "mimo-v2.5" (全模态理解, accepts images) — "mimo-v2.5-pro" is
    # text-only and will ignore/reject image content blocks.
    mimo_api_key: str = ""
    mimo_base_url: str = "https://api.xiaomimimo.com/anthropic"
    mimo_model: str = "mimo-v2.5"
    mimo_max_tokens: int = 2048

    # MiMo 语音 (ASR/TTS v2.5) — OpenAI 风格端点, 与上面的 Messages API 路径不同。
    # 复用 mimo_api_key 鉴权 (header: api-key)。base 拼接 "/v1/chat/completions"。
    mimo_audio_base_url: str = "https://api.xiaomimimo.com"
    mimo_asr_model: str = "mimo-v2.5-asr"
    mimo_tts_model: str = "mimo-v2.5-tts"
    mimo_tts_voicedesign_model: str = "mimo-v2.5-tts-voicedesign"  # 文本描述生成音色(古风名儒)
    mimo_tts_voice: str = "mimo_default"   # 预置音色: 冰糖/茉莉/苏打/白桦/Mia/Chloe/Milo/Dean ...
    mimo_tts_format: str = "mp3"           # wav | pcm16 | mp3

    minimax_api_key: str = ""
    minimax_base_url: str = "https://api.minimaxi.com/anthropic"
    minimax_model: str = "MiniMax-M2.7"
    minimax_max_tokens: int = 2048

    jwt_secret: str = "change-me"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 1440

    # 管理后台：role == "admin" 或用户名在此列表者可访问 /admin。
    # 逗号分隔，env: ADMIN_USERNAMES=alice,bob —— 便于免改库指定管理员。
    admin_usernames: str = ""

    @property
    def admin_username_set(self) -> set[str]:
        return {u.strip() for u in (self.admin_usernames or "").split(",") if u.strip()}

    upload_dir: str = "./uploads"
    cors_origins: str = "http://localhost:5173"

    # Reranker (cross-encoder over retriever candidates)
    rerank_model: str = "BAAI/bge-reranker-v2-m3"
    rerank_device: str = "auto"       # "auto" | "cuda" | "cpu"
    rerank_candidate_factor: int = 2  # oversample factor: retriever fetches top_k * factor before rerank
    rerank_default_enabled: bool = False

    # Hybrid retrieval fusion weights & thresholds
    rag_weight_vector: float = 1.0
    rag_weight_bm25: float = 0.8
    rag_weight_qa: float = 1.2        # QA questions are human-authored — weigh them up
    rag_qa_k: int = 10                # per-channel_k override for QA (QA corpus is smaller)
    rag_min_rrf: float = 0.0          # drop fused candidates below this score (0 = off)
    rag_min_vector_score: float = 0.25
    rag_min_qa_score: float = 0.30
    rag_context_max_chars: int = 3200
    # Vector/QA channels need an embedding model (bge-m3). The 书院 build runs
    # MiMo-only with no local model, so vector retrieval is disabled and the
    # retriever falls back to BM25 keyword search over the academy corpus.
    rag_vector_enabled: bool = False
    # 图文: how many images to surface to the UI per answer, and how many of
    # those to also base64-encode and feed to the MiMo multimodal model.
    rag_max_images: int = 4
    rag_max_images_to_llm: int = 4
    # 自备书院图片：用户手工整理的高清图，按书院名分子目录存放
    #   <academy_images_dir>/<书院名>/*.jpg|png|...
    # 问到某书院时优先取这里的图（比 PDF 抽取的更可控）。
    academy_images_dir: str = "./academy_images"
    academy_images_manifest: str = "manifest.json"
    # RAG relevance gate: prevents unrelated prompts from receiving arbitrary
    # citations just because a KB is selected in the chat UI.
    rag_gate_enabled: bool = True
    rag_gate_min_overlap: float = 0.16
    rag_gate_min_rrf: float = 0.020
    rag_gate_strong_rrf: float = 0.038
    rag_gate_min_vector: float = 0.52
    rag_gate_min_qa: float = 0.50
    rag_direct_qa_min_score: float = 0.72

    # LLM keep-alive (Ollama): how long to keep a model resident between calls.
    ollama_keep_alive: str = "30m"
    # Warm models during app startup to avoid first-request latency spike.
    # Only relevant for the Ollama provider; off by default for the MiMo build.
    warm_models_on_start: bool = False
    warm_reranker_on_start: bool = False

    # QA enrichment is useful but expensive. Keep it manual by default so
    # normal ingest stays focused on parse/chunk/embed/index.
    qa_auto_generate_on_ingest: bool = False

    # PDF parsing
    pdf_parser: str = "mineru"  # "mineru" | "legacy"
    # Keep figure extraction on MinerU even when PDF_PARSER=legacy.
    pdf_image_extractor: str = "mineru"  # "mineru" | "none"
    mineru_output_dir: str = "./mineru_out"
    mineru_lang: str = "ch"
    mineru_backend: str = "pipeline"  # "pipeline" (CPU-safe) | "vlm-*" | "hybrid-*"
    mineru_parse_method: str = "auto"  # "auto" | "ocr" | "txt"
    mineru_model_source: str = "modelscope"  # "modelscope" | "huggingface" | "local"
    hf_home: str = ""
    hf_endpoint: str = "https://hf-mirror.com"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def sqlalchemy_database_uri(self) -> str:
        return (
            f"mysql+aiomysql://{self.db_user}:{self.db_password}"
            f"@{self.db_host}:{self.db_port}/{self.db_name}?charset=utf8mb4"
        )

    @property
    def alembic_database_uri(self) -> str:
        return (
            f"mysql+pymysql://{self.db_user}:{self.db_password}"
            f"@{self.db_host}:{self.db_port}/{self.db_name}?charset=utf8mb4"
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
