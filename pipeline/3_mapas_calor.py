"""
Paso 3 · Mapas de calor por entidad.

El sistema base entrega un punto por lugar. Este paso entrega, por cada
lugar, la distribucion completa de donde puede estar segun el texto.
Donde el texto es claro la mancha es chica; donde se contradice, la
mancha se abre o se parte en dos. Esa es la salida que el enfoque
determinista no puede producir.

Marco de coordenadas
--------------------
El modelo trabaja en su propio marco, con un ancla y sin escala absoluta.
Para dibujar junto al grafo oficial se lleva todo al mismo marco con la
misma normalizacion min-max por eje que usa el comparador del sistema
base, calculada sobre los lugares con posicion oficial conocida.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from matplotlib.colors import LinearSegmentedColormap  # noqa: E402

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

from mapa_probabilistico.metricas import (  # noqa: E402
    VENTANA, alinear_a_referencia, region_creible)

TINTA = "#1F1915"
TENUE = "#6B6058"
ROJO = "#8C2F2F"
PAPEL = "#FBF8F4"

#: Paleta calida, del papel al rojo de la rubrica, para que las figuras
#: calcen con el informe y la presentacion.
CALOR = LinearSegmentedColormap.from_list(
    "calor", ["#FBF8F4", "#F0E4D6", "#E2C4A0", "#CF8F5E", "#B45A38", "#8C2F2F"])


def panel(ax, puntos, titulo, verdad=None, base=None, celdas=64):
    bordes = np.linspace(VENTANA[0], VENTANA[1], celdas + 1)
    H, _, _ = np.histogram2d(puntos[:, 0], puntos[:, 1], bins=[bordes, bordes])
    H = H.T / max(H.max(), 1)
    ax.imshow(H ** 0.6, origin="lower",
              extent=[VENTANA[0], VENTANA[1], VENTANA[0], VENTANA[1]],
              cmap=CALOR, interpolation="bilinear", aspect="equal", vmin=0, vmax=1)

    if verdad is not None:
        ax.plot(*verdad, marker="x", ms=9, mew=2.2, color="#17563F", zorder=5)
    if base is not None:
        ax.plot(*base, marker="+", ms=10, mew=2.0, color=TINTA, zorder=5)

    ax.set_title(titulo, fontsize=9.5, color=TINTA, pad=4)
    ax.set_xticks([]); ax.set_yticks([])
    for borde in ax.spines.values():
        borde.set_color("#D8CEC2")


def main():
    datos_sub = json.loads((RAIZ / "datos" / "subgrafo.json").read_text(encoding="utf-8"))
    z = np.load(RAIZ / "salida" / "muestras.npz", allow_pickle=True)
    muestras = z["muestras"].astype(float)
    lugares = list(z["lugares"])

    verdad = datos_sub["verdad_referencia"]
    base = datos_sub["sistema_base"]

    M, comunes, (escala, _) = alinear_a_referencia(muestras, lugares, verdad)
    V = {n: tuple(verdad[n]) for n in comunes}
    B = {n: tuple(base[n]) for n in comunes if n in base}
    areas_fn = lambda i: region_creible(M[:, i, :], nivel=0.80)[0]

    # --- figura 1: todos los lugares -------------------------------------
    fig, ejes = plt.subplots(3, 4, figsize=(13.2, 10.4))
    fig.patch.set_facecolor(PAPEL)
    areas = {}
    for ax, nombre in zip(ejes.ravel(), lugares):
        i = lugares.index(nombre)
        areas[nombre] = areas_fn(i)
        panel(ax, M[:, i, :], f"{nombre}   ·   {areas[nombre]:.3f}",
              verdad=V.get(nombre), base=B.get(nombre))
    fig.suptitle("Dónde puede estar cada lugar, según el texto",
                 fontsize=17, color=TINTA, y=0.995)
    fig.text(0.5, 0.962,
             "Posterior por entidad · 80.000 configuraciones · el número es el "
             "área de la región creíble al 80 % · × posición oficial   + sistema base",
             ha="center", fontsize=10, color=TENUE)
    fig.tight_layout(rect=[0, 0.01, 1, 0.95])
    fig.savefig(RAIZ / "salida" / "mapas_calor.png", dpi=170,
                facecolor=PAPEL, bbox_inches="tight", pad_inches=0.25)
    plt.close(fig)

    # --- figura 2: el contraste que define el aporte ----------------------
    foco = [n for n in ("Valle", "Hobbiton") if n in lugares]
    fig, ejes = plt.subplots(1, len(foco), figsize=(5.6 * len(foco), 5.6))
    fig.patch.set_facecolor(PAPEL)
    ejes = np.atleast_1d(ejes)
    for ax, nombre in zip(ejes, foco):
        i = lugares.index(nombre)
        panel(ax, M[:, i, :], nombre, verdad=V.get(nombre), base=B.get(nombre))
        ax.set_title(f"{nombre}   ·   área creíble 80 % = {areas[nombre]:.3f}",
                     fontsize=12, color=TINTA, pad=8)
    fig.suptitle("Un punto no es lo mismo que una creencia", fontsize=16, color=TINTA)
    fig.text(0.5, 0.905,
             "El sistema base (+) elige una coordenada. El modelo devuelve la "
             "distribución, y su ancho dice cuánto confiar.",
             ha="center", fontsize=10, color=TENUE)
    fig.tight_layout(rect=[0, 0.02, 1, 0.88])
    fig.savefig(RAIZ / "salida" / "contraste.png", dpi=170,
                facecolor=PAPEL, bbox_inches="tight", pad_inches=0.25)
    plt.close(fig)

    print(f"Escala del ajuste de semejanza: {escala:.4f}")
    print("Áreas de la región creíble al 80 %, por lugar:")
    for n, a in sorted(areas.items(), key=lambda kv: kv[1]):
        marca = "  (posición oficial conocida)" if n in verdad else ""
        print(f"  {n:<16} {a:.4f}{marca}")
    print(f"\nMedia: {np.mean(list(areas.values())):.4f}")
    print("\nFiguras en salida/mapas_calor.png y salida/contraste.png")
    return 0


if __name__ == "__main__":
    sys.exit(main())
