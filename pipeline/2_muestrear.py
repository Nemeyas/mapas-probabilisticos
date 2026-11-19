"""
Paso 2 · Muestrear la distribucion sobre configuraciones.

Corre cuatro cadenas de Metropolis-Hastings por bloques con semillas
distintas, comprueba que convergieron al mismo sitio y guarda la muestra.

Las semillas y el presupuesto se declaran aqui y quedan escritos en la
salida. Eso es deliberado: la verificacion del trabajo base mostro que no
declarar el presupuesto del solver hace que los resultados no se puedan
reproducir entre equipos.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

from mapa_probabilistico import datos, muestreo  # noqa: E402
from mapa_probabilistico.modelo import ModeloMapa  # noqa: E402

def main():
    ruta = RAIZ / "datos" / "subgrafo.json"
    if not ruta.exists():
        print("Falta datos/subgrafo.json. Corre primero el paso 1.")
        return 1
    with open(ruta, encoding="utf-8") as f:
        sub = json.load(f)

    # Todo el presupuesto y los parametros vienen de config.json, grabados
    # dentro de subgrafo.json por el paso 1. Asi la corrida queda atada a la
    # configuracion con la que se hizo.
    cfg = sub.get("config") or datos.cargar_config(RAIZ)
    mcfg, scfg = cfg["modelo"], cfg["muestreo"]
    SEMILLAS = scfg["semillas"]
    N_MUESTRAS = scfg["n_muestras"]
    DESCARTE = scfg["descarte"]
    SALTO = scfg.get("salto_inicial", 0.06)
    ANCLA = sub.get("ancla") or mcfg.get("ancla")
    EPS = mcfg["epsilon"]

    # Tipado geometrico. Si esta desactivado toda entidad es un punto, que
    # es la condicion del sistema base.
    tcfg = cfg.get("tipado") or {}
    tipos = tcfg.get("tipos", {}) if tcfg.get("activo") else {}
    radios = {n: tcfg.get("radio_region", 0.06) for n in sub["lugares"]}

    modelo = ModeloMapa(
        sub["lugares"], sub["relaciones"], epsilon=EPS, ancla=ANCLA,
        pos_ancla=(0.5, 0.5), d0_cerca=mcfg["d0_cerca"],
        d0_conecta=mcfg["d0_conecta"], suavidad=mcfg["suavidad"],
        dureza_cono=mcfg["dureza_cono"], tipos=tipos, radios=radios)
    print(f"Modelo: {modelo.n_lugares} lugares, {modelo.n_relaciones} relaciones, "
          f"epsilon = {EPS}")
    print(f"Geometria: d0_cerca = {mcfg['d0_cerca']}, "
          f"d0_conecta = {mcfg['d0_conecta']}, suavidad = {mcfg['suavidad']}, "
          f"dureza del cono = {mcfg['dureza_cono']}")
    if modelo.tipado_activo:
        from collections import Counter
        cuenta = Counter(modelo.tipos.values())
        print(f"Tipado: ACTIVO  {dict(cuenta)}  "
              f"({modelo.n_ranuras} posiciones para {modelo.n_lugares} entidades)")
    else:
        print("Tipado: desactivado, toda entidad es un punto")
    print(f"Ancla : {ANCLA} fijado en (0,5, 0,5) para quitar la invariancia "
          f"a traslaciones")
    print(f"Presupuesto declarado: {len(SEMILLAS)} cadenas x {N_MUESTRAS} muestras, "
          f"descarte {DESCARTE}, semillas {SEMILLAS}")
    print()

    cadenas, diagnosticos = [], []
    t0 = time.time()
    for s in SEMILLAS:
        m, d = muestreo.metropolis_bloques(
            modelo, n_muestras=N_MUESTRAS, descarte=DESCARTE, semilla=s,
            salto=SALTO)
        cadenas.append(m)
        diagnosticos.append(d)
        print(f"  cadena semilla {s}: aceptacion {d['tasa_aceptacion']:.0%}, "
              f"log densidad media {d['log_densidad_media']:.2f}")
    segundos = time.time() - t0

    R = muestreo.gelman_rubin(cadenas)
    peor = float(np.nanmax(R))
    print()
    print(f"Convergencia (Gelman-Rubin), peor coordenada: R = {peor:.4f}")
    print("  R por debajo de 1,05 indica que las cadenas mezclaron bien.")
    if peor >= 1.10:
        print("  AVISO: R alto. La cadena no mezclo, sube el descarte.")

    todas_ranuras = np.concatenate(cadenas, axis=0)
    # Las figuras y las metricas razonan con una ubicacion por entidad, no
    # por ranura. Para una curva esa ubicacion es el punto medio de sus dos
    # extremos; el detalle completo queda igualmente guardado.
    todas = modelo.representantes_lote(todas_ranuras)
    neff = [muestreo.tamano_efectivo(todas_ranuras[:, i, 0])
            for i in range(modelo.n_ranuras)]
    print(f"Tamano efectivo de muestra, minimo: {min(neff):.0f} de {len(todas)}")

    np.savez_compressed(
        RAIZ / "salida" / "muestras.npz",
        muestras=todas.astype(np.float32),
        ranuras=todas_ranuras.astype(np.float32),
        lugares=np.array(modelo.lugares, dtype=object),
        tipos=np.array([modelo.tipos[n] for n in modelo.lugares], dtype=object),
        por_cadena=np.array([len(c) for c in cadenas]))

    datos.guardar_json(RAIZ / "salida" / "diagnostico_muestreo.json", {
        "config": cfg,
        "epsilon": EPS,
        "ancla": ANCLA,
        "semillas": SEMILLAS,
        "n_muestras_por_cadena": N_MUESTRAS,
        "descarte": DESCARTE,
        "segundos": round(segundos, 1),
        "gelman_rubin_peor": peor,
        "tamano_efectivo_min": float(min(neff)),
        "tipado_activo": modelo.tipado_activo,
        "tipos": modelo.tipos if modelo.tipado_activo else None,
        "cadenas": diagnosticos,
    })
    print(f"\nMuestras guardadas en salida/muestras.npz  ({len(todas)} configuraciones)")
    print(f"Tiempo total: {segundos:.1f} s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
