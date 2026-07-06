# Expediente de Decisión — Especificación

**Versión:** 0.1 (aprobada a priori 2026-06-13 — **pendiente de validar contra un caso concreto**)
**Issue:** SEB-144 (sub de SEB-143 — Rethink). Contexto: `docs/progress/2026-06-12.md`, memoria `project_rethink_convergente`.
**Capa:** candidato a **plataforma** (el formato del entregable sirve a cualquier instancia, no solo CRIZA). Se define acá; promover a `platform/` cuando exista.

---

## Qué es

El **entregable único** del sistema (Fase 1 — Decisión). Cualquier oportunidad, entre por la puerta que
entre (sector / dolor / tecnología / planta-recurso / necesidad de empresario), termina en un expediente
con esta misma estructura. **El sistema arma el expediente; el humano elige.** El sistema NO decide ni
elige el producto.

## Convención transversal — etiqueta de estado por dato (no negociable)

Cada **dato** del expediente lleva una etiqueta:

| Estado | Qué significa | Qué lleva obligatoriamente |
|---|---|---|
| **establecido** | Verificado | `fuente` (cita + año + local/global). **Ningún número sin esto.** |
| **asumido** | Se da por cierto sin verificar | `peso` (cuánto depende la tesis de este supuesto) |
| **a-confirmar** | No se pudo establecer | `dónde_confirmar` (fuente o persona). **Nunca se inventa un valor.** |

Regla de oro: ante la duda, **a-confirmar declarado > número inventado**. (Es el principio de veracidad
del proyecto, ahora a nivel de cada dato.)

---

## Bloque 1 — Tesis + puerta de entrada
- `tesis` — 1-2 frases: qué solución/producto, para quién, por qué ahora.
- `puerta_de_entrada` — sector | dolor | tecnología | planta-recurso | necesidad-empresario.
- `disparador` — lo concreto que entró (ej. "olor del estiércol", "cepa de Metarhizium del Dr. X").
- `id`, `fecha`.

## Bloque 2 — Los 4 cruces del blue ocean
Cada campo lleva su etiqueta de estado.

| Cruce | Campos |
|---|---|
| **1 · Demanda** | `dolor` · `quién_lo_sufre` · `tamaño` (valor+unidad+fuente) · `urgencia` · `evidencia` |
| **2 · Capacidad/Tecnología** | `solución` · `factibilidad_técnica` · `estado_de_desarrollo` (idea/lab/piloto/comercial) · `ventaja_vs_alternativas` · `evidencia` |
| **3 · Competencia** | `qué_existe` (productos/jugadores) · `registros` (SENASA/patentes) · `intensidad` (vacío/débil/fuerte) · `evidencia` |
| **4 · Viabilidad en contexto** | `encuadre_regulatorio` · `accesibilidad_mercado_local` · `factibilidad_de_costo` · `evidencia` |

## Bloque 3 — Mapa de confianza
Síntesis transversal: qué está **establecido**, qué **asumido** (con su peso) y qué **a-confirmar** (con
dónde/quién y prioridad según cuánto mueve la decisión).

## Bloque 4 — Nivel de madurez
`hipótesis de screening` | `parcialmente validado` | `listo para decisión` + justificación del nivel.

## Bloque 5 — Qué falta para decidir
Lista **priorizada** de verificaciones pendientes (los `a-confirmar` de mayor impacto), cada una con
*cómo* y *quién/qué fuente*.

## Bloque 6 — Factores de ejecución
Misma regla establecido/a-juicio; **sin números inventados**.
- **Inversión** — componentes de costo + comparables si los hay; si no → "a estimar con [fuente/experto]".
- **Tiempo a mercado** — anclado en comparables reales; si no hay → a juicio del humano. **Nunca un
  timeline generado por el modelo** (el modelo sobreestima tiempos: ej. estimó "varios meses", real ~2 semanas).
- **Capacidades** — mapa de requeridas vs. disponibles (humano / red / CONICET-INTA / socios). El
  "¿podemos?" es juicio humano.
- **Regulatorio** — el camino (qué encuadre aplica) + anclas históricas; el plazo = incógnita conocida.

## Encabezado de trazabilidad (en cada expediente)
Qué agentes lo completaron · fuentes usadas · fecha.

---

## Estado y pendiente
- v0.1 aprobada a priori (campos OK). **Pendiente: validar contra un caso concreto** (lección del proyecto:
  no adoptar por sonar bien en los papeles; probar en la realidad). La validación cae naturalmente al
  construir el Armador (SEB-145) y correr una oportunidad real.
- Al cerrar la validación → v1.0 y SEB-144 a Done.
