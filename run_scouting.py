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
Identificar oportunidades de producto para un negocio B2B de biotecnología.

MODELO DE NEGOCIO:
Producir o conseguir producir un ingrediente biotecnológico y vendérselo (B2B)
a empresas que ya fabrican un producto final. El ingrediente reemplaza o potencia
uno que esas empresas ya usan. La producción puede ser propia (fermentación) o
subcontratada a un socio especializado si la oportunidad lo justifica.

CONTEXTO:
- Infraestructura propia: fermentadores ~500L, 28-32°C, pH 5.5-7.0, Córdoba, Argentina.
- Acceso a subproductos de maltería como sustratos de fermentación.
- GMO + procesamiento térmico (peletizado, pasteurización, UHT): elimina trazabilidad GMO.
  Es un habilitador opcional — NO un requisito para ser candidato.
- Argentina: ventaja por sustitución de importaciones en múltiples mercados.

PEDIDO:
Buscá en el universo más amplio posible. Sin restricción de sector ni dominio.
Cubrí al menos: nutrición humana B2B, nutrición animal, agropecuario, industrial,
cosmética/cuidado personal. No te limitás a fermentación: si hay una buena
oportunidad con otra tecnología de producción, incluilá y marcá que requiere socio.

Sé exigente con el filtro: preferí 5 candidatos muy sólidos a 10 mediocres.
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
