# Código del prototipo y cómo reproducir las cifras del informe

**Seminario de Título — Generación de mapas a partir de textos**
Nehemías Leiva · Ingeniería Civil en Informática, PUCV · Noviembre 2026

## Repositorio

El prototipo completo, con su código, sus pruebas unitarias y los datos de
salida, está publicado en acceso abierto:

**https://github.com/Nemeyas/mapas-probabilisticos**

Todas las cifras y figuras de la sección 7.8 del informe, y la totalidad de
los anexos, se generan automáticamente al ejecutarlo.

## Qué contiene

| Carpeta | Contenido |
|---|---|
| `mapa_probabilistico/` | El modelo: densidad, restricciones blandas, muestreo y métricas |
| `pipeline/` | Los ocho pasos, de la extracción a las figuras |
| `pruebas/` | Pruebas unitarias que verifican el fundamento del modelo |
| `config.json` | Único archivo que hay que tocar para probar con otra entrada |
| `salida/` | Figuras y resultados de la última ejecución |

## Cómo reproducir las cifras publicadas

Desde la carpeta del prototipo, con el entorno ya instalado:

```
python pipeline/1_preparar_subgrafo.py
python pipeline/2_muestrear.py
python pipeline/3_mapas_calor.py
python pipeline/4_comparar.py
python pipeline/8_figura_comparacion.py
```

O, en el equipo de trabajo, `DEMO.bat --rapido`, que ejecuta la secuencia
completa sobre la extracción que fija `config.json` — la misma sobre la que
se calcularon las cifras del informe.

Los valores esperados son:

| Métrica | Valor |
|---|---|
| Subgrafo | 12 entidades, 23 relaciones |
| Gelman-Rubin, peor coordenada | 1,0021 |
| Tamaño efectivo de muestra, mínimo | 1.734 |
| ECSR del modelo | 71,63 % (σ 9,57) |
| CSR, sistema base / prototipo / grafo oficial | 88,89 % / 77,78 % / 77,78 % |
| Nitidez (área creíble media al 80 %) | 0,331 |
| Correlación grado–área | −0,515 |
| Similitud posicional, prototipo / sistema base | 96,63 % / 93,50 % |

## Nota sobre la etapa de extracción

La extracción con modelo de lenguaje requiere una clave de API y saldo en la
cuenta. No es necesaria para reproducir lo anterior: la entrada del modelo es
un archivo JSON con dos listas, `lugares` y `relaciones`, y el repositorio
incluye las extracciones ya generadas. Esa independencia es deliberada, y es
lo que permite comparar la etapa de resolución contra el trabajo base sin que
la extracción intervenga en la diferencia.

## Sobre la estabilidad de la extracción

Dos ejecuciones del extractor sobre el mismo texto, con el mismo modelo y el
mismo prompt, comparten solo 24 de 151 relaciones distintas (índice de
Jaccard 0,159). El hallazgo está documentado en la sección 7.9 del informe y
en el documento que acompaña a este archivo. Por esa razón el repositorio
conserva cada ejecución por separado y nunca sobrescribe una anterior.
