"""
Paso 1 · Preparar la entrada.

Lee `config.json`, carga el JSON de entrada con los lugares y relaciones,
carga el grafo oficial de referencia, selecciona el subgrafo de trabajo y
deja todo en `datos/subgrafo.json`.

La entrada del sistema es siempre un JSON con dos listas, `lugares` y
`relaciones`. De donde venga ese JSON le da igual al modelo. Esa
independencia es deliberada: es lo que permite evaluar la etapa de
resolucion sin que la extraccion intervenga, y es la condicion que hace
valida la comparacion cabeza a cabeza con el trabajo base.

Uso:
    python pipeline\\1_preparar_subgrafo.py                  (usa config.json)
    python pipeline\\1_preparar_subgrafo.py otra.json         (otra entrada)
    python pipeline\\1_preparar_subgrafo.py otra.json --auto  (y elige solo)

La opcion --auto fuerza el modo automatico de seleccion del subgrafo. Es la
que hay que usar con una extraccion nueva, porque los nombres de lugar que
devuelve cada extraccion no son los mismos y una lista fija escrita para
otra corrida no va a coincidir.
"""

from __future__ import annotations

import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

from mapa_probabilistico import datos  # noqa: E402


def main(ruta_entrada=None, forzar_auto=False):
    cfg = datos.cargar_config(RAIZ)
    if forzar_auto:
        cfg["subgrafo"]["modo"] = "auto"

    ruta = Path(ruta_entrada) if ruta_entrada else (RAIZ / cfg["entrada"]["ruta"])
    ruta = ruta if ruta.is_absolute() else (RAIZ / ruta)
    ref = cfg["referencia"]
    ruta_ref = (RAIZ / ref["ruta"]) if ref.get("ruta") else None

    if not ruta.exists():
        print(f"No encuentro el JSON de entrada en:\n  {ruta.resolve()}\n")
        print("Revisa la ruta en config.json. Si el repositorio del trabajo")
        print("base no esta en la carpeta '5 Sistema base', ajustala ahi.")
        return 1

    # El grafo de referencia es OPCIONAL. Sin el, el sistema corre igual y
    # entrega las metricas que no dependen de una verdad conocida: ECSR,
    # nitidez y la correlacion entre evidencia textual e incertidumbre. Lo
    # que no se puede medir sin referencia es similitud posicional,
    # cobertura y calibracion. Esto permite evaluar textos para los que no
    # existe un mapa oficial, que es el caso de la mayoria de los textos
    # historicos.
    sin_referencia = ruta_ref is None or not ruta_ref.exists()
    if sin_referencia and ruta_ref is not None:
        print(f"AVISO: no encuentro el grafo de referencia en {ruta_ref}")

    lugares, relaciones = datos.cargar_extraccion(ruta)
    print(f"Entrada    : {ruta.name}")
    print(f"             {len(lugares)} lugares, {len(relaciones)} relaciones")

    if sin_referencia:
        verdad = {}
        print("Referencia : ninguna. Se omiten las metricas que requieren")
        print("             una verdad conocida: similitud posicional,")
        print("             cobertura y calibracion.")
    else:
        verdad = datos.cargar_referencia(ruta_ref, ref.get("y_hacia_el_sur", True),
                                         ref.get("alias"))
        print(f"Referencia : {ruta_ref.name}  ({len(verdad)} lugares con posicion)")

    sub = cfg["subgrafo"]
    if sub["modo"] == "auto":
        nombres, inducidas = datos.seleccionar_subgrafo_auto(
            lugares, relaciones, verdad, sub.get("n_lugares", 12))
        print(f"Subgrafo   : modo automatico, {len(nombres)} lugares")
    else:
        nombres, inducidas = datos.seleccionar_subgrafo(
            lugares, relaciones, sub["lugares"])
        print(f"Subgrafo   : lista fija de config.json")

    resumen = datos.resumen_subgrafo(nombres, inducidas, verdad)
    print(f"             {resumen['n_lugares']} lugares, "
          f"{resumen['n_relaciones']} relaciones")
    print(f"             por tipo: {resumen['por_tipo']}")
    print(f"             con posicion oficial: "
          f"{len(resumen['con_verdad_conocida'])} de {resumen['n_lugares']}"
          f"  -> {', '.join(resumen['con_verdad_conocida']) or 'ninguno'}")
    print()
    print("Relaciones del subgrafo:")
    for r in inducidas:
        print(f"  {r['origen']:<17} {r['tipo']:<10} {r['destino']}")

    if resumen["n_relaciones"] == 0:
        print("\nEl subgrafo quedo sin relaciones. Revisa la lista de lugares")
        print("en config.json, o cambia el modo a 'auto'.")
        return 1
    if verdad and len(resumen["con_verdad_conocida"]) < 3:
        print("\nAVISO: menos de tres lugares con posicion oficial. La")
        print("calibracion se puede calcular pero no sera informativa.")

    # El ancla siempre se resuelve. Sin ella la densidad es invariante a
    # traslaciones y las cadenas derivan, lo que arruina el diagnostico de
    # convergencia. Si config.json no la fija, se toma la de mayor grado.
    ancla = cfg["modelo"].get("ancla")
    if not ancla or ancla not in nombres:
        from collections import Counter
        g = Counter()
        for r in inducidas:
            g[r["origen"]] += 1
            g[r["destino"]] += 1
        ancla = g.most_common(1)[0][0]
        print(f"\nAncla: {ancla} (lugar de mayor grado del subgrafo)")

    # --- coordenadas del sistema base, para la comparacion --------------
    #
    # Solo son comparables si salieron de una corrida del solver sobre LA
    # MISMA extraccion. Se comprueba comparando el CONJUNTO DE RELACIONES
    # que el solver evaluo (campo `rel_eval` de solution.json) contra el de
    # la extraccion en uso.
    #
    # Antes esto se comprobaba por fecha de archivo, y esa prueba es
    # insuficiente: copiar o restaurar un fichero le cambia la fecha sin
    # cambiar su contenido, de modo que una solucion vieja podia quedar
    # marcada como comparable. La fecha se conserva solo como respaldo,
    # para soluciones antiguas que no traen `rel_eval`.
    base_cfg = cfg.get("sistema_base") or {}
    base_pos, base_meta, base_comparable, base_nota = {}, {}, False, ""
    ruta_base = base_cfg.get("ruta_solucion")
    if ruta_base:
        rb = RAIZ / ruta_base
        if rb.exists():
            base_pos, base_meta = datos.cargar_solucion_base(
                rb, base_cfg.get("y_hacia_el_sur", True))
            huella_base = {tuple(t) for t in (base_meta.get("relaciones_evaluadas") or [])}
            huella_ext = {(r["origen"], r["tipo"], r["destino"]) for r in relaciones}
            if huella_base:
                if huella_base == huella_ext:
                    base_comparable = True
                    base_nota = (f"solucion del solver base sobre esta misma "
                                 f"extraccion ({rb.name}, {len(huella_base)} relaciones)")
                else:
                    comunes = len(huella_base & huella_ext)
                    base_nota = (
                        f"la solucion del sistema base ({rb.name}) se calculo sobre "
                        f"OTRA extraccion: comparte {comunes} de "
                        f"{len(huella_base | huella_ext)} relaciones con la actual; "
                        f"no es comparable")
            elif rb.stat().st_mtime >= ruta.stat().st_mtime:
                base_comparable = True
                base_nota = (f"solucion del solver base ({rb.name}); sin huella de "
                             f"relaciones, verificado solo por fecha")
            else:
                base_nota = (f"la solucion del sistema base ({rb.name}) es ANTERIOR "
                             f"a la extraccion; no es comparable")
        else:
            base_nota = f"no existe {rb}"
    if not base_pos:
        base_pos = datos.posiciones_sistema_base()
        base_nota = base_nota or "coordenadas publicadas de run_01"
    print()
    print(f"Sistema base: {base_nota}")
    if not base_comparable:
        print("  AVISO: la comparacion cabeza a cabeza NO sera pareja.")
        print("  Corre COMPARAR_BASE.bat para resolver esta misma extraccion")
        print("  con el solver del trabajo base, y vuelve a correr el paso 1.")

    salida = RAIZ / "datos" / "subgrafo.json"
    datos.guardar_json(salida, {
        "fuente": str(ruta),
        "referencia": str(ruta_ref) if not sin_referencia else None,
        "sin_referencia": sin_referencia,
        "nota": ("La entrada es un JSON de lugares y relaciones. No se invoco "
                 "el modelo de lenguaje en esta ejecucion."),
        "lugares": nombres,
        "relaciones": inducidas,
        "resumen": resumen,
        "verdad_referencia": {k: v for k, v in verdad.items() if k in nombres},
        "sistema_base": {k: v for k, v in base_pos.items() if k in nombres},
        "sistema_base_comparable": base_comparable,
        "sistema_base_nota": base_nota,
        "sistema_base_meta": base_meta,
        "config": cfg,
        "ancla": ancla,
    })
    print(f"\nGuardado en: {salida}")
    return 0


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    sys.exit(main(args[0] if args else None, "--auto" in sys.argv))
