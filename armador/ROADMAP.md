# Armador del Expediente — ROADMAP

**Issue:** SEB-145  
**Capa:** 2 (CRIZA)  
**Estado actual:** v1 — en construcción (2026-06-16)

---

## v1 (actual — SEB-145)

**Objetivo:** ensamblar el expediente de decisión desde los props del KM.

**Tools activas:**
| Tool | Descripción |
|---|---|
| `submit_expediente` | Output estructurado obligatorio — captura el expediente completo (6 bloques) para KM write-back |

**Lo que cubre:**
- Lee `props.mercado` (cruces 1/3/4 + bloque_6_anclas del market agent)
- Lee `props.evidencia` (cruce 2 del evidence agent, si existe)
- Cruce 2 ausente → bloque `a-confirmar` explícito (SEB-149 pendiente)
- Bloque 3 (mapa confianza) y bloque 4 (madurez) sintetizados por el agente
- Bloque 5 (gaps priorizados) desde los a-confirmar de impacto
- Bloque 6 desde `bloque_6_anclas` del market agent + síntesis
- Write-back al KM: `props.expediente`
- Loop de aprendizaje (SEB-156): leccion_caso auto + leccion_proceso humano al cierre

**No cubre (deuda intencional v1):**
- Cruce 2 completo (requiere SEB-149 Evidence Agent)
- Búsqueda de vecinos para contexto comparativo
- Trigger automático desde Orquestador (SEB-152)

---

## v2 (futuro)

- Integración con Evidence Agent (SEB-149) → cruce 2 poblado
- `buscar_vecinos_oportunidad` — contexto de oportunidades análogas del KM
- Validación de integridad del expediente (controles post-corrida)

## v3 (futuro)

- Invocación automática por Orquestador (SEB-152) como último paso del pipeline

---

## Historial

| Versión | Fecha | Cambios |
|---|---|---|
| v1 | 2026-06-16 | Implementación inicial — SEB-145 |
