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


def modelo_de_config(sub, cfg, **cambios):
    """Construye el modelo SIEMPRE desde config.json.

    Existe para que no se repita el error que tuvo este archivo: varios
    sitios creaban ModeloMapa pasando solo epsilon y ancla, de modo que
    d0_cerca, d0_conecta, suavidad y dureza_cono se quedaban en los valores
    por omision del modulo. El barrido de epsilon devolvia entonces cifras
    identicas aunque se cambiara d0 en la configuracion, porque nunca lo
    leia. Cualquier parametro se puede sobreescribir con `cambios`.
    """
    m = dict(cfg["modelo"])
    m.pop("_ayuda", None)
    m["epsilon"] = max(m.get("epsilon", 0.05), 1e-12)
    m["ancla"] = sub.get("ancla") or m.get("ancla")
    m.update(cambios)
    if "epsilon" in cambios:
        m["epsilon"] = max(cambios["epsilon"], 1e-12)
    return ModeloMapa(sub["lugares"], sub["relaciones"], pos_ancla=(0.5, 0.5), **m)


def main():
    sub = json.loads((RAIZ / "datos" / "subgrafo.json").read_text(encoding="utf-8"))
    z = np.load(RAIZ / "salida" / "muestras.npz", allow_pickle=True)
    muestras = z["muestras"].astype(float)
    lugares = list(z["lugares"])
    verdad = sub["verdad_referencia"]
    base = sub["sistema_base"]
    cfg = sub.get("config") or datos.cargar_config(RAIZ)

    # Desde config.json, no desde las constantes del modulo: las muestras del
    # paso 2 se generaron con los parametros de la configuracion, y evaluarlas
    # con otros umbrales mide una densidad distinta de la que se muestreo.
    modelo = modelo_de_config(sub, cfg)

    M, comunes, (escala, _) = metricas.alinear_a_referencia(muestras, lugares, verdad)

    print("=" * 66)
    print(f"  Comparacion cabeza a cabeza")
    print(f"  Extraccion: {Path(sub.get('fuente', '?')).name}")
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

    hay_ref = len(comunes) >= 2
    if not hay_ref:
        print("  Sin grafo de referencia. Se omiten la similitud posicional,")
        print("  la calibracion y la comparacion en el marco oficial, porque")
        print("  las tres requieren posiciones verdaderas conocidas. Las que")
        print("  no las requieren si se reportan.")
        print()
        barrido = []
        print("  Barrido del termino de robustez:")
        print(f"    {'epsilon':>8} {'ECSR':>8} {'nitidez':>9}")
        for eps in cfg.get("barrido_epsilon", BARRIDO_EPSILON):
            m_eps = modelo_de_config(sub, cfg, epsilon=eps)
            mu, _ = muestreo.metropolis_bloques(m_eps, n_muestras=6000,
                                                descarte=4000, semilla=11)
            e_med, _, _ = metricas.ecsr(m_eps, mu)
            n_eps, _ = metricas.nitidez(metricas.centrar(mu), lugares, celdas=48)
            barrido.append({"epsilon": eps, "ecsr": e_med, "nitidez": n_eps})
            print(f"    {eps:8.2f} {100*e_med:7.2f}% {n_eps:9.4f}")

        datos.guardar_json(RAIZ / "salida" / "resultados.json", {
            "subgrafo": sub["resumen"],
            "sin_referencia": True,
            "ecsr_modelo": media, "ecsr_desviacion": desv,
            "csr_map": csr_map, "csr_media_posterior": csr_media,
            "nitidez_media": nit, "areas_creibles": areas,
            "grado_por_lugar": grado, "correlacion_grado_area": r,
            "probabilidad_por_relacion": {" ".join(k): v
                                          for k, v in por_relacion.items()},
            "barrido_epsilon": barrido,
        })
        print("\n  Resultados en salida/resultados.json")
        return 0

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

    # La escala NO se ajusta por candidato: se iguala el radio de giro al del
    # grafo oficial, con la misma regla para los tres. Ver la documentacion de
    # metricas.normalizar_a_escala_comun: ajustarla por minimos cuadrados le
    # daba escala 0,125 al sistema base, y un mapa comprimido ocho veces
    # satisface las relaciones de distancia por construccion.
    objetivo_ev = np.array([verdad[n] for n in evaluables], dtype=float)
    m_marco = ModeloMapa(evaluables, rel_eval,
                         d0_cerca=cfg["modelo"]["d0_cerca"],
                         d0_conecta=cfg["modelo"]["d0_conecta"],
                         dureza_cono=cfg["modelo"]["dureza_cono"])

    def csr_en_marco(pos_por_nombre, devolver_escala=False):
        P = np.array([pos_por_nombre[n] for n in evaluables], dtype=float)
        Q, esc = metricas.normalizar_a_escala_comun(P, objetivo_ev)
        v = m_marco.fraccion_satisfecha(Q)
        return (v, esc) if devolver_escala else v

    map_por_nombre = {n: X_map[lugares.index(n)] for n in evaluables}
    comparable = sub.get("sistema_base_comparable", False)
    print(f"  Sobre los {len(evaluables)} lugares con posicion del sistema base")
    print(f"  y sus {len(rel_eval)} relaciones, en el marco oficial:")
    print(f"  Origen de esas coordenadas: {sub.get('sistema_base_nota', '?')}")
    if not comparable:
        print()
        print("  *** AVISO: COMPARACION NO PAREJA ***")
        print("  Las coordenadas del sistema base no salieron de esta misma")
        print("  extraccion, asi que su solver nunca vio estas relaciones.")
        print("  La cifra de abajo FAVORECE al modelo y no se debe reportar")
        print("  como comparacion. Corre COMPARAR_BASE.bat para arreglarlo.")
    print()
    print(f"    sistema base (Z3, 120 s) : {100*csr_en_marco(base):.2f} %")
    print(f"    modelo, configuracion MAP: {100*csr_en_marco(map_por_nombre):.2f} %")
    print(f"    el propio grafo oficial  : {100*csr_en_marco(verdad):.2f} %")
    print()
    print("  La ultima fila es el techo real: es lo que saca el mapa verdadero")
    print("  de la Tierra Media contra estas mismas restricciones. Lo que le")
    print("  falte para 100 % no lo puede arreglar ningun solver, porque es")
    print("  error de extraccion.")
    print()
    csr_base, esc_base = csr_en_marco(base, True)
    csr_oficial, _ = csr_en_marco(verdad, True)
    csr_map_marco, esc_mod = csr_en_marco(map_por_nombre, True)
    print(f"  Escala aplicada por la regla comun: base x{esc_base:.3f}, "
          f"modelo x{esc_mod:.3f}, oficial x1.000")
    print()

    # --- sensibilidad del CSR al umbral, que es el resultado importante ---
    #
    # El CSR compara distancias contra un umbral que NADIE declara: ni el
    # trabajo base ni la literatura que lo precede. Este barrido mide que
    # pasa al moverlo dentro de un rango defendible, y la respuesta es que
    # el ganador de la comparacion cambia. Se publica siempre, porque sin el
    # cualquier cifra de CSR de esta tabla se puede elegir a gusto.
    barrido_d0 = cfg.get("barrido_d0") or []
    sens = []
    if barrido_d0:
        print("  Sensibilidad del CSR al umbral de distancia:")
        print(f"    {'d0_cerca':>9}{'d0_conecta':>12}{'base':>9}{'modelo':>9}"
              f"{'oficial':>9}   ganador")
        for d0c, d0k in barrido_d0:
            mm = ModeloMapa(evaluables, rel_eval, d0_cerca=d0c, d0_conecta=d0k,
                            dureza_cono=cfg["modelo"]["dureza_cono"])

            def _csr(pos):
                Q, _ = metricas.normalizar_a_escala_comun(
                    np.array([pos[n] for n in evaluables], dtype=float),
                    objetivo_ev)
                return mm.fraccion_satisfecha(Q)

            cb, cm, co = _csr(base), _csr(map_por_nombre), _csr(verdad)
            gan = ("empate" if abs(cb - cm) < 1e-9
                   else ("modelo" if cm > cb else "sistema base"))
            print(f"    {d0c:>9.2f}{d0k:>12.2f}{100*cb:>8.1f}%{100*cm:>8.1f}%"
                  f"{100*co:>8.1f}%   {gan}")
            sens.append({"d0_cerca": d0c, "d0_conecta": d0k, "csr_base": cb,
                         "csr_modelo": cm, "csr_oficial": co, "ganador": gan})
        ganadores = {x["ganador"] for x in sens}
        print()
        if len(ganadores) > 1:
            print("    El ganador CAMBIA con el umbral. Con solo "
                  f"{len(rel_eval)} relaciones cada una vale "
                  f"{100/len(rel_eval):.1f} puntos, asi que esta comparacion")
            print("    no distingue los dos sistemas. No se debe reportar como")
            print("    ventaja de ninguno de los dos. La conclusion que si")
            print("    aguanta es la de similitud posicional, mas abajo, que no")
            print("    depende de ningun umbral.")
        print()

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
    #
    # Los dos candidatos pasan por EL MISMO tratamiento: a cada uno se le
    # ajusta su propia semejanza contra las posiciones oficiales, sobre los
    # mismos lugares. Sin eso la comparacion es tramposa, porque el modelo
    # recibiria un ajuste de escala y traslacion que el sistema base no.
    objetivo = np.array([verdad[n] for n in comunes], dtype=float)
    idx = [lugares.index(n) for n in comunes]

    media_post = M.mean(axis=0)
    e_m, t_m = metricas.ajustar_semejanza(media_post[idx], objetivo)
    A_mod = e_m * media_post[idx] + t_m
    sim_modelo = float(100 * (1 - np.linalg.norm(A_mod - objetivo, axis=1).mean()
                              / np.sqrt(2)))

    disponibles = [n for n in comunes if n in base]
    if len(disponibles) >= 2:
        obj_b = np.array([verdad[n] for n in disponibles], dtype=float)
        B = np.array([base[n] for n in disponibles], dtype=float)
        e_b, t_b = metricas.ajustar_semejanza(B, obj_b)
        A_base = e_b * B + t_b
        sim_base = float(100 * (1 - np.linalg.norm(A_base - obj_b, axis=1).mean()
                                / np.sqrt(2)))
    else:
        sim_base = float("nan")

    print(f"  Similitud posicional contra el grafo oficial, con el mismo")
    print(f"  ajuste de semejanza aplicado a los dos candidatos:")
    print(f"    media posterior del modelo : {sim_modelo:.2f} %")
    print(f"    sistema base               : {sim_base:.2f} %  "
          f"({len(disponibles)} lugares)")
    print()

    # --- barrido de epsilon ----------------------------------------------
    print("  Barrido del termino de robustez:")
    print(f"    {'epsilon':>8} {'ECSR':>8} {'nitidez':>9} {'ECE':>7}")
    barrido = []
    for eps in cfg.get("barrido_epsilon", BARRIDO_EPSILON):
        m_eps = modelo_de_config(sub, cfg, epsilon=eps)
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
    datos.guardar_figura(fig, RAIZ / "salida" / "metricas.png", dpi=170,
                         facecolor=PAPEL, bbox_inches="tight", pad_inches=0.25)
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
        "sensibilidad_csr_al_umbral": sens,
        "escala_regla_comun": {"base": esc_base, "modelo": esc_mod},
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
