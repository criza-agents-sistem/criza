import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.km_decisiones import registrar_decision


async def main():
    r = await registrar_decision(
        componente="biotecnologo",
        titulo="Etapa 18 — cuarto especialista: Biotecnólogo",
        decision=(
            "Andrés (colaborador de Sebas) sugirió sumar un agente biotecnólogo; Sebas confirmó "
            "explícitamente que le parecía acertado. Antes de construir se propuso el ángulo "
            "diferenciador: los otros 3 especialistas ya cubren tratamiento del material "
            "(Microbiólogo), factibilidad de ingeniería (Ingeniero Ambiental) y uso agronómico "
            "del resultado (Agrónomo) -- faltaba quien evaluara qué producto FABRICAR vía "
            "bioprocesos y con qué ruta. Sebas confirmó ('me parece bien así el agente') antes "
            "de tocar código. Herramientas verificadas en vivo, no asumidas (mismo criterio que "
            "BRENDA): de 5 candidatas propuestas originalmente, 3 no eran viables sin trabajo "
            "adicional -- patentes (PatentsView/Lens.org exigen API key), Addgene (sin API "
            "pública), BioCyc/MetaCyc (búsqueda por texto libre devuelve HTML con hCaptcha, "
            "inútil como tool programático). Reemplazadas por PubChem y ChEBI (vía EBI OLS4, "
            "ambas confirmadas reales sin auth) más reuso de KEGG/Rhea (ya construidos para el "
            "Microbiólogo, ángulo distinto: biosíntesis del producto en vez de tratamiento). "
            "Construido biotecnologo_agent/ completo (mismo patrón que los otros 3 -- SEB-115, "
            "solo frente_id, chat conversacional con consulta libre, documentos_aportados). "
            "utils/pubchem.py y utils/chebi.py nuevos. Conectado en agents_registry.yaml, "
            "conductor.py, api/main.py y web/lib/api.ts. 29 tests nuevos en biotecnologo_agent/ "
            "(incluido el checklist anti-sesgo) + 17 en utils/tests para las 2 tools nuevas. "
            "531/531 unit en verde, npm run build limpio, auditor sin hallazgos nuevos. Bug "
            "encontrado y arreglado en el mismo pase: faltaba __init__.py, sin él el registry no "
            "podía cargar el módulo como paquete -- encontrado al intentar la corrida real, no "
            "en los tests unitarios. Verificado real de punta a punta contra producción vía la "
            "costura: corrida completa contra el Frente técnico de Helios, 8 búsquedas reales, 5 "
            "rutas biotecnológicas identificadas con madurez declarada (PHA/PHB desde VFAs, "
            "biomasa microalgal, struvita, proteína unicelular vía metanótrofos, ruta combinada "
            "en cascada), citando papers argentinos reales (CONICET-INBIOSUR, INTA). KEGG/Rhea "
            "no devolvieron resultados para los términos probados -- reportado como limitación "
            "honesta, no ocultado. PubChem confirmó estruvita real (CID 10220511), ChEBI "
            "confirmó PHB real (CHEBI:131525). documento_caso resultante conectado al frente "
            "junto a los 3 documentos previos de los otros especialistas -- confirmado leyendo "
            "el KM. 317.185 tokens totales de la corrida."
        ),
        motivo=(
            "Sebas: 'Andrés me decía que podíamos agregar un agente biotecnólogo, me parece "
            "acertado, pensemos qué herramientas le podemos sumar.' Confirmado después: 'me "
            "parece bien así el agente.'"
        ),
        alternativas_consideradas=[
            "BioCyc/MetaCyc para rutas metabólicas -- descartada: la búsqueda por texto libre no "
            "es programática (HTML + hCaptcha), solo el lookup directo por ID funciona sin auth, "
            "y eso solo no aporta valor sin una búsqueda previa.",
            "Búsqueda de patentes (PatentsView/Lens.org) -- deferida, no descartada: ambas "
            "requieren registrarse para una API key, no bloquea el arranque del agente, mismo "
            "criterio que BRENDA (Etapa 8 del microbiólogo).",
            "Addgene -- descartada definitivamente: sin API pública real, solo scraping frágil.",
        ],
        quien="Sebas + Claude (herramientas sugeridas por Andrés, colaborador de Sebas)",
    )
    print(r)


if __name__ == "__main__":
    asyncio.run(main())
