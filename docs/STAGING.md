# Staging — CRIZA

**Estado:** creado 2026-08-16, Etapa 4 del plan de construcción del nuevo sistema
(`C:\Users\sebab\.claude\plans\greedy-cooking-llama.md`).

---

## Qué es

Un branch de Neon (`staging`, copy-on-write instantáneo de `production`) del proyecto de Neon
`criza` (org `empresas-ia`, `org-still-art-13117113`). Mismos datos que producción al momento de
crearlo — verificado en vivo: 37.215 fichas `tenant_id='criza'` + 6 `tenant_id='instancia_test'`
en ambos branches, idénticos.

**Por qué en esta etapa y no antes:** hasta la Etapa 3 (inclusive) nada escribía datos nuevos
contra el modelo de `casos.yaml` (Helios/MicroBigs ya cargados, área `casos`) — bajo riesgo real.
El primer momento de riesgo de verdad es cuando un agente empieza a **escribir** fichas nuevas
(`frente`, `pendiente`, `documento_caso`) contra ese modelo — ahí un bug de escritura sí puede
ensuciar datos de un caso real. El staging existe para que ese trabajo de desarrollo no toque
`production` mientras se prueba.

## Housekeeping hecho junto con esto

El proyecto de Neon se llamaba `empresa-ia` (resabio de cuando CRIZA vivía anidada dentro del
código de `EMPRESAS-IA`, antes del 13/08) — se renombró a `criza`. Esto es cosmético, no afecta
aislamiento de datos: se verificó contra la base real que ya solo tenía `tenant_id='criza'` (+ un
tenant de prueba insignificante), sin mezcla con otras instancias.

## Cómo usarlo

`knowledge_module/db.py` lee `DATABASE_URL` del entorno de forma *lazy* (recién en la primera
conexión) — no hace falta tocar código para apuntar a staging, alcanza con la variable de
entorno:

```bash
# En vez de exportar el .env normal, usar la variable DATABASE_URL_STAGING como DATABASE_URL:
export DATABASE_URL="$DATABASE_URL_STAGING"
python algun_script_que_escribe.py
```

Si el proceso Python ya se conectó una vez con la `DATABASE_URL` vieja (ej. un REPL o sesión
larga), hace falta `knowledge_module.db.reset_engine()` antes de la siguiente query para que
tome el nuevo valor — mismo mecanismo que ya usan los tests de integración.

`DATABASE_URL_STAGING` vive en `.env` (real, gitignored) y `.env.example` (placeholder) — mismo
patrón que el resto de las credenciales del proyecto.

## Cuándo usar staging vs. producción

| Situación | DB |
|---|---|
| Corridas de verificación de un agente ya probado (no escribe nada nuevo al modelo de `casos`) | `DATABASE_URL` (producción) — ya es la norma de la sesión, corridas reales contra el KM real |
| Desarrollo/prueba de código que escribe `frente`/`pendiente`/`documento_caso` (conectar agentes a `casos.yaml`, resto de la Etapa 4) | `DATABASE_URL_STAGING` |
| Cualquier corrida contra un caso real (Helios, MicroBigs) mientras el código que lo toca todavía no está probado | `DATABASE_URL_STAGING` |

Promover staging a producción (cuando el código ya probado en staging está listo para tocar datos
reales) no tiene automatización todavía — es una decisión manual de Sebas, caso por caso, no un
paso de CI/CD. No se construyó un mecanismo de promoción automática porque no hay hoy un caso de
uso concreto que lo pida (mismo criterio del resto de la sesión: no diseñar en abstracto).

## Refrescar el branch

Si `staging` diverge mucho de `production` con el tiempo (datos de prueba acumulados, corridas
viejas) y hace falta un punto de partida limpio: borrar el branch (`neonctl branches delete`) y
crear uno nuevo desde `production` (`neonctl branches create --parent production`) — instantáneo,
sin migración manual, es la ventaja de copy-on-write. No hay una cadencia fija definida — se
refresca cuando haga falta, no en un calendario.
