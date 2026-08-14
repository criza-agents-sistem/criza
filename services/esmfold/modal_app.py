"""
ESMFold en Modal — reemplaza el pod RunPod.

Migración directa de criza/scientific_agent/pod_server.py.
Contrato HTTP idéntico: POST /predict, GET /health.
esmfold_local.py no requiere cambios — solo actualizar ESMFOLD_POD_URL en .env.

Deploy (primera vez):
    pip install modal
    modal setup          ← autenticación con tu cuenta Modal
    modal run services/esmfold/modal_app.py::download_model   ← descarga ~14GB al Volume (una sola vez)
    modal deploy services/esmfold/modal_app.py

La URL del endpoint se imprime al terminar el deploy:
    https://<tu-usuario>--criza-esmfold-esmfold-server.modal.run

Copiar esa URL a ESMFOLD_POD_URL en criza/scientific_agent/.env (sin trailing slash).

Costo estimado:
    - Cold start: ~30-60s (carga del Volume al VRAM de la GPU)
    - Por predicción (~45s en A10G): ~$0.03
    - Sin idle cost — la GPU se apaga sola al terminar
"""

import modal

# ── Imagen con dependencias ──────────────────────────────────────────────────
esmfold_image = (
    # Imagen base con CUDA + PyTorch pre-instalados (necesarios para compilar openfold)
    # Todo en run_commands para que torch esté disponible al instalar openfold
    modal.Image.from_registry("nvcr.io/nvidia/pytorch:23.06-py3")
    .apt_install("git")
    .add_local_file("services/esmfold/patch_openfold.py", "/patch_openfold.py", copy=True)
    .run_commands(
        # Paso 1: dependencias que no requieren torch en build time
        # biopython, pandas, etc. son requeridas por openfold.utils
        # Dependencias para openfold (solo inferencia, sin deepspeed/pytorch-lightning)
        # IMPORTANTE: no instalar torch — la imagen base ya tiene torch 2.1 compatible con apex
        # pytorch-lightning actualizaría torch y rompería apex/fused_layer_norm_cuda
        # pytorch-lightning con --no-deps para NO actualizar torch (que rompería apex del NVIDIA image)
        # luego instalar sus deps no-torch por separado
        # Paso 1a: deps principales — resuelven transitive deps normalmente
        # (omegaconf necesita antlr4-python3-runtime, se instala automáticamente aquí)
        "pip install "
        "'fair-esm>=2.0.0' 'fastapi>=0.100.0' 'uvicorn>=0.23.0' 'pydantic>=2.0.0' "
        "'omegaconf>=2.1.0' dm-tree ml-collections einops biopython pandas modelcif scipy",
        # Paso 1b: pytorch-lightning aislado con --no-deps para NO actualizar torch
        # Pinado a <2.0 porque 2.x usa @torch.compiler.disable que no existe en torch 2.1.0a0 pre-release
        # torch 2.1.0a0 de la imagen NVIDIA no debe actualizarse — apex compilado contra él
        "pip install --no-deps 'pytorch-lightning<2.0' "
        "&& pip install torchmetrics lightning-utilities fsspec packaging",
        # Paso 2: openfold — commit ESPECÍFICO 4b41059 (compatible con esmfold_3B_v1.pt checkpoint)
        # El latest main cambió la arquitectura y el checkpoint no carga
        "git clone https://github.com/aqlaboratory/openfold.git /tmp/openfold "
        "&& git -C /tmp/openfold checkout 4b41059694619831a7db195b7e0988fc4ff3a307 "
        "&& cp -r /tmp/openfold/openfold /usr/local/lib/python3.10/dist-packages/ "
        "&& python3 /patch_openfold.py "
        "&& rm -rf /tmp/openfold",
    )
)

# ── Volume para caché de pesos ───────────────────────────────────────────────
# Los pesos de ESMFold (~14GB) se descargan una vez con `modal run ... ::download_model`
# y se reutilizan en cada cold start. Sin esto, cada cold start re-descarga todo.
model_cache = modal.Volume.from_name("esmfold-model-cache", create_if_missing=True)

CACHE_PATH = "/esmfold_cache"   # path limpio — /root/.cache ya existe en la imagen base y Modal no monta volumes en paths no vacíos

# ── App Modal ────────────────────────────────────────────────────────────────
app = modal.App("criza-esmfold")


# ── Setup: descargar modelo al Volume (ejecutar una sola vez) ────────────────
@app.function(
    image=esmfold_image,
    gpu="A10G",
    timeout=1200,              # 20 min — la primera descarga puede tardar
    volumes={CACHE_PATH: model_cache},
)
def download_model():
    """
    Descarga los pesos de ESMFold al Volume.
    Ejecutar una sola vez: modal run services/esmfold/modal_app.py::download_model
    """
    import os
    import esm
    os.environ["TORCH_HOME"] = CACHE_PATH
    print("Descargando pesos de ESMFold v1 (~14GB)...")
    model = esm.pretrained.esmfold_v1()
    model.eval()
    print("Pesos descargados y guardados en el Volume.")
    model_cache.commit()


# ── FastAPI app (contrato idéntico a pod_server.py) ──────────────────────────
def build_fastapi_app():
    """Construye la FastAPI app. Llamada dentro del contexto Modal (torch disponible)."""
    import torch
    from fastapi import FastAPI, HTTPException
    from pydantic import BaseModel

    fastapi_app = FastAPI(title="ESMFold — CRIZA (Modal)")
    _model_state = {"model": None}

    def _load_model():
        if _model_state["model"] is None:
            import os, esm
            os.environ["TORCH_HOME"] = CACHE_PATH
            print("Cargando ESMFold v1 desde Volume...")
            m = esm.pretrained.esmfold_v1()
            m = m.eval().cuda()
            vram = round(torch.cuda.memory_allocated() / 1e9, 2)
            print(f"Modelo listo. VRAM usada: {vram} GB")
            _model_state["model"] = m
        return _model_state["model"]

    class PredictRequest(BaseModel):
        sequence: str
        protein_name: str

    @fastapi_app.get("/health")
    def health():
        return {
            "status": "ok",
            "model_loaded": _model_state["model"] is not None,
            "gpu": torch.cuda.get_device_name(0) if torch.cuda.is_available() else "CPU",
            "vram_used_gb": round(torch.cuda.memory_allocated() / 1e9, 2) if torch.cuda.is_available() else 0,
            "platform": "Modal",
        }

    @fastapi_app.post("/predict")
    def predict(req: PredictRequest):
        sequence = req.sequence.strip().upper()
        protein_name = req.protein_name
        original_length = len(sequence)

        if not sequence:
            raise HTTPException(status_code=400, detail="Secuencia vacía")

        model = _load_model()

        try:
            with torch.no_grad():
                pdb_content = model.infer_pdb(sequence)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"ESMFold error: {e}")

        # Extraer pLDDT por residuo (átomos CA)
        plddt_scores = []
        for line in pdb_content.split("\n"):
            if line.startswith("ATOM") and " CA " in line:
                try:
                    plddt_scores.append(float(line[60:66].strip()))
                except ValueError:
                    pass

        if not plddt_scores:
            raise HTTPException(status_code=500, detail="No se pudo parsear pLDDT del PDB")

        if max(plddt_scores) <= 1.0:
            plddt_scores = [v * 100.0 for v in plddt_scores]

        avg_plddt = round(sum(plddt_scores) / len(plddt_scores), 2)
        high_conf = sum(1 for s in plddt_scores if s >= 70)
        pct_high = round(100 * high_conf / len(plddt_scores), 1)

        if avg_plddt >= 90:
            confidence = "Muy alta (≥90) — estructura bien definida, predicción muy confiable"
            expression_implication = "Alta probabilidad de plegamiento correcto en sistema de expresión microbiano"
        elif avg_plddt >= 70:
            confidence = "Alta (70-90) — estructura confiable con posibles regiones flexibles"
            expression_implication = "Plegamiento correcto probable. Verificar regiones de baja confianza"
        elif avg_plddt >= 50:
            confidence = "Media (50-70) — regiones desordenadas o flexibles presentes"
            expression_implication = "Puede haber problemas de solubilidad o agregación. Considerar variantes más estables"
        else:
            confidence = "Baja (<50) — proteína probablemente intrínsecamente desordenada"
            expression_implication = "Alto riesgo de cuerpos de inclusión. Requiere optimización significativa de expresión"

        return {
            "protein_name":           protein_name,
            "original_length":        original_length,
            "analyzed_length":        original_length,
            "truncated":              False,
            "structure_obtained":     True,
            "method":                 "local",
            "device":                 "GPU (CUDA) — Modal A10G",
            "avg_plddt":              avg_plddt,
            "pct_residues_high_conf": pct_high,
            "confidence_level":       confidence,
            "expression_implication": expression_implication,
            "per_residue_plddt":      [round(v, 2) for v in plddt_scores],
            "pdb_content":            pdb_content,   # cliente guarda su copia local
            "note": (
                f"Secuencia completa analizada en Modal A10G ({original_length} aa) — sin truncación. "
                f"{pct_high}% de residuos con alta confianza (pLDDT ≥ 70)."
            ),
        }

    return fastapi_app


# ── Modal ASGI endpoint ──────────────────────────────────────────────────────
@app.function(
    image=esmfold_image,
    gpu="A10G",                # 24GB VRAM — suficiente para ESMFold (~14GB modelo)
    timeout=300,               # 5 min por request — cubre proteínas largas
    volumes={CACHE_PATH: model_cache},
    scaledown_window=300,      # mantiene el contenedor vivo 5 min post-request
    # keep_warm=0 (default) — sin instancias siempre encendidas, cold start ~30-60s
)
@modal.asgi_app()
def esmfold_server():
    return build_fastapi_app()
