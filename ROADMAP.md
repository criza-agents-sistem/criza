# Roadmap — Agente Científico CRIZA

> ⚠️ INSTRUCCIÓN PARA CLAUDE: Al iniciar cualquier sesión de desarrollo del agente científico,
> leer este archivo primero y mostrar el estado actual del roadmap antes de arrancar.
> Esto evita que trabajo planificado se pierda entre sesiones.

---

## Estado actual: v1 ✅

**Fecha de entrega:** Mayo 2026  
**Protocolo completo:**
```
PubMed (literatura) → UniProt (secuencia) → ESMFold (estructura + PDB)
→ analyze_stability (regiones débiles) → design_variants (candidatas)
→ compare_variants (validación computacional) → Brief técnico
```

### Herramientas activas

| Tool | Archivo | Estado | API / Método |
|---|---|---|---|
| `search_pubmed` | `tools/pubmed.py` | ✅ Producción | NCBI E-utilities |
| `get_protein_sequence` | `tools/uniprot.py` | ✅ Producción | UniProt REST |
| `predict_structure` | `tools/esmfold.py` | ✅ Producción | ESM Atlas API (Meta) |
| `analyze_stability` | `tools/stability.py` | ✅ Producción | Sin API — análisis pLDDT |
| `design_variants` | `tools/variants.py` | ✅ Producción | Rule-based (ver nota) |
| `compare_variants` | `tools/compare.py` | ✅ Producción | ESMFold sobre variantes |

**Nota sobre `design_variants`:** Implementación actual es rule-based (sustituciones de prolina, mutaciones de consenso, combinadas). Funciona y produce variantes validadas científicamente. La mejora a ProteinMPNN (ML) está planificada para v1.1.

---

## v1.1 — Pendiente 🔲

### [v1.1-0] Migrar search_pubmed → Semantic Scholar

**Por qué:** CRIZA apunta a ser multi-rubro (biotecnología, agricultura, agroindustria, materiales, etc.). PubMed cubre bien ciencias biomédicas pero tiene cobertura parcial fuera de ese dominio. Semantic Scholar cubre 200M+ papers de todos los dominios científicos, incluyendo todo PubMed.

**Implementación:**
```python
# tools/semantic_scholar.py — reemplaza tools/pubmed.py
# API gratuita: https://api.semanticscholar.org/graph/v1/paper/search
# Misma interfaz que search_pubmed() para compatibilidad
def search_literature(query: str, max_results: int = 10) -> dict:
    ...
```

**Impacto en agent.py:** cambiar import + nombre del tool. El workflow y el prompt no cambian.

**Prioridad:** Alta — cambio simple con alto impacto en cobertura

---

### [v1.1-A] Integrar ProteinMPNN para diseño de variantes basado en ML

**Por qué importa:** La versión actual de `design_variants` usa reglas basadas en conocimiento publicado (bien validadas, pero limitadas en diversidad). ProteinMPNN explora el espacio de secuencias de forma más amplia y puede descubrir variantes no obvias.

**Estado actual del problema:** ProteinMPNN no tiene instalación pip estándar — es un repo de scripts (`github.com/dauparas/ProteinMPNN`). Opciones:
1. Clonar repo y llamar como subprocess (más simple)
2. Usar ESM-IF1 via `fair-esm` pip package (alternativa Meta)
3. API de Hugging Face si algún modelo está hosteado

**Input necesario:** Archivo PDB de la estructura (ya lo generamos y guardamos en `structures/` desde v1)

**Implementación sugerida:**
```python
# tools/mpnn.py
def design_variants_mpnn(pdb_path: str, protein_name: str, n_sequences: int = 20) -> dict:
    # Corre ProteinMPNN sobre el PDB
    # Retorna N secuencias diseñadas con scores
    # El agente luego corre compare_variants sobre las top 5
```

**Prioridad:** Alta — es la mejora de mayor impacto técnico para v2

---

### [v1.1-B] Predicción de Tm (temperatura de desnaturalización)

**Por qué importa:** Actualmente el agente encuentra Tm en PubMed cuando está publicado, pero no puede predecir Tm de variantes diseñadas. Para decir "esta variante aguanta X°C" necesitamos cálculo computacional.

**Opciones evaluadas:**
- **FoldX:** Más preciso, calcula ΔΔG de mutaciones → estima cambio de Tm. Requiere instalación local y registro (gratuito para académicos). Tiene CLI que se puede llamar desde Python.
- **DynaMut / mCSM:** Web servers, sin API REST documentada — difícil de automatizar.
- **Aproximación actual:** Usamos delta pLDDT como proxy + Tm de literatura. Funciona pero no es directo.

**Implementación sugerida:**
```python
# tools/foldx.py
def predict_tm_change(wildtype_pdb: str, mutations: list[dict]) -> dict:
    # Corre FoldX BuildModel + Stability
    # Retorna ΔΔG y estimación de ΔTm
```

**Prerequisito:** Instalar FoldX en el entorno de ejecución

---

### [v1.1-C] Expandir ESMFold a secuencias completas

**Por qué importa:** Actualmente analizamos solo los primeros 200 aa por limitaciones de la API pública de ESM Atlas. Proteínas largas (lactoferrina: 708 aa) se analizan parcialmente.

**Solución:** Correr ESMFold localmente (modelo open-source disponible via `fair-esm`)
```bash
pip install fair-esm torch
```

**Implementación sugerida:**
```python
# tools/esmfold_local.py
def predict_structure_local(sequence: str, protein_name: str) -> dict:
    # Usa fair-esm local — sin límite de longitud, sin timeout
    # Misma interfaz que predict_structure() para compatibilidad
```

**Prerequisito:** GPU recomendada para secuencias largas (o CPU con ~20-30 min de cómputo)

---

## v2 — Backlog 🗂️

### [v2-A] Integración con Knowledge Module

**Qué es:** Cargar documentación de laboratorios socios (protocolos, experimentos fallidos, condiciones optimizadas localmente) en la capa de conocimiento del agente.

**Impacto:** El agente aprende calibraciones y condiciones específicas del laboratorio socio. Crea ventaja competitiva no replicable — ningún modelo global tiene esa información.

**Prerequisito:** Diseño del Knowledge Module (tarea SEB-7 en Linear, en Backlog)

---

### [v2-B] Análisis multi-proteína en paralelo

**Qué es:** Dado un objetivo de producción, evaluar y comparar 3–5 proteínas candidatas simultáneamente en lugar de una sola.

**Caso de uso:** "Quiero producir una proteína antimicrobiana — ¿lactoferrina, lisozima o defensina es la mejor opción para mi fermentador?"

---

### [v2-C] AlphaFold 3 para análisis de interacciones

**Qué es:** AlphaFold 3 predice interacciones proteína-ligando, proteína-ADN, proteína-proteína — más relevante que ESMFold para casos donde la función depende de un cofactor.

**Limitación actual:** AF3 no tiene API programática pública. Accesible solo via web server manual (alphafoldserver.com).

**Prerequisito:** API programática de AF3 (en desarrollo por DeepMind/Google)

---

### [v2-D] Análisis económico integrado

**Qué es:** El agente calcula automáticamente COGS (costo de producción por kg), margen estimado y payback period para cada proteína analizada.

**Input:** Precios de reactivos, costo de energía, amortización de equipos, precio de mercado del producto.

---

## Registro de versiones

| Versión | Fecha | Cambios principales |
|---|---|---|
| v0 | Mayo 2026 | PubMed + UniProt + ESMFold. Brief técnico básico. |
| v1 | Mayo 2026 | + analyze_stability + design_variants + compare_variants. PDB persistido. Brief incluye Tm y variantes diseñadas. |
| v1.1 | Pendiente | ProteinMPNN + FoldX + ESMFold local |
| v2 | Pendiente | Knowledge Module + multi-proteína + AF3 |
