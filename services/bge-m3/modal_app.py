"""
BGE-m3 Embeddings Service — Modal (Capa 1)

Servicio compartido central de embeddings. Stateless: texto → vector 1024 dims.
Self-hosted: los datos nunca salen de la infra. Sin lock-in de proveedor.

Setup (una sola vez):
    pip install modal
    modal run services/bge-m3/modal_app.py::download_model   ← descarga ~570MB al Volume
    modal deploy services/bge-m3/modal_app.py

La URL del endpoint se imprime al terminar el deploy:
    https://criza-dev--criza-bge-m3-embed-server.modal.run

Endpoints:
    GET  /health          — estado del servicio
    POST /embed           — texto único → embedding 1024 dims
    POST /embed/batch     — lista de textos → lista de embeddings (máx 256)
"""

import modal

# ── Imagen ───────────────────────────────────────────────────────────────────
bge_image = (
    modal.Image.debian_slim(python_version="3.11")
    .pip_install(
        "FlagEmbedding>=1.2.10",
        "fastapi>=0.100.0",
        "uvicorn>=0.23.0",
        "pydantic>=2.0.0",
        "torch>=2.0.0",          # CPU-only wheels — FlagEmbedding los trae como dep
        "transformers>=4.36.0",
        "sentence-transformers",
    )
)

# ── Volume para caché de pesos (~570MB) ──────────────────────────────────────
model_cache = modal.Volume.from_name("bge-m3-model-cache", create_if_missing=True)
CACHE_PATH = "/bge_m3_cache"
MODEL_NAME = "BAAI/bge-m3"

# ── App Modal ────────────────────────────────────────────────────────────────
app = modal.App("criza-bge-m3")


# ── Setup: descargar modelo al Volume (ejecutar una sola vez) ────────────────
@app.function(
    image=bge_image,
    cpu=2,
    memory=4096,
    timeout=600,
    volumes={CACHE_PATH: model_cache},
)
def download_model():
    """
    Descarga los pesos de BGE-m3 al Volume.
    Ejecutar una sola vez: modal run services/bge-m3/modal_app.py::download_model
    """
    from FlagEmbedding import BGEM3FlagModel

    print(f"Descargando {MODEL_NAME} (~570MB)...")
    # cache_dir apunta al Volume
    model = BGEM3FlagModel(MODEL_NAME, use_fp16=False, cache_dir=CACHE_PATH)
    # warm-up: asegura que todos los archivos estén en disco
    _ = model.encode(["warmup"], batch_size=1, max_length=16)
    print("Modelo descargado y verificado.")
    model_cache.commit()


# ── FastAPI app ───────────────────────────────────────────────────────────────
def build_fastapi_app():
    from fastapi import FastAPI, HTTPException
    from pydantic import BaseModel, Field

    fastapi_app = FastAPI(title="BGE-m3 Embeddings — CRIZA (Modal)")
    _state = {"model": None}

    def _load_model():
        if _state["model"] is None:
            from FlagEmbedding import BGEM3FlagModel
            import os
            print(f"Cargando {MODEL_NAME} desde Volume...")
            _state["model"] = BGEM3FlagModel(
                MODEL_NAME,
                use_fp16=False,       # CPU — fp16 no aplica
                cache_dir=CACHE_PATH,
            )
            print("Modelo listo.")
        return _state["model"]

    # ── Schemas ──────────────────────────────────────────────────────────────

    class EmbedRequest(BaseModel):
        text: str
        max_length: int = Field(default=512, ge=1, le=8192)

    class EmbedResponse(BaseModel):
        embedding: list[float]
        dims: int
        model: str

    class BatchEmbedRequest(BaseModel):
        texts: list[str] = Field(..., min_length=1, max_length=256)
        max_length: int = Field(default=512, ge=1, le=8192)
        batch_size: int = Field(default=32, ge=1, le=256)

    class BatchEmbedResponse(BaseModel):
        embeddings: list[list[float]]
        dims: int
        model: str
        count: int

    # ── Endpoints ────────────────────────────────────────────────────────────

    @fastapi_app.get("/health")
    def health():
        import platform
        return {
            "status": "ok",
            "model_loaded": _state["model"] is not None,
            "model": MODEL_NAME,
            "dims": 1024,
            "platform": "Modal",
            "python": platform.python_version(),
        }

    @fastapi_app.post("/embed", response_model=EmbedResponse)
    def embed(req: EmbedRequest):
        if not req.text.strip():
            raise HTTPException(status_code=400, detail="Texto vacío")
        model = _load_model()
        try:
            result = model.encode(
                [req.text],
                batch_size=1,
                max_length=req.max_length,
                return_dense=True,
                return_sparse=False,
                return_colbert_vecs=False,
            )
            embedding = result["dense_vecs"][0].tolist()
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error al generar embedding: {e}")
        return EmbedResponse(embedding=embedding, dims=len(embedding), model=MODEL_NAME)

    @fastapi_app.post("/embed/batch", response_model=BatchEmbedResponse)
    def embed_batch(req: BatchEmbedRequest):
        texts = [t for t in req.texts if t.strip()]
        if not texts:
            raise HTTPException(status_code=400, detail="Todos los textos están vacíos")
        model = _load_model()
        try:
            result = model.encode(
                texts,
                batch_size=req.batch_size,
                max_length=req.max_length,
                return_dense=True,
                return_sparse=False,
                return_colbert_vecs=False,
            )
            embeddings = result["dense_vecs"].tolist()
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error al generar embeddings: {e}")
        return BatchEmbedResponse(
            embeddings=embeddings,
            dims=len(embeddings[0]) if embeddings else 1024,
            model=MODEL_NAME,
            count=len(embeddings),
        )

    return fastapi_app


# ── Modal ASGI endpoint ───────────────────────────────────────────────────────
@app.function(
    image=bge_image,
    cpu=2,
    memory=4096,               # 4GB RAM — BGE-m3 en CPU necesita ~2GB, margen para batches
    timeout=120,               # 2 min — batch de 256 textos en CPU < 30s
    volumes={CACHE_PATH: model_cache},
    scaledown_window=300,      # modelo vivo 5 min post-request
)
@modal.asgi_app()
def embed_server():
    return build_fastapi_app()
