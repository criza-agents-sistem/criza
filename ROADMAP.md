# Roadmap — Agente Científico CRIZA

> ⚠️ INSTRUCCIÓN PARA CLAUDE: Al iniciar cualquier sesión de desarrollo del agente científico,
> leer este archivo primero y mostrar el estado actual del roadmap antes de arrancar.
> Esto evita que trabajo planificado se pierda entre sesiones.

---

## 🖥️ Protocolo RunPod — LEER ANTES DE CADA ANÁLISIS

**El pod está APAGADO por defecto.** Sebas lo stopea después de cada uso para no gastar.

**Cuándo pedir que lo inicien:**
Cualquier tarea que involucre ESMFold en proteínas completas (>200 aa):
- Correr el agente con `predict_structure_local`
- `compare_variants` sobre variantes de proteínas largas
- Deployar cambios a `pod_server.py`

**Cómo pedirlo:**
> "Para este análisis necesito el pod RunPod. ¿Podés iniciarlo en cloud.runpod.io → Pods → Start?"

**Cuándo avisar que lo apaguen:**
- Al terminar el análisis o la sesión de trabajo con ESMFold
- Antes de cerrar sesión si el pod estuvo activo
> "Ya terminamos con el pod — podés hacer Stop en RunPod para no gastar."

**Datos del pod:**
- URL panel: cloud.runpod.io → Pods
- SSH: `ssh root@216.249.100.66 -p 20475 -i ~/.ssh/id_criza`  
  *(IP/puerto pueden cambiar si se Termina y re-deployea — siempre usar Stop)*
- Servidor ESMFold: `https://53yj64wek7otne-8000.proxy.runpod.net/health`
- Iniciar servidor en el pod: `nohup python3 /root/pod_server.py > /root/pod_server.log 2>&1 &`

**Costo:** ~$1.39/hr solo mientras está Running. Stopped = $0/hr (solo storage).

---

## Estado actual: v1.4 ✅

**Fecha de entrega:** Mayo 2026  
**Pipeline completo:**
```
Semantic Scholar (literatura) → UniProt (secuencia) → ESMFold local (estructura completa + PDB)
→ analyze_stability (regiones débiles) → design_variants (candidatas rule-based)
→ [design_variants_mpnn] (ML, opcional) → [predict_tm_change] (FoldX, opcional)
→ compare_variants (validación computacional) → Brief técnico
```

### Herramientas activas

| Tool | Archivo | Estado | API / Método |
|---|---|---|---|
| `search_literature` | `tools/semantic_scholar.py` | ✅ Producción | Semantic Scholar API |
| `get_protein_sequence` | `tools/uniprot.py` | ✅ Producción | UniProt REST |
| `predict_structure` | `tools/esmfold.py` | ✅ Producción | ESM Atlas API (Meta) — 200aa, fallback |
| `predict_structure_local` | `tools/esmfold_local.py` | ✅ Producción | fair-esm local — sin límite de longitud |
| `analyze_stability` | `tools/stability.py` | ✅ Producción | Sin API — análisis pLDDT |
| `design_variants` | `tools/variants.py` | ✅ Producción | Rule-based (prolina, consenso) |
| `compare_variants` | `tools/compare.py` | ✅ Producción | ESMFold sobre variantes |
| `design_variants_mpnn` | `tools/mpnn.py` | ✅ Listo (opcional) | ProteinMPNN subprocess |
| `predict_tm_change` | `tools/foldx.py` | ✅ Listo (opcional) | FoldX CLI subprocess |

**Nota sobre herramientas opcionales:** `design_variants_mpnn` y `predict_tm_change` requieren software externo instalado (`PROTEINMPNN_PATH` y `FOLDX_PATH` en `.env`). Si no están configuradas, retornan `success=False` con instrucciones de setup — no interrumpen el análisis.

**ESMFold local:** Requiere pod RunPod A100 activo (cloud.runpod.io). Si el pod está apagado, el agente hace fallback automático a `predict_structure` (API pública, 200aa). SSH: `ssh root@216.249.100.66 -p 20475 -i ~/.ssh/id_criza`

### Tests

| Suite | Tests | Estado |
|---|---|---|
| Unit tests | 95 tests | ✅ Todos pasando (`pytest`) |
| Integration tests | 24 tests | ✅ Disponibles (`pytest -m integration`) |

---

## v2 — Backlog 🗂️

### [v2-A] Integración con Knowledge Module

**Qué es:** Cargar documentación de laboratorios socios (protocolos, experimentos fallidos, condiciones optimizadas localmente) en la capa de conocimiento del agente.

**Impacto:** El agente aprende calibraciones y condiciones específicas del laboratorio socio. Crea ventaja competitiva no replicable — ningún modelo global tiene esa información.

**Prerequisito:** Diseño del Knowledge Module (tarea SEB-7 en Linear, en Backlog)

---

### [v2-B] Análisis multi-proteína en paralelo

**Qué es:** Dado un objetivo de producción, evaluar y comparar 3–5 proteínas candidatas simultáneamente en lugar de una sola.

**Caso de uso:** "Quiero producir una proteína antimicrobiana — ¿lactoferrina, lisozima o defensina es la mejor opción para mi fermentador?"

---

### [v2-C] AlphaFold 3 para análisis de interacciones

**Qué es:** AlphaFold 3 predice interacciones proteína-ligando, proteína-ADN, proteína-proteína — más relevante que ESMFold para casos donde la función depende de un cofactor.

**Limitación actual:** AF3 no tiene API programática pública. Accesible solo via web server manual (alphafoldserver.com). Código local disponible pero requiere GPU 40GB.

**Prerequisito:** Lambda Labs A100 40GB (Etapa 2 de infraestructura)

---

### [v2-D] Análisis económico integrado

**Qué es:** El agente calcula automáticamente COGS, margen estimado y payback period para cada proteína analizada.

---

## Registro de versiones

| Versión | Fecha | Cambios principales |
|---|---|---|
| v0 | Mayo 2026 | PubMed + UniProt + ESMFold. Brief técnico básico. |
| v1 | Mayo 2026 | + analyze_stability + design_variants + compare_variants. PDB persistido. |
| v1.1 | Mayo 2026 | Migración a Semantic Scholar. Coverage multi-dominio (200M+ papers). |
| v1.2 | Mayo 2026 | + design_variants_mpnn (ProteinMPNN). + predict_tm_change (FoldX). Herramientas opcionales con fallback graceful. |
| v1.3 | Mayo 2026 | Suite de tests completa: 80 unit + 24 integration. Reorganización docs/ outputs/. |
| v1.4 | Mayo 2026 | + predict_structure_local (fair-esm, sin límite de longitud). GPU: RunPod A100 80GB. 95 tests. |
| v2 | Pendiente | Knowledge Module + multi-proteína + AF3. |
