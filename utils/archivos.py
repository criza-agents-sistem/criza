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


def _detectar_fila_header(df_crudo: pd.DataFrame) -> int:
    """
    Heurística real (no asume fila 0): una fila de header típica tiene la mayoría de sus celdas
    no-nulas y de tipo texto (nombres de columna) — a diferencia de filas de metadata/título
    (casi todo NaN) o filas de datos reales (mezcla de números/fechas). Encontrado real (Etapa 22
    cont., 2026-09-15): un archivo del proyecto tiene el header en la fila 6, con metadata de
    laboratorio arriba — mostrar la fila 0 ahí daba una previsualización vacía y engañosa (el
    Conductor la leyó como "el archivo está vacío", que era falso).

    Si ninguna fila escaneada supera un umbral mínimo de "parece header", devuelve 0 (mismo
    comportamiento que antes, sin cambio para el caso simple).
    """
    mejor_fila, mejor_score = 0, -1.0
    for i in range(len(df_crudo)):
        fila = df_crudo.iloc[i]
        no_nulos = fila.notna()
        frac_no_nulos = float(no_nulos.mean()) if len(fila) else 0.0
        if frac_no_nulos == 0:
            continue
        valores_no_nulos = fila[no_nulos]
        frac_texto = sum(isinstance(v, str) for v in valores_no_nulos) / len(valores_no_nulos)
        score = frac_no_nulos * frac_texto
        if score > mejor_score:
            mejor_fila, mejor_score = i, score
    return mejor_fila if mejor_score > 0.3 else 0


def previsualizar_excel(contenido: bytes, max_filas_preview: int = 5, max_filas_scan_header: int = 15) -> str:
    """
    Texto legible para mostrar en el chat / guardar como 'contenido' del documento_aportado.

    Detecta el header real de cada hoja (no asume que es la fila 0) y reporta hechos calculados
    en Python — cantidad de filas y, si hay una columna de fecha reconocible, su rango real
    (min/max) — en vez de dejar que el modelo que lee esto adivine o invente esos datos.
    Encontrado real (2026-09-15): sin este cálculo, el Conductor completó un rango de fechas que
    no existía en ningún lado ("desde febrero 2022") al no tener un dato real para citar — este
    texto ahora se lo da, así no hace falta que lo invente.

    NO reemplaza leer_serie_de_excel para cómputo real — es solo para que Sebas o el Conductor
    vean qué hay antes de pedir una serie puntual con los parámetros correctos.
    """
    try:
        xls = pd.ExcelFile(io.BytesIO(contenido))
    except Exception as e:
        return f"(No se pudo abrir como Excel: {e})"

    partes = []
    for nombre_hoja in xls.sheet_names:
        try:
            df_crudo = pd.read_excel(xls, sheet_name=nombre_hoja, header=None, nrows=max_filas_scan_header)
        except Exception as e:
            partes.append(f"## Hoja: {nombre_hoja}\n(no se pudo previsualizar: {e})")
            continue
        if df_crudo.empty:
            partes.append(f"## Hoja: {nombre_hoja}\n(hoja sin filas)")
            continue

        fila_header = _detectar_fila_header(df_crudo)
        try:
            df = pd.read_excel(xls, sheet_name=nombre_hoja, header=fila_header)
        except Exception as e:
            partes.append(f"## Hoja: {nombre_hoja}\n(no se pudo leer con header en la fila {fila_header}: {e})")
            continue

        columnas = [str(c).strip() for c in df.columns]
        df.columns = columnas  # bug real (2026-09-15): sin esto, df[col] con un nombre ya
        # "stripeado" tiraba KeyError apenas el header tenía un \n o espacios (caso real:
        # 'Base de datos Logística.xlsx' rompía la previsualización entera con esto).
        total_filas = len(df)

        # Bug real (2026-09-15): con VARIAS columnas de fecha (ej. el archivo real de T401 tiene
        # 6: presupuesto, envío, aprobación, recepción, análisis, muestreo), tomar la PRIMERA que
        # matcheaba el nombre agarró una columna administrativa casi vacía (25 fechas válidas de
        # 893 filas) en vez de la fecha de muestreo real — un rango de fechas técnicamente
        # calculado pero igual de engañoso que uno inventado. Ahora se evalúan todas las columnas
        # candidatas y se reporta la que tiene MÁS fechas válidas (la más completa / representativa).
        rango_fecha_txt = "sin columna de fecha reconocible"
        mejor_col, mejor_fechas = None, None
        for col in columnas:
            if "fecha" in col.lower() or "date" in col.lower():
                fechas_validas = pd.to_datetime(df[col], errors="coerce").dropna()
                if len(fechas_validas) >= 2 and (mejor_fechas is None or len(fechas_validas) > len(mejor_fechas)):
                    mejor_col, mejor_fechas = col, fechas_validas
        if mejor_col is not None:
            rango_fecha_txt = (
                f"columna '{mejor_col}': {mejor_fechas.min().date()} a "
                f"{mejor_fechas.max().date()} ({len(mejor_fechas)} de {total_filas} filas tienen "
                f"fecha válida en esta columna — puede no ser la única columna de fecha, ver "
                f"'Columnas' abajo)"
            )

        partes.append(
            f"## Hoja: {nombre_hoja}\n"
            f"Header real detectado en la fila {fila_header + 1} del archivo (1-indexed).\n"
            f"Filas de datos: {total_filas} (sin contar el header).\n"
            f"Rango de fechas: {rango_fecha_txt}.\n"
            f"Columnas: {columnas}\n"
            f"Primeras filas:\n{df.head(max_filas_preview).to_string(index=False)}"
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
