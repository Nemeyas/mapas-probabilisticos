"""
Paso 7 · Condición P1: ¿cuánto aporta el tipado geométrico?

P1 es, en el diseño experimental del informe, la propuesta **sin** tipado
geométrico. Este script ejecuta las dos condiciones sobre la misma entrada
y el mismo presupuesto, y las compara.

Qué se compara, y bajo qué vara
-------------------------------
El tipado cambia la geometría con que se evalúan las relaciones, así que
cambia también el predicado de satisfacción. Comparar cada condición bajo
su propio predicado respondería "¿es el sistema coherente consigo mismo?",
que no es la pregunta. Por eso se reportan tres cosas:

  ECSR propio      cada condición bajo su propia geometría.
  CSR puntual      ambas bajo el predicado de puntos, que es el del
                   sistema base. Es la vara común.
  Similitud        contra el grafo oficial. No depende de ningún
                   predicado, y es el árbitro real: dice si el mapa
                   obtenido se parece más al verdadero.

Uso:
    python pipeline\\7_condicion_P1.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

from mapa_probabilistico import datos, metricas, muestreo  # noqa: E402
from mapa_probabilistico.modelo import ModeloMapa  # noqa: E402


def construir(sub, cfg, con_tipado):
    m = cfg["modelo"]
    t = cfg.get("tipado") or {}
    tipos = t.get("tipos", {}) if con_tipado else {}
    radios = {n: t.get("radio_region", 0.06) for n in sub["lugares"]}
    return ModeloMapa(
        sub["lugares"], sub["relaciones"], epsilon=m["epsilon"],
        ancla=sub.get("ancla") or m.get("ancla"), pos_ancla=(0.5, 0.5),
        d0_cerca=m["d0_cerca"], d0_conecta=m["d0_conecta"],
        suavidad=m["suavidad"], dureza_cono=m["dureza_cono"],
        tipos=tipos, radios=radios)


def evaluar(modelo, modelo_puntual, sub, cfg, verdad):
    s = cfg["muestreo"]
    cadenas = []
    for semilla in s["semillas"]:
        mu, _ = muestreo.metropolis_bloques(
            modelo, n_muestras=s["n_muestras"], descarte=s["descarte"],
            semilla=semilla, salto=s.get("salto_inicial", 0.06))
        cadenas.append(mu)
    R = float(np.nanmax(muestreo.gelman_rubin(cadenas)))
    ranuras = np.concatenate(cadenas, axis=0)
    reps = modelo.representantes_lote(ranuras)

    # ECSR bajo la propia geometria de la condicion
    paso = max(1, len(ranuras) // 8000)
    ok = np.array([modelo.fraccion_satisfecha(ranuras[k])
                   for k in range(0, len(ranuras), paso)])
    ecsr = float(ok.mean())

    # MAP, y su CSR bajo la vara comun: el predicado de puntos
    logs = np.array([modelo.log_total_rapido(ranuras[k])
                     for k in range(0, len(ranuras), paso)])
    X_map = ranuras[int(np.argmax(logs)) * paso]
    rep_map = modelo.representantes_lote(X_map[None, :, :])[0]
    csr_puntual = modelo_puntual.fraccion_satisfecha(rep_map)

    # Nitidez y similitud, sobre los representantes
    M, comunes, _ = metricas.alinear_a_referencia(reps, modelo.lugares, verdad)
    nit, _ = metricas.nitidez(M, modelo.lugares)
    if len(comunes) >= 2:
        idx = [modelo.lugares.index(n) for n in comunes]
        objetivo = np.array([verdad[n] for n in comunes], dtype=float)
        med = M.mean(axis=0)[idx]
        e, t = metricas.ajustar_semejanza(med, objetivo)
        sim = float(100 * (1 - np.linalg.norm(e * med + t - objetivo, axis=1).mean()
                           / np.sqrt(2)))
    else:
        sim = float("nan")
    return {"ecsr": ecsr, "csr_map_puntual": csr_puntual, "nitidez": nit,
            "similitud": sim, "gelman_rubin": R,
            "ranuras": modelo.n_ranuras}


def main():
    ruta = RAIZ / "datos" / "subgrafo.json"
    if not ruta.exists():
        print("Falta datos/subgrafo.json. Corre primero el paso 1.")
        return 1
    sub = json.loads(ruta.read_text(encoding="utf-8"))
    cfg = sub.get("config") or datos.cargar_config(RAIZ)
    verdad = sub.get("verdad_referencia") or {}

    tcfg = cfg.get("tipado") or {}
    if not tcfg.get("tipos"):
        print("No hay tipos declarados en config.json, seccion 'tipado'.")
        return 1
    presentes = {n: t for n, t in tcfg["tipos"].items() if n in sub["lugares"]}
    if not presentes:
        print("Ninguna de las entidades tipadas esta en este subgrafo.")
        print("Declara tipos para los lugares que aparecen en datos/subgrafo.json.")
        return 1

    print("=" * 70)
    print("  Condición P1 · aporte del tipado geométrico")
    print("=" * 70)
    print(f"  Subgrafo: {len(sub['lugares'])} entidades, "
          f"{len(sub['relaciones'])} relaciones")
    print(f"  Tipos declarados y presentes: {presentes}")
    print()

    puntual = construir(sub, cfg, con_tipado=False)
    tipado = construir(sub, cfg, con_tipado=True)

    print("  Ejecutando P1, sin tipado...")
    r1 = evaluar(puntual, puntual, sub, cfg, verdad)
    print("  Ejecutando P2, con tipado...")
    r2 = evaluar(tipado, puntual, sub, cfg, verdad)

    print()
    print(f"  {'Métrica':<34}{'P1 sin tipado':>17}{'P2 con tipado':>17}")
    print("  " + "-" * 66)
    filas = [
        ("Posiciones muestreadas", "ranuras", "{:.0f}"),
        ("Gelman-Rubin (peor)", "gelman_rubin", "{:.4f}"),
        ("ECSR, geometría propia", "ecsr", "{:.2%}"),
        ("CSR del MAP, predicado puntual", "csr_map_puntual", "{:.2%}"),
        ("Nitidez (área creíble media)", "nitidez", "{:.4f}"),
        ("Similitud vs grafo oficial", "similitud", "{:.2f} %"),
    ]
    for etiqueta, clave, fmt in filas:
        a, b = r1[clave], r2[clave]
        print(f"  {etiqueta:<34}{fmt.format(a):>17}{fmt.format(b):>17}")
    print("  " + "-" * 66)
    print()

    if np.isfinite(r1["similitud"]) and np.isfinite(r2["similitud"]):
        d = r2["similitud"] - r1["similitud"]
        print(f"  Diferencia en similitud posicional: {d:+.2f} puntos.")
        print("  Esta es la comparación que importa: no depende del predicado,")
        print("  se mide contra el mapa verdadero y responde si el tipado")
        print("  produce una disposición más fiel.")
        if abs(d) < 1.0:
            print()
            print("  La diferencia es menor a un punto. Con este número de")
            print("  entidades y relaciones no se puede afirmar que el tipado")
            print("  aporte: hace falta ampliar el subgrafo o repetir con")
            print("  varias extracciones antes de concluir nada.")
    print()
    print("  Advertencia: los tipos se asignaron a mano, de modo que esto mide")
    print("  el mecanismo del tipado y no la capacidad del modelo de lenguaje")
    print("  para inferirlo. Esa segunda parte corresponde a OE2.")

    datos.guardar_json(RAIZ / "salida" / "condicion_P1.json", {
        "subgrafo": sub["resumen"], "tipos": presentes,
        "P1_sin_tipado": r1, "P2_con_tipado": r2,
        "nota": ("Tipos asignados manualmente. Mide el mecanismo, no la "
                 "extraccion del tipo."),
    })
    print("\n  Resultados en salida/condicion_P1.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
