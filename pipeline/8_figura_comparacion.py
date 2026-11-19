"""
Paso 8 · Los tres mapas, lado a lado.

Las figuras de los pasos 3 y 4 miran una entidad a la vez. Esta mira el
mapa entero, que es como lo mira un lector, y pone los tres candidatos en
el mismo marco:

    (a) sistema base      una coordenada por lugar
    (b) modelo propuesto  una region creible por lugar
    (c) grafo oficial     la geografia verdadera de la obra

Por que los tres en el mismo marco, y con la misma regla
--------------------------------------------------------
Un mapa esta definido salvo semejanza, asi que para dibujarlos juntos hay
que fijar la escala de alguna manera. Si se le da a cada candidato la
escala que mejor lo ajusta por minimos cuadrados, el que quede mas
comprimido parece mas cercano al oficial sin serlo. Se usa aqui la misma
regla no ajustable que el paso 4 aplica al CSR: igualar el radio de giro
al del grafo oficial, con lo cual el grafo oficial se transforma en si
mismo y los tres paneles comparten ejes.

Por que regiones creibles, y por que solo las entidades con referencia
----------------------------------------------------------------------
Sumar las nubes de todas las entidades en un solo mapa de calor produce una
mancha unica: las colas se solapan y no se distingue una entidad de otra.
La region creible al 80 % de cada una, dibujada como contorno suavizado,
dice lo mismo y se lee.

Los tres paneles muestran EL MISMO conjunto de entidades: las que tienen
posicion en el grafo oficial. El panel (c) no puede mostrar otras, asi que
dibujar en (a) y (b) entidades que (c) no tiene volveria los paneles no
comparables, que es justo lo que esta figura quiere evitar. Las demas
entidades del subgrafo aparecen una por una en la figura de los mapas de
calor del paso 3.

El sistema base publica DOS juegos de coordenadas: las que entrega Z3
(`solution.json`, que son las que llevan su CSR) y un refinamiento
posterior con un algoritmo de fuerzas (`solution_refined.json`, que es lo
que dibuja su propia figura). Se comprobo que ambas dan practicamente la
misma similitud posicional contra el grafo oficial, 93,50 % y 93,38 %, de
modo que la eleccion no altera la comparacion. Se dibuja la de Z3 por ser
la que respalda la cifra que ese trabajo reporta.

Uso:
    python pipeline\\8_figura_comparacion.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.patheffects as pe  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402
from matplotlib.patches import Patch  # noqa: E402

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

from mapa_probabilistico import metricas  # noqa: E402
from mapa_probabilistico.datos import guardar_figura  # noqa: E402

TINTA = "#1F1915"
TENUE = "#6B6058"
PAPEL = "#FBF8F4"
VERDE = "#17563F"
ROJO = "#8C2F2F"
BORDE = "#D8CEC2"

NIVEL = 0.80      # nivel de las regiones creibles
CELDAS = 220      # resolucion de la grilla sobre la que se calculan


def suavizar(h, sigma=3.0):
    """Desenfoque gaussiano separable, solo con numpy.

    Se evita depender de scipy a proposito: el entorno del prototipo se
    instala desde requirements.txt y una dependencia mas es una forma mas
    de que la demostracion falle en otra maquina. El nucleo es separable,
    asi que dos convoluciones 1-D bastan.
    """
    r = int(3 * sigma)
    k = np.exp(-0.5 * (np.arange(-r, r + 1) / sigma) ** 2)
    k /= k.sum()
    pad = np.pad(h, ((r, r), (0, 0)), mode="constant")
    h = np.apply_along_axis(lambda v: np.convolve(v, k, "valid"), 0, pad)
    pad = np.pad(h, ((0, 0), (r, r)), mode="constant")
    return np.apply_along_axis(lambda v: np.convolve(v, k, "valid"), 1, pad)


def halo(texto):
    texto.set_path_effects([pe.withStroke(linewidth=2.8, foreground=PAPEL)])


def etiquetar(ax, pos, color=TENUE, sep=0.085):
    """Etiqueta cada punto, alternando arriba y abajo cuando se estorban.

    Con cinco entidades muy juntas las etiquetas se pisan y el panel queda
    ilegible. Se recorren de izquierda a derecha y, si la anterior esta a
    menos de `sep`, esta se manda al lado contrario.
    """
    orden = sorted(pos.items(), key=lambda kv: kv[1][0])
    arriba, ult = True, None
    for n, (x, y) in orden:
        if ult is not None and abs(x - ult) < sep:
            arriba = not arriba
        else:
            arriba = True
        ult = x
        halo(ax.annotate(n, (x, y), textcoords="offset points",
                         xytext=(0, 11 if arriba else -19),
                         ha="center", fontsize=10.5, color=color, zorder=8))


def aristas(ax, pos, relaciones, color):
    for r in relaciones:
        a, b = r["origen"], r["destino"]
        if a in pos and b in pos:
            ax.plot([pos[a][0], pos[b][0]], [pos[a][1], pos[b][1]],
                    color=color, lw=0.8, alpha=0.5, zorder=1)


def marco(ax, titulo, lim, limy):
    ax.set_title(titulo, fontsize=13.5, color=TINTA, pad=9)
    ax.set_xlim(lim); ax.set_ylim(limy)
    ax.set_aspect("equal")
    ax.set_xticks([]); ax.set_yticks([])
    ax.set_facecolor(PAPEL)
    for b in ax.spines.values():
        b.set_color(BORDE)


def nivel_hpd(h, nivel):
    """Altura de corte que deja `nivel` de la masa por encima."""
    plano = np.sort(h.ravel())[::-1]
    acum = np.cumsum(plano)
    if acum[-1] <= 0:
        return None
    k = int(np.searchsorted(acum, nivel * acum[-1]))
    return float(plano[min(k, len(plano) - 1)])


def main():
    sub = json.loads((RAIZ / "datos" / "subgrafo.json").read_text(encoding="utf-8"))
    z = np.load(RAIZ / "salida" / "muestras.npz", allow_pickle=True)
    muestras = z["muestras"].astype(float)
    lugares = list(z["lugares"])
    verdad = sub["verdad_referencia"]
    base = sub["sistema_base"]
    relaciones = sub["relaciones"]

    comunes = [n for n in lugares if n in verdad]
    if len(comunes) < 2:
        print("Hacen falta al menos dos lugares con posicion oficial.")
        return 1
    objetivo = np.array([verdad[n] for n in comunes], dtype=float)
    idx = [lugares.index(n) for n in comunes]
    centro_of = objetivo.mean(axis=0)

    # --- los tres candidatos, bajo la MISMA regla de escala -------------
    #
    # Se parte de las muestras SOLO centradas. `alinear_a_referencia` ya
    # aplica un ajuste de semejanza, y encadenarle la regla de escala
    # comun escalaria dos veces.
    M = metricas.centrar(muestras)
    medias = M.mean(axis=0)
    _, esc_mod = metricas.normalizar_a_escala_comun(medias[idx], objetivo)
    nube = esc_mod * (M - medias[idx].mean(axis=0)) + centro_of
    pos_mod = {n: tuple(nube.mean(axis=0)[i]) for i, n in enumerate(lugares)}

    pos_mod = {n: v for n, v in pos_mod.items() if n in verdad}

    pos_base = {}
    con_base = [n for n in lugares if n in base and n in verdad]
    con_ambos = [n for n in con_base if n in verdad]
    if len(con_ambos) >= 2:
        Bc = np.array([base[n] for n in con_ambos], dtype=float)
        Oc = np.array([verdad[n] for n in con_ambos], dtype=float)
        _, esc_b = metricas.normalizar_a_escala_comun(Bc, Oc)
        B = np.array([base[n] for n in con_base], dtype=float)
        Q = esc_b * (B - Bc.mean(axis=0)) + Oc.mean(axis=0)
        pos_base = {n: tuple(Q[i]) for i, n in enumerate(con_base)}

    pos_of = {n: tuple(verdad[n]) for n in comunes}

    # --- limites: lo que de verdad se dibuja ----------------------------
    #
    # Los fijan los puntos y la extension de las regiones creibles que se
    # van a pintar, no las colas de las cadenas. Con las colas el dibujo
    # quedaba casi vacio y los paneles de puntos, ilegibles.
    puntos = [np.array(list(pos_mod.values())),
              np.array(list(pos_of.values()))]
    if pos_base:
        puntos.append(np.array(list(pos_base.values())))
    P = np.vstack(puntos)

    cajas = [P.min(axis=0), P.max(axis=0)]
    for n in pos_mod:
        i = lugares.index(n)
        lo = np.percentile(nube[:, i, :], 100 * (1 - NIVEL) / 2, axis=0)
        hi = np.percentile(nube[:, i, :], 100 * (1 + NIVEL) / 2, axis=0)
        cajas += [lo, hi]
    C = np.vstack(cajas)
    c = 0.5 * (C.min(axis=0) + C.max(axis=0))
    radio = float((C.max(axis=0) - C.min(axis=0)).max()) * 0.5 * 1.16 + 0.02
    lim = (c[0] - radio, c[0] + radio)
    limy = (c[1] - radio, c[1] + radio)

    fig, axes = plt.subplots(1, 3, figsize=(13.4, 5.4))
    fig.patch.set_facecolor(PAPEL)

    # (a) sistema base ---------------------------------------------------
    ax = axes[0]
    if pos_base:
        aristas(ax, pos_base, relaciones, "#C2B19B")
        A = np.array(list(pos_base.values()))
        ax.plot(A[:, 0], A[:, 1], linestyle="none", marker="+", ms=11, mew=2.0,
                color=TINTA, zorder=5)
        etiquetar(ax, pos_base)
    marco(ax, "(a)  Sistema base · una coordenada por lugar", lim, limy)

    # (b) modelo propuesto ------------------------------------------------
    ax = axes[1]
    bx = np.linspace(lim[0], lim[1], CELDAS + 1)
    by = np.linspace(limy[0], limy[1], CELDAS + 1)
    cx = 0.5 * (bx[:-1] + bx[1:])
    cy = 0.5 * (by[:-1] + by[1:])
    for n in pos_mod:
        i = lugares.index(n)
        h, _, _ = np.histogram2d(nube[:, i, 0], nube[:, i, 1], bins=[bx, by])
        # El contorno sobre el histograma crudo sale dentado: el ruido de
        # conteo cruza el nivel muchas veces. Se suaviza con un nucleo
        # gaussiano angosto, que no mueve la region, solo limpia el borde.
        h = suavizar(h, sigma=3.0)
        u = nivel_hpd(h, NIVEL)
        if u is None:
            continue
        ax.contourf(cx, cy, h.T, levels=[u, h.max() + 1],
                    colors=["#B45A38"], alpha=0.13, zorder=2)
        ax.contour(cx, cy, h.T, levels=[u], colors=["#8C2F2F"],
                   linewidths=1.1, alpha=0.8, zorder=3)
    aristas(ax, pos_mod, relaciones, "#A08D79")
    A = np.array(list(pos_mod.values()))
    ax.plot(A[:, 0], A[:, 1], linestyle="none", marker="o", ms=4.6,
            color=ROJO, mec=PAPEL, mew=0.9, zorder=5)
    etiquetar(ax, pos_mod)
    marco(ax, "(b)  Modelo propuesto · una región creíble por lugar", lim, limy)

    # (c) grafo oficial ---------------------------------------------------
    ax = axes[2]
    aristas(ax, pos_of, relaciones, "#A9BFB2")
    A = np.array(list(pos_of.values()))
    ax.plot(A[:, 0], A[:, 1], linestyle="none", marker="x", ms=10, mew=2.2,
            color=VERDE, zorder=5)
    etiquetar(ax, pos_of)
    marco(ax, "(c)  Grafo oficial · la geografía verdadera", lim, limy)

    # Sin titulo ni subtitulo dentro de la figura: al reducirla al ancho de
    # una pagina esos textos quedan ilegibles, y ademas repiten lo que dice
    # el pie de figura del informe. Lo que si tiene que leerse impreso son
    # los titulos de panel, las etiquetas y la leyenda, de ahi sus tamanos.

    claves = [
        Line2D([], [], linestyle="none", marker="+", ms=10, mew=2.0,
               color=TINTA, label="sistema base (Z3)"),
        Patch(facecolor="#B45A38", alpha=0.3, edgecolor="#8C2F2F",
              label=f"región creíble al {NIVEL:.0%} del modelo"),
        Line2D([], [], linestyle="none", marker="o", ms=5, color=ROJO,
               label="media posterior del modelo"),
        Line2D([], [], linestyle="none", marker="x", ms=9, mew=2.2,
               color=VERDE, label="posición oficial"),
    ]
    fig.legend(handles=claves, loc="lower center", ncol=4, frameon=False,
               fontsize=12.0, labelcolor=TENUE, bbox_to_anchor=(0.5, 0.012))

    fig.subplots_adjust(left=0.012, right=0.988, top=0.935, bottom=0.105,
                        wspace=0.045)
    salida = guardar_figura(fig, RAIZ / "salida" / "tres_mapas.png", dpi=190,
                            facecolor=PAPEL)
    plt.close(fig)

    print(f"  Entidades dibujadas : {len(lugares)}")
    print(f"  Con posicion oficial: {len(comunes)}")
    print(f"  Con coordenada base : {len(pos_base)}")
    print(f"\n  Figura en {salida}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
