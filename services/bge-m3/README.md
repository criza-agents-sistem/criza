# BGE-m3 Embeddings Service — Modal (Capa 1)

Servicio compartido de embeddings. Stateless: texto → vector 1024 dims.
Self-hosted en Modal — los datos nunca salen de la infra. Sin lock-in de proveedor.

## Setup (una sola vez)

```bash
# 1. Instalar Modal CLI
pip install modal

# 2. Autenticar
modal setup

# 3. Descargar pesos al Volume (~570MB, una sola vez)
modal run services/bge-m3/modal_app.py::download_model

# 4. Deploy
modal deploy services/bge-m3/modal_app.py
```

Endpoint: `https://criza-dev--criza-bge-m3-embed-server.modal.run`

## Endpoints

| Endpoint | Método | Descripción |
|---|---|---|
| `/health` | GET | Estado del servicio |
| `/embed` | POST | Texto único → embedding 1024 dims |
| `/embed/batch` | POST | Lista de textos → lista de embeddings (máx 256) |

### GET /health
```json
{
  "status": "ok",
  "model_loaded": false,
  "model": "BAAI/bge-m3",
  "dims": 1024,
  "platform": "Modal"
}
```

### POST /embed
```json
// Request
{ "text": "enzimas lignocelulolíticas en fermentación", "max_length": 512 }

// Response
{ "embedding": [0.008, -0.005, ...], "dims": 1024, "model": "BAAI/bge-m3" }
```

### POST /embed/batch
```json
// Request
{ "texts": ["texto 1", "texto 2", ...], "batch_size": 32, "max_length": 512 }

// Response
{ "embeddings": [[...], [...]], "dims": 1024, "model": "BAAI/bge-m3", "count": 2 }
```

## Características

| Parámetro | Valor |
|---|---|
| Modelo | BAAI/bge-m3 |
| Dimensiones | 1024 (dense, normalizado) |
| Hardware | CPU (2 cores, 4GB RAM) |
| Batch máximo | 256 textos por request |
| Cold start | ~15s |
| Latencia post-cold-start | ~200ms/texto, ~2s batch 64 textos |
| Idle cost | $0 — se apaga solo a los 5 min de inactividad |

## Por qué BGE-m3

- **Privacidad**: los textos nunca salen de la infra (OpenAI/Voyage = datos en manos de terceros)
- **Sin lock-in**: modelo abierto, deployable en cualquier infra
- **Multilingüe nativo**: fuerte en español sin fine-tuning
- **1024 dims**: índice pgvector eficiente

## Re-deploy

```bash
modal deploy services/bge-m3/modal_app.py
```

Los pesos en el Volume persisten — no requiere re-descargar.
