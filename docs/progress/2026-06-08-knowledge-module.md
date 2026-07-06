# Sesión 2026-06-08 (tarde) — Knowledge Module: diseño revisado + schema v0.5

## Qué se hizo

### 1. Cierre de pendientes de la metodología

- **Riesgo ecológico:** agregada categoría explícita en la sección "Posibles Riesgos" de
  `metodologia_busqueda_AGENTE.md`. Trigger condicional: aplica solo cuando el candidato involucra
  un organismo vivo con exposición al ambiente (liberación, aplicación en superficies expuestas,
  persistencia fuera de sistema controlado). Excluye organismos contenidos (probióticos, silaje).
  La redacción deja claro que son dos cosas: riesgos generales SIEMPRE + riesgo ecológico cuando aplica.

- **Must #12 / candidatos borderline:** "cepa local + valor diferencial" se acepta. Se dejó
  implícito en la metodología — explicitar generaría nuevo sesgo (el agente buscaría el framing
  "cepa local" para justificar sustitución de importación disfrazada).

### 2. Knowledge Base Ligera (archivo de reserva)

Creado `criza/docs/knowledge_base_ligera.md`. Captura la experiencia acumulada en 5 secciones:
sesgos documentados (con mecanismo y corrección), decisiones metodológicas de instancia, tabla
de candidatos identificados hasta ahora, aprendizajes negativos (lo que no funcionó y por qué),
y preguntas abiertas de instancia. Se usa si no llegamos a construir SEB-121 a tiempo.

### 3. Revisión del diseño del Knowledge Module

**Análisis 1 — cambios del proyecto vs. diseño original:**
- El schema v0.4 fue diseñado cuando CRIZA era transferencia tecnológica. El pivot demand-first
  cambia qué es valioso capturar.
- Faltaban dos nodos: `Oportunidad` (pre-proyecto, banco de suplentes) y `Corrida` (registro de
  ejecuciones del agente — permite saber cuántas veces apareció un candidato de forma independiente).
- El resto del schema sigue vigente.

**Análisis 2 — tecnología disponible:**
- Stack (Neon + pgvector + BGE-m3) se sostiene. No hay razón para cambiar.
- Escalabilidad: pgvector no es el límite. La arquitectura de tenancy (dedicado ahora / pooled
  después, SEB-116) escala bien. La abstracción de proveedor (SEB-117) deja el camino abierto
  a Qdrant si llega el momento.
- Cambio arquitectural relevante: exponer el KM como **MCP server** (tools: search_knowledge,
  store_learning, get_opportunity_history) en vez de integración directa. Más limpio, reutilizable
  entre agentes y entre instancias. No estaba en el diseño original.
- GraphRAG (Microsoft 2024): dejar la puerta abierta en el diseño, no para el MVP.

### 4. Schema v0.5

Actualizado `docs/knowledge-schema.md`:

**Nodo nuevo: Corrida**
- sector, agente, modo (A/B/C), fecha, modelo, tokens_input, tokens_output, costo_usd, notas

**Nodo nuevo: Oportunidad**
- sector, idea, prioridad, estado_análisis (detectada|en_análisis|validada|descartada),
  origen (agente|equipo|externo), veces_detectada, validaciones, gaps_pendientes, razón_descarte

**Aristas nuevas:**
- PRODUCE (Corrida → Oportunidad) — con prioridad asignada en esa corrida
- DERIVA_EN (Oportunidad → Proyecto) — con fecha y motivo de la decisión

**Índices:** oportunidad (sector+prioridad, estado_análisis, origen), corrida (agente+fecha, sector)

## Pendientes / próxima sesión

- Decidir orden de build: ¿SEB-118 (BGE-m3) primero o MCP server primero?
- Cuando vuelva feedback de Pablo y Andrés: revisar metodología y ajustar si corresponde
- SEB-130 (rediseño objective-first del divergente): revisar si ya está cubierto por la
  metodología actual → candidato a marcar Done o Backlog-descartado
