"""
Metricas para mapas con incertidumbre.

El trabajo base mide con CSR: la fraccion de restricciones que satisface
la unica configuracion que entrega. Esa metrica no se puede aplicar tal
cual a una distribucion, y ademas tiene un defecto propio que la
verificacion dejo a la vista: el denominador cambia entre ejecuciones, asi
que una ejecucion mejora su CSR simplemente extrayendo menos relaciones
(correlacion de Pearson -0,67 entre numero de restricciones y CSR sobre
las diez ejecuciones publicadas).

Este modulo define tres metricas que si aplican a una distribucion:

- ECSR     cuanto satisface en promedio, comparable cifra a cifra con el CSR.
- Nitidez  cuanto espacio ocupa la creencia. Una distribucion plana lo
           satisface todo y no dice nada, asi que ECSR solo no basta.
- Calibracion  si los intervalos de confianza son honestos.
"""

from __future__ import annotations

import numpy as np

from .modelo import satisface_dura


# ---------------------------------------------------------------------------
# ECSR
# ---------------------------------------------------------------------------

def ecsr(modelo, muestras):
    """Tasa esperada de satisfaccion de restricciones.

    Promedio sobre la posterior de la fraccion de relaciones que el
    predicado duro da por satisfechas. Con una distribucion degenerada en un
    punto se reduce exactamente al CSR del trabajo base, asi que las dos
    cifras son comparables.

    Devuelve (media, desviacion, por_relacion) donde `por_relacion` es la
    probabilidad posterior de que cada relacion se satisfaga.
    """
    muestras = np.asarray(muestras)
    n_m = muestras.shape[0]
    if modelo.n_relaciones == 0:
        return float("nan"), float("nan"), {}

    # Se usa el predicado DEL MODELO, no el del modulo. Antes se llamaba a
    # satisface_dura con sus parametros por omision, de modo que el ECSR
    # ignoraba el d0 configurado y el tipado geometrico: daba el mismo valor
    # con d0 = 0,02 que con d0 = 0,50.
    ok = np.zeros((n_m, modelo.n_relaciones), dtype=bool)
    if not getattr(modelo, "tipado_activo", False):
        # Sin tipado toda entidad es un punto y el predicado se puede
        # vectorizar sobre todas las muestras a la vez. Se le pasan los
        # umbrales DEL MODELO, que es justo lo que antes se omitia.
        for j, r in enumerate(modelo.relaciones):
            a = muestras[:, modelo.indice[r["origen"]], :]
            b = muestras[:, modelo.indice[r["destino"]], :]
            ok[:, j] = satisface_dura(a, b, r["tipo"],
                                      d0_cerca=modelo.d0_cerca,
                                      d0_conecta=modelo.d0_conecta)
    else:
        # Con tipado hay que evaluar forma a forma, muestra a muestra.
        for k in range(n_m):
            for j in range(modelo.n_relaciones):
                ok[k, j] = modelo.satisface(muestras[k], j)

    por_muestra = ok.mean(axis=1)
    por_relacion = {
        (r["origen"], r["tipo"], r["destino"]): float(ok[:, j].mean())
        for j, r in enumerate(modelo.relaciones)
    }
    return float(por_muestra.mean()), float(por_muestra.std(ddof=1)), por_relacion


# ---------------------------------------------------------------------------
# Nitidez
# ---------------------------------------------------------------------------

#: Ventana sobre la que se discretiza el espacio para medir areas. Es el
#: cuadrado del grafo oficial con un margen, de modo que las areas se leen
#: en unidades de "mapa oficial": 0,05 es un veinteavo del mapa.
VENTANA = (-0.25, 1.25)


def region_creible(puntos, nivel=0.80, celdas=60, ventana=VENTANA):
    """Region creible al `nivel` pedido, por conteo en una grilla.

    Se discretiza el cuadrado unitario, se acumula masa en las celdas de
    mayor densidad hasta alcanzar el nivel, y se devuelve el area resultante
    junto con la mascara de celdas incluidas.

    Es la version discreta de la region de mayor densidad posterior. Se
    prefiere al conteo por nucleo porque no depende de elegir un ancho de
    banda, y porque el area sale directo en unidades del cuadrado.
    """
    puntos = np.asarray(puntos, dtype=float)
    bordes = np.linspace(ventana[0], ventana[1], celdas + 1)
    H, _, _ = np.histogram2d(puntos[:, 0], puntos[:, 1], bins=[bordes, bordes])
    if H.sum() == 0:
        return float("nan"), H.astype(bool), bordes
    # Se normaliza por el TOTAL de muestras, no por las que cayeron dentro.
    # Si una parte de la nube se sale de la ventana, esa masa sigue contando
    # en el denominador y la region al nivel pedido crece para compensar.
    # Normalizar por lo de adentro subestimaba el area justo en las
    # entidades mas inciertas, que son las que mas masa pierden.
    H = H / float(len(puntos))
    plano = np.sort(H.ravel())[::-1]
    acumulado = np.cumsum(plano)
    if acumulado[-1] < nivel:
        # Ni toda la ventana alcanza el nivel pedido: la nube se escapa
        # demasiado. Se devuelve el area completa de la ventana como cota
        # inferior, en vez de una cifra enganosamente pequena.
        return (float((ventana[1] - ventana[0]) ** 2),
                np.ones_like(H, dtype=bool), bordes)
    corte_idx = int(np.searchsorted(acumulado, nivel))
    umbral = plano[min(corte_idx, len(plano) - 1)]
    mascara = H >= umbral
    area_celda = ((ventana[1] - ventana[0]) / celdas) ** 2
    return float(mascara.sum() * area_celda), mascara, bordes


def nitidez(muestras, lugares, nivel=0.80, celdas=60, ventana=VENTANA):
    """Area media de la region creible por entidad. Menor es mas nitido.

    Es la metrica que impide hacer trampa con ECSR: una posterior plana
    satisface casi todo y tiene area casi 1.
    """
    muestras = np.asarray(muestras)
    areas = {}
    for i, nombre in enumerate(lugares):
        area, _, _ = region_creible(muestras[:, i, :], nivel=nivel,
                                    celdas=celdas, ventana=ventana)
        areas[nombre] = area
    return float(np.mean(list(areas.values()))), areas


# ---------------------------------------------------------------------------
# Calibracion
# ---------------------------------------------------------------------------

def curva_calibracion(muestras, lugares, verdad, niveles=None, celdas=60,
                      ventana=VENTANA):
    """Curva de confiabilidad: cobertura empirica contra nivel nominal.

    Para cada nivel q se mide que fraccion de los lugares con posicion
    conocida cae dentro de su region creible al q por ciento. Un modelo
    calibrado da la diagonal. Por debajo de la diagonal el modelo es
    confiado de mas, que es el modo de fallo peligroso.

    `verdad` es un dict nombre -> (x, y) ya en el mismo marco que las
    muestras.
    """
    if niveles is None:
        niveles = [0.5, 0.6, 0.7, 0.8, 0.9, 0.95]
    muestras = np.asarray(muestras)
    comunes = [n for n in lugares if n in verdad]
    cobertura = []
    for q in niveles:
        dentro = 0
        for nombre in comunes:
            i = lugares.index(nombre)
            _, mascara, bordes = region_creible(muestras[:, i, :], nivel=q,
                                                celdas=celdas, ventana=ventana)
            x, y = verdad[nombre]
            cx = int(np.searchsorted(bordes, x, side="right") - 1)
            cy = int(np.searchsorted(bordes, y, side="right") - 1)
            if 0 <= cx < celdas and 0 <= cy < celdas and mascara[cx, cy]:
                dentro += 1
        cobertura.append(dentro / len(comunes) if comunes else float("nan"))
    return list(niveles), cobertura, comunes


def error_calibracion(niveles, cobertura):
    """Error de calibracion esperado: desviacion media de la diagonal."""
    return float(np.mean(np.abs(np.asarray(cobertura) - np.asarray(niveles))))


# ---------------------------------------------------------------------------
# Comparacion con la verdad de referencia
# ---------------------------------------------------------------------------

def centrar(muestras):
    """Quita la traslacion de cada configuracion llevandola a su centroide.

    La densidad es invariante a traslaciones: solo hay relaciones relativas.
    Durante el muestreo se fija un ancla para que la cadena no derive, pero
    eso deja al lugar anclado con una posterior degenerada en un punto, que
    es un artefacto. Re-centrando cada configuracion se recupera la
    posterior correcta de las posiciones relativas, incluida la del ancla.
    """
    M = np.asarray(muestras, dtype=float)
    return M - M.mean(axis=1, keepdims=True)


def ajustar_semejanza(origen, destino):
    """Semejanza de minimos cuadrados (escala uniforme + traslacion).

    Devuelve (escala, traslacion) tal que escala * origen + traslacion queda
    lo mas cerca posible de destino.

    Se usa escala uniforme y no una normalizacion min-max por eje a
    proposito: estirar cada eje por separado deforma las distribuciones y
    puede inflar o aplastar las regiones creibles, que es justamente lo que
    se quiere medir. La semejanza preserva la forma. No se ajusta rotacion
    porque el modelo ya tiene el norte fijado por las relaciones cardinales.
    """
    A = np.asarray(origen, dtype=float)
    B = np.asarray(destino, dtype=float)
    ca, cb = A.mean(axis=0), B.mean(axis=0)
    A0, B0 = A - ca, B - cb
    denom = float((A0 * A0).sum())
    escala = float((A0 * B0).sum() / denom) if denom > 1e-18 else 1.0
    return escala, cb - escala * ca


def alinear_a_referencia(muestras, lugares, verdad):
    """Lleva las muestras al marco del grafo oficial.

    Centra, ajusta una semejanza sobre las medias posteriores de los lugares
    con posicion conocida, y aplica esa misma transformacion a todas las
    muestras. La nube entera se mueve junta: las formas no cambian.
    """
    M = centrar(muestras)
    comunes = [n for n in lugares if n in verdad]
    if len(comunes) < 2:
        # Sin verdad de referencia no hay a que alinearse. Se deja la nube
        # centrada y escalada a una extension comparable, que es suficiente
        # para medir nitidez y para dibujar.
        esc = 0.5 / max(float(np.abs(M).max()), 1e-9)
        return esc * M + 0.5, [], (esc, np.array([0.5, 0.5]))
    idx = [lugares.index(n) for n in comunes]
    medias = M.mean(axis=0)[idx]
    objetivo = np.array([verdad[n] for n in comunes], dtype=float)
    escala, t = ajustar_semejanza(medias, objetivo)
    return escala * M + t, comunes, (escala, t)


def radio_giro(A):
    """Raiz del segundo momento respecto del centroide. Mide la extension."""
    A = np.asarray(A, dtype=float)
    return float(np.sqrt(((A - A.mean(axis=0)) ** 2).sum(axis=1).mean()))


def normalizar_a_escala_comun(posiciones, objetivo):
    """Lleva un candidato al marco del objetivo con una escala NO ajustable.

    POR QUE EXISTE ESTA FUNCION, y no se usa `ajustar_semejanza` para esto:
    el predicado duro compara distancias contra umbrales absolutos
    (d0_cerca, d0_conecta). Si cada candidato recibe la escala que mejor le
    ajusta por minimos cuadrados, la escala se vuelve un grado de libertad
    que el predicado premia. Medido: en la comparacion cabeza a cabeza el
    ajuste por minimos cuadrados daba escala 0,125 al sistema base y 1,547
    al modelo. Encoger ocho veces un mapa hace que todo quede "cerca de"
    todo, asi que el sistema base ganaba la comparacion por haber sido
    comprimido, no por ser mejor.

    Aqui la escala la fija una regla igual para todos: se iguala el radio de
    giro al del objetivo. El objetivo se transforma en si mismo, de modo que
    el grafo oficial sigue siendo el techo interpretable de la tabla.

    `ajustar_semejanza` se sigue usando para la similitud posicional, que es
    una distancia y no un predicado con umbral: ahi el ajuste optimo es lo
    correcto, porque no hay nada que un cambio de escala pueda regalar.
    """
    A = np.asarray(posiciones, dtype=float)
    B = np.asarray(objetivo, dtype=float)
    ra, rb = radio_giro(A), radio_giro(B)
    escala = (rb / ra) if ra > 1e-12 else 1.0
    return escala * (A - A.mean(axis=0)) + B.mean(axis=0), escala


def similitud_posicional(estimado, verdad_nombres, verdad, lugares):
    """Similitud posicional contra el grafo oficial, en porcentaje.

    1 menos la distancia media, escalada por la diagonal del cuadrado
    unitario. Misma definicion que usa el comparador del sistema base, para
    que las cifras se puedan poner una al lado de la otra. Se asume que
    `estimado` ya esta en el marco del grafo oficial.
    """
    idx = [lugares.index(n) for n in verdad_nombres]
    A = np.asarray(estimado, dtype=float)[idx]
    B = np.array([verdad[n] for n in verdad_nombres], dtype=float)
    d = np.linalg.norm(A - B, axis=1)
    return float(100.0 * (1.0 - d.mean() / np.sqrt(2.0)))
