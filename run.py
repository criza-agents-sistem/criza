"""
Runner del Agente Científico CRIZA v0
Uso: python run.py
"""

import os
import sys
from datetime import datetime
from agent import run_agent


CASOS = {
    "1": {
        "nombre": "Lactoferrina bovina (test interno v0)",
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
        "nombre": "Proteína de arveja (pea protein)",
        "query": (
            "Analizar la viabilidad de producir proteína de arveja recombinante "
            "(Pisum sativum legumin/vicilin) para suplementos plant-based "
            "en fermentadores tipo cervecero (500L, 28–32°C, pH 5.5–7.0).\n"
            "Evaluar si la producción recombinante microbiana compite con "
            "la extracción directa de arveja, y en qué escenarios tiene sentido."
        ),
    },
    "3": {
        "nombre": "Beta-lactoglobulina recombinante",
        "query": (
            "Analizar viabilidad de producir beta-lactoglobulina recombinante "
            "para suplementos proteicos en fermentadores tipo cervecero "
            "(500L, 28–32°C, pH 5.5–7.0). "
            "Determinar host, condiciones, compatibilidad y experimentos a validar."
        ),
    },
}


def main():
    print("\n" + "=" * 50)
    print("  AGENTE CIENTIFICO CRIZA - v0")
    print("=" * 50)
    print("\nSeleccioná el análisis a correr:\n")
    for key, caso in CASOS.items():
        print(f"  {key}. {caso['nombre']}")
    print("  4. Input personalizado")
    print()

    choice = input("Opción (1-4): ").strip()

    if choice in CASOS:
        query = CASOS[choice]["query"]
        nombre = CASOS[choice]["nombre"]
    elif choice == "4":
        nombre = "personalizado"
        query = input("\nDescribí el objetivo de análisis:\n> ").strip()
        if not query:
            print("Input vacío. Saliendo.")
            sys.exit(1)
    else:
        print("Opción inválida.")
        sys.exit(1)

    print(f"\nIniciando análisis: {nombre}\n")

    # Run agent
    resultado = run_agent(query, verbose=True)

    # Print result
    print("\n" + "=" * 60)
    print("  BRIEF TECNICO FINAL")
    print("=" * 60 + "\n")
    print(resultado)

    # Save to file
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"resultado_{nombre.replace(' ', '_').replace('(', '').replace(')', '')}_{timestamp}.txt"
    filepath = os.path.join(os.path.dirname(__file__), filename)

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(f"AGENTE CIENTÍFICO CRIZA v0\n")
        f.write(f"Análisis: {nombre}\n")
        f.write(f"Fecha: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write("=" * 60 + "\n\n")
        f.write(resultado)

    print(f"\n✓ Resultado guardado en: {filename}")


if __name__ == "__main__":
    main()
