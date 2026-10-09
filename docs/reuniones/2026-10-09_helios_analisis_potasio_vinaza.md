# Helios — Análisis de vinaza, potasio y alternativas (2026-10-09)

Seguimiento de la reunión del 2026-10-08 (`2026-10-08_helios_mateo.md`). Análisis de mesa para
decidir próximos ensayos: **no es diseño de ingeniería**.

## Convención de veracidad (leer primero)

| Etiqueta | Qué significa | Cómo usarlo |
|---|---|---|
| 🟢 **HELIOS-MEDIDO** | Dato de laboratorio sobre muestras de Helios (informes JLA en el Drive de Sebas) | Se puede usar, respetando la incertidumbre que informa JLA |
| ⚪ **REUNIÓN** | Dicho en la reunión, según una transcripción automática de mala calidad | Confirmar antes de usar |
| 🔵 **FUENTE EXTERNA** | Literatura, patentes o prensa; **no** es de Helios ni de RDC | Solo como referencia de orden de magnitud |
| 🟠 **ESTIMACIÓN** | Cálculo propio a partir de supuestos explícitos | Hipótesis; **no usar como dato** sin ensayo |

Durante la sesión la red no permitió abrir los documentos externos completos: las cifras 🔵 salen
de los resúmenes de búsqueda.

---

## 1. Datos reales de Helios (JLA) 🟢

| Muestra (fecha de muestreo) | K mg/kg | Na mg/kg | N-NH₄ mg/kg | S mg/kg | Ca mg/kg | Sólidos totales mg/kg | Conductividad µS/cm | Informe |
|---|---|---|---|---|---|---|---|---|
| **Digestato crudo T401 (19/11/2025)** | **5.565 ± 1.558** | **1.676 ± 335** | 2.120 | 532 ± 64 | 2.690 ± 780 | 29.220 | — | 638113 |
| Digestato crudo (15/08/2024) | 4.079 | 1.529 | 1.223 | <300 | 393 | 32.828 | 22.400 | 583611 |
| Digestato líquido (15/08/2024) | 3.972 | 1.516 | 1.216 | 465 | 1.248 | 29.506 | 22.540 | 583610 |
| Laguna general (21/08/2024) | 3.628 | 1.295 | — | — | 4.783 | 69.938 | 17.229 | 2-2 |
| Fertilizante líquido crudo (05/06/2026) | 2.264 ± 634 | 980 ± 196 | — | 1.204 | 8.782 | 82.144 | — | 661074 |
| Líquido clarificado de laguna (11/06/2026) | 1.835 ± 514 | 808 ± 162 | — | 541 | 703 | 11.644 | — | 661075 |

JLA no midió **cloruros, sulfatos (como anión), alcalinidad ni DQO**. Son necesarios para el
próximo paso.

Lectura directa de los datos:
- Relación K/Na: **2,3–3,3 en peso**, **1,3–2,0 en moles**. En la reunión se dijo "casi cuatro veces" ⚪: el dato medido es menor.
- El Na de T401 (1.676) coincide con los "1.600 ppm" mencionados en la reunión ⚪.
- **El azufre no alcanza para acompañar al K como sulfato:** ~33 meq/L de S frente a ~142 meq/L de K en T401. El anión dominante tiene que ser otro (bicarbonato o cloruro), pero no está medido.
- El K de T401 (5,6 g/L) está en la zona que la literatura asocia a **inhibición moderada** de las metanogénicas 🔵. Es hipótesis a verificar con las series de producción de gas.

## 2. Datos de la reunión 2026-10-08 ⚪ (sin verificar)

- Caudales: ~220 m³/día del biodigestor (T401) y ~80 m³/día de la torre (ácido).
- Conductividad 33,27 mS/cm. JLA midió 22,4 mS/cm en 2024: confirmar cuál corresponde a qué corriente y fecha.
- Vinaza: "~800 m³" (periodicidad no clara) y "80% del volumen" de ingreso.
- Una empresa que trabajaría con la vinaza de Refinería del Centro la secaría y vendería el producto para fertilizantes.

## 3. Origen de la vinaza

- 🔵 Refinería del Centro (Ferreyra, Córdoba) refina grasas y aceites y **fabrica levadura prensada** (directorios comerciales).
- 🔵 Una nota de prensa confirma que Helios recibe "vinaza de Refinería del Centro".
- 🟠 Inferencia: es **vinaza de fabricación de levadura a partir de melaza** (probablemente de caña), no de destilería. Hipótesis adicional: parte del Na podría venir de la refinación de aceites de RDC (neutralización con soda). **Confirmar con RDC.**

## 4. Composición y valor de la vinaza de levadura

- 🔵 Literatura sobre vinaza de melaza: rica en K, sulfato, N orgánico y materia orgánica. Concentrada al ~60%: cenizas 16–20%, K ~4%, N >2%.
- 🔵 Hay patentes que recuperan **sulfato de potasio** de vinaza de fábricas de levadura por concentración y cristalización.
- 🔵 Argentina importa sulfato de potasio (~10.000 t, según La Gaceta).
- 🟠 Hipótesis: lo "que vale fortuna" es un fertilizante potásico, sea vinaza seca o sulfato de potasio. **No confirmado.** Hay que preguntar qué vende la empresa de secado.

## 5. Tecnología para separar el K

- 🔵 **Ruta con antecedente:** clarificación → stripping de NH₃ → preconcentración (OI) → evaporación con calor del CHP → cristalización de una sal de potasio.
- 🔵 La clinoptilolita (zeolita) prefiere K y NH₄ sobre Na (37–78% de remoción de K en digestato), pero 🟠 a la escala de Helios se necesitaría del orden de ~35 t de zeolita por día. Sirve como pulido o como ingrediente del organomineral.
- 🔵 La estruvita potásica y la electrodiálisis se descartan como vías principales.
- 🟠 **Corrección por los datos JLA:** como falta sulfato, el sulfato de potasio no cristaliza solo.
  - Haría falta agregar ~7 kg de H₂SO₄ por m³ (~1,5 t/día).
  - **El líquido ácido de la torre pasa a ser una pieza clave**, pero hay que medir cuánto sulfato aporta.
  - Si el anión dominante es cloruro, el producto sería cloruro de potasio, más difícil de separar del de sodio.
- 🟠 Potencial con el dato JLA de T401 (5,6 g/L × 220 m³/día ⚪): **~1,2 t de K/día ≈ 2,7 t/día de sulfato de potasio equivalente (rango 2,0–3,5; ~1.000 t/año)**.

## 6. Potencial metanogénico: melaza vs. vinaza de RDC

Todo **🟠 ESTIMACIÓN**: no hay BMP medido de ninguna de las dos.

| | Melaza de caña | Vinaza de levadura RDC |
|---|---|---|
| Metano | ~185 Nm³ CH₄/t (150–210) | ~5,6 Nm³ CH₄/m³ (3,5–11) |
| K por unidad de metano | ~0,18 kg K/Nm³ | ~0,8 kg K/Nm³ |

- Equivalencia: ~33 m³ de vinaza ≈ 1 t de melaza.
- De 1 t de melaza, a la vinaza llega ~20% del metano posible y casi todo el K.
- Si los 800 m³ fueran diarios ⚪: ~4.500 Nm³ CH₄/día, ≈24 t de melaza/día, ≈0,75 MW eléctricos.
- 🔵 Precio de referencia de melaza: ~US$180/t (exportación Perú; no hay dato argentino).
  - 🟠 A ese precio, solo la materia prima cuesta ~US$0,24 por kWh eléctrico.
  - 🟠 El umbral para que la melaza "se pague" es de < ~US$100/t puesta en planta, suponiendo energía a US$0,16/kWh. **No conozco la tarifa real de Helios.**
- 🔵 Rendimientos de referencia: 0,27–0,37 Nm³ CH₄/kg de DQO removida, según el sustrato.

## 7. Otras fuentes de K (alternativas a la vinaza o la melaza)

Todas las cifras son **🔵 FUENTE EXTERNA** (literatura, no muestras locales). Los veredictos son 🟠.

| Fuente | K de referencia 🔵 | Rol posible 🟠 |
|---|---|---|
| Ceniza de cáscara de girasol (aceiteras) | 15–35% K₂O soluble | Ingrediente potásico del organomineral |
| Lactosuero / permeado (cuenca lechera) | ~1,45 g/L de K; 450–860 L CH₄/kg de sólidos volátiles | Reemplazo energético de la vinaza con poca sal |
| Vinaza de caña (Tucumán) | ~4,5 kg K₂O/m³ (ref. Cuba); 3–4 millones de m³/año | Mayor reserva de K del país; lejos |
| Alpechín / alperujo | 1,7 g/L hasta 24 g/kg | Rico en K; polifenoles inhiben el digestor |
| Agua de proceso de papa | ~1,8 g/L | Medio; relevar procesadoras cercanas |
| Efluente de feedlot | ~1,1 g/L (0,02–6,4) | Volumen, no energía |
| Glicerina de biodiesel | Depende del catalizador (K o Na) | Mucha energía; verificar el catalizador |

🟠 Propuesta a evaluar: **desacoplar energía y potasio**. Lactosuero o glicerina potásica en el
digestor; ceniza de cáscara para el K del organomineral.

## 8. Datos a pedir (para pasar de 🟠 a 🟢)

1. **JLA:** cloruros, sulfatos, alcalinidad, N-NH₄, conductividad y DQO, en T401, en la torre y en la vinaza tal como llega.
2. **RDC:** volumen diario real de vinaza, análisis completo, origen de la melaza, si mezclan efluentes de la refinería de aceites, y qué produce la empresa de secado.
3. **Helios:** balance de biogás por sustrato, tarifa de la energía, cuánto ácido genera la torre por día.
4. **BMP** de la vinaza real de RDC y de una melaza de referencia, con el inóculo de Helios.
5. **Ensayo de laboratorio:** evaporación por etapas del clarificado, con y sin ácido de la torre, e identificación de los cristales.
