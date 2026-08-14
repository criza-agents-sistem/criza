# ESMFold Service — Design Gate

**Versión:** 1.0
**Fecha:** 2026-06-09
**Módulo:** services/esmfold
**Capa:** 1 (compute compartido)
**Estado:** ✅ LISTO — migración directa de pod_server.py

> Este servicio es una migración 1:1 de `criza/scientific_agent/pod_server.py` de RunPod a Modal.
> Todas las decisiones de diseño ya están tomadas. No hay entidades nuevas.

---

## 1. Identidad

| Pregunta | Respuesta |
|---|---|
| ¿Qué es? | Servidor HTTP que expone ESMFold para predicción de estructura proteica |
| ¿Problema? | RunPod requiere gestión manual del pod + $4.39/hr idle; Modal es serverless y auto-provisiona GPU solo cuando hay una request |
| ¿Usuarios? | `criza/scientific_agent` via `ESMFOLD_POD_URL` — contrato HTTP idéntico al RunPod |
| ¿Depende de? | Modal (hosting), Volume `esmfold-model-cache` (pesos ~14GB) |
| ¿Qué depende de él? | `esmfold_local.py` — cero cambios de código, solo cambio de URL en `.env` |
| ¿Milestone? | SEB-95 — cierra RunPod |

---

## 2. Trazabilidad

| Entidad | Origen | En código | Estado |
|---|---|---|---|
| `/predict` endpoint | `pod_server.py` línea 63 | `modal_app.py` | ✅ migrado |
| `/health` endpoint | `pod_server.py` línea 53 | `modal_app.py` | ✅ migrado |
| Carga de modelo (`esmfold_v1`) | `pod_server.py` línea 30 | `modal_app.py` | ✅ migrado |
| Caché de pesos | volumen RunPod (ephemeral) | Modal Volume `esmfold-model-cache` | ✅ mejorado |
| Output format | `pod_server.py` línea 121 | `modal_app.py` | ✅ idéntico |

---

## 3. Decisiones

| # | Pregunta | Decisión | Fecha |
|---|---|---|---|
| 1 | ¿GPU? | A10G (24GB VRAM, suficiente para ESMFold ~14GB, más barato que A100) | 2026-06-09 |
| 2 | ¿keep_warm? | No — cold start ~30-60s aceptable para uso esporádico | 2026-06-09 |
| 3 | ¿scaledown_window? | 300s — modelo permanece cargado 5 min, útil en sesiones con múltiples predicciones | 2026-06-09 |
| 4 | ¿Cambiar contrato HTTP? | No — `/predict` y `/health` idénticos a RunPod. `esmfold_local.py` no cambia | 2026-06-09 |
| 5 | ¿Dónde quedan los PDB? | El cliente (`esmfold_local.py`) guarda el PDB localmente. El servicio devuelve `pdb_content` en el response | 2026-06-09 |

---

## 4. Estado del gate

**Estado actual:** ✅ LISTO

*Migración directa. Cero decisiones abiertas.*
