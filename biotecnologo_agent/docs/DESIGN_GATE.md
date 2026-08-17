# Design Gate — Especialista Biotecnólogo

**Versión:** 1.0
**Fecha:** 2026-08-17
**Módulo:** `criza/biotecnologo_agent/`
**Capa:** 2 (instancia CRIZA)
**Estado:** ✅ LISTO

---

## 1. Identidad

| Pregunta | Respuesta |
|---|---|
| ¿Qué es? | Cuarto especialista de la "biblioteca de especialistas" (`docs/PROPUESTA_DESTINO.md` §5) — evalúa **qué producto de valor construir vía bioprocesos** a partir de un material biológico/subproducto ya identificado (ej. un efluente), y con qué ruta metabólica/bioproceso. Distinto de los otros 3: el Microbiólogo diagnostica el proceso biológico DEL MATERIAL EN SÍ (¿cómo tratarlo?); el Ingeniero Ambiental evalúa factibilidad de ingeniería del tratamiento; el Agrónomo evalúa uso agronómico del producto final. El Biotecnólogo responde una pregunta distinta: "¿qué se puede FABRICAR a partir de esto, con qué ruta biotecnológica, y qué tan madura/libre de esa ruta está el terreno?" — el ángulo que faltaba cuando el Conductor generó ideas blue ocean (medio de cultivo, PHA/bioplásticos, biomasa microbiana) sin poder evaluarlas con rigor técnico. |
| ¿Qué problema resuelve en una oración? | Andrés (colaborador externo de Sebas) sugirió sumar este ángulo; Sebas confirmó que le parecía acertado — pedido real, no especulación abstracta. |
| ¿Quién lo usa? | Sebas, directo o vía el Conductor (`correr_especialista`, generalizado desde la Etapa 7 — sumar este especialista es una línea en `_ESPECIALISTAS_CASOS`, no tocar el Conductor). |
| ¿De qué depende? | Mismo patrón que los otros 3 — `utils/ai_client.py`, `utils/corpus.py`, `km_tools/search.py`, `utils/openalex.py`, `utils/agrovoc.py`, `utils/casos.py`, `knowledge_module.preflight`, `knowledge_module.aprendizaje`. Reusa `utils/kegg.py`/`utils/rhea.py` (ya construidos para el Microbiólogo) + dos utilidades nuevas: `utils/pubchem.py`, `utils/chebi.py`. |
| ¿Qué depende de él? | El Conductor, vía `correr_especialista`. |
| ¿Milestone? | Cuarto agente de la biblioteca de especialistas, 2026-08-17. |

---

## 2. Trazabilidad diseño → implementación

### Por qué este especialista, ahora

Sebas: "Andrés me decía que podíamos agregar un agente biotecnólogo, me parece acertado" —
mismo criterio que ya se aplicó con el Agrónomo (no se construye especulativamente, se preguntó
primero qué ángulo cubriría que los otros 3 no cubren). Se propuso la diferenciación (evaluar
QUÉ PRODUCTO fabricar vía bioprocesos, no cómo tratar el material ni cómo usarlo) y Sebas la
confirmó explícitamente ("me parece bien así el agente") antes de construir.

### Herramientas — verificadas en vivo, no asumidas (mismo criterio que BRENDA, Etapa 8)

Antes de fijar el tool set se probaron en vivo las candidatas propuestas originalmente
(BioCyc/MetaCyc, búsqueda de patentes, Addgene). Hallazgos reales:

- **Búsqueda de patentes** (Google Patents / Lens.org / PatentsView): ninguna tiene una API REST
  gratis sin registro accesible hoy — PatentsView (USPTO) migró a requerir API key. **Deferido**,
  mismo criterio que BRENDA (Etapa 8 del microbiólogo): no se bloquea el agente por esto, queda
  como pendiente real si Sebas consigue una key.
- **Addgene**: no tiene API pública, solo página de búsqueda HTML — no integrable de forma
  robusta sin scraping frágil. **Descartado** (no solo deferido — no hay camino API razonable).
- **BioCyc/MetaCyc**: el endpoint de lookup DIRECTO por ID (`getxml?id=...`) sí funciona sin auth
  (verificado real), pero el endpoint de BÚSQUEDA por texto libre devuelve una página HTML
  completa con hCaptcha, no datos estructurados — inútil como tool programático sin scraping.
  **Descartado** para v1 (una tool de "solo lookup por ID que el modelo no puede adivinar" no
  aporta valor real).

**Reemplazo, mismo pase de verificación:** dos APIs REST confirmadas reales, gratis, sin auth:
- **PubChem** (`utils/pubchem.py`, nuevo) — identidad química de un producto candidato (fórmula,
  peso molecular, SMILES). Verificado real: `struvite` (inglés) devuelve datos completos,
  `estruvita` (español) no matchea — mismo criterio de idioma que ya rige el resto de las tools.
- **ChEBI vía EBI OLS4** (`utils/chebi.py`, nuevo) — clasificación química/biológica de una
  entidad, con sinónimos y definición curada. El endpoint viejo de ChEBI
  (`webservices/chebi/2.0`) está deprecado (devuelve HTML) — confirmado al probarlo, se usa el
  OLS4 nuevo en su lugar.
- **KEGG y Rhea** (`utils/kegg.py`/`utils/rhea.py`, ya construidos para el Microbiólogo) — se
  REUSAN tal cual, sin duplicar código. Tienen sentido para este agente con un ángulo distinto:
  el Microbiólogo los usa para entender el proceso de TRATAMIENTO; el Biotecnólogo los usa para
  identificar la ruta de BIOSÍNTESIS del producto candidato.

### Entidades

| Entidad | Descripción | Estado |
|---|---|---|
| `search_literature` / `buscar_corpus_cientifico` / `search_corpus_inta` / `expand_agrovoc` | Mismas 4 tools genéricas de corpus que ya usan los otros 3 especialistas. | ✅ construido |
| `search_kegg` / `search_rhea` | Reusadas de `microbiologo_agent` (mismos módulos `utils/kegg.py`/`utils/rhea.py`) — ruta metabólica/reacción de biosíntesis del producto candidato, no del tratamiento. | ✅ construido (reuso) |
| `search_pubchem` (nuevo) | `utils/pubchem.py` — identidad química del producto candidato. | ✅ construido |
| `search_chebi` (nuevo) | `utils/chebi.py` — clasificación química/biológica curada. | ✅ construido |
| `submit_evaluacion_tecnica` | Mismo schema que los otros 3 — reusado tal cual. | ✅ construido |

### Contrato SEB-115

```python
INPUT_CONTRACT  = {"agent": "biotecnologo", "version": "1.0",
                   "fields": {caso, tarea, contexto, conocimiento: {"frente_id": str}, herramientas}}
OUTPUT_CONTRACT = {"agent": "biotecnologo", "version": "1.0",
                   "km_escribe": ["documento_caso conectado vía frente_produce_documento"],
                   "fields": {análisis, nivel_confianza, recomendaciones, próximo_agente, nuevo_conocimiento}}
```

Solo `frente_id` (modelo `casos.yaml`) — mismo criterio que Ingeniero Ambiental/Agrónomo: ningún
caller real necesitaría el modelo `oportunidad_id` para un especialista construido hoy.

### KM write

| Tipo de output | Qué contiene | Key en KM | Cómo | Estado |
|---|---|---|---|---|
| **Resultado estructurado + informe** | Mismo shape que los otros 3 especialistas | `documento_caso` conectado vía `frente_produce_documento` | La costura, no el agente | ✅ construido |
| **Token usage** | Tokens consumidos | `props.token_usage.biotecnologo` del **frente** | El agente escribe esto directo | ✅ construido |
| **Aprendizaje** | Lecciones del caso | área `lecciones` | 🔵 pendiente — misma deuda intencional que los otros 3 | — |

---

## 3. Checklist del playbook

### Estructura de archivos

- [x] `biotecnologo_agent.py` — SYSTEM_PROMPT + TOOLS + `run_agent_desde_frente()` + `run()` + chat
- [x] `run.py`
- [x] `docs/DESIGN_GATE.md` — este archivo
- [x] `.env.example`
- [x] `tests/`

### Testing

- [x] Test: `TOOLS` tiene exactamente 9 tools (4 genéricas + `search_kegg`/`search_rhea`/
      `search_pubchem`/`search_chebi` + `submit_evaluacion_tecnica`)
- [x] **Test explícito del checklist anti-sesgo: `SYSTEM_PROMPT` no contiene ninguna de las
      strings "Helios", "biogás", "biodigestor", "Mateo", "Andrés"** — mismo control que los
      otros 3 especialistas (checklist central contra el sesgo de `specialist_proteins.py`).
- [x] Test: `run()` requiere `frente_id`, no acepta `oportunidad_id`
- [x] Test: `run_agent_desde_frente` mock captura `submit_evaluacion_tecnica`
- [x] Test: dispatch de `search_pubchem`/`search_chebi`/`search_kegg`/`search_rhea`
- [x] `utils/tests/test_pubchem.py`/`test_chebi.py` nuevos, con tests unit (mock) + integration
      (real, sin auth) — verificados ambos en vivo antes de construir el agente
- [x] Al menos 1 corrida real vía la costura (`invocar_agente`) contra un frente real de
      producción, con `submit_evaluacion_tecnica` llamado por el modelo real (no mockeado).
      Corrida real contra el 'Frente técnico' de Helios: 8 búsquedas reales (CONICET/INTA/
      OpenAlex/KEGG/Rhea/PubChem/ChEBI), 5 rutas biotecnológicas identificadas (PHA/PHB desde
      VFAs, biomasa microalgal, struvita, proteína unicelular vía metanótrofos, y una ruta
      combinada en cascada), con fuentes reales citadas incluyendo dos papers argentinos
      (CONICET-INBIOSUR, INTA) encontrados vía `buscar_corpus_cientifico`. `search_kegg`/
      `search_rhea` no devolvieron resultados para los términos de PHA/PHB usados — reportado
      como limitación honesta en `fuentes_y_cobertura`, no ocultado (mismo criterio de veracidad
      por dato). `search_pubchem` confirmó la estruvita (CID 10220511) y `search_chebi` confirmó
      el PHB (CHEBI:131525) — las dos tools nuevas funcionaron con datos reales. `documento_caso`
      resultante (`439cda83-fb9a-4ccf-b207-1614f64d96ab`) confirmado conectado al frente junto a
      los 3 documentos previos de los otros especialistas. 317.185 tokens totales.

---

## 4. Scope explícito por versión

| Feature | Versión | Razón |
|---|---|---|
| Camino `oportunidad_id` | No planeado | Mismo criterio que Ingeniero Ambiental/Agrónomo. |
| Búsqueda de patentes | v2, si Sebas consigue una API key | PatentsView/Lens.org requieren registro — no bloquea el arranque, mismo criterio que BRENDA (Etapa 8). |
| Addgene | No planeado | Sin API pública real, solo scraping frágil — no vale la pena. |
| BioCyc/MetaCyc | Descartado para v1 | Su búsqueda por texto libre no es programática (HTML + hCaptcha); el lookup directo por ID no aporta valor sin una búsqueda previa. Reconsiderar si aparece una necesidad real de rutas MetaCyc específicas que KEGG no cubra. |
| Persistencia de lecciones de caso | backlog | Misma deuda intencional que los otros 3. |

---

## 5. Decisiones requeridas antes de arrancar

| # | Pregunta | Opciones | Decisión tomada | Fecha |
|---|---|---|---|---|
| A | ¿Hay necesidad real que justifique este especialista ahora? | Sí, señal concreta / No, esperar | **Sí** — Andrés (colaborador de Sebas) lo sugirió, Sebas confirmó explícitamente que le parecía acertado. | 2026-08-17 |
| B | ¿Rol exacto — trata el material, o evalúa qué producto fabricar a partir de él? | Tratamiento del material / Producto + ruta biotecnológica | **Producto + ruta biotecnológica** — el ángulo que faltaba: los otros 3 ya cubren tratamiento (Microbiólogo), factibilidad de ingeniería (Ingeniero Ambiental) y uso agronómico del resultado (Agrónomo). Ninguno evalúa qué fabricar vía bioprocesos ni con qué madurez de ruta. Propuesto a Sebas explícitamente y confirmado ("me parece bien así el agente") antes de construir. | 2026-08-17 |
| C | ¿Qué herramientas de dominio, más allá de las 4 genéricas? | Ver detalle en "Herramientas — verificadas en vivo" arriba | **KEGG + Rhea (reusadas) + PubChem + ChEBI (nuevas)** — las 4 candidatas originales (BioCyc, patentes, Addgene) se verificaron en vivo y 3 de las 4 no eran viables sin trabajo adicional (API key, o no tienen API real); se reemplazaron por 2 confirmadas reales + 2 ya construidas y reusables. | 2026-08-17 |
| D | ¿Chat directo con el especialista (mismo patrón que los otros 3, Etapa 10)? | Mismo patrón / uno propio | **Mismo patrón, sin variación** — cuarto consumidor del patrón conversacional (`_despachar_tool`, `TOOLS_CHAT`, `iniciar_sesion`/`enviar_mensaje`), incluida la consulta libre (Etapa 12, `frente_id: None`) y la inyección de `documentos_aportados` (Etapa 17b). | 2026-08-17 |

---

## 6. Estado del gate

**Estado actual:** ✅ LISTO

Decisiones A-D cerradas, ninguna abierta. Cuarto consumidor del patrón general (contrato SEB-115,
chat conversacional, consulta libre, documentos aportados) — la decisión real de esta ronda fue
el ángulo distintivo (decisión B) y verificar en vivo qué herramientas de dominio eran realmente
viables (decisión C), no asumir la lista propuesta inicialmente.

**Deuda intencional documentada:**
- Camino `oportunidad_id` → no planeado
- Búsqueda de patentes → v2, requiere que alguien consiga una API key (PatentsView/Lens.org)
- Persistencia de lecciones de caso → backlog, misma deuda que los otros 3
- El chat no escribe lecciones al cierre (a diferencia del Conductor, Etapa 9) — mismo backlog
