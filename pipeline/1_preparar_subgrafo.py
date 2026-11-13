"""
Paso 1 · Preparar el subgrafo de trabajo.

Lee la extraccion congelada de run_01 publicada por el trabajo base,
selecciona el subgrafo e imprime que entra al modelo. No llama al modelo
de lenguaje: esa es la condicion que hace valida la comparacion cabeza a
cabeza con el sistema base.
"""

from __future__ import annotations

import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

from mapa_probabilistico import datos  # noqa: E402

#: Ubicacion por defecto de la extraccion, relativa a la carpeta Seminario.
RUTA_DEFECTO = (RAIZ.parent / "5 Sistema base" / "experimentos" / "resultados" /
                "con_ambiguas" / "run_01" / "json" / "map_relations.json")


def main(ruta=None):
    ruta = Path(ruta) if ruta else RUTA_DEFECTO
    if not ruta.exists():
        print(f"No encuentro la extraccion en:\n  {ruta}\n")
        print("Pasa la ruta como argumento, o clona el repositorio del")
        print("trabajo base en la carpeta '5 Sistema base'.")
        return 1

    lugares, relaciones = datos.cargar_extraccion(ruta)
    print(f"Extraccion completa : {len(lugares)} lugares, {len(relaciones)} relaciones")

    nombres, inducidas = datos.seleccionar_subgrafo(lugares, relaciones)
    verdad = datos.verdad_referencia()
    resumen = datos.resumen_subgrafo(nombres, inducidas, verdad)

    print(f"Subgrafo de trabajo : {resumen['n_lugares']} lugares, "
          f"{resumen['n_relaciones']} relaciones")
    print(f"Por tipo            : {resumen['por_tipo']}")
    print(f"Con posicion oficial: {len(resumen['con_verdad_conocida'])} de "
          f"{resumen['n_lugares']} -> {', '.join(resumen['con_verdad_conocida'])}")
    print()
    print("Relaciones del subgrafo:")
    for r in inducidas:
        print(f"  {r['origen']:<16} {r['tipo']:<10} {r['destino']}")

    salida = RAIZ / "datos" / "subgrafo.json"
    datos.guardar_json(salida, {
        "fuente": str(ruta),
        "nota": ("Extraccion congelada de run_01 publicada por Diaz Ureta y "
                 "Mercado Meza. No se invoco el modelo de lenguaje."),
        "lugares": nombres,
        "relaciones": inducidas,
        "resumen": resumen,
        "verdad_referencia": verdad,
        "sistema_base": datos.posiciones_sistema_base(),
    })
    print(f"\nGuardado en: {salida}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else None))
