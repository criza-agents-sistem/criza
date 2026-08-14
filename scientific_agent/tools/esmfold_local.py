"""
ESMFold local structure prediction — SEB-79

Dos modos de operación (en orden de prioridad):

  1. Pod HTTP API (recomendado):
       Si ESMFOLD_POD_URL está en .env, llama al servidor FastAPI corriendo en el pod RunPod.
       Sin límite de longitud, ~45s por proteína en A100.
       Si el pod está apagado → fallback a modo 2 o 3.

  2. Ejecución local:
       Si fair-esm + torch están instalados localmente, corre el modelo en esta máquina.
       GPU: ~45s. CPU: ~25 min para secuencias > 400 aa.

  3. Fallback:
       Retorna structure_obtained=False con instrucciones de setup.
       El agente cae automáticamente a predict_structure() (API pública, 200aa).

Output idéntico a predict_structure() para compatibilidad con el pipeline downstream.
"""

import os
import requests
from pathlib import Path


def _get_pod_url() -> str:
    """Lee ESMFOLD_POD_URL del entorno en el momento de la llamada (no al importar).
    Así funciona correctamente aunque load_dotenv se llame después del import."""
    return os.getenv("ESMFOLD_POD_URL", "").rstrip("/")


# Alias de módulo para compatibilidad con compare.py que importa este nombre.
# Siempre vacío al importar — usar _get_pod_url() en runtime.
ESMFOLD_POD_URL = ""


def _check_dependencies() -> tuple[bool, str]:
    """Check si fair-esm y torch están instalados localmente."""
    try:
        import torch  # noqa: F401
    except ImportError:
        return False, "torch not installed — run: pip install torch"
    try:
        import esm  # noqa: F401
    except ImportError:
        return False, "fair-esm not installed — run: pip install fair-esm"
    return True, ""


def _is_gpu_available() -> bool:
    """Return True si hay GPU CUDA disponible."""
    try:
        import torch
        return torch.cuda.is_available()
    except ImportError:
        return False


def _fallback_response(protein_name: str, error: str, extra: dict = None) -> dict:
    """Respuesta estándar cuando ESMFold no está disponible."""
    resp = {
        "protein_name":       protein_name,
        "structure_obtained": False,
        "error":              error,
        "setup_instructions": (
            "Opciones para ESMFold sin límite de longitud:\n\n"
            "1. Modal (recomendado — serverless, sin gestión de pods):\n"
            "   - Ver services/esmfold/README.md\n"
            "   - pip install modal && modal setup\n"
            "   - modal run services/esmfold/modal_app.py::download_model\n"
            "   - modal deploy services/esmfold/modal_app.py\n"
            "   - Copiar la URL a ESMFOLD_POD_URL en .env\n"
            "   - Cold start ~30-60s | ~$0.03 por predicción | sin idle cost\n\n"
            "2. Instalación local:\n"
            "   pip install fair-esm torch\n"
            "   GPU: ~45s/proteína | CPU: ~25 min para >400 aa\n\n"
            "Modelo: ~14 GB, se descarga automáticamente en el primer uso."
        ),
        "fallback": (
            "predict_structure() via ESM Atlas public API — "
            "limitado a primeros 200 aa pero sin setup requerido"
        ),
    }
    if extra:
        resp.update(extra)
    return resp


def _predict_via_pod(sequence: str, protein_name: str, pod_url: str) -> dict:
    """Llama al servidor ESMFold en el pod RunPod via HTTP."""
    url = f"{pod_url}/predict"
    try:
        resp = requests.post(
            url,
            json={"sequence": sequence, "protein_name": protein_name},
            timeout=300,   # 5 min — suficiente para 710aa en A100
        )
    except requests.exceptions.ConnectionError:
        return _fallback_response(
            protein_name,
            f"Pod no alcanzable en {pod_url} — ¿está corriendo el pod?",
            {"pod_url": pod_url},
        )
    except requests.exceptions.Timeout:
        return _fallback_response(
            protein_name,
            f"Timeout al contactar el pod ({ESMFOLD_POD_URL}) — secuencia demasiado larga o pod ocupado",
        )

    if resp.status_code != 200:
        return _fallback_response(
            protein_name,
            f"Pod error {resp.status_code}: {resp.text[:200]}",
        )

    data = resp.json()

    # Guardar PDB localmente (para ProteinMPNN, FoldX si están configurados)
    pdb_content = data.pop("pdb_content", None)
    if pdb_content:
        pdb_dir = Path(__file__).parent.parent / "structures"
        pdb_dir.mkdir(exist_ok=True)
        safe_name = "".join(c if c.isalnum() else "_" for c in protein_name)
        local_pdb = pdb_dir / f"{safe_name}_{len(sequence)}aa_local.pdb"
        local_pdb.write_text(pdb_content)
        data["pdb_path"] = str(local_pdb)

    return data


def _predict_locally(sequence: str, protein_name: str) -> dict:
    """Corre ESMFold directamente en esta máquina (requiere fair-esm + torch)."""
    import esm
    import torch

    original_length = len(sequence)
    use_gpu = _is_gpu_available()
    device_label = "GPU (CUDA)" if use_gpu else "CPU (lento — GPU recomendada para >200 aa)"

    model = esm.pretrained.esmfold_v1()
    model = model.eval()
    if use_gpu:
        model = model.cuda()

    with torch.no_grad():
        pdb_content = model.infer_pdb(sequence)

    # Guardar PDB
    pdb_dir = Path(__file__).parent.parent / "structures"
    pdb_dir.mkdir(exist_ok=True)
    safe_name = "".join(c if c.isalnum() else "_" for c in protein_name)
    pdb_path = pdb_dir / f"{safe_name}_{original_length}aa_local.pdb"
    pdb_path.write_text(pdb_content)

    # pLDDT por residuo — solo átomos CA (uno por residuo, no por átomo)
    plddt_scores: list[float] = []
    for line in pdb_content.split("\n"):
        if line.startswith("ATOM") and " CA " in line:
            try:
                plddt_scores.append(float(line[60:66].strip()))
            except ValueError:
                pass

    if max(plddt_scores, default=0) <= 1.0:
        plddt_scores = [v * 100.0 for v in plddt_scores]

    if not plddt_scores:
        return {
            "protein_name":       protein_name,
            "structure_obtained": False,
            "error":              "No se pudo parsear pLDDT del PDB",
        }

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
        "device":                 device_label,
        "pdb_path":               str(pdb_path),
        "avg_plddt":              avg_plddt,
        "pct_residues_high_conf": pct_high,
        "confidence_level":       confidence,
        "expression_implication": expression_implication,
        "per_residue_plddt":      [round(v, 2) for v in plddt_scores],
        "note": (
            f"Secuencia completa analizada localmente ({original_length} aa) — sin truncación. "
            f"{pct_high}% de residuos con alta confianza (pLDDT ≥ 70). "
            f"Computado en {device_label}. PDB guardado en {pdb_path}."
        ),
    }


def predict_structure_local(sequence: str, protein_name: str) -> dict:
    """
    Predicción de estructura 3D con ESMFold — sin límite de longitud.

    Prioridad:
      1. Pod RunPod via HTTP (si ESMFOLD_POD_URL está en .env)
      2. Ejecución local (si fair-esm + torch instalados)
      3. Fallback con instrucciones de setup

    Args:
        sequence:     Secuencia completa en código de una letra
        protein_name: Nombre para referencia y nombre del archivo PDB

    Returns:
        dict compatible con predict_structure() — mismo formato de output.
    """
    sequence = sequence.strip().upper()

    # --- Modo 1: Pod HTTP API ---
    pod_url = _get_pod_url()
    if pod_url:
        return _predict_via_pod(sequence, protein_name, pod_url)

    # --- Modo 2: Ejecución local ---
    available, error_msg = _check_dependencies()
    if not available:
        return _fallback_response(protein_name, error_msg)

    try:
        return _predict_locally(sequence, protein_name)
    except Exception as e:
        return _fallback_response(protein_name, f"ESMFold local error: {e}")
