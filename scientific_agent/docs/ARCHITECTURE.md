# Arquitectura — Agente Científico CRIZA

**Versión:** v1.4.1 | **Última actualización:** Mayo 2026

## Visión general

El agente comprime el trabajo de diseño experimental que un laboratorio haría en meses a un análisis computacional de minutos. No reemplaza el wet lab — entrega hipótesis filtradas para que el laboratorio valide solo las más prometedoras.

```
Usuario (objetivo de producción)
        ↓
   [ agent.py ]  ←→  Claude claude-sonnet-4-5 (razonamiento)
        ↓
  ┌─────────────────────────────────────────────────────────┐
  │                   Tools (8 herramientas)                │
  │                                                         │
  │  OpenAlex → UniProt → ESMFold local (RunPod)             │
  │  analyze_stability → design_variants                    │
  │  → [design_variants_mpnn] → [predict_tm_change]         │
  │  → compare_variants                                     │
  └─────────────────────────────────────────────────────────┘
        ↓
   Brief técnico (texto estructurado)
```

Herramientas entre `[ ]` son opcionales: requieren software externo instalado. Si no están disponibles, retornan `success=False` con instrucciones de setup sin interrumpir el análisis.

---

## El loop agéntico

El agente corre en un loop `while True` usando la API de Anthropic con tool use:

```
1. Enviar mensajes + tools disponibles a Claude
2. Claude decide qué tool llamar (o terminar)
3. Si stop_reason == "tool_use" → ejecutar tool → agregar resultado → volver a 1
4. Si stop_reason == "end_turn" → retornar el texto final
```

Claude decide el orden y cantidad de llamadas a tools. El workflow mandatorio está estructurado en el system prompt, no hardcodeado en el loop — esto permite que el agente adapte la estrategia según lo que encuentre en la literatura.

### Por qué este diseño

- **Flexibilidad:** Si una proteína tiene poca literatura, Claude puede hacer más búsquedas. Si ya hay evidencia clara, puede avanzar más rápido.
- **Transparencia:** Cada tool call se loguea en consola (modo `verbose=True`) — el usuario ve exactamente qué buscó el agente y en qué orden.
- **Extensibilidad:** Agregar una nueva herramienta es declarar su schema en `TOOLS` y agregar el dispatch en `dispatch_tool()`. El loop no cambia.

---

## Workflow mandatorio

El system prompt instruye al agente a seguir este orden:

```
1. LITERATURE SCAN  → mínimo 3 búsquedas en OpenAlex (queries distintos)
2. SEQUENCE         → recuperar secuencia del candidato más prometedor (UniProt)
3. STRUCTURE LOCAL  → predicción ESMFold completa via RunPod (sin límite de longitud)
                      Fallback si pod apagado: predict_structure con primeros 200aa
4. STABILITY        → identificar weak regions con per-residue pLDDT
5. VARIANTS         → diseñar candidatas termoestables (rule-based)
6. [MPNN]           → si ProteinMPNN disponible, diseñar variantes adicionales por ML
7. [FOLDX]          → si FoldX disponible, calcular ΔΔG y ΔTm de variantes top
8. COMPARE          → validar variantes vs wildtype via ESMFold
9. BRIEF            → síntesis del output final
```

---

## Herramientas

### `search_literature` — OpenAlex API (primaria desde v1.4.1)

**Qué hace:** Busca papers científicos para fundamentar recomendaciones de sistemas de expresión, condiciones de fermentación y estabilidad térmica.

**Input:** `query: str`, `max_results: int = 10`

**Output:** `{query, total_found, returned, results: [{title, abstract, year, journal, authors, url, doi, citation_count}], source}`

**API primaria:** `https://api.openalex.org/works`
- Gratuita, sin API key
- Rate limit: 10 req/seg en polite pool (pasar `mailto=` en header)
- Abstract reconstruido desde inverted index (`_reconstruct_abstract()`)

**Fallback automático:** Si OpenAlex retorna 429/503 o timeout → `tools/semantic_scholar.py`
- Semantic Scholar: 100 req/5min sin key, 1 req/seg con `SEMANTIC_SCHOLAR_API_KEY`

**Por qué OpenAlex sobre Semantic Scholar:** SS tenía rate limiting persistente que degradaba el agente silenciosamente — caía a conocimiento interno de Claude sin notificar. OpenAlex tiene los mismos 200M+ papers con límites 10x más generosos.

**Historial:** PubMed (v1.0) → Semantic Scholar (v1.1) → OpenAlex (v1.4.1)

**Limitaciones:** Solo abstracts (no texto completo). Algunos papers muy recientes pueden no estar indexados.

---

### `get_protein_sequence` — UniProt REST API

**Qué hace:** Recupera la secuencia aminoacídica canónica y metadata funcional de la proteína objetivo.

**Input:** `protein_name: str`, `organism: str = None`

**Output:** `{protein_queried, organism_filter, results: [{accession, name, organism, length, sequence, function, url}]}`

**API:** `https://rest.uniprot.org/uniprotkb/search`

**Decisiones de implementación:**
- Prioriza entradas Swiss-Prot (`reviewed:true`) — curadas manualmente, más confiables que TrEMBL
- Fallback sin filtro si no hay entradas revisadas
- Campos solicitados: `accession, protein_name, sequence, organism_name, length` (campos más amplios daban error 400 en la API REST v2)

---

### `predict_structure_local` — ESMFold local via RunPod (primaria desde v1.4)

**Qué hace:** Predice estructura 3D completa usando ESMFold corriendo en un pod RunPod. Sin límite de longitud de secuencia.

**Input:** `sequence: str`, `protein_name: str`

**Output:** Idéntico a `predict_structure` — compatible con todos los tools downstream.

**Infraestructura:** Pod `qruo50jffhrgze` (mighty_brown_lark) — H200 SXM 141GB, US-CA-2. El pod está APAGADO por defecto — Sebas lo inicia antes de cada análisis con proteínas largas.

**Fallback:** Si `ESMFOLD_POD_URL` no está configurado o el pod no responde → retorna `structure_obtained=False` con instrucciones. El agente entonces usa `predict_structure` (API pública, 200aa).

**Variable de entorno:** `ESMFOLD_POD_URL=https://qruo50jffhrgze-8000.proxy.runpod.net`

**Decisión crítica de implementación:** `ESMFOLD_POD_URL` se lee en runtime con `_get_pod_url()`, nunca al importar el módulo. Esto evita el bug donde `load_dotenv()` corría después del import y la variable siempre quedaba vacía.

**Velocidad:** ~30-60s por proteína en H200 SXM, sin límite de longitud.

---

### `predict_structure` — ESM Atlas API (Meta) — fallback

**Qué hace:** Predice el plegamiento 3D y evalúa la expresabilidad de la proteína. Retorna pLDDT por residuo y persiste el archivo PDB.

**Input:** `sequence: str`, `protein_name: str`

**Output:** `{protein_name, original_length, analyzed_length, truncated, avg_plddt, pct_residues_high_conf, confidence_level, expression_implication, pdb_path, per_residue_plddt}`

**API:** `https://api.esmatlas.com/foldSequence/v1/pdb/` (POST, gratuita, sin auth)

**Decisiones de implementación críticas:**

1. **Límite de 200 aa:** La API pública tiene timeout con secuencias más largas. 400 aa causaban error 504 consistentemente. Reducido a 200 aa para confiabilidad.

2. **Normalización de pLDDT:** La API retorna valores en escala 0–1 (no 0–100 como AlphaFold). Se detecta y normaliza automáticamente: `if max(scores) <= 1.0: scores = [v * 100 for v in scores]`

3. **Persistencia del PDB:** El archivo PDB se guarda en `structures/` y su path se retorna en el output — es el input requerido por ProteinMPNN y FoldX.

**Interpretación de pLDDT:**
- ≥ 90: muy alta confianza — estructura bien definida
- 70–90: alta — confiable con posibles regiones flexibles
- 50–70: media — regiones desordenadas presentes
- < 50: baja — probable proteína intrínsecamente desordenada

**Limitaciones:** Solo analiza los primeros 200 aa. Sin SLA — API pública puede tener downtime.

---

### `analyze_stability` — análisis local de pLDDT

**Qué hace:** Identifica regiones térmicamente débiles usando los scores pLDDT por residuo. Define regiones candidatas para ingeniería de termoestabilidad.

**Input:** `sequence: str`, `plddt_scores: list[float]`, `protein_name: str`, `avg_plddt: float = None`

**Output:** `{protein_name, avg_plddt, weak_regions: [{start, end, avg_plddt, sequence}], n_weak_regions, stability_assessment}`

**Constantes clave:**
- `LOW_CONFIDENCE_THRESHOLD = 70.0` — residuos por debajo de este valor son candidatos
- `MIN_REGION_LENGTH = 4` — regiones menores de 4 residuos no se reportan (evita falsos positivos por ruido)

**Sin dependencias externas** — lógica pura sobre la lista de scores.

---

### `design_variants` — diseño rule-based de variantes

**Qué hace:** Diseña variantes termoestables usando reglas basadas en literatura publicada. Produce candidatos accionables para wet lab sin requerir software externo.

**Input:** `sequence: str`, `weak_regions: list[dict]`, `protein_name: str`, `n_variants: int = 5`

**Output:** `{protein_name, n_variants, variants: [{variant_id, sequence, mutations: [{position, from, to}], strategy, confidence}], design_notes}`

**Estrategias implementadas:**
1. **Sustituciones de prolina** en bucles — aumenta rigidez conformacional
2. **Mutaciones de consenso** — residuos más frecuentes en homólogos termoestables
3. **Variantes combinadas** — combina mutaciones de estrategia 1 y 2

**Sin dependencias externas** — reglas determinísticas, siempre disponible.

---

### `design_variants_mpnn` — diseño ML con ProteinMPNN *(opcional)*

**Qué hace:** Usa ProteinMPNN (Dauparas et al., Science 2022) para explorar el espacio de secuencias de forma más amplia que el diseño rule-based. Puede descubrir variantes no obvias.

**Input:** `pdb_path: str`, `protein_name: str`, `n_sequences: int = 10`, `temperature: float = 0.1`

**Output (éxito):** `{success: True, protein_name, sequences: [{sequence, score, global_score, mutations, confidence}], ...}`

**Output (sin instalar):** `{success: False, setup_instructions, fallback}`

**Requiere:** `PROTEINMPNN_PATH` en `.env` apuntando al directorio del repo clonado de ProteinMPNN.

**Parámetros clave:**
- `temperature`: controla diversidad — valores bajos (0.1) producen variantes más conservadoras, valores altos (0.5) producen mayor diversidad
- `score`: negative log-likelihood — menor es mejor (más probable bajo el modelo)
- `n_sequences`: clampeado a [1, 100]

**Fallback graceful:** Si no está configurado, retorna instrucciones de setup detalladas. El análisis continúa con `design_variants` rule-based.

---

### `predict_tm_change` — predicción ΔΔG/ΔTm con FoldX *(opcional)*

**Qué hace:** Calcula el cambio de energía libre de plegamiento (ΔΔG) para cada variante y estima el cambio en temperatura de desnaturalización (ΔTm).

**Input:** `wildtype_pdb: str`, `variants: list[dict]`, `protein_name: str`, `wildtype_tm: float = None`

**Output (éxito):** `{success: True, protein_name, results: [{variant_id, ddg, delta_tm, verdict, priority}], ...}`

**Output (sin instalar):** `{success: False, setup_instructions, fallback}`

**Requiere:** `FOLDX_PATH` en `.env` apuntando al binario de FoldX.

**Pipeline interno:**
1. `RepairPDB` sobre el wildtype (normaliza geometría)
2. `BuildModel` por variante con el archivo de mutaciones en formato FoldX
3. Parseo de `Average_BuildModel_*.fxout` → ΔΔG = G_mutant − G_wildtype

**Convenciones:**
- **ΔΔG negativo** = mutante más estable que wildtype (estabilizante)
- **ΔTm ≈ −ΔΔG × 1.7 °C·mol/kcal** (aproximación empírica, Guerois et al.)
- Prioridad 1: `ΔΔG < −2.0` | Prioridad 2: `< −0.5` | Prioridad 3: `≤ +0.5` | Prioridad 4: `≤ +2.0` | Prioridad 5: `> +2.0`

**Fallback graceful:** Si FoldX no está instalado, retorna instrucciones de setup. El análisis continúa sin predicción de ΔTm.

---

### `compare_variants` — validación computacional

**Qué hace:** Corre ESMFold sobre cada variante y compara el pLDDT resultante contra el wildtype. Rankea variantes por mejora estructural.

**Input:** `wildtype_sequence: str`, `variants: list[dict]`, `protein_name: str`

**Output:** `{protein_name, wildtype_plddt, results: [{variant_id, avg_plddt, delta_plddt, verdict, lab_candidate}], lab_candidates, summary}`

**Criterio de selección:** Una variante es "lab candidate" si su `delta_plddt > 0`. El brief final incluye solo las `lab_candidates`.

---

## Estructura de carpetas

```
scientific_agent/
├── agent.py              ← loop agéntico + tool dispatch + system prompt
├── run.py                ← CLI de entrada (casos preconfigurados)
├── README.md             ← entry point para developers
├── ROADMAP.md            ← estado de desarrollo (fuente de verdad)
├── pytest.ini            ← config de tests
├── requirements.txt      ← dependencias de producción
├── requirements-dev.txt  ← pytest + pytest-mock (no en producción)
├── Dockerfile            ← imagen de producción
├── docker-compose.yml    ← orquestación local
│
├── docs/                 ← documentación técnica
│   ├── ARCHITECTURE.md   ← este archivo
│   ├── DECISIONS.md      ← log ADR
│   └── ONBOARDING.md     ← setup para developers nuevos
│
├── tools/                ← herramientas del agente (una por archivo)
│   ├── semantic_scholar.py
│   ├── uniprot.py
│   ├── esmfold.py
│   ├── stability.py
│   ├── variants.py
│   ├── mpnn.py
│   ├── foldx.py
│   ├── compare.py
│   └── pubmed.py         ← legacy fallback
│
├── tests/                ← suite de tests
│   ├── conftest.py       ← fixtures compartidas
│   ├── test_stability.py
│   ├── test_variants.py
│   ├── test_foldx.py
│   ├── test_mpnn.py
│   ├── test_compare.py
│   ├── test_esmfold.py
│   ├── test_uniprot.py
│   └── test_semantic_scholar.py
│
├── structures/           ← PDB generados por ESMFold
└── outputs/              ← briefs y demos generados (no son código)
```

---

## System prompt

El system prompt cumple tres funciones:

1. **Contexto del productor:** Las condiciones del fermentador de Andrés están hardcodeadas en el prompt. Esto orienta todas las recomendaciones sin que el usuario tenga que repetirlo en cada query.

2. **Workflow mandatorio:** Instrucciones explícitas sobre el orden de los pasos y el mínimo de búsquedas requeridas.

3. **Template de output:** La estructura del brief está definida en el prompt. Esto garantiza consistencia entre análisis.

---

## Decisiones de diseño

Ver `docs/DECISIONS.md` para el log completo en formato ADR. Resumen:

| Decisión | Elección | Razón |
|---|---|---|
| Fuente bibliográfica | OpenAlex (v1.4.1) | 200M+ papers, 10 req/seg, sin rate limiting. SS tenía límites que degradaban el agente silenciosamente |
| Motor de razonamiento | Claude (tool use) | Conocimiento científico nativo, loop adaptativo |
| Arquitectura | Loop agéntico | Flexible según cantidad de literatura disponible |
| ESMFold sin límite | RunPod H200 SXM | predict_structure_local analiza proteínas completas (708aa lactoferrina = 85.78 pLDDT) |
| Env vars lazy loading | `_get_pod_url()` en runtime | Bug histórico: module-level `os.getenv()` evaluado antes de `load_dotenv()` siempre retornaba `""` |
| Herramientas opcionales | Fallback graceful | No romper el pipeline si falta software externo |
| Entorno | Docker + Python directo | Docker para onboarding de equipo; Python directo para desarrollo diario |

---

## Limitaciones del sistema (v1.4.1)

| Limitación | Impacto | Solución planeada |
|---|---|---|
| Pod RunPod manual | Hay que iniciarlo antes de cada análisis con proteínas largas | SEB-95: migración a RunPod Serverless o Modal |
| ProteinMPNN requiere instalación manual | Tool opcional, no en producción base | `.env.example` con instrucciones detalladas |
| FoldX requiere licencia + binario | Tool opcional, retorna estimaciones sin configurar | SEB-94: registrarse en foldxsuite.crg.eu y subir binario al pod |
| OpenAlex/SS solo abstracts | Puede perder datos en texto completo | Aceptable para v1; mejora futura |
| ESM Atlas sin SLA (fallback) | API pública puede fallar | Fallback documentado; usar pod RunPod para producción |
| ΔTm es aproximación empírica | Error ±2–3°C típico | Suficiente para filtrar hipótesis; wet lab confirma |
| Anthropic 30k tokens/min | Análisis con muchas búsquedas puede hacer rate limit | Retry con backoff implementado en agent.py |
