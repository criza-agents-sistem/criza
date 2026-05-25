# Roadmap — Agente Científico CRIZA

> ⚠️ INSTRUCCIÓN PARA CLAUDE: Al iniciar cualquier sesión de desarrollo del agente científico,
> leer este archivo primero y mostrar el estado actual del roadmap antes de arrancar.
> Esto evita que trabajo planificado se pierda entre sesiones.

---

## Estado actual: v1.3 ✅

**Fecha de entrega:** Mayo 2026  
**Pipeline completo:**
```
Semantic Scholar (literatura) → UniProt (secuencia) → ESMFold (estructura + PDB)
→ analyze_stability (regiones débiles) → design_variants (candidatas rule-based)
→ [design_variants_mpnn] (ML, opcional) → [predict_tm_change] (FoldX, opcional)
→ compare_variants (validación computacional) → Brief técnico
```

### Herramientas activas

| Tool | Archivo | Estado | API / Método |
|---|---|---|---|
| `search_literature` | `tools/semantic_scholar.py` | ✅ Producción | Semantic Scholar API |
| `get_protein_sequence` | `tools/uniprot.py` | ✅ Producción | UniProt REST |
| `predict_structure` | `tools/esmfold.py` | ✅ Producción | ESM Atlas API (Meta) — 200aa |
| `analyze_stability` | `tools/stability.py` | ✅ Producción | Sin API — análisis pLDDT |
| `design_variants` | `tools/variants.py` | ✅ Producción | Rule-based (prolina, consenso) |
| `compare_variants` | `tools/compare.py` | ✅ Producción | ESMFold sobre variantes |
| `design_variants_mpnn` | `tools/mpnn.py` | ✅ Listo (opcional) | ProteinMPNN subprocess |
| `predict_tm_change` | `tools/foldx.py` | ✅ Listo (opcional) | FoldX CLI subprocess |

**Nota sobre herramientas opcionales:** `design_variants_mpnn` y `predict_tm_change` requieren software externo instalado (`PROTEINMPNN_PATH` y `FOLDX_PATH` en `.env`). Si no están configuradas, retornan `success=False` con instrucciones de setup — no interrumpen el análisis.

### Tests

| Suite | Tests | Estado |
|---|---|---|
| Unit tests | 80 tests | ✅ Todos pasando (`pytest`) |
| Integration tests | 24 tests | ✅ Disponibles (`pytest -m integration`) |

---

## v1.4 — Pendiente 🔲

### [SEB-79] ESMFold local — secuencias completas

**Por qué:** Actualmente analizamos solo los primeros 200 aa por limitaciones de la API pública. Proteínas largas (lactoferrina: 708 aa) se analizan parcialmente.

**Solución:** Correr ESMFold localmente via `fair-esm`
```python
# tools/esmfold_local.py
def predict_structure_local(sequence: str, protein_name: str) -> dict:
    # Usa fair-esm local — sin límite de longitud, sin timeout
    # Misma interfaz que predict_structure() para compatibilidad
```

**Estado:** 🔴 **Bloqueado** — decisión de infraestructura GPU pendiente con Pablo (Mayo 2026)

**Prerequisito:** GPU recomendada (Lambda Labs A10 24GB, ~$0.60/hr). Sin GPU, el cómputo toma 20-30 min por secuencia en CPU.

Ver documento: `C:\Users\sebab\Documents\Plataformas\KRIZA\infraestructura_computacional_etapas.md`

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
| v1.4 | Pendiente | ESMFold local (SEB-79) — bloqueado por decisión GPU. |
| v2 | Pendiente | Knowledge Module + multi-proteína + AF3. |
