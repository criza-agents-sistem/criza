import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.km_decisiones import registrar_decision


async def main():
    r = await registrar_decision(
        componente="orquestador",
        titulo="Etapa 4 del plan (parte 1) — staging real vía Neon branching",
        decision=(
            "Creado el branch 'staging' (copy-on-write de production) en el proyecto de Neon de "
            "CRIZA — verificado en vivo con datos idénticos a producción (37.215 fichas "
            "tenant_id='criza' + 6 'instancia_test' en ambos). DATABASE_URL_STAGING agregado a "
            ".env/.env.example. docs/STAGING.md documenta cuándo usar cada DB y cómo apuntar "
            "a staging (DATABASE_URL es lazy, alcanza con la env var + reset_engine() si el "
            "proceso ya se conectó). De paso: el proyecto de Neon se llamaba 'empresa-ia' "
            "(resabio de antes del 13/08, cuando CRIZA vivía anidada en el código de "
            "EMPRESAS-IA) — se renombró a 'criza'. Verificado antes de renombrar que no había "
            "mezcla de datos con otras instancias (solo tenant_id='criza' + un tenant de prueba "
            "insignificante) — el nombre viejo era un descuido cosmético de infraestructura, no "
            "un problema de aislamiento real."
        ),
        motivo=(
            "Sebas pidió un ambiente de staging real (no verificación incremental) desde el "
            "arranque del plan del 16/08 — 'quiero que sea una copia separada, no solo verificar "
            "cada paso'. Se ubicó acá (no antes) porque es el primer momento del plan donde algo "
            "empieza a escribir contra el modelo de casos.yaml (Helios/MicroBigs reales) — antes "
            "de eso, todo el trabajo (Etapas 0-3) era construir agentes/primitivas nuevos o "
            "diseño puro, sin tocar datos de casos reales."
        ),
        alternativas_consideradas=[
            "Crear el branch vía la consola de Neon (Sebas, manual) — descartado tras encontrar "
            "que la cuenta de neonctl autenticada por defecto no tenía acceso a la org correcta; "
            "Sebas pidió explícitamente que se resuelva por CLI una vez identificada la cuenta "
            "correcta (criza.dev@gmail.com), no que lo haga él a mano.",
            "Dejar el nombre del proyecto de Neon como 'empresa-ia' — descartado: Sebas pidió "
            "el rename explícitamente al notar la confusión con la org de EMPRESAS-IA.",
        ],
        quien="Sebas + Claude",
    )
    print(r)


if __name__ == "__main__":
    asyncio.run(main())
