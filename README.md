# Agente Científico CRIZA

Analiza la viabilidad técnica de producir proteínas por fermentación microbiana y entrega un brief técnico con recomendaciones accionables para el laboratorio.

## Qué hace

Dado un objetivo de producción (proteína + contexto del fermentador), el agente:

1. Revisa la literatura científica disponible en PubMed
2. Recupera la secuencia proteica desde UniProt
3. Predice la estructura 3D y evalúa confianza de plegamiento con ESMFold
4. Sintetiza todo en un brief técnico estructurado con host recomendado, condiciones de fermentación, rendimiento esperado, compatibilidad con el setup y experimentos concretos para el laboratorio

El laboratorio recibe hipótesis ya filtradas — no preguntas abiertas.

---

## Instalación

**Requisitos:** Python 3.10+

```bash
cd scientific_agent
pip install -r requirements.txt
```

**Dependencias:**
```
anthropic>=0.49.0
requests>=2.31.0
python-dotenv>=1.0.0
```

**Configuración de API key:**

Crear el archivo `.env` en esta carpeta:
```
ANTHROPIC_API_KEY=sk-ant-...
```

Opcionalmente agregar clave de NCBI para mayor rate limit en PubMed:
```
NCBI_API_KEY=...
```

---

## Uso

```bash
python run.py
```

El CLI muestra un menú con análisis preconfigurados y opción de input personalizado:

```
1. Lactoferrina bovina
2. Proteína de arveja (pea protein)
3. Beta-lactoglobulina recombinante
4. Input personalizado
```

El resultado se imprime en consola y se guarda automáticamente como `.txt` con timestamp en la misma carpeta.

---

## Estructura del proyecto

```
scientific_agent/
├── agent.py          # Loop agéntico principal, definición de tools y system prompt
├── run.py            # CLI runner con casos preconfigurados
├── requirements.txt
├── .env              # API keys (no versionar)
├── .env.example      # Template de configuración
└── tools/
    ├── __init__.py   # Exports públicos
    ├── pubmed.py     # Búsqueda en PubMed via NCBI E-utilities
    ├── uniprot.py    # Recuperación de secuencias via UniProt REST API
    └── esmfold.py    # Predicción de estructura via ESM Atlas API
```

---

## Output

El agente produce un brief técnico con las siguientes secciones:

| Sección | Contenido |
|---|---|
| Proteína analizada | Nombre, función, justificación como candidata |
| Sistema de expresión recomendado | Host microbiano con evidencia bibliográfica |
| Condiciones de fermentación | Temperatura, pH, medio, inductor, tiempo |
| Compatibilidad con el setup | Análisis honesto de fit, adaptaciones requeridas, riesgos |
| Rendimiento esperado | Rango en g/L basado en literatura |
| Análisis estructural | pLDDT, interpretación, implicancia para expresión |
| Experimentos concretos | 3–5 experimentos priorizados para validación en wet lab |
| Limitaciones | Qué no puede predecirse sin experimentación |
| Fuentes | PMIDs con links a PubMed |

---

## Contexto del productor (caso base)

El system prompt está configurado para el contexto de Andrés (Buenas Maltas):

- Fermentadores tipo cervecero, ~500 litros
- Temperatura: 28–32°C
- pH: 5.5–7.0
- Experiencia en fermentación industrial, sin capacidad de ingeniería genética
- Preferencia por organismos GRAS para uso alimentario

Para adaptar a otro productor, modificar el system prompt en `agent.py`.

---

## Herramientas disponibles (v0)

| Tool | API | Propósito |
|---|---|---|
| `search_pubmed` | NCBI E-utilities | Revisión de literatura científica |
| `get_protein_sequence` | UniProt REST | Secuencia y metadata de la proteína objetivo |
| `predict_structure` | ESM Atlas (Meta) | Score de confianza estructural (pLDDT) |

Ver `ARCHITECTURE.md` para decisiones de diseño y roadmap.
