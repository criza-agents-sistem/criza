"""
Lectura de archivos tabulares originales (Excel) aportados a un caso — utilidad compartida CRIZA.

Etapa 22 (cont., 2026-09-15): hasta ahora un `documento_aportado` solo persistía el texto
extraído de un archivo — para un Excel eso pierde la estructura tabular por completo (confirmado
real: `.xlsx` ni siquiera estaba en `_EXTENSIONES_SOPORTADAS` de `api/main.py`, subirlo fallaba
directo). Sebas, sobre el caso real de Helios (2026-09-15): "los agentes no se pueden
auto-abastecer... necesitan que yo le pida a Claude Science o a vos esos datos, con los riesgos
que eso tiene (sesgos, contexto, etc.)" — el dato de un caso real (T401) se sigue actualizando
con el tiempo, depender de una extracción manual cada vez no escala ni es auditable.

Este módulo guarda además los BYTES ORIGINALES (base64, en el mismo prop JSONB del documento —
sin migración de schema) y los relee bajo demanda con los parámetros exactos que se necesiten
(hoja, columnas, filtro) — nunca intenta "adivinar" la estructura del archivo sola: los Excel
reales de este proyecto tienen headers desplazados, múltiples códigos mezclados en una misma
hoja y metadata de laboratorio antes de la tabla real (ver docs/progress/2026-09-14.md) — pedir
los parámetros explícitos es más seguro que un auto-detección que puede fallar en silencio.

Tope de tamaño: 8 MB (generoso para los Excel de laboratorio/logística de este proyecto — no
pensado para archivos masivos; si aparece esa necesidad, hace falta blob storage real, no JSONB).
"""

import base64
import io

import pandas as pd

_MAX_BYTES_ARCHIVO = 8 * 1024 * 1024


def codificar_archivo(contenido: bytes) -> str:
    """Bytes crudos -> string base64 para persistir en un prop JSONB. Levanta ValueError si
    supera el tope de tamaño."""
    if len(contenido) > _MAX_BYTES_ARCHIVO:
        raise ValueError(f"Archivo de {len(contenido):,} bytes supera el tope de {_MAX_BYTES_ARCHIVO:,} bytes.")
    return base64.b64encode(contenido).decode("ascii")


def previsualizar_excel(contenido: bytes, max_filas_preview: int = 5) -> str:
    """
    Texto legible para mostrar en el chat / guardar como 'contenido' del documento_aportado —
    lista de hojas, sus columnas (fila 1 cruda, sin asumir dónde está el header real) y las
    primeras filas. NO reemplaza leer_serie_de_excel para cómputo real — es solo para que Sebas
    o el agente vean qué hay antes de pedir una serie puntual con los parámetros correctos.
    """
    try:
        xls = pd.ExcelFile(io.BytesIO(contenido))
    except Exception as e:
        return f"(No se pudo abrir como Excel: {e})"

    partes = []
    for nombre_hoja in xls.sheet_names:
        try:
            df = pd.read_excel(xls, sheet_name=nombre_hoja, header=None, nrows=max_filas_preview + 1)
        except Exception as e:
            partes.append(f"## Hoja: {nombre_hoja}\n(no se pudo previsualizar: {e})")
            continue
        primera_fila = list(df.iloc[0].astype(str)) if len(df) else []
        partes.append(
            f"## Hoja: {nombre_hoja}\n"
            f"Fila 1 (puede o no ser el header real): {primera_fila}\n"
            f"Primeras filas:\n{df.head(max_filas_preview).to_string(index=False, header=False)}"
        )
    return "\n\n".join(partes) or "(Excel sin hojas legibles)"


def leer_serie_de_excel(
    archivo_b64: str, hoja: str, columna_fecha: str, columna_valor: str,
    header_fila: int = 0, filtro_columna: str | None = None, filtro_valor: str | None = None,
    max_filas: int = 5000,
) -> dict:
    """
    Decodifica un Excel guardado (base64) y devuelve una serie [{'fecha', 'valor'}] lista para
    usar directo en utils/estadistica.py — mismo formato de entrada que esas funciones.

    Args:
        archivo_b64: contenido del archivo en base64 (tal como queda en
            documento_aportado.props.archivo_original_b64).
        hoja: nombre exacto de la hoja a leer.
        columna_fecha, columna_valor: nombres exactos de columna, según la fila de header.
        header_fila: qué fila (0-indexed) es el header real — no siempre es la primera fila del
            archivo (encontrado real: la hoja 'BD-MET' del caso de Helios tenía el header en la
            fila 6, con metadata de laboratorio arriba).
        filtro_columna, filtro_valor: opcional — se queda solo con las filas donde esa columna
            es exactamente ese valor (ej. filtrar 'CÓDIGO' == 'T401'). Encontrado real: sin este
            filtro, una hoja mezclaba 4 códigos de digestor distintos en la misma columna y
            arruinaba cualquier análisis de estabilidad — no asumir que una hoja es un solo punto.
        max_filas: techo de seguridad.

    Returns:
        dict con 'serie' [{'fecha', 'valor'}], 'n', 'hoja'. Si la hoja/columna pedida no existe,
        {"error": ..., "hojas_disponibles": [...]} o {"error": ..., "columnas_disponibles": [...]}
        — para que quien pidió mal el parámetro pueda corregir sin adivinar. {"error": ...} si
        falla la decodificación o el archivo no es un Excel válido.
    """
    try:
        contenido = base64.b64decode(archivo_b64)
    except Exception as e:
        return {"error": f"No se pudo decodificar el archivo: {e}"}

    try:
        xls = pd.ExcelFile(io.BytesIO(contenido))
    except Exception as e:
        return {"error": f"No se pudo abrir como Excel: {e}"}

    if hoja not in xls.sheet_names:
        return {"error": f"Hoja '{hoja}' no existe.", "hojas_disponibles": xls.sheet_names}

    try:
        df = pd.read_excel(xls, sheet_name=hoja, header=header_fila)
    except Exception as e:
        return {"error": f"No se pudo leer la hoja '{hoja}' con header_fila={header_fila}: {e}"}

    df.columns = [str(c).strip() for c in df.columns]
    columnas = list(df.columns)
    faltantes = [c for c in (columna_fecha, columna_valor) if c not in columnas]
    if faltantes:
        return {"error": f"Columna(s) no encontrada(s): {faltantes}", "columnas_disponibles": columnas}

    if filtro_columna:
        if filtro_columna not in columnas:
            return {"error": f"Columna de filtro '{filtro_columna}' no encontrada.", "columnas_disponibles": columnas}
        df = df[df[filtro_columna].astype(str).str.strip() == str(filtro_valor)]

    fechas = pd.to_datetime(df[columna_fecha], errors="coerce")
    valores = pd.to_numeric(df[columna_valor], errors="coerce")
    mask = fechas.notna() & valores.notna()

    serie = [
        {"fecha": str(f.date()), "valor": float(v)}
        for f, v in zip(fechas[mask], valores[mask])
    ][:max_filas]

    return {"serie": serie, "n": len(serie), "hoja": hoja}
