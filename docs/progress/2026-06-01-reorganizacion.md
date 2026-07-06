# Sesión 2026-06-01 — Reorganización de estructura del proyecto

## Qué se hizo

Reorganización completa de la estructura de carpetas para que CRIZA y EMPRESAS-IA tengan
separación clara y para que la estructura del repo siga el playbook v1.3.

### Cambios en filesystem

| Acción | Origen | Destino |
|---|---|---|
| Movido | `C:\Users\sebab\criza\` | `EMPRESAS-IA\criza\` |
| Creado | — | `criza\agents.md` (raíz) |
| Creado | — | `criza\docs\architecture.md` |
| Movido | `scientific_agent\docs\progress\*.md` | `criza\docs\progress\` |
| Creado | — | `market_agent\ROADMAP.md` |
| Eliminado | `scientific_agent\agents.md` | — (reemplazado por raíz) |
| Eliminado | `market_agent\agents.md` | — (era incorrecto) |
| Eliminado | `criza\STATUS.md` | — (contenido en architecture.md) |
| Actualizado | `CLAUDE.md` | Paths y protocolo actualizados |
| Memoria | — | Preparada en carpeta EMPRESAS-IA |

### Pendiente operativo (no se puede hacer con sesión activa)

- [ ] Renombrar carpeta `KRIZA/` → `EMPRESAS-IA/` desde Explorador de Windows con Claude Code cerrado

## Decisiones tomadas

### EMPRESAS-IA vs CRIZA — separación de espacios

**Decisión:** `EMPRESAS-IA/` (hoy KRIZA/) es el espacio de plataforma (docs estratégicos). `criza/` es el repo de código de la instancia biotech. Son cosas distintas en carpetas distintas.

**Por qué:** El FD define 4 capas y múltiples repos futuros. La separación física desde el día uno evita deuda de reorganización y permite que un colaborador nuevo entienda el proyecto mirando la estructura.

### agents.md — un solo archivo en raíz de repo

**Decisión:** Un solo `agents.md` en la raíz de `criza/`. No hay agents.md por componente.

**Por qué:** El playbook define un agents.md por proyecto. Para multi-agente, agents.md es el mapa del sistema (alto nivel, ~200 líneas). El detalle técnico profundo va en ROADMAP.md de cada componente.

**Aclaración importante:** agents.md es contexto para Claude-desarrollador, no para los agentes desplegados. Los agentes tienen sus propios SYSTEM_PROMPT en el código Python.

### Convención para nuevos agentes documentada

Agregada en `criza/agents.md` sección "Convención para agregar un nuevo agente":
- Estructura de archivos estándar
- Contrato de output de tools (success/data/source/error)
- Checklist de creación (= DoD del agente)

## Estado al cerrar

- `criza/agents.md` — ✅ creado, describe sistema completo
- `criza/docs/architecture.md` — ✅ decisiones técnicas consolidadas
- `criza/docs/progress/` — ✅ logs de sesiones migrados
- `market_agent/ROADMAP.md` — ✅ creado
- CLAUDE.md — ✅ actualizado con nueva estructura y paths
- Memoria de Claude — ✅ preparada en EMPRESAS-IA
