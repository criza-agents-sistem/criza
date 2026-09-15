"""
Balance de masa / rendimiento teórico de un bioproceso — utilidad compartida CRIZA.

Etapa 22 (cont., 2026-09-15): identificado en la conversación sobre qué funciones necesitan los
agentes para "simular el laboratorio" — la brecha real entre "este producto es biológicamente
posible según la literatura" (lo que ya hace search_literature) y "vale la pena con el sustrato
real que Helios tiene" (lo que faltaba). Composición real ya disponible desde ayer
(utils/archivos.py::leer_serie_de_excel); pesos moleculares e identidad química ya disponibles
(utils/pubchem.py, utils/chebi.py); la pieza que faltaba era el balance de masa que conecta todo
eso con un número real: cuánto producto se puede obtener, como máximo teórico.

Deliberadamente NO es un balanceador de ecuaciones químicas de propósito general — sería un
proyecto mucho más grande y frágil (inferir la reacción real de un bioproceso a partir de nombres
de compuestos, en general, no es un problema resuelto). En cambio, toma la relación
estequimétrica (mol producto : mol sustrato) como un dato que el propio especialista trae —
derivado de una reacción real que ya encontró con search_kegg/search_rhea, o de un paper vía
search_literature — nunca inventada por el módulo. Mismo principio de veracidad por dato que rige
el resto de CRIZA: el resultado es un TECHO TEÓRICO, nunca una medición, y así se declara.
"""


def calcular_rendimiento_teorico(
    masa_sustrato_disponible_g: float,
    peso_molecular_sustrato: float,
    peso_molecular_producto: float,
    relacion_estequiometrica_producto_sustrato: float,
    fuente_relacion_estequiometrica: str,
    eficiencia_conversion_pct: float = 100.0,
) -> dict:
    """
    Rendimiento máximo teórico de un producto vía balance de masa molar — NO una medición, un
    techo teórico. moles_sustrato = masa / PM_sustrato -> moles_producto_teorico = moles_sustrato
    * relación estequiométrica -> masa_producto_teorica = moles_producto_teorico * PM_producto ->
    ajustada por la eficiencia de conversión asumida.

    Args:
        masa_sustrato_disponible_g: masa real de sustrato limitante disponible, en gramos (el
            especialista la convierte desde la concentración real del caso — ej. g/L * litros,
            o directo de una serie leída con utils/archivos.py).
        peso_molecular_sustrato, peso_molecular_producto: g/mol (de search_pubchem — nunca un
            valor "recordado" sin verificar).
        relacion_estequiometrica_producto_sustrato: mol de producto por mol de sustrato
            consumido, según la reacción REAL (de search_kegg/search_rhea, o de un rendimiento
            reportado en un paper de search_literature) — nunca un valor inventado. Ej.: si la
            reacción produce 1 mol de producto por cada 3 moles de sustrato, este valor es
            1/3 = 0.333.
        fuente_relacion_estequiometrica: de dónde salió esa relación — obligatorio, se propaga al
            resultado para que quede auditable en el informe (veracidad por dato).
        eficiencia_conversion_pct: % del máximo teórico que se asume alcanzable en la práctica
            (default 100 = techo teórico puro, sin pérdidas — dejarlo en 100 solo si no hay
            ninguna base real para asumir menos; en bioprocesos reales casi siempre es menor,
            declarar la fuente de esa eficiencia también en el informe si se ajusta).

    Returns:
        dict con moles_sustrato, moles_producto_teorico, masa_producto_teorica_g,
        masa_producto_con_eficiencia_g, rendimiento_masico_pct (g producto / g sustrato, %),
        fuente_relacion_estequiometrica, eficiencia_conversion_pct, estado ("teórico —
        techo máximo, no validado experimentalmente"). {"error": ...} si algún dato es inválido
        (peso molecular <= 0, masa <= 0, eficiencia fuera de [0, 100]).
    """
    if masa_sustrato_disponible_g <= 0:
        return {"error": "masa_sustrato_disponible_g tiene que ser mayor que cero."}
    if peso_molecular_sustrato <= 0 or peso_molecular_producto <= 0:
        return {"error": "Los pesos moleculares tienen que ser mayores que cero."}
    if relacion_estequiometrica_producto_sustrato <= 0:
        return {"error": "relacion_estequiometrica_producto_sustrato tiene que ser mayor que cero."}
    if not (0 < eficiencia_conversion_pct <= 100):
        return {"error": "eficiencia_conversion_pct tiene que estar entre 0 (exclusivo) y 100."}
    if not fuente_relacion_estequiometrica or not fuente_relacion_estequiometrica.strip():
        return {"error": "fuente_relacion_estequiometrica es obligatoria — de dónde sale la relación mol:mol."}

    moles_sustrato = masa_sustrato_disponible_g / peso_molecular_sustrato
    moles_producto_teorico = moles_sustrato * relacion_estequiometrica_producto_sustrato
    masa_producto_teorica_g = moles_producto_teorico * peso_molecular_producto
    masa_producto_con_eficiencia_g = masa_producto_teorica_g * (eficiencia_conversion_pct / 100)
    rendimiento_masico_pct = (masa_producto_con_eficiencia_g / masa_sustrato_disponible_g) * 100

    return {
        "moles_sustrato": moles_sustrato,
        "moles_producto_teorico": moles_producto_teorico,
        "masa_producto_teorica_g": masa_producto_teorica_g,
        "masa_producto_con_eficiencia_g": masa_producto_con_eficiencia_g,
        "rendimiento_masico_pct": rendimiento_masico_pct,
        "fuente_relacion_estequiometrica": fuente_relacion_estequiometrica,
        "eficiencia_conversion_pct": eficiencia_conversion_pct,
        "estado": "teórico — techo máximo bajo la relación estequiométrica y eficiencia dadas, no validado experimentalmente",
    }
