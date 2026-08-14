# ESMFold Service — Modal

Servicio de predicción de estructura proteica. Reemplaza el pod RunPod.
Expone la misma API HTTP que el pod — el agente científico no requiere cambios de código.

## Setup (una sola vez)

```bash
# 1. Instalar Modal CLI
pip install modal

# 2. Autenticar con tu cuenta Modal (abre el browser)
modal setup

# 3. Descargar pesos al Volume (~14GB, tarda ~10 min, se ejecuta UNA SOLA VEZ)
modal run services/esmfold/modal_app.py::download_model

# 4. Deploy
modal deploy services/esmfold/modal_app.py
```

Al terminar el deploy Modal imprime la URL del endpoint:
```
✓ Created web function esmfold_server =>
  https://<usuario>--criza-esmfold-esmfold-server.modal.run
```

## Conectar al agente científico

Copiar la URL a `criza/scientific_agent/.env`:
```
ESMFOLD_POD_URL=https://<usuario>--criza-esmfold-esmfold-server.modal.run
```

Sin trailing slash. Eso es todo — `esmfold_local.py` no requiere ningún cambio.

## Endpoints

| Endpoint | Método | Descripción |
|---|---|---|
| `/health` | GET | Estado del servicio y modelo |
| `/predict` | POST | Predicción de estructura |

### POST /predict

```json
// Request
{ "sequence": "MKTIIALSYIFCLVFA...", "protein_name": "mi_proteina" }

// Response (mismo formato que RunPod)
{
  "structure_obtained": true,
  "avg_plddt": 87.3,
  "pct_residues_high_conf": 74.2,
  "confidence_level": "Alta (70-90)...",
  "expression_implication": "...",
  "pdb_content": "ATOM ...",
  "device": "GPU (CUDA) — Modal A10G"
}
```

## Comportamiento

| Situación | Comportamiento |
|---|---|
| Primera request (cold start) | ~30-60s de espera (carga el modelo desde el Volume) |
| Requests siguientes en misma sesión | Respuesta inmediata (modelo ya cargado en VRAM) |
| Sin uso por 5 min | Contenedor se apaga solo |
| Siguiente request después de inactivo | Nuevo cold start (~30-60s) |

## Costo estimado

- Por predicción (~45s de A10G): **~$0.03**
- Sin idle cost — la GPU no corre cuando no hay requests
- Comparado con RunPod H200: $4.39/hr solo cuando está encendido

## Re-deploy (actualizaciones)

```bash
modal deploy services/esmfold/modal_app.py
```

No requiere re-descargar los pesos (el Volume persiste).
