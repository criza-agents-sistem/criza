# DECISIONS.md — Log de decisiones arquitectónicas

Registro de decisiones técnicas relevantes en formato ADR (Architecture Decision Record).
Cada decisión incluye contexto, opciones evaluadas y razón de la elección.

---

## ADR-001 — Semantic Scholar como fuente bibliográfica principal

**Fecha:** Mayo 2026  
**Estado:** Activo

**Contexto:**  
El agente necesita revisar literatura científica para fundamentar recomendaciones de sistemas de expresión, condiciones de fermentación y estabilidad térmica.

**Opciones evaluadas:**
- PubMed (NCBI E-utilities) — cobertura biomédica, API estable
- Semantic Scholar — 200M+ papers, todos los dominios, API gratuita

**Decisión:** Semantic Scholar  

**Razón:**  
Para análisis de sweet spot de fermentación de precisión necesitamos cubrir química, ciencias de alimentos, materiales y contexto económico de mercado — dominios fuera de PubMed. Semantic Scholar los cubre con la misma calidad de API. PubMed se mantiene en `tools/pubmed.py` como fallback.

**Consecuencias:**  
Rate limit sin API key: 100 req/5min. Suficiente para uso normal del agente (3-5 búsquedas por análisis). Agregar `SEMANTIC_SCHOLAR_API_KEY` en `.env` para 1 req/seg.

---

## ADR-002 — Loop agéntico vs. pipeline determinístico

**Fecha:** Mayo 2026  
**Estado:** Activo

**Contexto:**  
El agente necesita ejecutar múltiples herramientas en orden para producir un brief técnico. Hay dos enfoques: pipeline fijo (siempre hace A→B→C→D) o loop agéntico donde Claude decide qué herramienta llamar.

**Opciones evaluadas:**
- Pipeline determinístico — orden hardcodeado, predecible
- Loop agéntico (tool use) — Claude decide el orden y cantidad de llamadas

**Decisión:** Loop agéntico  

**Razón:**  
Proteínas con mucha literatura necesitan menos búsquedas; proteínas poco estudiadas necesitan más. Un pipeline fijo no puede adaptarse. El workflow mandatorio se define en el system prompt como guía, no como código — Claude lo sigue pero puede adaptarse si encuentra algo inesperado. El loop no cambia al agregar nuevas herramientas.

**Consecuencias:**  
El agente es menos predecible en tiempo de ejecución. En compensación, el `verbose=True` loguea cada tool call en tiempo real para trazabilidad completa.

---

## ADR-003 — ESMFold limitado a 200 aa

**Fecha:** Mayo 2026  
**Estado:** Activo (deuda técnica — resolver en SEB-79)

**Contexto:**  
ESMFold via API pública (api.esmatlas.com) tiene timeout con secuencias largas.

**Opciones evaluadas:**
- Pasar secuencia completa — causa timeout 504 en proteínas > 400 aa
- Truncar a 400 aa — inestable en la API pública
- Truncar a 200 aa — confiable, cubre región N-terminal
- ESMFold local (Docker + GPU) — sin límite, pero requiere hardware

**Decisión:** Truncar a 200 aa para API pública  

**Razón:**  
Confiabilidad sobre completitud. La región N-terminal contiene la mayoría de los motivos de señal y dominios estructuralmente críticos para expresión. Para proteínas donde la región analizada es insuficiente, el agente lo documenta explícitamente en el brief.

**Consecuencias:**  
Solo analiza el N-terminal de proteínas largas. ESMFold local (SEB-79) resolverá esto cuando se implemente con GPU.

---

## ADR-004 — Docker como entorno de desarrollo estándar

**Fecha:** Mayo 2026  
**Estado:** Activo

**Contexto:**  
Con múltiples developers potenciales en diferentes sistemas operativos, se necesita un entorno reproducible.

**Decisión:** Docker + Docker Compose obligatorio  

**Razón:**  
Elimina el problema "funciona en mi máquina". Especialmente crítico para componentes futuros con dependencias complejas (ESMFold local, graph DB, modelos de ML). El volumen `.:/app` permite hot reload sin rebuild para desarrollo fluido.

**Consecuencias:**  
Requiere Docker Desktop instalado. Para GPU (ESMFold local), agregar NVIDIA Container Toolkit. El overhead inicial de aprender Docker se amortiza rápido con el equipo.

---

## ADR-005 — Multi-repo por dominio de negocio

**Fecha:** Mayo 2026  
**Estado:** Activo

**Contexto:**  
La plataforma CRIZA tiene múltiples dominios (biotech, DPN) con potenciales developers externos distintos por dominio. GitHub no tiene control de acceso por carpeta dentro de un repo.

**Opciones evaluadas:**
- Monorepo — todo en `criza-platform/criza`, simple pero sin aislamiento
- Multi-repo por dominio — repos separados, acceso controlado por repo

**Decisión:** Multi-repo

```
criza-platform/scientific  ← este repo
criza-platform/dpn         ← cuando salga del backlog
criza-platform/core        ← Knowledge Module + Orchestration (M2)
```

**Razón:**  
Un developer externo de biotech no debe ver el código del dominio DPN (y viceversa). Con monorepo, cualquier contributor con acceso al repo ve todo. Los repos se comunican via API interna (core como servicio), no compartiendo código.

**Consecuencias:**  
Cuando `core` exista, `scientific` lo llamará via HTTP — el dev no necesita ver el código del core, solo el contrato de API. Mayor complejidad de gestión compensada por aislamiento real de dominios.

---

## ADR-007 — Herramientas opcionales con fallback graceful

**Fecha:** Mayo 2026  
**Estado:** Activo

**Contexto:**  
ProteinMPNN y FoldX requieren instalación manual y, en el caso de FoldX, registro en un sitio externo. No pueden incluirse en `requirements.txt` ni instalarse automáticamente. El agente no puede depender de su presencia para funcionar.

**Opciones evaluadas:**
- Hacer las herramientas obligatorias — rompe el pipeline si no están instaladas
- Omitirlas del agente — el agente pierde capacidades
- Integrarlas con fallback graceful — el agente las usa si están disponibles, continúa sin ellas si no lo están

**Decisión:** Fallback graceful

**Implementación:**
```python
def design_variants_mpnn(pdb_path, protein_name, ...):
    mpnn_path = _find_proteinmpnn()
    if not mpnn_path:
        return {
            "success": False,
            "setup_instructions": "...",
            "fallback": "Usar design_variants() rule-based"
        }
    # ... resto de la lógica
```

**Razón:**  
El pipeline base (sin ProteinMPNN ni FoldX) es ya científicamente válido. Las herramientas opcionales mejoran la calidad del análisis pero no son prerequisito. Bloquear el pipeline por software no instalado sería un error de UX. El agente reporta en el brief cuando una herramienta no estaba disponible.

**Consecuencias:**  
El system prompt instruye al agente a intentar las herramientas opcionales y reportar su resultado en el brief. `.env.example` documenta cómo instalar cada herramienta opcional.

---

## ADR-006 — Variantes proteicas como hipótesis computacionales

**Fecha:** Mayo 2026  
**Estado:** Activo

**Contexto:**  
El agente diseña variantes de proteínas para mejorar termoestabilidad. ¿Cómo presentar estos resultados?

**Decisión:** Presentar variantes como hipótesis computacionales explícitas, no como resultados

**Razón:**  
Las variantes diseñadas (ej. G12P+M1L para lactoferrina) no existen en ningún paper — son propuestas originales del agente. El laboratorio confirma o refuta estas hipótesis con wet lab. Presentarlas como "resultados" sería científicamente incorrecto y generaría expectativas erróneas. El brief siempre incluye una sección "Limitaciones del análisis computacional".

**Consecuencias:**  
El valor del agente es claro: comprime el espacio de hipótesis de meses de exploración a minutos de análisis. El laboratorio valida solo las más prometedoras — no explora a ciegas.
