"""
Runner del Scout Científico Multidominio — CRIZA / EMPRESAS-IA

Uso: python run_scouting.py
El scout barre el universo de productos posibles y devuelve candidatos
rankeados con tag de dominio. NO hace análisis profundo — eso es del
especialista correspondiente una vez que el usuario / orquestador decide.

Modelo: claude-sonnet-4-6 por defecto (configurable en .env con SCOUT_MODEL).
"""
import sys
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent))

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent / ".env", override=True)

from scout import run_scout

# ──────────────────────────────────────────────
# QUERY DE SCOUTING
# Editá esto para cambiar el objetivo del barrido.
# ──────────────────────────────────────────────

QUERY = """
Identificar oportunidades de producto para un negocio B2B en biotecnología.

CONTEXTO:
- Modelo de negocio: producir un ingrediente biotecnológico y vendérselo a empresas
  que ya fabrican un producto final (B2B). El ingrediente reemplaza o potencia uno que ya usan.
- Infraestructura disponible: fermentadores ~500L (28-32°C, pH 5.5-7.0), experiencia
  en fermentación industrial. Acceso potencial a una maltería en Córdoba, Argentina.
- Sector inicial: agropecuario (regulación más liviana que humano/farma).
- Dato relevante: procesamiento térmico y peletizado borran la trazabilidad GMO —
  abre la puerta a producción con organismos GMO sin etiquetado especial en el producto final.

CRITERIOS DE OPORTUNIDAD:
1. Mercado grande y establecido (demanda real, no especulativa)
2. Ingrediente de pequeñas cantidades con alto impacto en el producto final
3. Actualmente caro de producir o con limitaciones de abastecimiento
4. La fermentación microbiana puede mejorar costo, rendimiento o disponibilidad
5. Dolor concreto en la industria destino

PEDIDO EXPLÍCITO:
- Explorá TODO el universo: enzimas, proteínas, moléculas pequeñas, ácidos orgánicos,
  pigmentos, bacteriocinas, vitaminas, biosurfactantes, biopolímeros, etc.
- No te limites a proteínas. El sesgo hacia proteínas empobrece el resultado.
- Sé exigente: preferí 5 candidatos muy sólidos a 10 candidatos mediocres.
"""


def main():
    print("Iniciando scout multidominio...\n")
    resultado = run_scout(QUERY, verbose=True)

    # Guardar output
    outdir = Path(__file__).parent / "outputs"
    outdir.mkdir(exist_ok=True)
    fecha = datetime.now().strftime("%Y-%m-%d")
    filepath = outdir / f"scout_{fecha}.md"

    counter = 1
    while filepath.exists():
        filepath = outdir / f"scout_{fecha}_{counter}.md"
        counter += 1

    with open(filepath, "w", encoding="utf-8") as f:
        f.write("# Scout Científico Multidominio — CRIZA\n\n")
        f.write(f"**Generado:** {datetime.now().strftime('%Y-%m-%d %H:%M')}\n")
        f.write("**Agente:** Scout Multidominio v1.0 (claude-sonnet-4-6)\n\n")
        f.write("---\n\n")
        f.write(resultado)

    print(f"\n\nGuardado en: {filepath}")


if __name__ == "__main__":
    main()
