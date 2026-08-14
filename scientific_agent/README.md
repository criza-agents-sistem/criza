# Agente Científico CRIZA

Analiza la viabilidad técnica de producir moléculas de alto valor por fermentación microbiana. Dado un objetivo de producción, ejecuta un pipeline computacional completo y entrega un brief técnico con hipótesis ya filtradas para que el laboratorio valide solo las más prometedoras.

**Versión actual:** v1.4.1 | **Estado:** Producción (M1)

---

## Qué hace

1. **Literatura** — Revisa 250M+ papers via OpenAlex
2. **Secuencia** — Recupera secuencia canónica desde UniProt
3. **Estructura** — Predice plegamiento 3D completo con ESMFold local (RunPod, sin límite de longitud)
4. **Estabilidad** — Identifica regiones térmicamente débiles
5. **Variantes** — Diseña candidatos termoestables (reglas + ML opcional)
6. **ΔTm** — Predice cambio en temperatura de desnaturalización (FoldX, opcional)
7. **Validación** — Compara variantes vs. wildtype computacionalmente
8. **Brief** — Síntesis estructurada con recomendaciones accionables para el laboratorio

El laboratorio recibe hipótesis priorizadas — no preguntas abiertas.

---

## Setup rápido

### Opción A — Python directo (recomendado para desarrollo)

```bash
git clone git@github-criza:criza-platform/scientific.git
cd scientific
python -m venv .venv && source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env        # completar ANTHROPIC_API_KEY
python run.py
```

### Opción B — Docker (recomendado para onboarding de equipo)

```bash
git clone git@github-criza:criza-platform/scientific.git
cd scientific
cp .env.example .env        # completar ANTHROPIC_API_KEY
docker compose build
docker compose run --rm scientific-agent
```

> Para onboarding completo (SSH, configuración, workflow de desarrollo) → **[docs/ONBOARDING.md](docs/ONBOARDING.md)**

---

## Pod RunPod — para análisis de proteínas largas (>200aa)

El pod está **APAGADO por defecto** para no gastar. Solo iniciarlo cuando sea necesario.

```bash
# 1. Iniciar pod en cloud.runpod.io → Pods → Start (mighty_brown_lark)
# 2. Esperar ~3-5 min hasta que ESMFold esté listo
# 3. Verificar:
curl https://qruo50jffhrgze-8000.proxy.runpod.net/health
# 4. Asegurarse que ESMFOLD_POD_URL está en .env
# 5. Al terminar → Stop el pod (~$4.39/hr mientras corre)
```

Sin el pod activo, el agente hace fallback automático a la API pública de ESMFold (máx 200aa).

---

## Herramientas disponibles (v1.4.1)

| Tool | API / Método | Propósito | Disponibilidad |
|------|-------------|-----------|----------------|
| `search_literature` | OpenAlex (→ Semantic Scholar fallback) | Literatura científica (250M+ papers) | Siempre |
| `get_protein_sequence` | UniProt REST | Secuencia y metadata de la proteína | Siempre |
| `predict_structure_local` | ESMFold local (RunPod) | Estructura completa, sin límite de longitud | Con pod activo |
| `predict_structure` | ESM Atlas API (Meta) | Estructura, max 200aa — fallback | Siempre |
| `analyze_stability` | Local | Mapeo de regiones inestables | Siempre |
| `design_variants` | Local (rule-based) | Variantes termoestables por reglas | Siempre |
| `compare_variants` | ESMFold | Validación computacional de variantes | Siempre |
| `design_variants_mpnn` | ProteinMPNN (ML) | Variantes por aprendizaje automático | Opcional* |
| `predict_tm_change` | FoldX CLI | ΔΔG y ΔTm por mutación | Opcional* |

*Requieren software externo. Ver `.env.example` para instrucciones de configuración.

---

## Tests

```bash
# Unit tests (rápidos, sin APIs externas) — recomendado
pytest

# Integration tests (requieren acceso a APIs)
pytest -m integration

# Todo
pytest -m ""
```

**Estado:** 110 unit tests ✅ | 32 integration tests ✅

---

## Output

Brief técnico estructurado con:

| Sección | Contenido |
|---------|-----------|
| Objetivo | Qué se analizó y por qué |
| ¿Se alcanzó? | Respuesta directa al objetivo planteado |
| Metodología | Pipeline ejecutado paso a paso |
| Análisis estructural | pLDDT completo, regiones débiles, Tm estimada |
| Variantes termoestables | Top candidatas con mutaciones y delta_pLDDT |
| Experimentos concretos | 3-5 experimentos priorizados para wet lab |
| Limitaciones | Qué no puede predecirse sin experimentación |
| Fuentes | Papers con DOI/URL verificables |

---

## Documentación

| Doc | Contenido |
|-----|-----------|
| [agents.md](agents.md) | Contexto activo del proyecto (estado, pendientes, estructura) |
| [ROADMAP.md](ROADMAP.md) | Versiones planificadas y estado de desarrollo |
| [docs/ONBOARDING.md](docs/ONBOARDING.md) | Setup completo para developers nuevos |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | Diseño técnico, APIs, decisiones de implementación |
| [docs/DECISIONS.md](docs/DECISIONS.md) | Log de decisiones arquitectónicas (ADR) |
| [docs/progress/](docs/progress/) | Registro de sesiones de trabajo |
