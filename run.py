"""
Runner del Agente Científico CRIZA
Uso: python run.py
"""

import os
import sys
from datetime import datetime
from pathlib import Path
from agent import run_agent


OUTPUTS_DIR = Path(__file__).parent / "outputs"

CASOS = {
    "1": {
        "nombre": "lactoferrina_bovina",
        "display": "Lactoferrina bovina",
        "query": (
            "Analizar la viabilidad técnica de producir lactoferrina bovina "
            "para suplementos nutricionales en fermentadores tipo cervecero:\n"
            "- Capacidad: ~500 litros\n"
            "- Temperatura operativa: 28–32°C\n"
            "- pH: 5.5–7.0\n"
            "- El productor tiene experiencia en fermentación pero NO en ingeniería genética\n"
            "- Necesita un socio científico que haya desarrollado el sistema de expresión\n\n"
            "Determinar: microorganismo host más adecuado, condiciones de fermentación, "
            "compatibilidad con el setup, rendimiento esperado, análisis estructural "
            "y experimentos concretos para que el laboratorio valide."
        ),
    },
    "2": {
        "nombre": "pea_protein",
        "display": "Proteína de arveja (pea protein)",
        "query": (
            "Analizar la viabilidad de producir proteína de arveja recombinante "
            "(Pisum sativum legumin/vicilin) para suplementos plant-based "
            "en fermentadores tipo cervecero (500L, 28–32°C, pH 5.5–7.0).\n"
            "Evaluar si la producción recombinante microbiana compite con "
            "la extracción directa de arveja, y en qué escenarios tiene sentido."
        ),
    },
    "3": {
        "nombre": "beta_lactoglobulina",
        "display": "Beta-lactoglobulina recombinante",
        "query": (
            "Analizar viabilidad de producir beta-lactoglobulina recombinante "
            "para suplementos proteicos en fermentadores tipo cervecero "
            "(500L, 28–32°C, pH 5.5–7.0). "
            "Determinar host, condiciones, compatibilidad y experimentos a validar."
        ),
    },
}


def save_brief(nombre: str, query: str, resultado: str) -> Path:
    """Guarda el brief en outputs/ como markdown. Retorna el path del archivo."""
    OUTPUTS_DIR.mkdir(exist_ok=True)
    fecha = datetime.now().strftime("%Y-%m-%d")
    filename = f"brief_{nombre}_{fecha}.md"
    filepath = OUTPUTS_DIR / filename

    # Si ya existe un archivo con ese nombre, agregar sufijo numérico
    counter = 1
    while filepath.exists():
        filename = f"brief_{nombre}_{fecha}_{counter}.md"
        filepath = OUTPUTS_DIR / filename
        counter += 1

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(f"# Brief Técnico — {nombre.replace('_', ' ').title()}\n\n")
        f.write(f"**Generado:** {datetime.now().strftime('%Y-%m-%d %H:%M')}\n")
        f.write(f"**Agente:** CRIZA Scientific Agent v1.4\n\n")
        f.write("---\n\n")
        f.write("## Query\n\n")
        f.write(query + "\n\n")
        f.write("---\n\n")
        f.write(resultado)

    return filepath


def main():
    print("\n" + "=" * 50)
    print("  AGENTE CIENTIFICO CRIZA")
    print("=" * 50)
    print("\nSeleccioná el análisis a correr:\n")
    for key, caso in CASOS.items():
        print(f"  {key}. {caso['display']}")
    print("  4. Input personalizado")
    print()

    choice = input("Opción (1-4): ").strip()

    if choice in CASOS:
        query = CASOS[choice]["query"]
        nombre = CASOS[choice]["nombre"]
        display = CASOS[choice]["display"]
    elif choice == "4":
        display = input("\nNombre corto del análisis (ej: insulina_humana): ").strip()
        nombre = display.lower().replace(" ", "_")
        if not nombre:
            print("Input vacío. Saliendo.")
            sys.exit(1)
        print(f"\nDescribí el objetivo del análisis:")
        query = input("> ").strip()
        if not query:
            print("Input vacío. Saliendo.")
            sys.exit(1)
    else:
        print("Opción inválida.")
        sys.exit(1)

    print(f"\nIniciando análisis: {display}\n")

    # Correr agente
    resultado = run_agent(query, verbose=True)

    # Mostrar brief
    print("\n" + "=" * 60)
    print("  BRIEF TECNICO FINAL")
    print("=" * 60 + "\n")
    print(resultado)

    # Guardar automáticamente
    filepath = save_brief(nombre, query, resultado)
    print("\n" + "=" * 60)
    print(f"  Brief guardado en:")
    print(f"  {filepath}")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    main()
