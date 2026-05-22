# Agente Científico CRIZA

Analiza la viabilidad técnica de producir proteínas de alto valor por fermentación microbiana. Diseña variantes termoestables y entrega un brief técnico con hipótesis ya filtradas para el laboratorio.

**Versión actual:** v1.1-0 | **Estado:** En desarrollo activo (M1)

---

## Qué hace

Dado un objetivo de producción (proteína + contexto del fermentador), el agente ejecuta un pipeline computacional completo:

1. **Literatura** — Revisa 200M+ papers via Semantic Scholar
2. **Secuencia** — Recupera secuencia canónica desde UniProt
3. **Estructura** — Predice plegamiento 3D con ESMFold (pLDDT por residuo)
4. **Estabilidad** — Identifica regiones térmicamente débiles
5. **Variantes** — Diseña candidatos termoestables (sustituciones de prolina, puentes disulfuro, consenso)
6. **Validación** — Compara variantes vs. wildtype computacionalmente
7. **Brief** — Síntesis estructurada con recomendaciones accionables para el laboratorio

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

Para onboarding completo (SSH, configuración, workflow de desarrollo) → ver **[ONBOARDING.md](ONBOARDING.md)**.

---

## Herramientas disponibles (v1.1)

| Tool | API | Propósito |
|------|-----|-----------|
| `search_literature` | Semantic Scholar | Literatura científica (200M+ papers) |
| `get_protein_sequence` | UniProt REST | Secuencia y metadata de la proteína |
| `predict_structure` | ESM Atlas (Meta) | Predicción estructural, pLDDT por residuo |
| `analyze_stability` | Local | Mapeo de regiones inestables |
| `design_variants` | Local | Diseño de variantes termoestables |
| `compare_variants` | ESM Atlas | Validación computacional de variantes |

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
| Variantes termoestables | Top 3 candidatas con mutaciones y delta_pLDDT |
| Experimentos concretos | 3-5 experimentos priorizados para wet lab |
| Limitaciones | Qué no puede predecirse sin experimentación |
| Fuentes | Papers con DOI/URL |

---

## Documentación

| Doc | Contenido |
|-----|-----------|
| [ONBOARDING.md](ONBOARDING.md) | Setup completo para developers nuevos |
| [ARCHITECTURE.md](ARCHITECTURE.md) | Diseño técnico, APIs, decisiones de implementación |
| [DECISIONS.md](DECISIONS.md) | Log de decisiones arquitectónicas (ADR) |
| [ROADMAP.md](ROADMAP.md) | Versiones planificadas y estado de desarrollo |
