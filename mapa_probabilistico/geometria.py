"""
Geometria de las entidades.

El sistema base representa todo lugar como un punto, incluso un rio o una
region. Esta propuesta distingue tres tipos y evalua las relaciones contra
la forma real de cada entidad, que es la seccion 5.3 del informe.

    punto   una posicion.
    curva   un segmento, definido por sus dos extremos. "Cerca del rio"
            se mide contra el punto mas cercano del segmento, no contra un
            punto que pretenda representar al rio entero.
    region  un disco, definido por su centro y su radio. "Cerca de la
            Comarca" se mide contra el borde, y vale cero si esta dentro.
            Es la version mas simple del modelo de yema y clara de Cohn y
            Gotts: el radio delimita la yema.

Toda la aritmetica es escalar a proposito. El muestreo evalua estas
funciones millones de veces sobre dos o tres relaciones, y a esa escala el
costo esta en el despacho de numpy y no en las operaciones.
"""

from __future__ import annotations

from math import hypot

PUNTO, CURVA, REGION = "punto", "curva", "region"
TIPOS = (PUNTO, CURVA, REGION)

#: Radio por defecto de una region, en unidades del cuadrado unitario.
RADIO_REGION = 0.06


def dist_punto_segmento(px, py, ax, ay, bx, by):
    """Distancia de un punto al segmento AB."""
    vx, vy = bx - ax, by - ay
    largo2 = vx * vx + vy * vy
    if largo2 <= 1e-18:                 # el segmento degenero en un punto
        return hypot(px - ax, py - ay)
    t = ((px - ax) * vx + (py - ay) * vy) / largo2
    t = 0.0 if t < 0.0 else (1.0 if t > 1.0 else t)
    return hypot(px - (ax + t * vx), py - (ay + t * vy))


def _cruzan(ax, ay, bx, by, cx, cy, dx, dy):
    """Verdadero si los segmentos AB y CD se cruzan."""
    def lado(x1, y1, x2, y2, x3, y3):
        return (x2 - x1) * (y3 - y1) - (y2 - y1) * (x3 - x1)
    d1 = lado(ax, ay, bx, by, cx, cy)
    d2 = lado(ax, ay, bx, by, dx, dy)
    d3 = lado(cx, cy, dx, dy, ax, ay)
    d4 = lado(cx, cy, dx, dy, bx, by)
    return ((d1 > 0) != (d2 > 0)) and ((d3 > 0) != (d4 > 0))


def dist_segmento_segmento(ax, ay, bx, by, cx, cy, dx, dy):
    """Distancia minima entre los segmentos AB y CD.

    Si se cruzan la distancia es cero. Si no, el minimo se alcanza en algun
    extremo, de modo que basta el menor de los cuatro casos punto-segmento.
    """
    if _cruzan(ax, ay, bx, by, cx, cy, dx, dy):
        return 0.0
    return min(
        dist_punto_segmento(ax, ay, cx, cy, dx, dy),
        dist_punto_segmento(bx, by, cx, cy, dx, dy),
        dist_punto_segmento(cx, cy, ax, ay, bx, by),
        dist_punto_segmento(dx, dy, ax, ay, bx, by),
    )


def distancia_formas(fa, fb):
    """Distancia entre dos entidades, segun sus formas.

    Cada forma es una tupla (tipo, x1, y1, x2, y2, radio). Para un punto y
    para una region el segundo par de coordenadas se ignora; para una curva
    son los dos extremos. El radio solo aplica a las regiones.

    La distancia se mide entre los soportes y luego se descuentan los
    radios, con piso en cero: dos entidades que se solapan estan a
    distancia nula.
    """
    ta, ax, ay, a2x, a2y, ra = fa
    tb, bx, by, b2x, b2y, rb = fb

    if ta == CURVA and tb == CURVA:
        d = dist_segmento_segmento(ax, ay, a2x, a2y, bx, by, b2x, b2y)
    elif ta == CURVA:
        d = dist_punto_segmento(bx, by, ax, ay, a2x, a2y)
    elif tb == CURVA:
        d = dist_punto_segmento(ax, ay, bx, by, b2x, b2y)
    else:
        d = hypot(ax - bx, ay - by)

    d -= (ra if ta == REGION else 0.0) + (rb if tb == REGION else 0.0)
    return d if d > 0.0 else 0.0


def representante(forma):
    """Punto que representa a la entidad para las relaciones direccionales.

    Las direcciones cardinales se evaluan entre los representantes: el punto
    mismo, el centro de la region o el punto medio de la curva. Un cono
    direccional sobre una forma extensa no tiene una definicion unica, y
    tomar el centro es la convencion habitual en razonamiento espacial
    cualitativo.
    """
    t, x1, y1, x2, y2, _ = forma
    if t == CURVA:
        return 0.5 * (x1 + x2), 0.5 * (y1 + y2)
    return x1, y1
