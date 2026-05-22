# Arquitectura — Agente Científico CRIZA

## Visión general

El agente comprime el trabajo de diseño experimental que un laboratorio haría en meses a un análisis computacional de minutos. No reemplaza el wet lab — entrega hipótesis filtradas para que el laboratorio valide solo las más prometedoras.

```
Usuario (objetivo de producción)
        ↓
   [ agent.py ]  ←→  Claude claude-sonnet-4-5 (razonamiento)
        ↓
  ┌──────────────────────────────────────────────────┐
  │              Tools (APIs externas)               │
  │                                                  │
  │  Semantic Scholar → UniProt → ESMFold            │
  │  analyze_stability → design_variants →           │
  │  compare_variants                                │
  └──────────────────────────────────────────────────┘
        ↓
   Brief técnico (texto estructurado)
```

---

## El loop agéntico

El agente corre en un loop `while True` usando la API de Anthropic con tool use:

```
1. Enviar mensajes + tools disponibles a Claude
2. Claude decide qué tool llamar (o terminar)
3. Si stop_reason == "tool_use" → ejecutar tool → agregar resultado → volver a 1
4. Si stop_reason == "end_turn" → retornar el texto final
```

Claude decide el orden y cantidad de llamadas a tools. El workflow mandatorio está instruccturado en el system prompt, no hardcodeado en el loop — esto permite que el agente adapte la estrategia según lo que encuentre en la literatura.

### Por qué este diseño

- **Flexibilidad:** Si una proteína tiene poca literatura, Claude puede hacer más búsquedas. Si ya hay evidencia clara, puede avanzar más rápido.
- **Transparencia:** Cada tool call se loguea en consola (modo `verbose=True`) — el usuario ve exactamente qué buscó el agente y en qué orden.
- **Extensibilidad:** Agregar una nueva herramienta es declarar su schema en `TOOLS` y agregar el dispatch en `dispatch_tool()`. El loop no cambia.

---

## Workflow mandatorio

El system prompt instruye al agente a seguir este orden:

```
1. LITERATURE SCAN  → mínimo 3 búsquedas en Semantic Scholar (queries distintos)
2. SEQUENCE         → recuperar secuencia del candidato más prometedor
3. STRUCTURE        → predicción ESMFold (pasar solo primeros 200 aa — límite confiable)
4. STABILITY        → identify weak regions con per-residue pLDDT
5. VARIANTS         → diseñar candidatas termoestables
6. COMPARE          → validar variantes vs wildtype via ESMFold
7. BRIEF            → síntesis del output final
```

### Por qué este orden

- **Semantic Scholar primero:** El host recomendado y las condiciones de fermentación deben estar respaldados por evidencia publicada, no por conocimiento general del modelo. Semantic Scholar (200M+ papers) reemplaza PubMed desde v1.1-0 — cubre biotech, química, ciencias de alimentos y mercados.
- **UniProt después de literatura:** La elección de qué proteína recuperar depende de lo que la literatura indica como candidato más prometedor.
- **ESMFold al final:** La predicción estructural es un dato de apoyo, no una decisión — se usa para validar que la proteína es "expresable", no para elegir el host.
- **Brief al final:** Síntesis de todo lo anterior. El modelo no puede escribir el brief sin haber ejecutado los pasos previos.

---

## Herramientas

### `search_literature` — Semantic Scholar API *(desde v1.1-0)*

**Propósito:** Revisar la literatura científica disponible sobre el sistema de expresión, condiciones de fermentación, rendimientos reportados y contexto de mercado.

**API:** `https://api.semanticscholar.org/graph/v1/paper/search`
- Gratuita sin API key: 100 req/5min
- Con `SEMANTIC_SCHOLAR_API_KEY` en `.env`: 1 req/seg

**Por qué Semantic Scholar y no PubMed:**
- Cubre 200M+ papers de todos los dominios (vs. PubMed que es solo biomédico)
- Para análisis de sweet spot de fermentación de precisión necesitamos química, ciencias de alimentos, materiales y economía — dominios fuera de PubMed
- Retorna DOI, PDF open access, citation count — metadatos más ricos
- PubMed se mantiene en `tools/pubmed.py` como fallback/referencia

**Limitaciones conocidas:**
- Rate limit sin API key: 100 req/5min (suficiente para el agente en uso normal)
- Solo retorna abstracts, no texto completo
- Algunos papers muy recientes pueden no estar indexados aún

**Output:** `{query, total_found, returned, results: [{title, abstract, year, journal, authors, url, doi, pmid, pdf_url, citation_count, paper_id}]}`

---

### `get_protein_sequence` — UniProt REST API

**Propósito:** Recuperar la secuencia aminoacídica canónica y metadata funcional de la proteína objetivo.

**API:** `https://rest.uniprot.org/uniprotkb/search`

**Decisiones de implementación:**
- Prioriza entradas Swiss-Prot (`reviewed:true`) — son curadas manualmente y más confiables que TrEMBL
- Si no hay entradas revisadas, hace fallback sin filtro
- Campos solicitados: `accession, protein_name, sequence, organism_name, length` — un intento previo con más campos (`cc_function`, `ft_signal`, `annotation_score`) devolvía error 400 porque no todos son válidos en la API REST v2

**Por qué UniProt y no NCBI Protein:**
- Base de datos canónica para secuencias de proteínas
- Anotación funcional más rica y curada
- Mejor coverage de proteínas de organismos no modelo

**Output:** `{protein_queried, organism_filter, results: [{accession, name, organism, length, sequence, function, has_signal_peptide, url, note}]}`

---

### `predict_structure` — ESM Atlas API (Meta)

**Propósito:** Evaluar si la proteína tiene alta probabilidad de plegarse correctamente en un sistema de expresión microbiano.

**API:** `https://api.esmatlas.com/foldSequence/v1/pdb/` (POST, gratuita, sin auth)

**Output de la API:** Archivo PDB con scores pLDDT en la columna B-factor

**Decisiones de implementación críticas:**

1. **Límite de 200 aa (no 400):** La API pública de ESM Atlas tiene timeout con secuencias más largas. En pruebas, 400 aa causaban error 504 consistentemente. El límite se redujo a 200 aa para confiabilidad.

2. **Normalización de pLDDT:** La API retorna valores en escala 0–1 (no 0–100 como AlphaFold). Se detecta automáticamente y se normaliza: `if max(scores) <= 1.0: scores = [v * 100 for v in scores]`

3. **Interpretación estándar AlphaFold/ESMFold:**
   - ≥ 90: muy alta confianza — estructura bien definida
   - 70–90: alta — confiable con posibles regiones flexibles
   - 50–70: media — regiones desordenadas presentes
   - < 50: baja — probable proteína intrínsecamente desordenada

**Por qué ESMFold y no AlphaFold 3:**
- AlphaFold 3 es más preciso para interacciones proteína-ligando, pero los pesos del modelo no son públicos — solo accessible via web server manual
- ESMFold tiene API programática, necesaria para un agente autónomo
- Para el propósito de este agente (evaluar expresabilidad, no docking), ESMFold es suficiente

**Limitaciones:**
- Solo analiza los primeros 200 aa de proteínas largas
- No predice glicosilación ni modificaciones post-traduccionales
- No estima temperatura de desnaturalización (Tm)
- API pública sin SLA — puede tener downtime

**Output:** `{protein_name, original_length, analyzed_length, truncated, avg_plddt, pct_residues_high_conf, confidence_level, expression_implication, note}`

---

## System prompt

El system prompt cumple tres funciones:

1. **Contexto del productor:** Las condiciones del fermentador de Andrés están hardcodeadas en el prompt. Esto orienta todas las recomendaciones (temperatura, pH, organismos GRAS, etc.) sin que el usuario tenga que repetirlo en cada query.

2. **Workflow mandatorio:** Instrucciones explícitas sobre el orden de los pasos y el mínimo de búsquedas requeridas.

3. **Template de output:** La estructura del brief está definida en el prompt como secciones con headers. Esto garantiza consistencia entre análisis y facilita comparar resultados de diferentes proteínas.

---

## Decisiones de diseño

### Por qué Claude como motor de razonamiento

El modelo ya tiene conocimiento científico extenso en bioquímica, biología molecular y biotecnología de producción. Las herramientas le dan acceso a datos en tiempo real (literatura reciente, secuencias actualizadas) — no le enseñan ciencia. La distinción importa: no necesitamos "entrenar" al agente en proteínas, necesitamos darle acceso a la información específica del problema.

### Por qué no un pipeline determinístico

Un pipeline fijo (siempre busca X, siempre hace Y) sería más predecible pero menos útil. Proteínas con mucha literatura necesitan menos búsquedas; proteínas poco estudiadas necesitan más. El agente adapta la cantidad y enfoque de las búsquedas según lo que encuentra.

### Por qué guardar el output en archivo

El análisis puede tomar varios minutos y genera texto extenso. Guardar en `.txt` permite comparar resultados de diferentes proteínas, revisarlo offline y compartirlo sin necesidad de repetir el análisis.

### Por qué `load_dotenv(override=True)`

Claude Code setea `ANTHROPIC_API_KEY` como string vacío en el entorno del subprocess. Sin `override=True`, `python-dotenv` no pisa variables ya existentes aunque estén vacías, y el cliente de Anthropic falla con error de autenticación.

---

## Limitaciones del sistema (v0)

| Limitación | Impacto | Solución planeada |
|---|---|---|
| ESMFold limitado a 200 aa | Solo analiza N-terminal de proteínas largas | Agregar ColabFold local para secuencias completas |
| Sin predicción de Tm | No puede estimar termoestabilidad | Integrar FoldX o DynaMut (v1) |
| Sin diseño de variantes | No puede proponer proteínas mejoradas | Integrar ProteinMPNN (v1) |
| Semantic Scholar solo abstracts | Puede perder datos en texto completo | Aceptable para v1; mejora futura con acceso full-text |
| ESM Atlas sin SLA | API pública puede fallar | Fallback documentado en el output |

---

## Roadmap

### v0 (actual)
- PubMed + UniProt + ESMFold
- Brief técnico con recomendaciones basadas en literatura
- CLI con casos preconfigurados

### v1 (en desarrollo)
- **`analyze_stability`:** Mapeo per-residuo de regiones inestables usando pLDDT. Identificación de targets para ingeniería de termoestabilidad (sustituciones de prolina, puentes de disulfuro, optimización de núcleo hidrofóbico).
- **`design_variants`:** Diseño de variantes usando ProteinMPNN. Genera N secuencias candidatas rediseñadas para mayor estabilidad térmica o expresabilidad.
- **`compare_variants`:** Validación computacional de variantes diseñadas. Corre ESMFold sobre cada candidata y rankea por mejora de pLDDT respecto al original.
- **Upgrade de ESMFold:** Retornar y persistir el PDB completo — necesario como input de ProteinMPNN.

**Pipeline v1 completo:**
```
PubMed → UniProt → ESMFold (+ PDB) → analyze_stability 
  → design_variants (ProteinMPNN) → compare_variants → Brief
```

### v2 (backlog)
- Integración con Knowledge Module (documentación de laboratorios socios)
- Soporte multi-proteína (analizar y comparar 3–5 candidatas en paralelo)
- AlphaFold 3 para casos que requieran análisis de interacciones proteína-ligando
