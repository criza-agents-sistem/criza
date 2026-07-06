# CRIZA — Estado del Sistema y Roadmap

> Documento de descripción general del proyecto: qué es, qué está desarrollado, y qué
> upgrades están previstos por componente — en dos escenarios: **versión base** (sin
> financiamiento externo) y **versión con financiamiento** (datos pagos, más cómputo, etc.).
>
> Fecha: 2026-06-02 · Para revisión de equipo (Sebas · Pablo · Andrés)

---

## 1. Qué es CRIZA

CRIZA es un sistema de agentes de IA para **transferencia de tecnología ciencia → industria**,
con foco en biotecnología en Argentina. El objetivo: encontrar productos que hoy se importan o se
producen de forma tradicional, y que podrían producirse localmente con biotecnología (fermentación
u otras técnicas), **destrabando demanda reprimida** por precio, escasez o dependencia de importación.

**Principio rector — trabajo científico, no marketing:** el sistema no asume respuestas. Compara
caminos con datos reales, distingue lo verificado de lo inferido, y declara lo que no sabe. Su
output alimenta decisiones de inversión reales (wet lab), por eso prioriza información veraz y
encuadrada en la realidad argentina, no narrativas globales.

---

## 2. El pipeline

```
   DIVERGENTE  →  CONVERGENTE  →  ESPECIALISTA  →  (decisión wet lab)
  (descubrir)     (profundizar)    (validar ciencia)
       ↑ demand-first   ↑ embudo N→1     ↑ proteínas/estructura

  Tejido conectivo (en construcción): Orquestador + Knowledge Module
```

- **Divergente:** barre oportunidades de sustitución (ancho, barato, demand-first).
- **Convergente:** toma el conjunto y converge a 1 con rigor creciente (deep-dive sobre finalistas).
- **Especialista científico:** valida la viabilidad técnica de producción (estructura, estabilidad).
- **Agente de Mercado:** datos reales de comercio y demanda.
- **Orquestador + Knowledge Module:** conectan los agentes y acumulan aprendizaje (pendientes).

---

## 3. Estado por componente

### 3.1 Agente Divergente — descubrimiento demand-first

| | |
|---|---|
| **Estado actual** | ✅ v1 construido y funcionando. Razona desde el mercado objetivo (construye el contexto él mismo), evalúa 5 palancas de sustitución, separa demanda directa vs. desbloqueo, compara vías de producción sin pre-decidir, audita la geografía de sus fuentes, y produce un artefacto trazable (razonamiento-primero, sin scores numéricos prematuros). Defensas anti-sesgo de encuadre integradas. |
| **Upgrade base** | Linter de prompt + evals de regresión de sesgo (SEB-129). Modos B y C validados (hoy validado modo A). |
| **Upgrade con financiamiento** | Acceso a **datos de aduana a nivel embarque** (NOSIS / Penta-Transaction) → desagrega precios que hoy quedan ocultos en códigos HS agregados. Acceso a **market research pago** (Mordor, Markets&Markets). Presupuesto de tokens para correr en Opus análisis profundos. |

### 3.2 Agente Convergente — deep-dive (embudo N→1)

| | |
|---|---|
| **Estado actual** | 📐 Diseñado y especificado (SEB-128). Toma el conjunto de candidatos del divergente, hace una pasada comparativa media, elimina, y profundiza solo sobre 1-2 finalistas. Pendiente de construir. |
| **Upgrade base** | Construcción v1: precio techo real, dimensionamiento de demanda latente, mapeo de fabricantes locales, camino regulatorio, go/no-go para wet lab. Circuito de outreach humano (email con aprobación). |
| **Upgrade con financiamiento** | Datos de aduana para precio techo exacto. Bases regulatorias (ANMAT/SENASA). Outreach asistido. |

### 3.3 Especialista científico — proteínas

| | |
|---|---|
| **Estado actual** | ✅ v1.4.1. Pipeline completo: literatura → secuencia (UniProt) → estructura 3D (ESMFold local en GPU) → estabilidad → diseño de variantes → validación in silico. Probado con lactoferrina (710 aa, análisis completo). |
| **Upgrade base** | FoldX para ΔΔG real (SEB-94). Más especialistas por dominio (no solo proteínas: moléculas pequeñas, metabolitos). |
| **Upgrade con financiamiento** | **AlphaFold3** (binding de ligandos, complejos multi-cadena). GPU dedicada / serverless (SEB-95) para eliminar gestión manual del pod. Acceso a literatura paga (Wiley, etc.). |

### 3.4 Agente de Mercado

| | |
|---|---|
| **Estado actual** | ✅ v0. COMTRADE (importaciones reales), datos.gob.ar, web fetch dirigido, redacción de emails con gate de aprobación humana. Etiquetas de confianza [VERIFICADO]/[ESTIMADO]/[INFERIDO]. |
| **Upgrade base** | Integración al pipeline diverge/converge (sus capacidades se absorben en el convergente). |
| **Upgrade con financiamiento** | Datos de aduana a nivel embarque (resuelve la limitación del HS agregado que vimos en lactoferrina). Gmail MCP para envío con aprobación. |

### 3.5 Knowledge Module — memoria y aprendizaje

| | |
|---|---|
| **Estado actual** | 📐 Diseñado (schema CRIZA cerrado). Pendiente de construir (SEB-121 ligero, SEB-62 completo). |
| **Upgrade base** | Versión ligera: RAG + memoria de casos + loop de aprendizaje. Persiste datos verificados para no re-buscarlos. |
| **Upgrade con financiamiento** | Embeddings BGE-m3 self-hosted (SEB-118). Infraestructura de grafo + vectores (Neon + pgvector). |

### 3.6 Orquestador

| | |
|---|---|
| **Estado actual** | 🧑 Hoy el rol de orquestador lo cumple el humano (Sebas): decide qué candidato avanza, conecta los agentes. El embrión ya existe (flujo guiado de activación del divergente). |
| **Upgrade base** | Orquestador-agente formal: rutea según el punto de entrada (producto / capacidad / abierto), pasa el artefacto entre agentes automáticamente. |
| **Upgrade con financiamiento** | Flujos asíncronos, intervención humana en momentos clave, trazado completo. |

### 3.7 Infraestructura de cómputo

| | |
|---|---|
| **Estado actual** | GPU on-demand (RunPod H200, encendido manual). ESMFold local. APIs gratuitas (OpenAlex, COMTRADE, datos.gob.ar). |
| **Upgrade base** | Serverless GPU (SEB-95) — auto-provisión, sin gestión manual. |
| **Upgrade con financiamiento** | Más capacidad GPU, AlphaFold3, ventana de tokens ampliada (Opus por defecto en análisis críticos). |

### 3.8 Disciplina de calidad — lo que protege la inversión

| | |
|---|---|
| **Estado actual** | ✅ Integrada en el divergente: principio de veracidad (dos ejes — dato real + dato pertinente a Argentina), defensas anti-sesgo de encuadre (los modelos tienden al marco USA/exportador), construcción de prompts estructural (imposible inyectar anclas), razonamiento trazable. |
| **Upgrade base** | Evals de regresión de sesgo (SEB-129) — tests fijos que garantizan que ninguna versión nueva reintroduzca el sesgo. Linter de prompts. |
| **Upgrade con financiamiento** | Observabilidad y trazado completo, gobernanza de costo de tokens (SEB-120). |

---

## 4. Qué destraba el financiamiento — resumen

| Inversión | Qué resuelve |
|---|---|
| **Datos de aduana (NOSIS/Penta)** | El gap #1 que vimos en lactoferrina: precios reales ocultos en códigos HS agregados. |
| **Market research pago** | Dimensionamiento de mercado con fuentes establecidas. |
| **AlphaFold3 + GPU dedicada** | Análisis de binding, complejos, sin gestión manual de cómputo. |
| **Embeddings + Knowledge Module** | Memoria persistente: el sistema aprende entre casos en vez de empezar de cero. |
| **Presupuesto de tokens (Opus)** | Análisis profundos sin restricción de costo en los puntos críticos. |

---

## 5. Estado de madurez (resumen visual)

```
Especialista científico   ████████████░░  v1.4.1 — operativo
Agente de Mercado         ██████████░░░░  v0 — operativo
Agente Divergente         ████████████░░  v1 — operativo (recién validado)
Agente Convergente        ████░░░░░░░░░░  diseñado, por construir
Knowledge Module          ███░░░░░░░░░░░  diseñado, por construir
Orquestador               ██░░░░░░░░░░░░  humano hoy, agente por construir
```

---

*Disciplina del proyecto: trabajo científico (no pre-decidir), información veraz y encuadrada en
la realidad argentina, decisiones documentadas con su porqué. Seguimiento en Linear (proyecto CRIZA).*
