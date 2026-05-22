# Onboarding — Agente Científico CRIZA

Bienvenido al repo `criza-platform/scientific`. Este documento te lleva de cero a correr el agente en menos de 15 minutos.

---

## Qué es esto

El **Agente Científico CRIZA** analiza la viabilidad técnica de producir proteínas de alto valor por fermentación microbiana. Dado un objetivo ("quiero producir lactoferrina bovina"), el agente:

1. Revisa literatura científica (Semantic Scholar, 200M+ papers)
2. Recupera la secuencia proteica (UniProt)
3. Predice estructura 3D y evalúa estabilidad térmica (ESMFold)
4. Diseña variantes termoestables (engineering computacional)
5. Valida variantes vs. wildtype
6. Entrega un brief técnico con hipótesis filtradas para el laboratorio

El laboratorio recibe candidatos ya priorizados — no preguntas abiertas.

**Contexto de negocio:** Este agente es la herramienta de inteligencia de una venture de biotecnología. El stack técnico vive en `criza-platform`. Docs de arquitectura de plataforma: hablar con Sebas.

---

## Prerequisitos

- **Docker Desktop** instalado y corriendo → [docker.com](https://www.docker.com/products/docker-desktop/)
- **Git** configurado
- **Acceso al repo** `criza-platform/scientific` en GitHub
- **API key de Anthropic** → pedírsela a Sebas

Si vas a contribuir con commits, también necesitás:
- SSH configurado para la cuenta `criza-platform` (ver sección SSH más abajo)

---

## Setup en 4 pasos

### 1. Clonar el repo

```bash
git clone git@github-criza:criza-platform/scientific.git
cd scientific
```

> Si `github-criza` no está en tu SSH config, ver sección **SSH multi-cuenta** más abajo.

### 2. Configurar variables de entorno

```bash
cp .env.example .env
```

Abrí `.env` y completá:

```
ANTHROPIC_API_KEY=sk-ant-...        # requerido
SEMANTIC_SCHOLAR_API_KEY=           # opcional, mejora rate limits
```

### 3. Build del contenedor

```bash
docker compose build
```

Primera vez tarda ~1-2 minutos (descarga imagen base Python + dependencias).

### 4. Verificar que todo funciona

```bash
docker compose run --rm scientific-agent python -c "from tools import search_literature, get_protein_sequence; print('OK')"
```

Tiene que imprimir `OK`. Si falla, revisá que `.env` tenga la API key.

---

## Correr el agente

```bash
docker compose run --rm scientific-agent
```

Muestra un menú con análisis preconfigurados y opción de input personalizado.

Para desarrollo con hot reload (cambios en código se reflejan sin rebuild):

```bash
docker compose run --rm scientific-agent python agent.py
```

El volumen `.:/app` está montado — editás en tu máquina, corre en el contenedor.

---

## Estructura del repo

```
scientific/
├── agent.py              # Loop agéntico principal + TOOLS + SYSTEM_PROMPT
├── run.py                # CLI runner con casos preconfigurados
├── requirements.txt      # Dependencias Python
├── Dockerfile            # Imagen del agente
├── docker-compose.yml    # Configuración de servicios
├── .env.example          # Template de variables de entorno
│
├── tools/                # Herramientas que el agente puede llamar
│   ├── __init__.py       # Exports públicos
│   ├── semantic_scholar.py  # Búsqueda bibliográfica (200M+ papers)
│   ├── pubmed.py         # Búsqueda PubMed (fallback/referencia)
│   ├── uniprot.py        # Secuencias proteicas
│   ├── esmfold.py        # Predicción estructural (pLDDT)
│   ├── stability.py      # Análisis de regiones inestables
│   ├── variants.py       # Diseño de variantes termoestables
│   └── compare.py        # Comparación variantes vs wildtype
│
├── structures/           # PDB files generados (no se versionan)
├── outputs/              # Briefs generados (no se versionan)
│
├── ARCHITECTURE.md       # Diseño técnico, decisiones, APIs usadas
├── DECISIONS.md          # Log de decisiones arquitectónicas (ADR)
├── ROADMAP.md            # Versiones planificadas y estado actual
└── ONBOARDING.md         # Este archivo
```

**Archivos clave para entender el sistema:**
1. `agent.py` — el cerebro. Acá vive el loop, los tools y el system prompt
2. `ARCHITECTURE.md` — por qué está diseñado así
3. `ROADMAP.md` — qué falta y en qué orden

---

## Cómo contribuir

### Ramas

```
main          ← producción, siempre estable
feat/<name>   ← features nuevas
fix/<name>    ← bug fixes
```

Nunca commiteés directo a `main`. Abrí una rama, hacé PR.

### Formato de commits

```
feat: descripción corta del cambio
fix: descripción del bug corregido
docs: cambio en documentación
refactor: refactor sin cambio de comportamiento
```

### Linear

Cada tarea tiene un issue en Linear (proyecto CRIZA). Antes de arrancar una tarea, movela a **In Progress**. Al terminar, **Done**.

Si encontrás algo roto o faltante que no tiene issue → creá el issue antes de arrancar.

---

## SSH multi-cuenta GitHub

Si ya tenés una cuenta personal de GitHub, necesitás una entrada separada en `~/.ssh/config` para usar la clave CRIZA:

```
# Cuenta CRIZA
Host github-criza
  HostName github.com
  User git
  IdentityFile ~/.ssh/id_criza
```

Para generar la clave CRIZA:

```bash
ssh-keygen -t ed25519 -C "criza.dev@gmail.com" -f ~/.ssh/id_criza
```

Agregá la clave pública en GitHub → Settings → SSH keys.

Verificá que funciona:

```bash
ssh -T git@github-criza
# Hi criza-dev! You've successfully authenticated...
```

---

## Contacto

- **Sebas** — producto, arquitectura, accesos → sebabizzi@gmail.com
- **Linear** → proyecto CRIZA (pedí acceso a Sebas)
