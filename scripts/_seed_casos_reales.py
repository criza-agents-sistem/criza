"""
Migración única — carga los dos casos reales (Biogás/Helios, MicroBigs) al área `casos` del KM,
con datos sacados de `casos/*.md` (no inventados — cada campo tiene su fuente en el archivo
original). Correr una sola vez, después de cargar config/plantillas/casos.yaml.

Fechas de inicio (`fecha_inicio`) quedan en null a propósito: los archivos fuente no traen una
fecha exacta de arranque del caso, y CLAUDE.md prohíbe inventar timelines.
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from knowledge_module.motor import api as motor_api

TENANT = "criza"
AREA = "casos"


async def crear_caso_biogas() -> str:
    caso = await motor_api.guardar_ficha(
        area=AREA, tipo="caso", tenant=TENANT,
        campos=dict(
            nombre="Efluentes biogás (Helios)",
            descripcion=(
                "Mateo Ligato, dueño de Helios Bioenergía, busca generar valor del líquido "
                "que sale del biodigestor: alto volumen de agua, producto superdiluido, altos "
                "costos logísticos de transporte que hoy limitan el uso a zonas cercanas a la "
                "planta (el productor paga el flete, la planta regala el efluente). Problema "
                "trasladable a otras plantas de biogás del país/mundo y a efluentes pecuarios "
                "en general — podría trabajarse con varias plantas de biogás, no solo Helios."
            ),
            estadio="desde_cero",
            fecha_inicio=None,
            participantes=[
                {"usuario_nombre": "Andrés", "rol_en_caso": "referente"},
                {"usuario_nombre": "Sebas", "rol_en_caso": "admin"},
            ],
            notas="Fecha de inicio a-confirmar — no está en la transcripción fuente.",
            texto_busqueda=(
                "Efluentes biogás (Helios). Mateo Ligato, dueño de Helios Bioenergía, busca "
                "generar valor del líquido que sale del biodigestor: alto volumen de agua, "
                "producto superdiluido, altos costos logísticos de transporte."
            ),
        ),
    )
    caso_id = caso["id"]
    assert caso["success"], caso

    frente_tecnico = await motor_api.guardar_ficha(
        area=AREA, tipo="frente", tenant=TENANT,
        campos=dict(
            nombre="Frente técnico",
            descripcion=(
                "Solución tecnológica al problema del efluente — reducir/concentrar el agua o "
                "generar un producto de mayor valor agregado (biotecnología con "
                "microorganismos + secado spray, o geles retenedores de agua). Competencia "
                "identificada: una empresa desarrolla pellets de arcilla que absorben el agua "
                "del efluente, con financiamiento del gobierno de Entre Ríos, cerca de Jesús "
                "María."
            ),
            estado="activo",
        ),
    )
    frente_asociacion = await motor_api.guardar_ficha(
        area=AREA, tipo="frente", tenant=TENANT,
        campos=dict(
            nombre="Frente de asociación",
            descripcion=(
                "Cómo estructurar el trabajo con Mateo/Helios, posiblemente extensible a otras "
                "plantas de biogás. Ideas sobre la mesa: cobrar un servicio de desarrollo "
                "(ingreso mensual), ser dueño/socio de una tecnología aplicable a todas las "
                "plantas, o cobrar regalías sobre la facturación del productor."
            ),
            estado="activo",
        ),
    )
    for f in (frente_tecnico, frente_asociacion):
        await motor_api.guardar_conexion(
            area=AREA, tipo="tiene_frente", desde_ficha_id=caso_id, hacia_ficha_id=f["id"],
            tenant=TENANT,
        )

    pendientes = [
        dict(
            descripcion="Definir y presentar la propuesta de forma de trabajo a Mateo (reunión pendiente).",
            estado="abierto", fecha=None,
        ),
        dict(
            descripcion=(
                "Confirmar si la situación actual descrita (el productor paga el flete, la "
                "planta regala el efluente) es exacta — 'no sé si es tan así, hay que "
                "estudiarlo'."
            ),
            estado="abierto", fecha=None,
        ),
    ]
    for p in pendientes:
        ficha = await motor_api.guardar_ficha(area=AREA, tipo="pendiente", campos=p, tenant=TENANT)
        await motor_api.guardar_conexion(
            area=AREA, tipo="tiene_pendiente", desde_ficha_id=caso_id, hacia_ficha_id=ficha["id"],
            tenant=TENANT,
        )

    dato = await motor_api.guardar_ficha(
        area=AREA, tipo="dato_extraido", tenant=TENANT,
        campos=dict(
            categoria="contacto",
            valor="Mateo Ligato — dueño de Helios Bioenergía",
            contexto="Trajo el desafío a través de Andrés.",
        ),
    )
    await motor_api.guardar_conexion(
        area=AREA, tipo="tiene_dato", desde_ficha_id=caso_id, hacia_ficha_id=dato["id"],
        tenant=TENANT,
    )

    return caso_id


async def crear_caso_microbigs() -> str:
    caso = await motor_api.guardar_ficha(
        area=AREA, tipo="caso", tenant=TENANT,
        campos=dict(
            nombre="MicroBigs — escalamiento y alianza comercial",
            descripcion=(
                "Producto biológico (bacterias del género Bacillus) para tratamiento de "
                "efluentes, ya validado técnicamente — Melina (fundadora) busca escalar. El "
                "cuello de botella es regulatorio y estratégico, no científico: identificación "
                "taxonómica de cepas, evaluación de seguridad, estrategia regulatoria, cepario "
                "institucional (y luego propio), y después capital/equipo/propiedad "
                "intelectual. En paralelo, propuesta de alianza comercial a riesgo con aliados "
                "externos."
            ),
            estadio="validado_escalando",
            fecha_inicio=None,
            participantes=[
                {"usuario_nombre": "Pablo", "rol_en_caso": "referente"},
                {"usuario_nombre": "Sebas", "rol_en_caso": "admin"},
            ],
            notas="Fecha de inicio a-confirmar — no está en los documentos fuente.",
            texto_busqueda=(
                "MicroBigs — escalamiento y alianza comercial. Producto biológico (Bacillus) "
                "para tratamiento de efluentes, ya validado técnicamente. Cuello de botella "
                "regulatorio y estratégico."
            ),
        ),
    )
    caso_id = caso["id"]
    assert caso["success"], caso

    frente_regulatorio = await motor_api.guardar_ficha(
        area=AREA, tipo="frente", tenant=TENANT,
        campos=dict(
            nombre="Frente regulatorio/científico",
            descripcion=(
                "Identificación taxonómica de cepas por ADN, evaluación de seguridad y "
                "potencial comercial, definición de estrategia regulatoria, vinculación con "
                "una institución con cepario para depositar las cepas, y desarrollo a mediano "
                "plazo de cepario propio. Incluye Tratado de Nagoya (pago del 2-3% de la "
                "facturación a la provincia) y necesidad de constituir una SAS para "
                "registrarse."
            ),
            estado="activo",
        ),
    )
    frente_comercial = await motor_api.guardar_ficha(
        area=AREA, tipo="frente", tenant=TENANT,
        campos=dict(
            nombre="Frente comercial/alianza",
            descripcion=(
                "Propuesta de alianza: MicroBigs conserva la propiedad intelectual, los "
                "aliados asumen la expansión comercial a riesgo (comisión 15-20% por cierres "
                "directos, 8-12% por referidos, límite de 18-24 meses de comisión por cliente "
                "desde la primera venta). Tres etapas: (1) validación técnica + piloto "
                "comercial en 90-120 días, foco porcino/avícola del centro del país; (2) "
                "escalamiento por canales agropecuario/industrial/institucional; (3) inversión "
                "y proyección territorial."
            ),
            estado="activo",
        ),
    )
    for f in (frente_regulatorio, frente_comercial):
        await motor_api.guardar_conexion(
            area=AREA, tipo="tiene_frente", desde_ficha_id=caso_id, hacia_ficha_id=f["id"],
            tenant=TENANT,
        )

    pendientes = [
        dict(
            descripcion=(
                "ENTENDER CON PABLO: etapas del proceso productivo del sector ganadero y "
                "vocabulario de microbiología (sección explícita del documento fuente)."
            ),
            estado="abierto", fecha=None,
        ),
        dict(
            descripcion="Definir el % de comisión de la etapa 1 — 'habría que negociar'.",
            estado="abierto", fecha=None,
        ),
        dict(
            descripcion="Entender el negocio de los ceparios institucionales.",
            estado="abierto", fecha=None,
        ),
        dict(
            descripcion=(
                "Registro de cepas — definir en qué puede ayudar CRIZA (contactos ya "
                "identificados: Vicky Arcamone, Miguel Magnasco de la Subsecretaría de "
                "Ambiente de Córdoba)."
            ),
            estado="abierto", fecha=None,
        ),
    ]
    for p in pendientes:
        ficha = await motor_api.guardar_ficha(area=AREA, tipo="pendiente", campos=p, tenant=TENANT)
        await motor_api.guardar_conexion(
            area=AREA, tipo="tiene_pendiente", desde_ficha_id=caso_id, hacia_ficha_id=ficha["id"],
            tenant=TENANT,
        )

    artefactos = [
        dict(
            titulo="MicroBigs — Propuesta de Alianza (slides)",
            tipo="google_slide",
            url="https://docs.google.com/presentation/d/1FdGKR3N2t8R96-Vx9SpF29XcS0to9p0dn-Pfdysysqs/edit?slide=id.p1#slide=id.p1",
        ),
        dict(
            titulo="Propuesta de Alianza para la Expansión Comercial y Escalamiento de MicroBigs",
            tipo="google_doc",
            url="https://docs.google.com/document/d/1q7Rh3n6YDJ_cPm4dhCdTcRDEAhs__y-D-xG_eKYFRSw/edit?usp=drive_link",
        ),
    ]
    for a in artefactos:
        ficha = await motor_api.guardar_ficha(area=AREA, tipo="artefacto_externo", campos=a, tenant=TENANT)
        await motor_api.guardar_conexion(
            area=AREA, tipo="frente_tiene_artefacto_externo",
            desde_ficha_id=frente_comercial["id"], hacia_ficha_id=ficha["id"], tenant=TENANT,
        )

    documento = await motor_api.guardar_ficha(
        area=AREA, tipo="documento_caso", tenant=TENANT,
        campos=dict(
            titulo="Acuerdo Marco de Alianza Estratégica, Desarrollo Comercial y Consultoría",
            modo="documento",
            contenido=(
                "Acuerdo marco entre MicroBigs y sus aliados comerciales. MicroBigs conserva "
                "la titularidad exclusiva de cepas/fórmulas/procesos (individualizados en un "
                "anexo de activos tecnológicos). Contiene múltiples placeholders [●] sin "
                "completar: razón social/CUIT/domicilio/representante de MicroBigs y de cada "
                "aliado, anexo de activos tecnológicos, lugar y fecha de firma, y los datos de "
                "firma (nombre/cargo) de cada parte — borrador real, todavía sin cerrar."
            ),
            version="2",
            estado="borrador",
        ),
    )
    await motor_api.guardar_conexion(
        area=AREA, tipo="frente_produce_documento",
        desde_ficha_id=frente_comercial["id"], hacia_ficha_id=documento["id"], tenant=TENANT,
    )

    datos = [
        dict(categoria="contacto", valor="Vicky Arcamone",
             contexto="Contacto identificado para el registro de cepas."),
        dict(categoria="contacto", valor="Miguel Magnasco — Subsecretaría de Ambiente de Córdoba",
             contexto="Contacto identificado para el registro de cepas."),
        dict(categoria="cifra", valor="Primer productor porcino: 150.000 litros (prueba)",
             contexto="Primera prueba con productor porcino."),
        dict(
            categoria="cifra",
            valor="Dosis: 3ml/animal en recría (400 animales, 150m3), 1ml en gestación (60m3), 3 partes por millón en tambos",
            contexto="Dosificación por etapa productiva en las pruebas piloto.",
        ),
        dict(categoria="plazo", valor="Etapa 1 (validación técnica + piloto comercial): primeros 90-120 días",
             contexto="Cronograma de implementación en tres etapas de la propuesta de alianza."),
        dict(
            categoria="plazo",
            valor="Comisiones limitadas a 18-24 meses desde la primera venta de cada cliente",
            contexto="Modelo económico de la propuesta de alianza — 'salvaguarda de madurez'.",
        ),
    ]
    for d in datos:
        ficha = await motor_api.guardar_ficha(area=AREA, tipo="dato_extraido", campos=d, tenant=TENANT)
        await motor_api.guardar_conexion(
            area=AREA, tipo="tiene_dato", desde_ficha_id=caso_id, hacia_ficha_id=ficha["id"],
            tenant=TENANT,
        )

    return caso_id


async def main():
    biogas_id = await crear_caso_biogas()
    print(f"Biogás: caso {biogas_id}")
    microbigs_id = await crear_caso_microbigs()
    print(f"MicroBigs: caso {microbigs_id}")


if __name__ == "__main__":
    asyncio.run(main())
