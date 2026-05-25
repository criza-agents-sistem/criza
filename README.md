# Agente Científico CRIZA

Analiza la viabilidad técnica de producir proteínas de alto valor por fermentación microbiana. Diseña variantes termoestables y entrega un brief técnico con hipótesis ya filtradas para el laboratorio.

**Versión actual:** v1.3 | **Estado:** Producción (M1)

---

## Qué hace

Dado un objetivo de producción (proteína + contexto del fermentador), el agente ejecuta un pipeline computacional completo:

1. **Literatura** — Revisa 200M+ papers via Semantic Scholar
2. **Secuencia** — Recupera secuencia canónica desde UniProt
3. **Estructura** — Predice plegamiento 3D con ESMFold (pLDDT por residuo)
4. **Estabilidad** — Identifica regiones térmicamente débiles
5. **Variantes** — Diseña candidatos termoestables (reglas + ML opcional)
6. **ΔTm** — Predice cambio en temperatura de desnaturalización (FoldX, opcional)
7. **Validación** — Compara variantes vs. wildtype computacionalmente
8. **Brief** — Síntesis estructurada con recomendaciones accionables para el laboratorio

El laboratorio recibe hipótesis priorizadas — no preguntas abiertas.

---

## Inicio rápido

**Prerequisito:** Docker Desktop corriendo.

```bash
git clone git@github-criza:criza-platform/scientific.git
cd scientific
cp .env.example .env        # completar ANTHROPIC_API_KEY
docker compose build
docker compose run --rm scientific-agent
```

Para onboarding completo (SSH, configuración, workflow de desarrollo) → ver **[docs/ONBOARDING.md](docs/ONBOARDING.md)**.

---

## Herramientas disponibles (v1.3)

| Tool | API / Método | Propósito | Disponibilidad |
|------|-------------|-----------|----------------|
| `search_literature` | Semantic Scholar | Literatura científica (200M+ papers) | Siempre |
| `get_protein_sequence` | UniProt REST | Secuencia y metadata de la proteína | Siempre |
| `predict_structure` | ESM Atlas (Meta) | Predicción estructural, pLDDT por residuo | Siempre |
| `analyze_stability` | Local | Mapeo de regiones inestables | Siempre |
| `design_variants` | Local (rule-based) | Variantes termoestables por reglas | Siempre |
| `compare_variants` | ESM Atlas | Validación computacional de variantes | Siempre |
| `design_variants_mpnn` | ProteinMPNN (ML) | Variantes por aprendizaje automático | Opcional* |
| `predict_tm_change` | FoldX CLI | ΔΔG y ΔTm por mutación | Opcional* |

*Requieren software externo. Ver `.env.example` para instrucciones de configuración.

---

## Tests

```bash
# Unit tests (rápidos, sin APIs externas) — default
pytest

# Integration tests (requieren acceso a APIs)
pytest -m integration

# Todo
pytest -m ""
```

**Estado:** 80 unit tests ✅ | 24 integration tests ✅

---

## Output

Brief técnico estructurado con:

| Sección | Contenido |
|---------|-----------|
| Proteína analizada | Nombre, función, justificación como candidata |
| Sistema de expresión | Host microbiano con evidencia bibliográfica |
| Condiciones de fermentación | Temperatura, pH, medio, inductor, tiempo |
| Compatibilidad con el setup | Fit, adaptaciones requeridas, riesgos reales |
| Rendimiento esperado | Rango en g/L basado en literatura |
| Análisis estructural | pLDDT wildtype, regiones débiles, Tm estimada |
| Variantes termoestables | Top candidatas con mutaciones y delta_pLDDT |
| Experimentos concretos | 3-5 experimentos priorizados para wet lab |
| Limitaciones | Qué no puede predecirse sin experimentación |
| Fuentes | Papers con DOI/URL |

---

## Documentación

| Doc | Contenido |
|-----|-----------|
| [docs/ONBOARDING.md](docs/ONBOARDING.md) | Setup completo para developers nuevos |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | Diseño técnico, APIs, decisiones de implementación |
| [docs/DECISIONS.md](docs/DECISIONS.md) | Log de decisiones arquitectónicas (ADR) |
| [ROADMAP.md](ROADMAP.md) | Versiones planificadas y estado de desarrollo |
