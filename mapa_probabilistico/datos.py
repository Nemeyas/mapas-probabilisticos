"""
Carga de datos y seleccion del subgrafo de trabajo.

La entrada es la extraccion congelada que Diaz Ureta y Mercado Meza
publicaron en su repositorio (run_01 del estudio con relaciones
ambiguas): 63 lugares y 90 relaciones. No se vuelve a llamar al modelo de
lenguaje, de modo que cualquier diferencia de resultados viene de la
etapa de resolucion y no de la extraccion. Esa es la condicion que hace
la comparacion cabeza a cabeza valida.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

#: Los nueve lugares que el comparador del sistema base logra emparejar con
#: el grafo oficial de la Tierra Media, con sus coordenadas oficiales
#: normalizadas. El grafo oficial usa y creciente hacia el sur; aca se
#: invierte para dejar y creciente hacia el norte, que es la convencion del
#: modelo. Ver modelo.py.
VERDAD_OFICIAL_Y_SUR = {
    "Bree": (0.384, 0.337),
    "Erebor": (0.752, 0.193),
    "Fornost": (0.360, 0.250),
    "Hobbiton": (0.300, 0.313),
    "Comarca": (0.260, 0.330),          # "La Comarca" en el grafo oficial
    "Puertos Grises": (0.120, 0.333),
    "Rivendel": (0.580, 0.317),
    "Tharbad": (0.420, 0.417),
    "Valle": (0.772, 0.207),
}

#: Posicion del sistema base para esos mismos lugares, segun la ejecucion
#: propia del 10 de noviembre de 2026 (CSR 70,00 %). Sirve de linea base.
BASE_Y_SUR = {
    "Bree": (0.465, 0.515),
    "Erebor": (0.621, 0.283),
    "Fornost": (0.464, 0.225),
    "Hobbiton": (0.472, 0.390),
    "Comarca": (0.507, 0.393),
    "Puertos Grises": (0.319, 0.295),
    "Rivendel": (0.660, 0.353),
    "Tharbad": (0.755, 0.198),
    "Valle": (0.593, 0.341),
}

#: Subgrafo de trabajo. Criterio de seleccion, en este orden:
#:   1. incluir el maximo de lugares con posicion conocida en el grafo
#:      oficial, para poder medir calibracion contra verdad de referencia;
#:   2. que el subgrafo inducido quede conexo;
#:   3. quedarse en una docena de entidades, que son 24 dimensiones, donde
#:      el muestreo todavia mezcla bien.
#: Siete de los doce tienen posicion oficial conocida.
SUBGRAFO = [
    "Comarca", "Hobbiton", "Bree", "Rivendel", "Valle", "Erebor",
    "Fornost", "Norburgo", "Bolson Cerrado", "Delagua", "Quebradas",
    "Tierras de Tuk",
]

#: Algunos nombres traen tilde en el JSON de origen.
ALIAS = {"Bolson Cerrado": "Bolsón Cerrado"}


def invertir_y(d):
    """Pasa de y creciente al sur (imagen) a y creciente al norte (modelo)."""
    return {k: (x, 1.0 - y) for k, (x, y) in d.items()}


def verdad_referencia():
    """Coordenadas oficiales en la convencion del modelo."""
    return invertir_y(VERDAD_OFICIAL_Y_SUR)


def posiciones_sistema_base():
    """Coordenadas del sistema base en la convencion del modelo."""
    return invertir_y(BASE_Y_SUR)


def cargar_extraccion(ruta):
    """Lee el map_relations.json publicado por el trabajo base."""
    with open(ruta, encoding="utf-8") as f:
        d = json.load(f)
    return d["lugares"], d["relaciones"]


def seleccionar_subgrafo(lugares, relaciones, nombres=None):
    """Devuelve (nombres, relaciones inducidas) para el subgrafo pedido."""
    if nombres is None:
        nombres = SUBGRAFO
    reales = [ALIAS.get(n, n) for n in nombres]
    faltan = [n for n in reales if n not in lugares]
    if faltan:
        raise KeyError(f"Lugares que no estan en la extraccion: {faltan}")
    conjunto = set(reales)
    inducidas = [r for r in relaciones
                 if r["origen"] in conjunto and r["destino"] in conjunto]
    return reales, inducidas


def resumen_subgrafo(nombres, relaciones, verdad):
    """Diccionario con el conteo de lo que entra al modelo."""
    from collections import Counter
    return {
        "n_lugares": len(nombres),
        "n_relaciones": len(relaciones),
        "por_tipo": dict(Counter(r["tipo"] for r in relaciones)),
        "con_verdad_conocida": sorted(n for n in nombres if n in verdad),
    }


def guardar_json(ruta, objeto):
    ruta = Path(ruta)
    ruta.parent.mkdir(parents=True, exist_ok=True)
    with open(ruta, "w", encoding="utf-8") as f:
        json.dump(objeto, f, ensure_ascii=False, indent=2, default=_json_default)


def _json_default(o):
    if isinstance(o, (np.floating,)):
        return float(o)
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, np.ndarray):
        return o.tolist()
    raise TypeError(type(o))
