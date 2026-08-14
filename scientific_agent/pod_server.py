"""
ESMFold HTTP server — corre en el pod RunPod A100.
Expone ESMFold como API REST para que el agente CRIZA lo llame remotamente.

El modelo se carga una sola vez al arrancar el servidor (~10s, pesos cacheados).
Cada predicción tarda ~45s en A100.

Uso en el pod:
    pip install fastapi uvicorn
    nohup python3 /root/pod_server.py > /root/pod_server.log 2>&1 &

URL pública (RunPod proxy):
    https://53yj64wek7otne-8000.proxy.runpod.net/health
    https://53yj64wek7otne-8000.proxy.runpod.net/predict
"""

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import uvicorn
import os
import torch
import esm

app = FastAPI(title="ESMFold Pod Server — CRIZA")

# Modelo global — se carga una vez al arrancar, se reutiliza en cada request
_model = None


def _load_model():
    global _model
    if _model is None:
        print("Cargando ESMFold v1 (pesos cacheados)...")
        _model = esm.pretrained.esmfold_v1()
        _model = _model.eval().cuda()
        vram = round(torch.cuda.memory_allocated() / 1e9, 2)
        print(f"Modelo listo. VRAM: {vram} GB")
    return _model


class PredictRequest(BaseModel):
    sequence: str
    protein_name: str


@app.on_event("startup")
async def startup():
    _load_model()
    print("Servidor listo.")


@app.get("/health")
def health():
    return {
        "status": "ok",
        "model_loaded": _model is not None,
        "gpu": torch.cuda.get_device_name(0) if torch.cuda.is_available() else "CPU",
        "vram_used_gb": round(torch.cuda.memory_allocated() / 1e9, 2),
        "vram_total_gb": round(torch.cuda.get_device_properties(0).total_memory / 1e9, 1),
    }


@app.post("/predict")
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

    # Extraer pLDDT por residuo — solo átomos CA (uno por residuo)
    plddt_scores = []
    for line in pdb_content.split("\n"):
        if line.startswith("ATOM") and " CA " in line:
            try:
                plddt_scores.append(float(line[60:66].strip()))
            except ValueError:
                pass

    if not plddt_scores:
        raise HTTPException(status_code=500, detail="No se pudo parsear pLDDT del PDB")

    # ESMFold local devuelve escala 0-100
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

    # Guardar PDB en el pod (para referencia)
    pdb_dir = "/root/structures"
    os.makedirs(pdb_dir, exist_ok=True)
    safe_name = "".join(c if c.isalnum() else "_" for c in protein_name)
    pod_pdb_path = f"{pdb_dir}/{safe_name}_{original_length}aa_local.pdb"
    with open(pod_pdb_path, "w") as f:
        f.write(pdb_content)

    return {
        "protein_name":           protein_name,
        "original_length":        original_length,
        "analyzed_length":        original_length,
        "truncated":              False,
        "structure_obtained":     True,
        "method":                 "local",
        "device":                 "GPU (CUDA) — RunPod A100 80GB",
        "avg_plddt":              avg_plddt,
        "pct_residues_high_conf": pct_high,
        "confidence_level":       confidence,
        "expression_implication": expression_implication,
        "per_residue_plddt":      [round(v, 2) for v in plddt_scores],
        "pdb_content":            pdb_content,   # el agente lo guarda localmente
        "pod_pdb_path":           pod_pdb_path,
        "note": (
            f"Secuencia completa analizada en RunPod A100 ({original_length} aa) — sin truncación. "
            f"{pct_high}% de residuos con alta confianza (pLDDT ≥ 70)."
        ),
    }


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
