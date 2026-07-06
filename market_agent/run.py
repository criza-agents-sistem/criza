"""
Runner del Agente de Mercado CRIZA v1 (SEB-148)

Modos:
  1-3. Caso de ejemplo (testing sin KM)
  4.   Oportunidad del KM por oportunidad_id
  5.   Texto libre

Al terminar: write-back al KM (si hay oportunidad_id), loop de aprendizaje, guardar informe.
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

_KM_PATH = Path(__file__).parent.parent.parent / "knowledge_module"
sys.path.insert(0, str(_KM_PATH))

from motor import api as motor_api
import aprendizaje

from market_agent import run_agent

OUTPUTS_DIR = Path(__file__).parent / "outputs"
_AGENTE = "mercado"
_TENANT = "criza"

# Casos de ejemplo para testing sin KM (reemplazar hardcoding v0 centrado en COMTRADE)
CASOS = {
    "1": {
        "nombre": "fitasa_nutricion_animal",
        "display": "Fitasa — digestibilidad fósforo en porcinos/aves",
        "texto": (
            "Oportunidad a evaluar: producción local de fitasa para nutrición animal.\n"
            "Problema: productores de cerdos y aves necesitan mejorar la digestibilidad del fósforo "
            "en las dietas. La fitasa degrada el ácido fítico de los granos (soja, maíz) liberando "
            "fósforo biodisponible. Hoy se importa fitasa o se usa fósforo inorgánico como suplemento.\n"
            "Sector: producción porcina (Argentina ~7M cabezas) y avícola (gran productor regional).\n"
            "Evaluar: ¿hay demanda real no resuelta, qué soluciones existen, "
            "y hay espacio para un productor emergente argentino?"
        ),
    },
    "2": {
        "nombre": "lactoferrina_bovino",
        "display": "Lactoferrina bovina — proteína antimicrobiana",
        "texto": (
            "Oportunidad a evaluar: producción de lactoferrina bovina en Argentina.\n"
            "Problema: la lactoferrina es una proteína con propiedades antimicrobianas "
            "usada en suplementos y alimentos funcionales. Se importa de Nueva Zelanda/Europa.\n"
            "Argentina es el mayor productor de leche de Sudamérica.\n"
            "Evaluar: ¿hay mercado local real para lactoferrina, quiénes la usarían, "
            "qué soluciones existen, y es viable producirla acá?"
        ),
    },
    "3": {
        "nombre": "enzimas_coluliticas_bovinos",
        "display": "Complejo celulolítico — digestión fibra en rumiantes",
        "texto": (
            "Oportunidad a evaluar: enzimas celulolíticas para mejorar la digestión de fibra "
            "en bovinos de carne y tambo.\n"
            "Problema: la digestibilidad de la fibra en bovinos es baja. Complejos enzimáticos "
            "(celulasas, xilanasas) pueden mejorarla, reduciendo consumo de proteína y mejorando "
            "la conversión. Argentina tiene el rodeo bovino más grande de América fuera de Brasil.\n"
            "Evaluar: ¿hay demanda real, soluciones locales, y espacio para un bioinsumo argentino?"
        ),
    },
}


def save_report(nombre: str, descripcion: str, resumen: str, cruces: dict) -> Path:
    OUTPUTS_DIR.mkdir(exist_ok=True)
    fecha = datetime.now().strftime("%Y-%m-%d")
    filename = f"market_report_{nombre}_{fecha}.md"
    filepath = OUTPUTS_DIR / filename

    counter = 1
    while filepath.exists():
        filename = f"market_report_{nombre}_{fecha}_{counter}.md"
        filepath = OUTPUTS_DIR / filename
        counter += 1

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(f"# Informe de Mercado — {nombre.replace('_', ' ').title()}\n\n")
        f.write(f"**Generado:** {datetime.now().strftime('%Y-%m-%d %H:%M')}\n")
        f.write(f"**Agente:** CRIZA Market Agent v1\n\n")
        f.write("---\n\n")
        f.write("## Oportunidad analizada\n\n")
        f.write(descripcion + "\n\n")
        f.write("---\n\n")
        f.write(resumen)
        if cruces:
            f.write("\n\n---\n\n## Cruces estructurados (KM write-back)\n\n```json\n")
            f.write(json.dumps(cruces, ensure_ascii=False, indent=2))
            f.write("\n```\n")

    return filepath


async def main():
    print("\n" + "=" * 55)
    print("  AGENTE DE MERCADO CRIZA v1")
    print("=" * 55)
    print("\nModo de input:\n")
    print("  1-3. Caso de ejemplo (testing sin KM)")
    print("  4.   Oportunidad del KM (oportunidad_id)")
    print("  5.   Texto libre")
    print()

    choice = input("Opción (1-5): ").strip()

    oportunidad_id = None
    texto_libre = None
    nombre = "mercado"
    descripcion = ""

    if choice in CASOS:
        caso = CASOS[choice]
        nombre = caso["nombre"]
        descripcion = caso["display"]
        texto_libre = caso["texto"]
    elif choice == "4":
        oportunidad_id = input("\noportunidad_id (UUID del KM): ").strip()
        if not oportunidad_id:
            print("ID vacío. Saliendo.")
            sys.exit(1)
        nombre = f"oportunidad_{oportunidad_id[:8]}"
        descripcion = f"Oportunidad KM: {oportunidad_id}"
    elif choice == "5":
        nombre = input("\nNombre corto del análisis (ej: beta_glucanasa): ").strip() or "mercado_libre"
        nombre = nombre.lower().replace(" ", "_")
        print("\nDescribí la oportunidad (sector, problema, qué evaluar):")
        texto_libre = input("> ").strip()
        if not texto_libre:
            print("Input vacío. Saliendo.")
            sys.exit(1)
        descripcion = texto_libre[:100]
    else:
        print("Opción inválida.")
        sys.exit(1)

    print(f"\nIniciando análisis: {descripcion}\n")

    resumen, cruces, lecciones_auto = await run_agent(
        oportunidad_id=oportunidad_id,
        texto_libre=texto_libre,
        verbose=True,
    )

    # Mostrar resultado
    print("\n" + "=" * 60)
    print("  INFORME DE MERCADO")
    print("=" * 60 + "\n")
    print(resumen)

    # Write-back al KM (solo si hay oportunidad_id)
    # Guarda: resultado estructurado (cruces) + informe narrativo completo
    if oportunidad_id and cruces:
        datos_mercado = {**cruces, "informe_completo": resumen}
        result = await motor_api.actualizar_props(oportunidad_id, {"mercado": datos_mercado}, tenant=_TENANT)
        if result.get("success"):
            print(f"\n  KM actualizado: oportunidad {oportunidad_id[:8]}... → cruces 1/3/4 + informe completo escritos.")
        else:
            print(f"\n  Error en write-back KM: {result.get('error')}")

    # Loop de aprendizaje — guardar lecciones de caso
    for leccion in lecciones_auto:
        await aprendizaje.guardar_leccion_caso(
            contenido=leccion,
            agente=_AGENTE,
            contexto=descripcion,
            oportunidad_id=oportunidad_id,
            tenant=_TENANT,
        )

    # Cierre — prompt humano para lección de proceso
    await aprendizaje.cierre_aprendizaje(agente=_AGENTE, lecciones_auto=lecciones_auto)

    # Guardar informe markdown
    filepath = save_report(nombre, descripcion, resumen, cruces)
    print(f"  Informe guardado: {filepath}")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    asyncio.run(main())
