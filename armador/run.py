"""
Runner del Armador del Expediente — CRIZA (SEB-145)

Modos:
  1. Caso de ejemplo (testing sin KM — fitasa con output de mercado simulado)
  2. Oportunidad del KM por oportunidad_id

Al terminar: write-back al KM (si hay oportunidad_id), loop de aprendizaje, guardar expediente.
"""

import asyncio
import json
import sys
from datetime import datetime
from pathlib import Path

if sys.stdout.encoding != "utf-8":
    sys.stdout = open(sys.stdout.fileno(), mode="w", encoding="utf-8", buffering=1)
if sys.stderr.encoding != "utf-8":
    sys.stderr = open(sys.stderr.fileno(), mode="w", encoding="utf-8", buffering=1)

_ARMADOR_DIR = Path(__file__).parent
_KM_PATH = _ARMADOR_DIR.parent.parent / "knowledge_module"
sys.path.insert(0, str(_KM_PATH))

from motor import api as motor_api
import aprendizaje

from armador import run_agent

OUTPUTS_DIR = _ARMADOR_DIR / "outputs"
_AGENTE = "armador"
_TENANT = "criza"

# Caso de ejemplo: fitasa con output realista del market agent
# (simula lo que market_agent.py escribiría en props.mercado)
CASO_FITASA = {
    "nombre": "Fitasa — digestibilidad fósforo en porcinos y aves",
    "descripcion": (
        "Producción local de fitasa para nutrición animal. Problema: productores de cerdos "
        "y aves necesitan mejorar la digestibilidad del fósforo en las dietas. La fitasa "
        "degrada el ácido fítico de los granos (soja, maíz) liberando fósforo biodisponible. "
        "Hoy se importa fitasa o se usa fósforo inorgánico como suplemento."
    ),
    "props": {
        "mercado": {
            "cruce_1": {
                "dolor": "Los productores de cerdos y aves tienen baja digestibilidad de fósforo en las dietas basadas en soja/maíz, obligando a suplementar con fósforo inorgánico a alto costo y con excreción contaminante.",
                "quien_lo_sufre": {
                    "valor": "Productores porcinos (~7M cabezas AR) y avícolas (~150M aves). SENASA registra ~1.200 establecimientos porcinos habilitados y >4.000 avícolas.",
                    "estado": "establecido",
                    "fuente": "SENASA padrón productivo 2023",
                },
                "tamanio": {
                    "valor": "Mercado enzimas digestivas nutrición animal Argentina estimado USD 15–25M/año",
                    "estado": "asumido",
                    "peso": "alto",
                    "nota": "No hay cifra oficial; estimación por analogía con mercados regionales",
                },
                "urgencia": {
                    "valor": "Media-alta: regulación ambiental de efluentes con fósforo se endurece (OPDS); costo de fosfato inorgánico volátil post-pandemia",
                    "estado": "asumido",
                    "peso": "medio",
                },
                "evidencia": {
                    "fuentes": ["SENASA padrón 2023", "Corpus CONICET: 3 papers sobre fitasa en porcinos AR"],
                    "estado": "establecido",
                },
            },
            "cruce_3": {
                "que_existe": {
                    "valor": "Novozymes (Phytase 5000L), DSM (Ronozyme), BASF (Natuphos) — todos importados. Sin productor local registrado en SENASA.",
                    "estado": "establecido",
                    "fuente": "SENASA registro productos veterinarios + web cámaras 2024",
                },
                "registros": {
                    "valor": "3 patentes activas de Novozymes en espacio fitasa 6-phytase; sin patentes argentinas en INPI.",
                    "estado": "asumido",
                    "peso": "alto",
                    "nota": "Búsqueda INPI no exhaustiva — confirmar con búsqueda formal",
                },
                "intensidad": {
                    "valor": "Débil localmente: incumbentes internacionales sin presencia de fabricación AR; mercado pequeño para su escala. Espacio para productor emergente local.",
                    "estado": "asumido",
                    "peso": "alto",
                },
                "evidencia": {
                    "fuentes": ["SENASA RNE", "Web Novozymes/DSM/BASF", "Corpus CONICET patentes"],
                    "estado": "establecido",
                },
            },
            "cruce_4": {
                "encuadre_regulatorio": {
                    "valor": "SENASA: encuadre como aditivo zootécnico (Res. SENASA 593/2012). Requiere registro de producto y establecimiento elaborador.",
                    "estado": "establecido",
                    "fuente": "Res. SENASA 593/2012",
                },
                "accesibilidad_mercado_local": {
                    "valor": "Canal principal: distribuidores de insumos agropecuarios y nutricionistas independientes. Acceso a red CONINAGRO/SRA facilita entrada.",
                    "estado": "asumido",
                    "peso": "medio",
                },
                "factibilidad_de_costo": {
                    "valor": "Precio de mercado fitasa importada: USD 8–15/kg producto. Costo de producción fermentativa local: a-confirmar con planta piloto.",
                    "estado": "a-confirmar",
                    "donde_confirmar": "Cotización con INTI/empresa fermentación local o INTA Castelar",
                },
                "evidencia": {
                    "fuentes": ["SENASA normativa", "Precios spot distribuidores AR"],
                    "estado": "establecido",
                },
            },
            "bloque_6_anclas": {
                "inversion_ancla": {
                    "valor": "Planta fermentación microbiana escala piloto: USD 200K–500K (referencia INTI 2022 para bioinsumos similares)",
                    "estado": "asumido",
                    "peso": "alto",
                    "nota": "Rango amplio — requiere ingeniería de detalle",
                },
                "regulatorio_ancla": {
                    "valor": "Tiempo de registro SENASA para nuevos aditivos zootécnicos: 18–36 meses históricamente",
                    "estado": "establecido",
                    "fuente": "Experiencias previas INTA/CONICET con bioinsumos SENASA",
                },
            },
            "gaps_prioritarios": [
                "Costo de producción fermentativa local (cotizar con INTI o empresa piloto)",
                "Búsqueda formal de patentes en INPI y espacios expirados de Novozymes",
                "Validar acceso real de canal de distribución (entrevista nutricionistas)",
            ],
            "agente": "mercado",
            "fecha": "2026-06-16",
            "modelo": "claude-sonnet-4-6",
            "informe_completo": """## Análisis de Mercado — Fitasa para Nutrición Animal

**Agente:** CRIZA Market Agent v1 | **Fecha:** 2026-06-16

---

### Cruce 1 — Demanda Real No Resuelta

**Dolor identificado:** Los productores de cerdos y aves en Argentina enfrentan baja digestibilidad del fósforo en dietas basadas en soja y maíz. El ácido fítico presente en estos granos (60–80% del fósforo total) es indigestible para cerdos y aves monogástricos, lo que obliga a suplementar con fósforo inorgánico (fosfato dicálcico/monocálcico) a costos elevados y con consecuencias ambientales significativas: los animales excretan el fósforo no absorbido, contaminando suelos y napas freáticas con efluentes ricos en fósforo.

**Quién lo sufre:**
- Productores porcinos: Argentina tiene aproximadamente 7 millones de cabezas (SENASA padrón productivo 2023, establecido). Se estiman 1.200 establecimientos habilitados bajo categorías industriales y semipastoriles.
- Productores avícolas: Argentina es el 3er productor de Sudamérica. SENASA registra más de 4.000 establecimientos avícolas (incluye broilers, ponedoras y reproductoras). Producción 2023: ~2,5 millones de toneladas equivalente carcasa (dato establecido, fuente SENASA/MAGYP estadísticas agropecuarias).

**Tamaño de mercado:**
El mercado de enzimas digestivas para nutrición animal en Argentina se estima en USD 15–25 millones anuales (asumido, peso alto). No existe una cifra oficial disponible; la estimación surge de triangular:
- Precios de lista de fitasa importada: USD 8–15 por kg de producto formulado (referencia distribuidores AR, establecido)
- Consumo estimado por tonelada de alimento: 50–100 g de fitasa por tonelada, a ~100 unidades FTU/g
- Producción de alimento balanceado en Argentina: ~25 millones de toneladas anuales para monogástricos (CAENA 2022)
Esta triangulación es aproximativa; el mercado específico de fitasa es un subconjunto de enzimas.

**Urgencia del problema:**
- Media-alta y creciente por dos factores convergentes:
  1. Regulación ambiental: OPDS (Provincia de Buenos Aires) y normativas provinciales están endureciendo los límites de fósforo en efluentes de feed-lots y granjas. Las multas por incumplimiento son crecientes (asumido, peso medio — no se encontró resolución específica publicada, confirmado con nutricionistas o OPDS directamente).
  2. Volatilidad de precio de fosfato inorgánico: post-pandemia 2020-2022 el precio del fosfato dicálcico importado se triplicó. Actualmente más estable pero la dependencia de importación es un riesgo latente (establecido, fuente: series datos.gob.ar precio insumos agropecuarios).

**Evidencia de corpus científico CONICET:**
Se encontraron 3 papers en corpus local relevantes:
1. Estudio sobre eficiencia de fitasa en dietas de cerdos en destete — INTA Balcarce, 2021. Confirma ganancia de digestibilidad del 15–22% con fitasa microbiana 500 FTU/kg.
2. Paper sobre fitasas termostables producidas en Argentina (Universidad Nacional de Rosario, grupo biotech), publicado en revista regional. Indica capacidad técnica local para producción.
3. Revisión de bioinsumos para nutrición animal en Argentina — CONICET, 2022. Menciona gap de producción local de enzimas digestivas como oportunidad de sustitución.

---

### Cruce 3 — Competencia y Estado del Arte

**Qué existe en el mercado:**
El mercado está dominado por tres productores multinacionales que venden producto importado:
- **Novozymes (Dinamarca):** Phytase 5000L — líder global, precio USD 12–14/kg en AR
- **DSM (Países Bajos):** Ronozyme HiPhos — presentación granulada, precio USD 10–13/kg en AR
- **BASF (Alemania):** Natuphos E — fitasa 6-phytase de 3ra generación, precio USD 11–15/kg en AR

Todos importados. SENASA Registro Nacional de Establecimientos y Productos Veterinarios confirma que no hay productor local registrado de fitasa (establecido, verificado en RNPA SENASA online).

**Estado de patentes:**
- Novozymes tiene 3 patentes activas en el espacio de fitasa 6-phytase, que vencen entre 2026 y 2031 (asumido, peso alto — búsqueda en Espacenet, no se realizó búsqueda formal en INPI).
- En INPI Argentina: búsqueda preliminar no arrojó patentes activas de fitasa (asumido, peso medio — búsqueda no exhaustiva; se requiere búsqueda formal por abogado de PI).
- El espacio de fitasas 3-phytase (generación anterior) tiene patentes vencidas — zona de libertad de operación potencial.

**Intensidad competitiva local:**
Débil. Los tres incumbentes internacionales no tienen presencia de fabricación en Argentina. El mercado argentino (~USD 15-25M) es pequeño para su escala de operación global y no justifica inversión local por parte de ellos. Distribuyen vía importadores (Química Luar, Biogénesis Bagó, representantes menores). Hay espacio estructural para un productor emergente local que pueda ofrecer:
- Precio más competitivo (eliminando costo de importación + arancel ~10%)
- Servicio técnico local (nutricionistas propios)
- Flexibilidad de lote y plazo de entrega

---

### Cruce 4 — Viabilidad en Contexto Argentino

**Encuadre regulatorio:**
La fitasa encuadra como **aditivo zootécnico enzimático** bajo Resolución SENASA 593/2012 (establecido). Requiere:
1. Registro del establecimiento elaborador (habilitación como laboratorio productor veterinario)
2. Registro del producto: dossier técnico con caracterización del microorganismo productor, datos de eficacia y seguridad, análisis fisicoquímico del producto final.
Tiempo histórico de registro: 18–36 meses (establecido, fuente: experiencias INTA Castelar y CONICET con bioinsumos ante SENASA en los últimos 5 años).

**Acceso al mercado:**
Canal principal: distribuidores de insumos agropecuarios y asesores nutricionistas independientes. El mercado de insumos pecuarios en Argentina está bien articulado vía:
- CAENA (Cámara Argentina de Empresas de Nutrición Animal) — directorio de formuladores
- Ferias: Expoagro, AgroActiva — punto de encuentro con nutricionistas y productores
- CONINAGRO y SRA tienen redes de productores con las que una empresa emergente puede establecer contacto (asumido, peso medio).

**Factibilidad de costo de producción:**
- Precio de mercado fitasa importada: USD 8–15/kg (establecido)
- Costo de producción fermentativa local: a-confirmar. Requiere cotización con:
  - INTI (tiene planta piloto de fermentación en Miguelete)
  - Empresas de fermentación industrial (ej: Bio Sidus, Bioarsenio)
  La referencia de bioinsumos similares (enzimas celulolíticas, inoculantes líquidos) sugiere costos de producción en el rango USD 3–6/kg en escala piloto, con margen de mejora en escala industrial (asumido, peso bajo — extrapolación, requiere confirmación).

**Gaps de viabilidad principales:**
1. Costo real de producción fermentativa local (gap de mayor impacto en la decisión de inversión)
2. Encuadre del microorganismo productor por SENASA (si es OGM → trámite diferente y más complejo)
3. Acceso a cepa productora con libertad de operación (royalty-free o cepa propia)
""",
        }
    },
}


def save_expedition(nombre: str, resumen: str, expediente: dict) -> Path:
    OUTPUTS_DIR.mkdir(exist_ok=True)
    fecha = datetime.now().strftime("%Y-%m-%d")
    base = f"expediente_{nombre}_{fecha}"
    filepath_md = OUTPUTS_DIR / f"{base}.md"
    filepath_json = OUTPUTS_DIR / f"{base}.json"

    counter = 1
    while filepath_md.exists():
        filepath_md = OUTPUTS_DIR / f"{base}_{counter}.md"
        filepath_json = OUTPUTS_DIR / f"{base}_{counter}.json"
        counter += 1

    with open(filepath_md, "w", encoding="utf-8") as f:
        f.write(f"# Expediente de Decisión — {nombre.replace('_', ' ').title()}\n\n")
        f.write(f"**Generado:** {datetime.now().strftime('%Y-%m-%d %H:%M')}\n")
        f.write(f"**Agente:** CRIZA Armador v1\n\n---\n\n")
        f.write(resumen)

    with open(filepath_json, "w", encoding="utf-8") as f:
        json.dump(expediente, f, ensure_ascii=False, indent=2)

    return filepath_md


async def main():
    print("\n" + "=" * 55)
    print("  ARMADOR DEL EXPEDIENTE CRIZA v1")
    print("=" * 55)
    print("\nModo de input:\n")
    print("  1. Caso de ejemplo (fitasa, testing sin KM)")
    print("  2. Oportunidad del KM (oportunidad_id)")
    print()

    choice = input("Opción (1-2): ").strip()

    oportunidad_id = None
    oportunidad_dict = None
    nombre = "expediente"

    if choice == "1":
        oportunidad_dict = CASO_FITASA
        nombre = "fitasa_nutricion_animal"
        print(f"\nUsando caso de ejemplo: {CASO_FITASA['nombre']}\n")
    elif choice == "2":
        oportunidad_id = input("\noportunidad_id (UUID del KM): ").strip()
        if not oportunidad_id:
            print("ID vacío. Saliendo.")
            sys.exit(1)
        nombre = f"oportunidad_{oportunidad_id[:8]}"
    else:
        print("Opción inválida.")
        sys.exit(1)

    resumen, expediente, lecciones_auto = await run_agent(
        oportunidad_id=oportunidad_id,
        oportunidad_dict=oportunidad_dict,
        verbose=True,
    )

    print("\n" + "=" * 60)
    print("  EXPEDIENTE DE DECISIÓN")
    print("=" * 60 + "\n")
    print(resumen)

    # Write-back al KM (solo si hay oportunidad_id real)
    # Guarda: expediente estructurado (6 bloques) + informe narrativo completo (el markdown íntegro)
    if oportunidad_id and expediente:
        datos_expediente = {**expediente, "informe_completo": resumen}
        result = await motor_api.actualizar_props(oportunidad_id, {"expediente": datos_expediente}, tenant=_TENANT)
        if result.get("success"):
            print(f"\n  KM actualizado: oportunidad {oportunidad_id[:8]}... → expediente + informe completo escritos.")
        else:
            print(f"\n  Error en write-back KM: {result.get('error')}")

    # Loop de aprendizaje — guardar lecciones de caso
    for leccion in lecciones_auto:
        await aprendizaje.guardar_leccion_caso(
            contenido=leccion,
            agente=_AGENTE,
            contexto=nombre,
            oportunidad_id=oportunidad_id,
            tenant=_TENANT,
        )

    # Cierre — prompt humano para lección de proceso
    await aprendizaje.cierre_aprendizaje(agente=_AGENTE, lecciones_auto=lecciones_auto)

    # Guardar expediente
    filepath = save_expedition(nombre, resumen, expediente)
    print(f"  Expediente guardado: {filepath}")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    asyncio.run(main())
