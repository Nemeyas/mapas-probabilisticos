# Inestabilidad de la extracción entre corridas

El 19 de noviembre, al reponer el saldo de la API, se ejecutó por segunda vez
la etapa de extracción sobre **el mismo texto, con el mismo modelo, el mismo
prompt y la misma configuración**. El resultado no se parece al de la primera
corrida.

| | corrida 1 | corrida 2 | en ambas |
|---|---:|---:|---:|
| lugares | 66 | 55 | 33 |
| relaciones | 104 | 71 | **24** |
| CERCA_DE | 41 | 21 | 8 |
| CONECTA | 47 | 33 | 12 |
| ESTE_DE | 8 | 7 | 3 |
| NORTE_DE | 1 | 1 | 0 |
| OESTE_DE | 5 | 5 | 1 |
| SUR_DE | 2 | 4 | 0 |

- **Índice de Jaccard de relaciones: 0,159.** De las 151 relaciones distintas
  que produjeron las dos corridas juntas, solo 24 aparecen en las dos.
- Índice de Jaccard de lugares: 0,375.
- Del subgrafo de doce entidades sobre el que se calculan las cifras del
  informe, la segunda corrida conserva 10 de los 12 lugares y **10 de las 23
  relaciones**.
- Las relaciones cardinales son las más inestables: `NORTE_DE` y `SUR_DE` no
  comparten ni una sola instancia entre corridas.

## Por qué importa

El informe sostiene que el CSR del trabajo base es una métrica rota, con
cuatro argumentos: el denominador cambia entre ejecuciones; la correlación de
Pearson entre número de restricciones y CSR es −0,67; el mapa verdadero
obtiene menos que ambos sistemas; y el orden entre sistemas se invierte al
mover un umbral que nadie declara.

Esta medición es el quinto, y es el de raíz: **la entrada misma no es
reproducible.** Dos ejecuciones del extractor sobre el mismo texto comparten
menos del 16 % de sus relaciones. Un CSR calculado sobre una de ellas no es
comparable con un CSR calculado sobre la otra, aunque los dos digan medir lo
mismo sobre el mismo libro. Las diez ejecuciones publicadas por el trabajo
base, y la varianza de 16,67 puntos que la reproducción encontró entre
máquinas, quedan explicadas por esto.

## Qué habilita

Esta es la justificación empírica que faltaba para los **pesos de confianza
derivados de múltiples extracciones** (OE2, sección 6.2 del informe). Hasta
ahora eran una decisión de diseño apoyada solo en la literatura. Con esta
medición pasan a ser una respuesta a un problema medido en los propios datos
del trabajo:

- Una relación que aparece en las dos corridas (24 de 151) merece más peso
  que una que aparece en una sola.
- El modelo propuesto ya admite un peso por relación en su densidad, de modo
  que la frecuencia entre corridas se puede usar directamente como peso sin
  cambiar el modelo.
- Es también el argumento más claro para no evaluar nunca contra una única
  extracción.

## Consecuencias prácticas que ya se aplicaron

1. `EXTRAER.py` **nunca sobrescribe** una extracción anterior. Antes el
   nombre del archivo dependía solo del texto, así que la segunda corrida
   borró a la primera, que es la que respalda las cifras del informe. Ahora
   las corridas sucesivas se guardan como `..._run02.json`, `..._run03.json`.
2. La comprobación de que la solución del solver base corresponde a la misma
   extracción **ya no usa la fecha del archivo**, que cambia con solo copiarlo.
   Compara el conjunto de relaciones que el solver evaluó (`rel_eval` de
   `solution.json`) contra el de la extracción en uso, e informa cuántas
   comparten.
3. `DEMO.bat --rapido` usa la extracción que fija `config.json`, que es la del
   informe, de modo que la demostración rápida reproduce las cifras
   publicadas y no depende de cuál haya sido la última corrida.
   `DEMO.bat` sin argumentos sigue extrayendo y trabajando sobre datos
   nuevos, que es lo que corresponde para mostrar el sistema en vivo.

## Estado de los archivos

- `map_relations_..._todo.json` — corrida 1, la del informe. Restaurada.
- `map_relations_..._todo_run02.json` — corrida 2, del 19 de noviembre.
- `solution.json` — solver base sobre la corrida 1. Restaurada, y verificada
  por contenido contra ella.
