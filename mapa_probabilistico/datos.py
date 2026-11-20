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


#: Pares de relaciones direccionales que afirman lo mismo al reves. Una
#: extraccion puede devolver las dos formas de una misma afirmacion del
#: texto, y entonces "A al este de B" y "B al oeste de A" entran como dos
#: restricciones distintas.
OPUESTO = {
    "NORTE_DE": "SUR_DE", "SUR_DE": "NORTE_DE",
    "ESTE_DE": "OESTE_DE", "OESTE_DE": "ESTE_DE",
    "CERCA_DE": "CERCA_DE", "CONECTA": "CONECTA",
}


def colapsar_reciprocas(relaciones):
    """Deja una sola copia de cada afirmacion, y devuelve (unicas, pares).

    POR QUE: el modelo multiplica un factor por relacion, asi que una
    afirmacion duplicada entra al producto dos veces y la posterior sale mas
    angosta de lo que la evidencia permite. Medido sobre el subgrafo de doce
    entidades, el unico par reciproco presente (Comarca OESTE_DE Bree y Bree
    ESTE_DE Comarca) hacia bajar el area creible media de 0,322 a 0,257: un
    25 % de nitidez que no venia del texto sino de contar dos veces la misma
    frase. Tambien inflaba el denominador del CSR, 24 en vez de 23.

    El trabajo base no hace este colapso: sus restricciones recorren la lista
    tal cual. Se aplica aqui a la ENTRADA, antes de repartirla, de modo que
    los tres candidatos que se comparan en el paso 4 (solver base, MAP del
    modelo y grafo oficial) se evaluan sobre la misma lista y la comparacion
    sigue siendo pareja.
    """
    vistas, unicas, pares = {}, [], []
    for r in relaciones:
        clave = (r["origen"], r["tipo"], r["destino"])
        inversa = (r["destino"], OPUESTO.get(r["tipo"], r["tipo"]), r["origen"])
        if inversa in vistas:
            pares.append((vistas[inversa], clave))
            continue
        vistas[clave] = clave
        unicas.append(r)
    return unicas, pares


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
    inducidas, _ = colapsar_reciprocas(inducidas)
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


# ---------------------------------------------------------------------------
# Configuracion
# ---------------------------------------------------------------------------

def cargar_config(raiz=None):
    """Lee config.json. Las claves que empiezan con guion bajo son ayuda."""
    from pathlib import Path as _P
    raiz = _P(raiz) if raiz else _P(__file__).resolve().parents[1]
    with open(raiz / "config.json", encoding="utf-8") as f:
        cfg = json.load(f)
    return _sin_ayuda(cfg)


def _sin_ayuda(o):
    if isinstance(o, dict):
        return {k: _sin_ayuda(v) for k, v in o.items() if not k.startswith("_")}
    if isinstance(o, list):
        return [_sin_ayuda(v) for v in o]
    return o


def cargar_referencia(ruta, y_hacia_el_sur=True, alias=None):
    """Carga un grafo oficial y lo normaliza al cuadrado unitario.

    Los grafos oficiales del trabajo base vienen en pixeles sobre un lienzo
    con `width` y `height`, y con y creciente hacia el sur. Aqui se pasan a
    [0,1] y, si corresponde, se invierte el eje y para dejarlo creciente al
    norte, que es la convencion del modelo.
    """
    with open(ruta, encoding="utf-8") as f:
        g = json.load(f)
    coords = g.get("coords", g)
    W = float(g.get("width") or 1.0)
    H = float(g.get("height") or W)
    alias = alias or {}
    salida = {}
    for nombre, p in coords.items():
        x = float(p["x"]) / W
        y = float(p["y"]) / H
        if y_hacia_el_sur:
            y = 1.0 - y
        salida[alias.get(nombre, nombre)] = (x, y)
    return salida


def seleccionar_subgrafo_auto(lugares, relaciones, verdad, n_lugares=12):
    """Elige un subgrafo conexo sin intervencion manual.

    Se construye por crecimiento desde una semilla, en vez de tomar los n
    mejores y despues quedarse con lo que quede conexo. La version anterior
    hacia eso ultimo y gastaba cupos en lugares con posicion oficial pero
    una sola relacion, que terminaban descartados por aislados: pedir doce
    lugares devolvia ocho.

    Criterio de crecimiento, en este orden:
      1. preferir lugares con posicion conocida en el grafo oficial, que son
         los unicos con los que se puede medir calibracion;
      2. entre iguales, preferir los de mayor grado dentro del conjunto ya
         elegido, que es lo que mantiene el subgrafo bien conectado;
      3. desempatar por grado total y por nombre, para que sea determinista.

    El resultado es conexo por construccion y tiene exactamente n_lugares,
    salvo que el grafo entero sea mas chico.
    """
    from collections import Counter

    grado = Counter()
    ady = {}
    for r in relaciones:
        a, b = r["origen"], r["destino"]
        if a == b:
            continue
        grado[a] += 1
        grado[b] += 1
        ady.setdefault(a, set()).add(b)
        ady.setdefault(b, set()).add(a)

    disponibles = [l for l in lugares if grado[l] > 0]
    if not disponibles:
        return [], []

    # Semilla: el lugar mejor conectado, prefiriendo los que tienen verdad.
    semilla = min(disponibles,
                  key=lambda l: (0 if l in verdad else 1, -grado[l], l))
    elegidos = [semilla]
    frontera = set(ady.get(semilla, ()))

    while len(elegidos) < n_lugares and frontera:
        dentro = set(elegidos)
        mejor = min(
            frontera,
            key=lambda l: (0 if l in verdad else 1,
                           -len(ady.get(l, set()) & dentro),
                           -grado[l], l))
        elegidos.append(mejor)
        frontera.discard(mejor)
        frontera |= (ady.get(mejor, set()) - set(elegidos))

    conjunto = set(elegidos)
    inducidas = [r for r in relaciones
                 if r["origen"] in conjunto and r["destino"] in conjunto]
    inducidas, _ = colapsar_reciprocas(inducidas)
    return elegidos, inducidas


def cargar_solucion_base(ruta, y_hacia_el_sur=True):
    """Carga las coordenadas que produjo el solver del trabajo base.

    `solution.json` del trabajo base trae `coords` en pixeles sobre un
    lienzo `width` x `height`, con y creciente hacia el sur. Se normaliza al
    cuadrado unitario y se invierte y, igual que el grafo oficial.

    Esto importa para que la comparacion sea pareja: las coordenadas del
    sistema base tienen que venir de una corrida sobre LA MISMA extraccion
    que usa el modelo. Compararlas contra las de otra extraccion favorece
    artificialmente al modelo, porque su solver nunca vio esas relaciones.
    """
    with open(ruta, encoding="utf-8") as f:
        g = json.load(f)
    coords = g.get("coords", {})
    W = float(g.get("width") or 1.0)
    H = float(g.get("height") or W)
    salida = {}
    for nombre, p in coords.items():
        x = float(p["x"]) / W
        y = float(p["y"]) / H
        if y_hacia_el_sur:
            y = 1.0 - y
        salida[nombre] = (x, y)
    # `rel_eval` son las relaciones que el solver del trabajo base
    # realmente evaluo. Es la huella exacta de la extraccion que vio, y
    # permite decidir si la comparacion es pareja sin depender de fechas
    # de archivo, que se alteran con solo copiar un fichero.
    huella = {(r.get("origen"), r.get("tipo"), r.get("destino"))
              for r in (g.get("rel_eval") or [])}
    return salida, {"CSR": g.get("CSR"),
                    "total_constraints": g.get("total_constraints"),
                    "solver_mode": g.get("solver_mode"),
                    "relaciones_evaluadas": sorted(huella)}


def guardar_figura(fig, ruta, **kw):
    """Guarda una figura aunque el archivo este abierto en un visor.

    En Windows, tener el PNG abierto en el visor de imagenes bloquea el
    archivo y matplotlib falla con OSError 22. Como el pipeline abre las
    figuras al terminar, la corrida siguiente chocaba con su propia salida.

    Si el destino esta bloqueado se guarda junto a el con una marca de
    tiempo y se avisa, en vez de abortar la corrida entera por un visor
    abierto.
    """
    from pathlib import Path as _P
    import time as _t
    ruta = _P(ruta)
    ruta.parent.mkdir(parents=True, exist_ok=True)
    try:
        fig.savefig(ruta, **kw)
        return ruta
    except OSError as e:
        alt = ruta.with_name(f"{ruta.stem}_{_t.strftime('%H%M%S')}{ruta.suffix}")
        fig.savefig(alt, **kw)
        print(f"  AVISO: no se pudo escribir {ruta.name} ({e.strerror}).")
        print(f"  Probablemente esta abierto en el visor de imagenes.")
        print(f"  Se guardo como {alt.name}. Cierra el visor y vuelve a correr.")
        return alt


# --- formato numerico de las figuras ---------------------------------------
#
# El informe usa coma decimal (convencion del espanol). Las figuras deben
# usar la misma, o el lector ve 0,048 en el texto y 0.048 en la figura.

def coma(x, decimales=3):
    """Numero con coma decimal: coma(0.0481) -> '0,048'."""
    return f"{x:.{decimales}f}".replace(".", ",")


def ejes_con_coma(*ejes):
    """Hace que las marcas de los ejes usen coma decimal."""
    from matplotlib.ticker import ScalarFormatter

    class _Coma(ScalarFormatter):
        def __call__(self, x, pos=None):
            return super().__call__(x, pos).replace(".", ",")

    for ax in ejes:
        for eje in (ax.xaxis, ax.yaxis):
            # Solo los ejes numericos: un eje con nombres (barras
            # horizontales, por ejemplo) conserva sus etiquetas.
            if type(eje.get_major_formatter()) is ScalarFormatter:
                eje.set_major_formatter(_Coma())
