"""
Estadística sobre series temporales — utilidad compartida CRIZA.

Etapa 22 (cont., 2026-09-14): construido después de una corrida real de análisis del efluente
de Helios (T401) donde quedó claro que ningún agente tenía forma de hacer cómputo numérico real
sobre datos que Sebas aporta — solo podían "leer" una tabla como texto y estimar a ojo, que no es
matemática confiable para correlación con desfase o clasificación de estabilidad.

Metodología validada en esa corrida real, y corregida contra un análisis independiente más
riguroso (hecho en Claude Science) que encontró un error real en la primera versión de este
trabajo: una correlación "fuerte" (r=-0.71) entre ingreso de sustrato y conductividad de un
efluente resultó ser una coincidencia de tendencias compartidas, no una relación real — al
diferenciar ambas series (comparar el cambio de un período al siguiente, no el nivel) la
correlación cayó a r=0.09, no significativa. Por eso `correlacion_con_desfase` SIEMPRE aplica
ese chequeo — no es un parámetro opcional, es la diferencia entre un hallazgo real y uno espurio
(ver docs/progress/2026-09-14.md para el caso real completo).

Convención de entrada: toda función toma listas de {"fecha": "YYYY-MM-DD", "valor": float} — la
misma forma en la que un especialista puede extraer puntos de un documento_aportado (texto) sin
necesitar acceso al archivo original. No exhaustivo, no reemplaza análisis con el dataset
completo cuando existe (ver Etapa 22 cont., el caso real de T401 se hizo con pandas directo
sobre el Excel, no con estas tools) — esto es para cuando el especialista tiene una serie
extraída, no el archivo.
"""

import numpy as np
import pandas as pd
from scipy import stats


def _a_serie(datos: list[dict]) -> pd.Series:
    """[{'fecha': 'YYYY-MM-DD', 'valor': float}, ...] -> pd.Series indexada por fecha, ordenada."""
    if not datos:
        raise ValueError("`datos` está vacío.")
    df = pd.DataFrame(datos)
    if "fecha" not in df.columns or "valor" not in df.columns:
        raise ValueError("Cada elemento de `datos` requiere las claves 'fecha' y 'valor'.")
    df["fecha"] = pd.to_datetime(df["fecha"], errors="coerce")
    df["valor"] = pd.to_numeric(df["valor"], errors="coerce")
    df = df.dropna(subset=["fecha", "valor"]).sort_values("fecha")
    return pd.Series(df["valor"].values, index=pd.DatetimeIndex(df["fecha"].values))


def analizar_estabilidad(datos: list[dict], umbral_estable: float = 15.0, umbral_variable: float = 30.0) -> dict:
    """
    Estabilidad real de una serie temporal — media, desvío, CV%, tendencia (Kendall tau, no
    paramétrica) y clasificación. Mismo criterio validado en la corrida real de Helios (Etapa 22
    cont., 2026-09-14): CV% < umbral_estable -> estable, < umbral_variable -> moderadamente
    variable, si no -> no estable. Los umbrales son una convención práctica, no una verdad
    absoluta — quedan explícitos en el resultado.

    Args:
        datos: [{"fecha": "YYYY-MM-DD", "valor": float}, ...], mínimo 5 puntos válidos.
        umbral_estable: CV% por debajo del cual se clasifica ESTABLE.
        umbral_variable: CV% por debajo del cual se clasifica MODERADAMENTE_VARIABLE (si no,
            NO_ESTABLE).

    Returns:
        dict con n, periodo, media, sd, cv_pct, min, max, tendencia (kendall_tau, p_value,
        cambio_pct_total_periodo, significativa), clasificacion, umbrales_usados.
        {"error": ...} si hay menos de 5 puntos válidos.
    """
    try:
        serie = _a_serie(datos)
    except ValueError as e:
        return {"error": str(e)}

    n = len(serie)
    if n < 5:
        return {"error": f"Se necesitan al menos 5 puntos válidos, hay {n}."}

    media = float(serie.mean())
    sd = float(serie.std())
    cv_pct = (sd / media * 100) if media else None

    dias = (serie.index - serie.index.min()).days.values.astype(float)
    if np.std(dias) > 0:
        tau, p_value = stats.kendalltau(dias, serie.values)
        slope, intercept, r, p_lin, se = stats.linregress(dias, serie.values)
        cambio_pct_total = (slope * (dias.max() - dias.min())) / media * 100 if media else None
    else:
        tau, p_value, cambio_pct_total = None, None, None
    significativa = bool(
        p_value is not None and p_value < 0.05
        and cambio_pct_total is not None and abs(cambio_pct_total) > 10
    )

    if cv_pct is None:
        clasificacion = "NO_CALCULABLE (media = 0)"
    elif cv_pct < umbral_estable:
        clasificacion = "ESTABLE"
    elif cv_pct < umbral_variable:
        clasificacion = "MODERADAMENTE_VARIABLE"
    else:
        clasificacion = "NO_ESTABLE"

    return {
        "n": n,
        "periodo": {"desde": str(serie.index.min().date()), "hasta": str(serie.index.max().date())},
        "media": media, "sd": sd, "cv_pct": cv_pct,
        "min": float(serie.min()), "max": float(serie.max()),
        "tendencia": {
            "kendall_tau": float(tau) if tau is not None else None,
            "p_value": float(p_value) if p_value is not None else None,
            "cambio_pct_total_periodo": cambio_pct_total,
            "significativa": significativa,
        },
        "clasificacion": clasificacion,
        "umbrales_usados": {"estable_bajo_cv_pct": umbral_estable, "variable_bajo_cv_pct": umbral_variable},
    }


def detectar_cambios_de_regimen(datos: list[dict], periodo: str = "M", min_periodos_sostenido: int = 2) -> dict:
    """
    Detecta cambios de NIVEL sostenidos (no ruido de un solo punto) — agrupa la serie por período
    (default mensual), compara la mediana de cada período contra el anterior con un test de
    Mann-Whitney U, y reporta como "quiebre real" solo los cambios donde el nuevo nivel se
    sostiene al menos `min_periodos_sostenido` períodos seguidos.

    Heurística real y auditable, NO un test formal de punto de cambio (Pettitt/CUSUM) — más
    simple a propósito. Encontrado real (Etapa 22 cont., 2026-09-14): el efluente de Helios tuvo
    3 regímenes distintos en 3.5 años (dilución, quiebre puntual, concentración sostenida) que un
    CV% sobre todo el período no distinguía — mezclaba las tres realidades en un solo número.

    Args:
        datos: [{"fecha": "YYYY-MM-DD", "valor": float}, ...], mínimo 10 puntos válidos.
        periodo: código de pandas Period ("M" mensual, "W" semanal, "Q" trimestral).
        min_periodos_sostenido: cuántos períodos seguidos tiene que sostenerse el nuevo nivel
            para contar como quiebre real (filtra blips de un solo período).

    Returns:
        dict con n_periodos, medianas_por_periodo, quiebres_detectados
        [{periodo, mediana_antes, mediana_despues, cambio_pct, p_value}], metodo (nota de
        limitación). {"error": ...} si hay menos de 10 puntos válidos.
    """
    try:
        serie = _a_serie(datos)
    except ValueError as e:
        return {"error": str(e)}
    if len(serie) < 10:
        return {"error": f"Se necesitan al menos 10 puntos válidos, hay {len(serie)}."}

    df = serie.to_frame("valor")
    df["periodo"] = df.index.to_period(periodo)
    medianas = df.groupby("periodo")["valor"].median()
    grupos = df.groupby("periodo")["valor"].apply(list)
    periodos_ordenados = list(medianas.index)

    quiebres = []
    for i in range(1, len(periodos_ordenados)):
        antes = grupos[periodos_ordenados[i - 1]]
        despues = grupos[periodos_ordenados[i]]
        if len(antes) < 2 or len(despues) < 2:
            continue
        try:
            _, p_value = stats.mannwhitneyu(antes, despues, alternative="two-sided")
        except ValueError:
            continue

        mediana_antes, mediana_despues = float(np.median(antes)), float(np.median(despues))
        cambio_pct = (mediana_despues - mediana_antes) / mediana_antes * 100 if mediana_antes else None
        if cambio_pct is None or p_value >= 0.05 or abs(cambio_pct) <= 10:
            continue

        punto_medio = (mediana_antes + mediana_despues) / 2
        sube = mediana_despues > mediana_antes
        sostenido = True
        for j in range(i, min(i + min_periodos_sostenido, len(periodos_ordenados))):
            m = medianas.iloc[j]
            if (sube and m < punto_medio) or (not sube and m > punto_medio):
                sostenido = False
                break
        if sostenido:
            quiebres.append({
                "periodo": str(periodos_ordenados[i]),
                "mediana_antes": mediana_antes, "mediana_despues": mediana_despues,
                "cambio_pct": cambio_pct, "p_value": float(p_value),
            })

    return {
        "n_periodos": len(medianas),
        "medianas_por_periodo": {str(k): float(v) for k, v in medianas.items()},
        "quiebres_detectados": quiebres,
        "metodo": (
            f"Mann-Whitney U entre medianas de períodos consecutivos (agrupados por '{periodo}'), "
            "exige sostenerse al menos min_periodos_sostenido períodos — heurística real, no test "
            "formal de changepoint (Pettitt/CUSUM)."
        ),
    }


def correlacion_con_desfase(
    serie_x: list[dict], serie_y: list[dict], ventana_dias: int = 7,
    lag_min_dias: int = 0, lag_max_dias: int = 90,
) -> dict:
    """
    Correlación de Pearson entre X (promedio móvil de `ventana_dias`, terminando `lag` días antes
    de cada fecha de Y) e Y, barriendo el desfase entre lag_min_dias y lag_max_dias — devuelve el
    desfase con |r| máximo.

    SIEMPRE incluye el chequeo de robustez de series diferenciadas — NO es opcional (ver
    docstring del módulo: encontrado real, una corrida sin este chequeo reportó r=-0.71 entre
    ingreso de sustrato y conductividad de un efluente que resultó espuria; diferenciada, r=0.09,
    no significativa). Si la correlación en niveles no sobrevive el chequeo, `robusta: false` y
    el resultado incluye una advertencia explícita — es la señal de que puede ser una coincidencia
    de tendencias compartidas, no una relación real con ese desfase.

    Args:
        serie_x: [{"fecha", "valor"}, ...] — la variable que se sospecha "causa" (ej. ingreso).
        serie_y: [{"fecha", "valor"}, ...] — la variable de salida, mínimo 10 puntos válidos.
        ventana_dias: ancho del promedio móvil de X.
        lag_min_dias, lag_max_dias: rango de desfases a probar (en días).

    Returns:
        dict con mejor_desfase {lag_dias, ventana_dias, r_niveles, p_niveles, n, r_diferenciada,
        p_diferenciada, robusta}, y advertencia si no es robusta. {"error": ...} si no hay
        suficiente superposición temporal o datos insuficientes.
    """
    try:
        sx, sy = _a_serie(serie_x), _a_serie(serie_y)
    except ValueError as e:
        return {"error": str(e)}
    if len(sy) < 10:
        return {"error": f"serie_y necesita al menos 10 puntos válidos, tiene {len(sy)}."}
    if len(sx) < 2:
        return {"error": f"serie_x necesita al menos 2 puntos válidos, tiene {len(sx)}."}

    idx_completo = pd.date_range(sx.index.min(), sx.index.max(), freq="D")
    x_diario = sx.reindex(idx_completo, fill_value=0.0)

    mejor = None
    for lag in range(lag_min_dias, lag_max_dias + 1):
        valores_x = []
        for f in sy.index:
            fin = f - pd.Timedelta(days=lag)
            ini = fin - pd.Timedelta(days=ventana_dias - 1)
            if ini < x_diario.index.min():
                valores_x.append(np.nan)
                continue
            valores_x.append(x_diario.loc[ini:fin].mean())
        x_ventana = pd.Series(valores_x, index=sy.index)
        mask = x_ventana.notna() & sy.notna()
        if mask.sum() < 20 or x_ventana[mask].std() == 0:
            continue
        r, p = stats.pearsonr(x_ventana[mask], sy[mask])
        if mejor is None or abs(r) > abs(mejor["r"]):
            mejor = {"lag": lag, "r": r, "p": p, "n": int(mask.sum()), "x_ventana": x_ventana, "mask": mask}

    if mejor is None:
        return {"error": "No hay suficiente superposición temporal entre las dos series para ningún desfase probado."}

    x_dif = mejor["x_ventana"][mejor["mask"]].diff().dropna()
    y_dif = sy[mejor["mask"]].diff().dropna()
    idx_comun = x_dif.index.intersection(y_dif.index)
    if len(idx_comun) >= 10 and x_dif.loc[idx_comun].std() > 0 and y_dif.loc[idx_comun].std() > 0:
        r_dif, p_dif = stats.pearsonr(x_dif.loc[idx_comun], y_dif.loc[idx_comun])
        robusta = bool(p_dif < 0.05)
    else:
        r_dif, p_dif, robusta = None, None, False

    resultado = {
        "mejor_desfase": {
            "lag_dias": mejor["lag"], "ventana_dias": ventana_dias,
            "r_niveles": float(mejor["r"]), "p_niveles": float(mejor["p"]), "n": mejor["n"],
            "r_diferenciada": float(r_dif) if r_dif is not None else None,
            "p_diferenciada": float(p_dif) if p_dif is not None else None,
            "robusta": robusta,
        },
    }
    if not robusta:
        resultado["advertencia"] = (
            "La correlación en niveles no sobrevive el chequeo de series diferenciadas — es "
            "probable que sea una coincidencia de tendencias compartidas (ambas series cambiando "
            "por razones propias en el mismo período, tipo 'ventas de helado y ahogamientos'), no "
            "una relación real con este desfase. No usar como señal operativa sin evidencia "
            "adicional."
        )
    return resultado


def comparar_fuentes(serie_a: list[dict], serie_b: list[dict], nombre_a: str = "A", nombre_b: str = "B") -> dict:
    """
    Compara dos series que deberían medir lo mismo (ej. dos laboratorios, dos métodos analíticos)
    antes de asumir que se pueden combinar en una sola serie — detecta sesgo sistemático (razón
    constante entre ambas) en vez de ruido aleatorio. Empareja por fecha exacta (pensado para
    pares de muestras duplicadas el mismo día, no series independientes).

    Encontrado real (Etapa 22 cont., 2026-09-14): dos laboratorios midiendo metales en el mismo
    efluente difirieron hasta 146x para el mismo elemento en la misma muestra (uno medía metal
    total, otro fracción disuelta) — lo que parecía "tendencia creciente" al combinar ambas series
    era en realidad el cambio de laboratorio a lo largo del tiempo, no un cambio real.

    Args:
        serie_a, serie_b: [{"fecha", "valor"}, ...] — mínimo 2 fechas en común con valores
            no-nulos y no-cero.
        nombre_a, nombre_b: etiquetas para el resultado (ej. nombres de laboratorio).

    Returns:
        dict con n_pares, razon_media_<A>_sobre_<B>, razon_min, razon_max, cv_de_la_razon_pct,
        diferencia_media, comparables (bool), interpretacion. {"error": ...} si hay menos de 2
        fechas en común.
    """
    try:
        sa, sb = _a_serie(serie_a), _a_serie(serie_b)
    except ValueError as e:
        return {"error": str(e)}

    pares = sa.to_frame("valor_a").join(sb.to_frame("valor_b"), how="inner")
    pares = pares[(pares["valor_a"] != 0) & (pares["valor_b"] != 0)]
    if len(pares) < 2:
        return {"error": f"Se necesitan al menos 2 fechas en común con valores no nulos/no-cero, hay {len(pares)}."}

    razones = pares["valor_a"] / pares["valor_b"]
    diferencias = pares["valor_a"] - pares["valor_b"]
    cv_razon = float(razones.std() / razones.mean() * 100) if razones.mean() else None
    comparables = bool(cv_razon is not None and cv_razon < 30 and 0.5 < razones.mean() < 2.0)

    return {
        "n_pares": len(pares),
        f"razon_media_{nombre_a}_sobre_{nombre_b}": float(razones.mean()),
        "razon_min": float(razones.min()), "razon_max": float(razones.max()),
        "cv_de_la_razon_pct": cv_razon,
        "diferencia_media": float(diferencias.mean()),
        "comparables": comparables,
        "interpretacion": (
            "Comparables -- la razón entre fuentes es estable, la diferencia observada es ruido, "
            "no sesgo sistemático."
            if comparables else
            "NO comparables -- la razón entre fuentes varía de forma sistemática o el nivel medio "
            "difiere demasiado. No combinar estas dos series en una sola sin corregir el sesgo "
            "primero."
        ),
    }
