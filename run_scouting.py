"""
Runner temporal para scouting de oportunidades agro biotech.
"""
import sys
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent))

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent / ".env", override=True)

from agent import run_agent

QUERY = """
Identificar oportunidades de negocio B2B en biotecnología para el sector agropecuario.

CONTEXTO DEL NEGOCIO:
- Modelo: producir un ingrediente biotecnológico y vendérselo a empresas que ya fabrican un producto final (B2B)
- El ingrediente reemplaza o potencia uno que esas empresas ya usan
- Sector inicial: agropecuario (regulación más liviana que alimentos humanos o farma)
- Producción: fermentación microbiana (fermentadores 500L, 28-32°C, pH 5.5-7.0)
- Infraestructura disponible: laboratorio con experiencia en fermentación, potencial acceso a una maltería (Buenas Maltas, Córdoba, Argentina)
- Dato relevante: procesos térmicos y peletizado borran la trazabilidad GMO del producto final — abre la puerta a producción con organismos GMO sin que el producto final requiera etiquetado especial

CRITERIOS DE OPORTUNIDAD:
1. La industria destino mueve mucho dinero (mercado grande, demanda establecida)
2. El ingrediente se usa en pequeñas cantidades pero tiene alto impacto en el producto final
3. Actualmente ese ingrediente es caro de producir o tiene limitaciones de disponibilidad
4. La biotecnología puede reducir el costo de producción o mejorar el rendimiento
5. Hay un dolor concreto de la industria que resolver (calidad, rendimiento, costo, consistencia)

TAREA:
1. Buscar en literatura científica ingredientes biotecnológicos emergentes o establecidos con alto valor
   en el sector agropecuario: enzimas, péptidos bioactivos, antimicrobianos naturales, aditivos funcionales,
   inoculantes, promotores de crecimiento, mejoradores de calidad de pienso/alimento animal, etc.
2. Para cada candidato identificar: qué dolor resuelve, qué industria lo consume, costo aproximado de
   producción actual, qué tan viable es producirlo por fermentación microbiana.
3. Rankear los 5-8 mejores candidatos según: tamaño de mercado, viabilidad técnica de producción por
   fermentación, ventaja competitiva potencial, tiempo al mercado.
4. Identificar cuáles se benefician más del dato GMO + procesamiento térmico (trazabilidad borrada).

IMPORTANTE: usar max_results=8 en cada búsqueda para mantener el contexto manejable.

Hacer múltiples búsquedas con distintos ángulos. No limitarse a proteínas — incluir enzimas, metabolitos,
péptidos, compuestos bioactivos.
"""


def main():
    print("Iniciando scouting agro biotech...\n")
    resultado = run_agent(QUERY, verbose=True)

    outdir = Path(__file__).parent / "outputs"
    outdir.mkdir(exist_ok=True)
    fecha = datetime.now().strftime("%Y-%m-%d")
    filepath = outdir / f"scouting_agro_{fecha}.md"

    # Manejar nombre duplicado
    counter = 1
    while filepath.exists():
        filepath = outdir / f"scouting_agro_{fecha}_{counter}.md"
        counter += 1

    with open(filepath, "w", encoding="utf-8") as f:
        f.write("# Scouting — Oportunidades Biotech Agro\n\n")
        f.write(f"**Generado:** {datetime.now().strftime('%Y-%m-%d %H:%M')}\n")
        f.write("**Agente:** CRIZA Scientific Agent v1.4\n\n")
        f.write("---\n\n")
        f.write(resultado)

    print(f"\n\nGuardado en: {filepath}")


if __name__ == "__main__":
    main()
