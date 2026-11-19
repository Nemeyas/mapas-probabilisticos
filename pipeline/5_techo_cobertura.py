"""
Paso 5 · El techo real de la cobertura de nodos.

El trabajo base evalua la extraccion contra el grafo oficial de la Tierra
Media y reporta una "cobertura de nodos" del 24,8 % de media. Esa cifra se
lee como un resultado pobre.

Pero el grafo oficial cubre la Tierra Media entera, con Minas Tirith,
Edoras, Mordor y Osgiliath, mientras que el texto de entrada es *La
Comunidad del Anillo I*, que transcurre casi por completo entre la Comarca
y Rivendel. Los lugares que el texto nunca nombra no se pueden extraer de
el por ningun metodo.

Este script mide cuantos lugares del grafo oficial aparecen realmente en el
texto, y con eso calcula el techo estructural de la metrica. Es una
medicion, no una estimacion: cuenta ocurrencias en el texto completo,
considerando los alias que el propio Tolkien usa para cada lugar.

Uso:
    python pipeline\\5_techo_cobertura.py [ruta al PDF o TXT del texto]
"""

from __future__ import annotations

import json
import re
import sys
import unicodedata
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

from mapa_probabilistico import datos  # noqa: E402

BASE = RAIZ.parent / "5 Sistema base"
RUTA_TEXTO = BASE / "data" / "textos" / "J.R.R. Tolkien La Comunidad del anillo I.pdf"
RUTA_OFICIAL = BASE / "output" / "json" / "TierraMedia_GrafoOficial.json"
RUTA_EXTRACCION = (BASE / "experimentos" / "resultados" / "con_ambiguas" /
                   "run_01" / "json" / "map_relations.json")

#: Alias por lugar oficial. Tolkien nombra varios sitios de mas de una
#: forma, y contar solo el nombre del grafo subestimaria las menciones.
#: Se incluyen solo equivalencias que son el mismo lugar, no vecindades.
ALIAS_OFICIALES = {
    "Carn Dum": ["carn dum"],
    "Monte Gundabad": ["gundabad"],
    "Salas de Thranduil": ["thranduil"],
    "Erebor": ["erebor", "montana solitaria"],
    "Valle": ["valle"],
    "Esgaroth": ["esgaroth", "ciudad del lago"],
    "Fornost": ["fornost"],
    "Casa de Beorn": ["beorn"],
    "Puertos Grises": ["puertos grises", "mithlond"],
    "La Comarca": ["la comarca"],
    "Hobbiton": ["hobbiton"],
    "Bree": ["bree"],
    "Amon Sul": ["amon sul", "cima de los vientos"],
    "Rivendel": ["rivendel", "imladris"],
    "Tharbad": ["tharbad"],
    "Puerta Oeste de Moria": ["moria", "khazad"],
    "Dol Guldur": ["dol guldur"],
    "Caras Galadhon": ["caras galadhon", "lothlorien", "lorien"],
    "Isengard": ["isengard", "orthanc"],
    "Abismo de Helm": ["abismo de helm"],
    "Edoras": ["edoras"],
    "Sagrario": ["sagrario", "dunharrow"],
    "Puerta Negra": ["puerta negra", "morannon"],
    "Cair Andros": ["cair andros"],
    "Minas Tirith": ["minas tirith", "mundburgo"],
    "Osgiliath": ["osgiliath"],
    "Minas Morgul": ["minas morgul", "minas ithil"],
    "Cirith Ungol": ["cirith ungol"],
    "Monte del Destino": ["monte del destino", "orodruin", "grietas del destino"],
    "Barad-dur": ["barad-dur", "barad dur"],
    "Pelargir": ["pelargir"],
    "Dol Amroth": ["dol amroth"],
    "Umbar": ["umbar"],
}

#: El grafo oficial dice "La Comarca"; la extraccion dice "Comarca".
EQUIVALE_EN_EXTRACCION = {"La Comarca": "Comarca"}


def plano(s):
    """Minuscula sin tildes, para comparar nombres sin depender del acento."""
    s = unicodedata.normalize("NFD", s.lower())
    return "".join(c for c in s if unicodedata.category(c) != "Mn")


def leer_texto(ruta):
    ruta = Path(ruta)
    if ruta.suffix.lower() == ".txt":
        return ruta.read_text(encoding="utf-8", errors="replace")
    for modulo, clase in (("pypdf", "PdfReader"), ("PyPDF2", "PdfReader")):
        try:
            lector = getattr(__import__(modulo), clase)
        except Exception:
            continue
        return "\n".join((p.extract_text() or "") for p in lector(str(ruta)).pages)
    raise SystemExit(
        "Para leer el PDF hace falta pypdf:  pip install pypdf\n"
        "Alternativa: convierte el PDF a .txt y pasa esa ruta como argumento.")


def main(ruta_texto=None):
    ruta_texto = Path(ruta_texto) if ruta_texto else RUTA_TEXTO
    for r in (ruta_texto, RUTA_OFICIAL, RUTA_EXTRACCION):
        if not r.exists():
            print(f"No encuentro: {r}")
            return 1

    texto = plano(leer_texto(ruta_texto))
    oficial = json.loads(RUTA_OFICIAL.read_text(encoding="utf-8"))["coords"]
    extraccion = json.loads(RUTA_EXTRACCION.read_text(encoding="utf-8"))
    extraidos = set(extraccion["lugares"])

    faltan = set(oficial) - set(ALIAS_OFICIALES)
    if faltan:
        print(f"AVISO: lugares oficiales sin alias declarado: {sorted(faltan)}")

    mencionados, ausentes = [], []
    for nombre in oficial:
        vs = ALIAS_OFICIALES.get(nombre, [plano(nombre)])
        n = sum(texto.count(plano(v)) for v in vs)
        hallado = EQUIVALE_EN_EXTRACCION.get(nombre, nombre) in extraidos
        (mencionados if n > 0 else ausentes).append(
            {"lugar": nombre, "menciones": n, "extraido": hallado})

    mencionados.sort(key=lambda d: -d["menciones"])
    n_ofi, n_men = len(oficial), len(mencionados)
    n_hall = sum(1 for d in mencionados if d["extraido"])

    print("=" * 64)
    print("  El techo real de la cobertura de nodos")
    print("=" * 64)
    print(f"  Lugares en el grafo oficial      : {n_ofi}")
    print(f"  Mencionados en el texto de entrada: {n_men}")
    print(f"  Ausentes del texto                : {n_ofi - n_men}")
    print()
    print("  Mencionados en el texto:")
    for d in mencionados:
        print(f"    {d['lugar']:<24} {d['menciones']:>4} menciones   "
              f"{'extraido' if d['extraido'] else 'NO EXTRAIDO'}")
    print()
    print("  Ausentes del texto, imposibles de extraer por cualquier metodo:")
    print("    " + ", ".join(d["lugar"] for d in ausentes))
    print()
    print("-" * 64)
    print(f"  Cobertura como la reporta el trabajo base : {n_hall}/{n_ofi} = "
          f"{100*n_hall/n_ofi:.1f} %")
    print(f"  Techo estructural de esa metrica          : {n_men}/{n_ofi} = "
          f"{100*n_men/n_ofi:.1f} %")
    print(f"  Recall real sobre lo que si es extraible  : {n_hall}/{n_men} = "
          f"{100*n_hall/n_men:.1f} %")
    print("-" * 64)
    print()
    print("  La cobertura de nodos no mide la calidad de la extraccion:")
    print("  mide ademas cuanto se solapan el texto y el grafo de referencia.")
    print(f"  Con este par, {n_ofi - n_men} de {n_ofi} lugares del grafo son")
    print("  inalcanzables, porque pertenecen a volumenes posteriores de la obra.")
    print("  Medido contra lo que el texto si nombra, la extraccion del trabajo")
    print(f"  base acierta {100*n_hall/n_men:.0f} %, no {100*n_hall/n_ofi:.0f} %.")

    perdidos = [d for d in mencionados if not d["extraido"]]
    if perdidos:
        print()
        print("  Fallos de extraccion reales, ya descontado lo inalcanzable:")
        for d in perdidos:
            print(f"    {d['lugar']:<24} aparece {d['menciones']} veces y no se extrajo")

    datos.guardar_json(RAIZ / "salida" / "techo_cobertura.json", {
        "fuente_texto": str(ruta_texto),
        "n_oficiales": n_ofi,
        "n_mencionados": n_men,
        "n_extraidos_de_los_oficiales": n_hall,
        "cobertura_reportada": n_hall / n_ofi,
        "techo_estructural": n_men / n_ofi,
        "recall_sobre_lo_mencionable": n_hall / n_men,
        "mencionados": mencionados,
        "ausentes": [d["lugar"] for d in ausentes],
    })
    print("\nResultados en salida/techo_cobertura.json")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else None))
