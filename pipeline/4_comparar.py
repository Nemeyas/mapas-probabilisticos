"""
Paso 4 · Metricas y comparacion cabeza a cabeza.

Compara el modelo probabilistico contra el sistema base sobre exactamente
la misma entrada, y mide tres cosas que una coordenada unica no puede dar:
cuanto satisface en promedio (ECSR), cuanto espacio ocupa la creencia
(nitidez) y si los intervalos son honestos (calibracion).

Incluye ademas un barrido del termino de robustez epsilon. Ese barrido es
la respuesta a la pregunta "como elegiste epsilon": no se elige a dedo, se
mide el compromiso entre robustez y nitidez y se declara el criterio.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

from mapa_probabilistico import datos, metricas, muestreo  # noqa: E402
from mapa_probabilistico.modelo import EPSILON, ModeloMapa  # noqa: E402

TINTA, TENUE, ROJO, VERDE, PAPEL = "#1F1915", "#6B6058", "#8C2F2F", "#17563F", "#FBF8F4"

#: Valores de epsilon del barrido. 0 es la formulacion sin robustez.
BARRIDO_EPSILON = [0.0, 0.01, 0.02, 0.05, 0.10, 0.20]


def main():
    sub = json.loads((RAIZ / "datos" / "subgrafo.json").read_text(encoding="utf-8"))
    z = np.load(RAIZ / "salida" / "muestras.npz", allow_pickle=True)
    muestras = z["muestras"].astype(float)
    lugares = list(z["lugares"])
    verdad = sub["verdad_referencia"]
    base = sub["sistema_base"]

    modelo = ModeloMapa(sub["lugares"], sub["relaciones"],
                        epsilon=EPSILON, ancla="Comarca")

    M, comunes, (escala, _) = metricas.alinear_a_referencia(muestras, lugares, verdad)

    print("=" * 66)
    print("  Comparacion cabeza a cabeza sobre la extraccion de run_01")
    print("=" * 66)
    print(f"  {modelo.n_lugares} lugares, {modelo.n_relaciones} relaciones, "
          f"{len(comunes)} con posicion oficial")
    print()

    # --- ECSR -------------------------------------------------------------
    media, desv, por_relacion = metricas.ecsr(modelo, muestras)
    # Resumen puntual del modelo, para comparar manzana con manzana contra
    # el punto unico del sistema base: la configuracion de maxima densidad
    # (MAP) y la media posterior, ambas evaluadas con el predicado duro.
    log_pi = np.array([modelo.log_total_rapido(muestras[k])
                       for k in range(0, len(muestras), 10)])
    X_map = muestras[int(np.argmax(log_pi)) * 10]
    csr_map = modelo.fraccion_satisfecha(X_map)
    csr_media = modelo.fraccion_satisfecha(muestras.mean(axis=0))

    print(f"  ECSR del modelo        : {100*media:.2f} %  (desviacion {100*desv:.2f})")
    print(f"  CSR de la config. MAP  : {100*csr_map:.2f} %")
    print(f"  CSR de la media post.  : {100*csr_media:.2f} %")
    print()
    print("  El ECSR promedia sobre toda la posterior, incluida su cola, asi")
    print("  que por construccion queda por debajo del CSR de un punto unico.")
    print("  La comparacion pareja contra el sistema base es la del MAP.")
    print()

    # --- comparacion en el marco del grafo oficial ------------------------
    #
    # Para que la comparacion sea pareja los tres candidatos pasan por el
    # mismo tratamiento: se les ajusta la misma semejanza contra las
    # posiciones oficiales y se evaluan con el mismo predicado duro y el
    # mismo umbral, sobre el mismo subconjunto de relaciones. Solo se
    # pueden usar los lugares de los que el sistema base publica posicion.
    evaluables = [n for n in lugares if n in base and n in verdad]
    rel_eval = [r for r in sub["relaciones"]
                if r["origen"] in evaluables and r["destino"] in evaluables]

    def csr_en_marco(pos_por_nombre):
        P = np.array([pos_por_nombre[n] for n in evaluables], dtype=float)
        objetivo = np.array([verdad[n] for n in evaluables], dtype=float)
        esc, t = metricas.ajustar_semejanza(P, objetivo)
        Q = {n: esc * np.asarray(pos_por_nombre[n]) + t for n in evaluables}
        m_tmp = ModeloMapa(evaluables, rel_eval)
        X = np.array([Q[n] for n in evaluables], dtype=float)
        return m_tmp.fraccion_satisfecha(X)

    map_por_nombre = {n: X_map[lugares.index(n)] for n in evaluables}
    print(f"  Sobre los {len(evaluables)} lugares con posicion publicada por el")
    print(f"  sistema base y sus {len(rel_eval)} relaciones, en el marco oficial:")
    print(f"    sistema base (Z3, 120 s) : {100*csr_en_marco(base):.2f} %")
    print(f"    modelo, configuracion MAP: {100*csr_en_marco(map_por_nombre):.2f} %")
    print(f"    el propio grafo oficial  : {100*csr_en_marco(verdad):.2f} %")
    print()
    print("  La ultima fila es el techo real: es lo que saca el mapa verdadero")
    print("  de la Tierra Media contra estas mismas restricciones. Lo que le")
    print("  falte para 100 % no lo puede arreglar ningun solver, porque es")
    print("  error de extraccion.")
    print()
    csr_base = csr_en_marco(base)
    csr_oficial = csr_en_marco(verdad)
    csr_map_marco = csr_en_marco(map_por_nombre)
    print("  Probabilidad posterior de satisfaccion, por relacion:")
    for (o, t, d), p in sorted(por_relacion.items(), key=lambda kv: kv[1]):
        print(f"    {p:5.1%}   {o} {t} {d}")
    print()

    # --- nitidez ----------------------------------------------------------
    nit, areas = metricas.nitidez(M, lugares)
    grado = {n: len(modelo.relaciones_de[modelo.indice[n]]) for n in lugares}
    g = np.array([grado[n] for n in lugares], dtype=float)
    a = np.array([areas[n] for n in lugares], dtype=float)
    r = float(np.corrcoef(g, a)[0, 1])
    print(f"  Nitidez (area creible 80 % media): {nit:.4f}")
    print(f"  Correlacion entre numero de relaciones y area: r = {r:+.3f}")
    print("    Negativa es lo esperado: cuanto mas dice el texto de un lugar,")
    print("    mas angosta es la creencia sobre donde esta.")
    print()

    # --- calibracion ------------------------------------------------------
    niveles, cobertura, usados = metricas.curva_calibracion(M, lugares, verdad)
    ece = metricas.error_calibracion(niveles, cobertura)
    print(f"  Calibracion sobre {len(usados)} lugares con posicion oficial:")
    for q, c in zip(niveles, cobertura):
        print(f"    nivel {q:.0%}  ->  cobertura {c:.0%}")
    print(f"  Error de calibracion esperado: {ece:.3f}")
    print()

    # --- similitud posicional --------------------------------------------
    media_post = M.mean(axis=0)
    sim_modelo = metricas.similitud_posicional(media_post, comunes, verdad, lugares)
    idx = [lugares.index(n) for n in comunes]
    B = np.array([base[n] for n in comunes], dtype=float)
    d_base = np.linalg.norm(B - np.array([verdad[n] for n in comunes]), axis=1)
    sim_base = float(100 * (1 - d_base.mean() / np.sqrt(2)))
    print(f"  Similitud posicional, media posterior : {sim_modelo:.2f} %")
    print(f"  Similitud posicional, sistema base    : {sim_base:.2f} %")
    print()

    # --- barrido de epsilon ----------------------------------------------
    print("  Barrido del termino de robustez:")
    print(f"    {'epsilon':>8} {'ECSR':>8} {'nitidez':>9} {'ECE':>7}")
    barrido = []
    for eps in BARRIDO_EPSILON:
        m_eps = ModeloMapa(sub["lugares"], sub["relaciones"],
                           epsilon=max(eps, 1e-12), ancla="Comarca")
        mu, _ = muestreo.metropolis_bloques(m_eps, n_muestras=6000, descarte=4000,
                                            semilla=11)
        e_med, _, _ = metricas.ecsr(m_eps, mu)
        Me, com_e, _ = metricas.alinear_a_referencia(mu, lugares, verdad)
        n_eps, _ = metricas.nitidez(Me, lugares, celdas=48)
        niv_e, cob_e, _ = metricas.curva_calibracion(Me, lugares, verdad, celdas=48)
        ece_e = metricas.error_calibracion(niv_e, cob_e)
        barrido.append({"epsilon": eps, "ecsr": e_med, "nitidez": n_eps, "ece": ece_e})
        print(f"    {eps:8.2f} {100*e_med:7.2f}% {n_eps:9.4f} {ece_e:7.3f}")
    print()
    print("    epsilon = 0 es la formulacion sin robustez. Subirlo hace el")
    print("    modelo mas tolerante a contradicciones y menos nitido: es un")
    print("    compromiso, no un parametro libre, y se declara medido.")

    # --- figura -----------------------------------------------------------
    fig, ejes = plt.subplots(1, 3, figsize=(15.5, 4.9))
    fig.patch.set_facecolor(PAPEL)

    ax = ejes[0]
    orden = sorted(lugares, key=lambda n: areas[n])
    ax.barh(range(len(orden)), [areas[n] for n in orden],
            color=[ROJO if n in verdad else "#C9A227" for n in orden], height=0.62)
    ax.set_yticks(range(len(orden)))
    ax.set_yticklabels(orden, fontsize=9, color=TINTA)
    ax.set_xlabel("área de la región creíble al 80 %", fontsize=9.5, color=TENUE)
    ax.set_title("La incertidumbre sigue a lo que el texto dice",
                 fontsize=12, color=TINTA, pad=10)
    for i, n in enumerate(orden):
        ax.text(areas[n] + 0.008, i, f"{grado[n]} rel.", va="center",
                fontsize=8, color=TENUE)

    ax = ejes[1]
    ax.plot([0, 1], [0, 1], ls="--", lw=1.2, color="#BFB4A8")
    ax.plot(niveles, cobertura, marker="o", lw=2.0, color=ROJO)
    ax.set_xlim(0.45, 1.0); ax.set_ylim(0, 1.05)
    ax.set_xlabel("nivel nominal", fontsize=9.5, color=TENUE)
    ax.set_ylabel("cobertura empírica", fontsize=9.5, color=TENUE)
    ax.set_title(f"Calibración   ·   ECE = {ece:.3f}", fontsize=12, color=TINTA, pad=10)
    ax.text(0.47, 0.06, "bajo la diagonal = confiado de más",
            fontsize=8.5, color=TENUE)

    ax = ejes[2]
    eps = [b["epsilon"] for b in barrido]
    ax.plot(eps, [100 * b["ecsr"] for b in barrido], marker="o", lw=2.0,
            color=ROJO, label="ECSR (%)")
    ax2 = ax.twinx()
    ax2.plot(eps, [b["nitidez"] for b in barrido], marker="s", lw=2.0,
             color=VERDE, label="área creíble media")
    ax.set_xlabel("término de robustez ε", fontsize=9.5, color=TENUE)
    ax.set_ylabel("ECSR (%)", fontsize=9.5, color=ROJO)
    ax2.set_ylabel("área creíble media", fontsize=9.5, color=VERDE)
    ax.set_title("ε es un compromiso, no un parámetro libre",
                 fontsize=12, color=TINTA, pad=10)
    ax.axvline(EPSILON, color=TINTA, lw=1.0, ls=":")

    for a_ in list(ejes) + [ax2]:
        for s in a_.spines.values():
            s.set_color("#D8CEC2")
        a_.tick_params(colors=TENUE, labelsize=8.5)
        a_.set_facecolor(PAPEL)

    fig.tight_layout()
    fig.savefig(RAIZ / "salida" / "metricas.png", dpi=170, facecolor=PAPEL,
                bbox_inches="tight", pad_inches=0.25)
    plt.close(fig)

    datos.guardar_json(RAIZ / "salida" / "resultados.json", {
        "subgrafo": sub["resumen"],
        "ecsr_modelo": media,
        "csr_map": csr_map,
        "csr_media_posterior": csr_media,
        "ecsr_desviacion": desv,
        "comparacion_marco_oficial": {
            "lugares": evaluables,
            "n_relaciones": len(rel_eval),
            "csr_sistema_base": csr_base,
            "csr_modelo_map": csr_map_marco,
            "csr_grafo_oficial": csr_oficial,
        },
        "csr_sistema_base_grafo_completo": 0.70,
        "nitidez_media": nit,
        "areas_creibles": areas,
        "grado_por_lugar": grado,
        "correlacion_grado_area": r,
        "calibracion": {"niveles": niveles, "cobertura": cobertura, "ece": ece},
        "similitud_posicional_modelo": sim_modelo,
        "similitud_posicional_base": sim_base,
        "probabilidad_por_relacion": {" ".join(k): v for k, v in por_relacion.items()},
        "barrido_epsilon": barrido,
        "escala_alineamiento": escala,
    })
    print("\nResultados en salida/resultados.json y salida/metricas.png")
    return 0


if __name__ == "__main__":
    sys.exit(main())
