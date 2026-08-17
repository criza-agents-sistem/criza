# CLAUDE.md — CRIZA

## Norte global — leer primero, siempre

> **EMPRESAS-IA es el producto.** El producto es una plataforma para crear empresas 100%
> agénticas y virtuales.
>
> **CRIZA NO es el producto final.** Es la primera instancia que valida que el modelo es
> replicable. CRIZA = encontrar blue oceans. Su entregable es el **expediente de decisión**: el
> sistema **ARMA**, el humano **ELIGE** (no "el sistema decide el producto"). Blue ocean = cruce
> de 4 condiciones (demanda real no resuelta + capacidad/tecnología + competencia débil +
> viabilidad en contexto).
>
> Esto significa: cada decisión de diseño en CRIZA debe poder documentarse como un paso
> replicable. Si algo no se puede replicar para otra instancia (DPN, Conflur, Biodarg, futuras),
> hay que preguntarse si en realidad es plataforma (Capa 0-1) y no algo específico de CRIZA.
>
> Fuente: `C:\Users\sebab\Documents\Plataformas\EMPRESAS-IA\docs\VISION-EMPRESAS-IA.md` ·
> `C:\Users\sebab\Documents\Plataformas\EMPRESAS-IA\docs\KRIZA_Foundation_Document.md`

---

## Qué es CRIZA

Primera empresa agéntica de la plataforma EMPRESAS-IA (Capa 2). Sistema de transferencia de
tecnología ciencia-industria, foco biotech agro argentino. **Diseño vigente:** múltiples puertas
de entrada (sector / dolor / tecnología / planta-recurso / empresario) → Orquestador (motor
dirigido por objetivo) → agentes investigadores (Investigación Amplia, Evidencia Científica,
Mercado) → Armador → **expediente de decisión** → el humano decide.

> Esta instancia es completamente independiente de DPN, Conflur y Biodarg.
> Lo que CRIZA sabe, aprende y almacena NO se filtra a otras instancias (tenant_id="criza" en el
> Knowledge Module, base de datos propia).

**Repo:** `github.com/criza-agents-sistem/criza` (privado). Independizada de `EMPRESAS-IA/` el
2026-08-13 — antes vivía nested en ese árbol; el código y el historial no cambiaron, solo la
ubicación y que ahora instala `knowledge_module` por pip en vez de asumirlo como carpeta hermana.
Transferida de la cuenta personal `sebasbizzi` a la organización `criza-agents-sistem` el
2026-08-17 (Etapa 19) — aísla CRIZA de los proyectos personales de Sebas y de los límites
gratuitos de Vercel/Railway ya usados por esos otros proyectos, mismo criterio de aislamiento
entre instancias que ya rige el resto de este documento.

---

## Protocolo de inicio de sesión

**Al iniciar cualquier sesión en CRIZA:**

1. Leer el bloque **Norte global** de este `CLAUDE.md` — no es negociable, no cambia
2. Leer `agents.md` — contexto activo del sistema: agentes, stack, pendientes, convenciones
3. Leer el cycle activo en Linear (proyecto CRIZA, equipo Sebabizz._dev)
4. Leer el último `docs/progress/YYYY-MM-DD.md`
5. Mostrar: qué está In Progress, qué está en Todo, si hay Bloqueados
6. Si la sesión involucra el agente científico → leer también `scientific_agent/ROADMAP.md`
7. Si la sesión involucra el agente de mercado → leer también `market_agent/ROADMAP.md`
8. Preguntar: "¿Arrancamos con X o preferís otra cosa?"

---

## Fuentes de verdad

| Fuente | Rol | Cuándo leer |
|---|---|---|
| Linear | Estado operativo de tareas | Siempre al iniciar |
| `agents.md` | Contexto activo: agentes, stack, pendientes, convenciones | Siempre al iniciar |
| `docs/architecture.md` | Decisiones técnicas del sistema: por qué se hizo así | Si la tarea requiere contexto técnico previo |
| `docs/progress/YYYY-MM-DD.md` | Log de la sesión anterior | Si hay duda de qué quedó pendiente |
| `C:\Users\sebab\Documents\Plataformas\EMPRESAS-IA\docs\VISION-EMPRESAS-IA.md` | Norte global del producto — qué es EMPRESAS-IA y para qué existe | **Siempre al iniciar** — es el norte |
| `C:\Users\sebab\Documents\Plataformas\EMPRESAS-IA\docs\KRIZA_Foundation_Document.md` | Arquitectura de plataforma (4 capas, principios) | Si la tarea afecta diseño de plataforma |
| `C:\Users\sebab\Documents\Plataformas\EMPRESAS-IA\docs\platform-boundary.md` | Qué es plataforma (Capa 0-1) vs qué es instancia (Capa 2) | Al tomar decisiones de dónde vive un dato o módulo |
| `C:\Users\sebab\Documents\Plataformas\EMPRESAS-IA\docs\NEW_INSTANCE_PROTOCOL.md` | Protocolo canónico de alta de instancia nueva | Solo si se crea una instancia nueva desde CRIZA como referencia |
| `C:\Users\sebab\Documents\Plataformas\EMPRESAS-IA\docs\DESIGN_GATE_TEMPLATE.md` | Template de gate de diseño | Al iniciar cualquier módulo nuevo |
| `<módulo>/docs/DESIGN_GATE.md` | Gate de diseño del módulo — trazabilidad + playbook | Antes de codear en ese módulo |
| `knowledge_module/docs/KM_DESIGN_GATE.md` (repo `km-knowledge-module`) | Qué del schema del KM está realmente implementado | Antes de asumir que un nodo/tabla del KM existe |
| `C:\Users\sebab\Documents\Plataformas\EMPRESAS-IA\docs\AUDITORIA_CUMPLIMIENTO_2026-07-05.md` | Auditoría de cumplimiento de plataforma, 48 hallazgos, ninguno resuelto | Antes de un cierre de sesión grande — **no resolver nada sin Sebas** |

Si hay conflicto: **Linear gana** para estado de tareas. **`docs/architecture.md` gana** para
decisiones técnicas de CRIZA. El **Norte global** de arriba gana sobre cualquier otra cosa para
decisiones de qué es plataforma vs qué es CRIZA.

---

## Principios que heredan del CLAUDE.md de plataforma

(Lista completa y su porqué: `C:\...\EMPRESAS-IA\CLAUDE.md` § Principios fundacionales — leer ahí
si hace falta el detalle, acá solo el resumen operativo.)

- **Plataforma primero (no negociable):** declarar qué es genérico (va a `knowledge_module` u
  otro repo de plataforma) vs específico de CRIZA (va acá) *antes* de diseñar. Prohibido
  "solo-CRIZA por ahora, lo generalizamos después".
- **Consultar antes de actuar + honestidad total:** ante duda, preguntar a Sebas antes de
  proceder. Si hay un riesgo/desvío/error, nombrarlo antes de seguir.
- **Veracidad por dato:** establecido (con fuente) / asumido (con peso) / a-confirmar. Nunca un
  número inventado. Nunca confiar en timelines generados por el modelo.
- **Anti-sesgo por estructura:** el sesgo se atrapa con estructura/proceso, no con prompts de
  "tenelo en cuenta".
- **La tecnología es una variable, no una restricción:** ningún agente asume ni sugiere qué
  tecnología resuelve un problema — la determina el análisis. Prohibido listar tecnologías como
  ejemplos en prompts de agentes.
- **Eficiencia de tokens — medir, no mutilar:** todo agente usa Sonnet 4.6 por defecto (no Haiku),
  configurable por `.env`. Persistir `token_usage` en el KM al terminar cada corrida.
- **Decisión final siempre humana:** el sistema arma y propone; Sebas decide/aprueba.
- **Aislamiento entre instancias (no negociable):** lo que CRIZA sabe/aprende/almacena no se
  filtra a DPN, Conflur, Biodarg ni futuras.
- **Aprendizaje transversal:** los agentes aprenden de la experiencia — leer lecciones análogas
  antes de actuar, escribir después.

---

## Regla de capa — qué es plataforma y qué es CRIZA

**Pregunta obligatoria antes de diseñar o construir cualquier pieza:**
> ¿Esto serviría igual para DPN, Conflur, Biodarg o una futura instancia sin modificarlo?
> - Sí → es plataforma — no va en este repo (avisar a Sebas, se diseña en `knowledge_module` u
>   otro repo de Capa 0-1)
> - No → va en este repo (Capa 2 — CRIZA)

### Tabla de referencia rápida

| Componente | Dónde va | Por qué |
|---|---|---|
| Knowledge Module (motor genérico, auditor, embeddings, conectores) | `knowledge_module` — repo propio, instalado por pip | Cualquier instancia lo usa |
| Datos del KM de CRIZA | Neon propio de CRIZA, `tenant_id="criza"` | Infraestructura compartida (el paquete), datos aislados |
| Design Gate template, playbook | repo `EMPRESAS-IA/docs/` — plataforma | Aplica a todos los proyectos |
| **Agentes de CRIZA** (`market_agent/`, `evidence_generalista/`, `investigacion_amplia/`, `armador/`, `scientific_agent/`) | este repo | Dominio específico: transferencia tecnológica biotech agro |
| **Orquestador** (`orquestador/motor.py`, `registry.py`, `flows/*.yaml`) | este repo | Flows declarativos específicos de CRIZA — el patrón motor-dirigido-por-objetivo sí es candidato a plataforma a futuro (ver Norte global), pero mientras solo lo use CRIZA no se generaliza sin otra instancia real que lo necesite |
| **Conectores INTA/CONICET/AGROVOC** (`utils/inta.py`, `utils/agrovoc.py`, `config/connectors/`) | este repo | Fuentes específicas del dominio agro/biotech |
| **`auditor_registry.yaml`** | este repo | Config de instancia — el auditor en sí es genérico (`knowledge_module`) |
| **Migraciones de schema/seed-data específicas de INTA/CRIZA** | `migrations/` en este repo | No genéricas — ver `migrations/README.md` |

---

## Regla de escritura al KM — todo lo que un agente genera va al KM

Todo lo que un agente produce se persiste en el KM, sin excepción — 3 tipos, los 3 al KM:
resultado estructurado (`props.[clave_agente]` vía `motor_api.actualizar_props`), informe
narrativo completo (`props.[clave_agente]_informe`), y aprendizaje (área `lecciones`). Si el
output de un agente no está en el KM, no existe para el sistema — un archivo en `outputs/` local
es invisible para el Armador, el Orquestador y cualquier agente futuro.

**Check obligatorio en el gate de cada agente nuevo:** §2 (Trazabilidad) debe tener una tabla
"KM write" que confirme que cada uno de los 3 tipos va al KM, o documente con decisión por qué no.

---

## Design Gate antes de codear un módulo nuevo

Antes de escribir código en un módulo nuevo (agente, flow, tool): verificar que existe
`<módulo>/docs/DESIGN_GATE.md` (crearlo desde el template de plataforma si no existe), completar
trazabilidad + playbook + scope + decisiones, y que el estado sea 🟡 o ✅ antes de arrancar
desarrollo. El gate es un issue en Linear que bloquea los issues de desarrollo.

---

## Durante el trabajo

- Al empezar una tarea → moverla a **In Progress** en Linear inmediatamente
- Al terminar → verificar Definition of Done ANTES de marcarla **Done**:
  1. `docs/DESIGN_GATE.md` con estado ✅
  2. Tests unitarios — casos críticos cubiertos con pytest
  3. **Corrida real de punta a punta — contra el sistema real, no mocks.** Si escribe al KM,
     verificar leyendo el KM que el dato quedó. Los tests unitarios verifican las piezas; solo
     una corrida real verifica las costuras (agregado 2026-07-22 tras encontrar 3 piezas
     desconectadas en una corrida real con 199 tests unitarios en verde — detalle en
     `docs/progress/2026-07-22.md`)
  4. Si la tarea generó una decisión de arquitectura/desarrollo (no una decisión de negocio,
     esas van a `docs/architecture.md` normal) → registrarla en `decisiones_sistema` (KM) con
     `scripts/km_decisiones.registrar_decision(...)` y correr
     `python scripts/generar_agents_md.py` para que "Agentes activos" y "Estado operativo" de
     `agents.md` reflejen la decisión. **Ya no se edita esas dos secciones a mano** — es lo que
     las desactualizaba (decisión 2026-08-15, `docs/progress/2026-08-15.md`). El resto de
     `agents.md` (Stack activo, Dónde están las cosas, Convención, REGLAS OPERATIVAS) sigue
     siendo edición manual normal si la tarea lo justifica.
  5. `docs/progress/YYYY-MM-DD.md` — sesión documentada
- Al tomar una decisión técnica → registrar en `docs/architecture.md` en ese momento
- Si surge un bloqueador → label **Bloqueado** + nota en Linear con el motivo
- Si surge una tarea nueva → crearla en Linear antes de arrancar

### Granularidad de issues

- **Un issue = un resultado entregable** (feature, módulo, capacidad visible)
- Las subtareas técnicas van como **sub-issues**, no como issues separados
- Nunca crear issues con sufijos tipo "parte 1", "parte 2" — eso va dentro del issue padre como sub-issue
- Al completar un issue, marcarlo Done inmediatamente para que el auto-archive lo limpie

### Limpieza inicial — solo la primera sesión con este CLAUDE.md actualizado

Al inicio de la próxima sesión, **una sola vez**:
1. Revisar todos los issues existentes en Linear (proyecto CRIZA)
2. Identificar cuáles tienen trabajo concreto pendiente → dejarlos activos
3. Los que no tienen trabajo pendiente real → cancelarlos
4. Los que en realidad ya están hechos → marcarlos Done y borrarlos
5. Reestructurar los issues activos al nuevo esquema: si hay issues con "parte 1/2/3" o subtareas como issues separados, consolidarlos en un issue padre con sub-issues
6. Una vez hecha la limpieza, eliminar este bloque "Limpieza inicial" del CLAUDE.md

### Labels y prioridades de Linear

| Label | Uso |
|---|---|
| Dev / Arquitectura / Stakeholder / Docs / Admin | mismo criterio que el resto de las instancias |
| Bloqueado | esperando algo externo |
| En revisión | esperando feedback de Sebas |

Prioridades: Urgent (hoy) · High (esta semana sin falta) · Medium (esta semana si hay tiempo) ·
Low (backlog).

---

## Al cerrar cada sesión

1. Verificar que todo lo trabajado esté actualizado en Linear
2. Tareas a medias → dejarlas In Progress con nota del estado actual
3. Crear `docs/progress/YYYY-MM-DD.md` con resumen de la sesión
4. **Si `agents.md` quedó desactualizado por el trabajo de hoy → actualizarlo ahora, no
   "después".** Causa más común de que una sesión nueva arranque con contexto incorrecto.
5. Sugerir cuál debería ser la próxima sesión

---

## Aislamiento de contexto

Abrir Claude Code **desde `C:\Users\sebab\Documents\Plataformas\criza\`** para trabajar en CRIZA.
Nunca desde el árbol de `EMPRESAS-IA/` ni mezclar contextos de otra instancia en una misma sesión.
