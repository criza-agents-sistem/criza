# Roadmap — Agente de Mercado CRIZA

---

## Estado actual: v1 ✅

**Fecha de entrega:** Junio 2026 (SEB-148)
**Construido en:** sesión 2026-06-27

### Herramientas activas

| Tool | Archivo | API / Fuente | Etiqueta | Key requerida |
|---|---|---|---|---|
| `buscar_corpus_cientifico` | `tools/corpus.py` | KM motor (fichas/embeddings) | [VERIFICADO] | No |
| `search_series` | `tools/datosgobar.py` | APIs de Series datos.gob.ar | [VERIFICADO] | No |
| `get_series_values` | `tools/datosgobar.py` | APIs de Series datos.gob.ar | [VERIFICADO] | No |
| `search_official_stats` | `tools/datosgobar.py` | datos.gob.ar CKAN | [VERIFICADO] | No |
| `fetch_page_text` | `tools/web_fetch.py` | HTTP directo | [VERIFICADO] | No |
| `draft_outreach_email` | `tools/email_draft.py` | Sin API — solo redacta | PENDIENTE_APROBACION | No |
| `submit_analysis` | inline | Submit final con cruces 1/3/4 + bloque 6 | - | No |

### Contrato estándar (SEB-115)

Expone `INPUT_CONTRACT`, `OUTPUT_CONTRACT` y `run(contract_input)` para el Orquestador.
`próximo_agente` siempre `None` — el Orquestador decide el routing.

### Tests

| Suite | Tests | Estado |
|---|---|---|
| Unit tests | 18 tests (7 nuevos de contrato SEB-115) | ✅ Pasando |
| Integration tests | 4 tests (datos.gob.ar real, search_series, get_series_values, corpus KM) | ✅ Pasando |

### Setup mínimo para correr

1. Copiar `.env.example` → `.env` y completar `ANTHROPIC_API_KEY`
2. `pip install -r requirements.txt`
3. `python run.py`

**Sin COMTRADE_API_KEY:** el agente funciona, pero `get_import_data` retorna error con instrucciones de registro. Registrarse gratis en comtrade.un.org.

---

## v1 — Pendiente

### Integración Gmail MCP (acción externa real)

**Qué es:** Conectar `draft_outreach_email` con Gmail MCP para que el usuario pueda enviar con un click desde la interfaz, manteniendo el gate de aprobación.

**Prerequisito:** Gmail MCP operativo + Orchestration Layer con flujos asíncronos.

**Regla que no cambia:** la aprobación humana antes de enviar es obligatoria en toda versión.

---

### Integración Knowledge Module

**Qué es:** Guardar datos de mercado verificados en el Knowledge Module para reutilizarlos en análisis futuros. Los precios CIF de un año no se vuelven a buscar — se recuperan del grafo.

**Prerequisito:** Knowledge Module ligero operativo (SEB-121).

---

### Contrato estándar de agentes (SEB-115)

**Qué es:** Adoptar el I/O estándar de la plataforma para que el Agente de Mercado sea plug-in al Orquestador.

**Qué cambia:** agregar `input_contract` y `output_contract` al agente. El `next_agent` queda vacío hasta que exista el Orquestador-agente formal.

---

## Registro de versiones

| Versión | Fecha | Cambios |
|---|---|---|
| v0 | 2026-06-01 | COMTRADE + datos.gob.ar + web fetch + email draft. 26 tests. |
| v1 | Pendiente | Gmail MCP + Knowledge Module + contrato estándar |
