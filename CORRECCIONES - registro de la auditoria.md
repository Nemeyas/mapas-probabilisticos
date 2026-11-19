# Registro de correcciones a la evaluación del prototipo

Noviembre de 2026

Este documento registra seis defectos detectados en la implementación de las
métricas y del procedimiento de comparación de este prototipo, junto con la
corrección aplicada a cada uno y su efecto sobre las cifras publicadas. Se
incluye en el repositorio porque las cifras del informe cambiaron a raíz de
estas correcciones, y porque cualquier lector que reproduzca los resultados
debe poder distinguir qué valores corresponden a qué versión del código.

Cuatro de los seis defectos mejoraban artificialmente los resultados del
prototipo y dos los perjudicaban. La causa común es la misma en todos los
casos: un parámetro, un marco de referencia o una escala fijados sin una
regla declarada. Cuando no existe esa regla, el valor termina siendo el que
favorece el resultado, sin que medie una decisión deliberada.

---

## 1. La tasa esperada de satisfacción ignoraba la configuración del modelo

La función que calcula el ECSR invocaba el predicado duro con sus valores por
omisión en lugar de los umbrales configurados. El efecto era que la métrica
no respondía a su propio parámetro: el ECSR arrojaba 66,2367 % tanto con
`d0 = 0,02` como con `d0 = 0,50`.

El valor publicado resultó correcto por coincidencia, ya que la configuración
contenía justamente el valor por omisión. Cualquier experimento que variara
el umbral habría producido una cifra sin sentido.

**Corrección.** El predicado se evalúa con los umbrales del modelo. Se añadió
una prueba unitaria que ata el resultado a la configuración.

## 2. Pérdida de masa fuera de la ventana de medición

El cálculo de la región creíble normalizaba el histograma por la masa
contenida dentro de la ventana de medición, no por el total de muestras. Las
entidades con mayor incertidumbre son las que más masa pierden por los
bordes, de modo que el error subestimaba el área justamente donde la
incertidumbre es mayor.

| Entidad | masa fuera de la ventana |
|---|---|
| Norburgo | 5,27 % |
| Bosque Negro | 2,50 % |
| Los Gamos | 1,87 % |
| Fornost | 1,35 % |
| Eriador | 1,24 % |

**Corrección.** La normalización se realiza sobre el total de muestras, con
una salvaguarda que devuelve el área completa de la ventana cuando el nivel
pedido no se alcanza.

## 3. Afirmación incorrecta sobre la equivalencia de predicados

La documentación del código y el nombre de una prueba unitaria afirmaban que
el predicado duro de este prototipo coincide con el del trabajo base. La
lectura del código fuente de ese trabajo mostró que difieren en los tres
tipos de relación:

| | Trabajo base | Este prototipo |
|---|---|---|
| `CERCA_DE` | círculo de radio 0,5 del lienzo | círculo de radio `d0_cerca` |
| `CONECTA` | caja de Chebyshev de medio lado 0,4 | círculo de radio `d0_conecta` |
| Dirección | semiplano con margen 0,036 más caja de 0,333 | cono de 45°, sin cota de alcance |

La diferencia no invalida la comparación, puesto que los tres candidatos se
evalúan con el mismo predicado declarado, que opera como vara común. Lo
incorrecto era afirmar una equivalencia inexistente.

**Corrección.** La documentación describe el predicado como criterio
declarado y detalla la diferencia. La prueba se renombró en consecuencia.

## 4. Relaciones recíprocas contabilizadas dos veces

Las formas «A al este de B» y «B al oeste de A» expresan la misma afirmación
del texto. La extracción puede devolver ambas, y entraban como dos
restricciones independientes: dos factores en la densidad y dos casillas en
el denominador del CSR.

Medido sobre el subgrafo de evaluación, colapsar el único par recíproco
presente modifica el resultado de forma apreciable:

| | con duplicado | sin duplicado |
|---|---|---|
| área creíble media | 0,257 | **0,322** |
| ECSR | 66,25 % | 64,37 % |

Un 25 % de la nitidez reportada no provenía del texto, sino de contabilizar
dos veces la misma frase.

**Corrección.** Las relaciones recíprocas se colapsan en la entrada, antes de
repartirla, de modo que los tres candidatos se evalúan sobre la misma lista y
la comparación conserva la paridad.

## 5. La escala actuaba como grado de libertad en la comparación

La comparación en el marco del grafo oficial ajustaba a cada candidato su
propia semejanza por mínimos cuadrados y evaluaba después con umbrales
absolutos. Las escalas resultantes fueron:

- sistema base: **×0,125**
- prototipo: **×1,547**
- grafo oficial: ×1,000

Comprimir un mapa ocho veces acerca todas sus entidades entre sí y satisface
las relaciones de distancia por construcción. El sistema base obtenía ventaja
por haber sido comprimido, no por producir una disposición mejor.

**Corrección.** El CSR se evalúa tras llevar a cada candidato al marco oficial
con una regla única y no ajustable, que iguala su radio de giro al del grafo
oficial y transforma al grafo oficial en sí mismo. La similitud posicional
conserva el ajuste óptimo, ya que es una distancia y no un predicado con
umbral, de modo que la escala no concede ventaja.

## 6. Umbral de distancia sin justificación, y no leído por todo el pipeline

El umbral `d0_cerca = 0,08` se había fijado sin regla. Las distancias reales
entre los pares `CERCA_DE` que el grafo oficial permite verificar son 0,043,
0,124 y 0,320, con mediana 0,124: el valor empleado excluía dos de los tres
pares verificables.

Por otra parte, los pasos 4 y 6 del pipeline construían el modelo con las
constantes del módulo en lugar de la configuración. El paso 2 muestreaba con
un umbral y el paso 4 evaluaba esas muestras con otro, es decir, medía una
densidad distinta de la que se había muestreado. El barrido del término de
robustez presentaba el mismo defecto y devolvía cifras idénticas aunque se
modificara el umbral.

**Corrección.** El umbral se ancla a la mediana de las distancias
verificables y la regla queda declarada en la configuración, con la
advertencia explícita de que se apoya en tres pares y constituye una cota de
cordura, no una calibración. La construcción del modelo pasa por una función
única que lee siempre la configuración.

---

## Consecuencia principal

Con la escala corregida, la comparación por tasa de satisfacción queda así al
variar el umbral dentro de un rango defendible:

```
   d0_cerca  d0_conecta     base   modelo  oficial   resultado
       0,08        0,20    77,8%    66,7%    77,8%   gana el sistema base
       0,12        0,20    88,9%    77,8%    77,8%   gana el sistema base
       0,12        0,13    66,7%    77,8%    66,7%   gana el prototipo
       0,15        0,20    88,9%    88,9%    88,9%   empate
       0,20        0,25    88,9%    88,9%    88,9%   empate
```

El orden entre ambos sistemas depende de un umbral que la métrica no declara.
Con nueve relaciones evaluadas, cada una desplaza el indicador 11,1 puntos
porcentuales. **No corresponde, por lo tanto, reportar ventaja de ninguno de
los dos sistemas en tasa de satisfacción de restricciones.**

Este resultado no debilita la propuesta: la refuerza. El informe ya sostiene
que esa métrica es inadecuada, con tres argumentos previos —el denominador
varía entre ejecuciones, la correlación de Pearson entre número de
restricciones y CSR es −0,67, y el mapa verdadero obtiene menos que ambos
sistemas—. Este es un cuarto argumento, y el más directo.

La conclusión que sí se sostiene es la de similitud posicional, que no
depende de ningún umbral: **96,63 % para el prototipo frente a 93,50 % para
el sistema base**, valor estable entre 96,35 % y 96,97 % a lo largo de todo
el barrido.

Para evitar que una cifra de este tipo vuelva a depender de una elección no
declarada, el paso 4 del pipeline publica el barrido de sensibilidad en cada
ejecución, junto con la advertencia correspondiente cuando el orden entre los
sistemas no se conserva.

## Cifras antes y después

| | antes | después |
|---|---|---|
| lugares / relaciones | 12 / 24 | 12 / **23** |
| Gelman-Rubin | 1,0014 | 1,0021 |
| muestra efectiva mínima | 1.617 | 1.734 |
| ECSR | 66,24 % (σ 9,42) | **71,63 % (σ 9,57)** |
| CSR del MAP, marco propio | 87,50 % | **95,65 %** |
| CSR en marco oficial: base | 90,00 % | **88,89 %** |
| CSR en marco oficial: prototipo | 90,00 % | **77,78 %** |
| CSR en marco oficial: grafo oficial | 80,00 % | **77,78 %** |
| área creíble media | 0,245 | **0,331** |
| correlación grado–área | −0,508 | **−0,515** |
| similitud posicional, prototipo | 96,65 % | 96,63 % |
| similitud posicional, sistema base | 93,50 % | 93,50 % |
| error de calibración esperado | 0,258 | 0,258 |

Las cifras de la columna derecha son las que figuran en el informe y las que
reproduce el código de este repositorio.
