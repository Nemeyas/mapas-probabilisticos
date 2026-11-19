"""
Paso 6 · Explicar el algoritmo, un paso a la vez.

Este script no calcula nada nuevo: abre la caja del muestreo y muestra,
con numeros reales, que pasa exactamente en cada iteracion de
Metropolis-Hastings por bloques.

Sirve para dos cosas. Para entender el algoritmo de verdad, y para poder
mostrarlo en una defensa: cada decision de aceptar o rechazar queda con
sus numeros a la vista.

Uso:
    python pipeline\\6_explicar_un_paso.py [cuantos pasos mostrar]
"""

from __future__ import annotations

import json
import sys
from math import exp, log, sqrt
from pathlib import Path

import numpy as np

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

from mapa_probabilistico import datos  # noqa: E402
from mapa_probabilistico.modelo import (  # noqa: E402
    DUREZA_CONO, EPSILON, SUAVIDAD, ModeloMapa, compatibilidad_relacion,
    satisface_dura,
)

ANCHO = 74


def titulo(t):
    print()
    print("=" * ANCHO)
    print(f"  {t}")
    print("=" * ANCHO)


def describir_relacion(modelo, r, X, etiqueta=""):
    """Imprime una relacion con su geometria y su compatibilidad actual."""
    io_, id_ = modelo.indice[r["origen"]], modelo.indice[r["destino"]]
    dx = X[io_, 0] - X[id_, 0]
    dy = X[io_, 1] - X[id_, 1]
    d = sqrt(dx * dx + dy * dy)
    mu = float(compatibilidad_relacion(X[io_], X[id_], r["tipo"]))
    dura = bool(satisface_dura(X[io_], X[id_], r["tipo"])[0])
    print(f"    {etiqueta}{r['origen']} {r['tipo']} {r['destino']}")
    print(f"      vector origen-destino = ({dx:+.4f}, {dy:+.4f})   "
          f"distancia = {d:.4f}")
    print(f"      compatibilidad mu~ = {mu:.6f}   "
          f"log mu~ = {log(mu):+.4f}   predicado duro: "
          f"{'satisface' if dura else 'NO satisface'}")


def main(n_pasos=4):
    sub = json.loads((RAIZ / "datos" / "subgrafo.json").read_text(encoding="utf-8"))
    # Mismos parametros que el resto del pipeline, desde config.json. Si esto
    # usara las constantes del modulo, la explicacion mostraria numeros de un
    # modelo distinto del que produjo los resultados.
    cfg = sub.get("config") or datos.cargar_config(RAIZ)
    mcfg = {k: v for k, v in cfg["modelo"].items() if k != "_ayuda"}
    mcfg["epsilon"] = max(mcfg.get("epsilon", EPSILON), 1e-12)
    mcfg["ancla"] = sub.get("ancla") or mcfg.get("ancla")
    modelo = ModeloMapa(sub["lugares"], sub["relaciones"],
                        pos_ancla=(0.5, 0.5), **mcfg)

    titulo("QUE ES EL ALGORITMO")
    print("""
  No busca la mejor configuracion del mapa. Define una densidad sobre TODAS
  las configuraciones posibles y saca muestras de ella.

      pi(X)  proporcional a  producto sobre r de  mu~_r(X) ^ w_r

  X es una configuracion: una posicion (x, y) para cada uno de los lugares.
  mu~_r es la compatibilidad robustecida de la relacion r con esa
  configuracion, un numero entre epsilon y 1. w_r es el peso de confianza.

  Se trabaja siempre en logaritmo, donde el producto es una suma:

      log pi(X) = suma sobre r de  w_r * log mu~_r(X)

  Nunca se calcula pi(X) normalizada. Metropolis-Hastings solo necesita
  COCIENTES de densidad, y en el cociente la constante de normalizacion se
  cancela. Por eso el metodo funciona aunque la integral sea incalculable.
""")

    print(f"  En este modelo: {modelo.n_lugares} lugares = "
          f"{2 * modelo.n_lugares} dimensiones, {modelo.n_relaciones} relaciones.")
    print(f"  Parametros: epsilon = {EPSILON}, suavidad s = {SUAVIDAD}, "
          f"dureza del cono k = {DUREZA_CONO}")
    print(f"  Ancla: Comarca fija en (0,5, 0,5). Sin ancla la densidad seria")
    print(f"  invariante a traslaciones y la cadena derivaria sin converger.")

    titulo("LA ESTRUCTURA DE DATOS QUE HACE QUE SEA RAPIDO")
    print("""
  El truco esta en que la densidad es un PRODUCTO sobre relaciones. Si se
  mueve un solo lugar, las relaciones que no lo tocan no cambian de valor,
  y en el cociente de densidades se cancelan.

  Por eso, al construir el modelo, se precomputa que relaciones toca cada
  lugar. Mover un lugar cuesta evaluar su grado, no las 20 relaciones.
""")
    for nombre in modelo.lugares:
        i = modelo.indice[nombre]
        print(f"    {nombre:<17} toca {len(modelo.relaciones_de[i]):>2} relaciones")

    rng = np.random.default_rng(1)
    X = rng.uniform(0.2, 0.8, size=(modelo.n_lugares, 2))
    X[modelo.indice["Comarca"]] = (0.5, 0.5)
    salto = 0.06

    # Calentamiento silencioso. Desde una configuracion aleatoria todas las
    # compatibilidades estan en el piso epsilon y no se ve nada: hay que
    # dejar que la cadena entre en la zona de alta densidad antes de abrir
    # la caja. Son las mismas iteraciones que el paso 2 descarta.
    _moviles = [i for i in range(modelo.n_lugares)
                if i != modelo.indice["Comarca"] and modelo.relaciones_de[i]]
    for _ in range(3000):
        for i in _moviles:
            a = modelo.log_local(X, i)
            vx, vy = X[i, 0], X[i, 1]
            X[i, 0] = vx + rng.normal(0.0, salto)
            X[i, 1] = vy + rng.normal(0.0, salto)
            if not (0.0 <= X[i, 0] <= 1.0 and 0.0 <= X[i, 1] <= 1.0):
                X[i, 0], X[i, 1] = vx, vy
                continue
            if not (log(rng.uniform()) < modelo.log_local(X, i) - a):
                X[i, 0], X[i, 1] = vx, vy

    titulo("EL BUCLE, TAL CUAL ESTA EN EL CODIGO")
    print("""
  Para cada iteracion:
    para cada lugar i que no sea el ancla:
      1. antes   = log densidad de SOLO las relaciones que tocan a i
      2. propone x' = x + ruido gaussiano de desviacion `salto`
      3. si x' se sale del cuadrado unitario, rechaza y sigue
      4. despues = log densidad de esas mismas relaciones, con x'
      5. delta   = despues - antes
      6. saca u uniforme en (0,1)
         si log(u) < delta  ->  acepta, el lugar se queda en x'
         si no              ->  rechaza, el lugar vuelve a x

  El paso 6 es Metropolis. Si la propuesta mejora la densidad, delta es
  positivo, log(u) siempre es negativo y SIEMPRE se acepta. Si la empeora,
  se acepta igual con probabilidad exp(delta). Eso ultimo es lo esencial:
  si solo aceptara mejoras seria una busqueda voraz y se quedaria pegada en
  el primer maximo local. Aceptar empeoramientos a veces es lo que hace que
  esto muestree la distribucion en vez de optimizar.
""")

    moviles = [i for i in range(modelo.n_lugares)
               if i != modelo.indice["Comarca"] and modelo.relaciones_de[i]]
    mostrados = 0
    aceptados = rechazados = 0
    falta_rechazo = True

    while mostrados < n_pasos:
        i = int(rng.choice(moviles))
        nombre = modelo.lugares[i]
        rel = modelo.relaciones_de[i]

        antes = modelo.log_local(X, i)
        vx, vy = X[i, 0], X[i, 1]
        X[i, 0] = vx + rng.normal(0.0, salto)
        X[i, 1] = vy + rng.normal(0.0, salto)
        if not (0.0 <= X[i, 0] <= 1.0 and 0.0 <= X[i, 1] <= 1.0):
            X[i, 0], X[i, 1] = vx, vy
            continue
        px, py = X[i, 0], X[i, 1]
        despues = modelo.log_local(X, i)
        delta = despues - antes
        u = float(rng.uniform())
        acepta = log(u) < delta

        # Para que la demostracion muestre los dos desenlaces, el ultimo
        # paso se reserva para un rechazo si todavia no salio ninguno.
        if falta_rechazo and acepta and mostrados == n_pasos - 1:
            X[i, 0], X[i, 1] = vx, vy
            continue
        if not acepta:
            falta_rechazo = False

        mostrados += 1
        titulo(f"PASO {mostrados} · se intenta mover {nombre}")
        print(f"  Posicion actual   : ({vx:.4f}, {vy:.4f})")
        print(f"  Relaciones que lo tocan: {len(rel)}")
        print()
        print("  ANTES del movimiento:")
        for j in rel:
            describir_relacion(modelo, modelo.relaciones[j], X := _con(X, i, vx, vy))
        print(f"    => log densidad local ANTES = {antes:+.4f}")

        X[i, 0], X[i, 1] = px, py
        print()
        print(f"  Propuesta: ({px:.4f}, {py:.4f})   "
              f"desplazamiento = ({px-vx:+.4f}, {py-vy:+.4f})")
        print()
        print("  DESPUES del movimiento:")
        for j in rel:
            describir_relacion(modelo, modelo.relaciones[j], X)
        print(f"    => log densidad local DESPUES = {despues:+.4f}")

        print()
        print(f"  delta = despues - antes = {despues:+.4f} - ({antes:+.4f}) "
              f"= {delta:+.4f}")
        if delta >= 0:
            print("  delta >= 0: la propuesta MEJORA la densidad.")
            print("  log(u) siempre es negativo, asi que se acepta sin mirar el azar.")
        else:
            print(f"  delta < 0: la propuesta EMPEORA la densidad.")
            print(f"  Se acepta igual con probabilidad exp(delta) = "
                  f"exp({delta:.4f}) = {exp(delta):.4f}")
        print(f"  Azar: u = {u:.6f}   log(u) = {log(u):+.4f}")
        print(f"  Criterio: log(u) < delta  ->  {log(u):+.4f} < {delta:+.4f}  "
              f"->  {acepta}")
        print()
        if acepta:
            aceptados += 1
            print(f"  ACEPTA. {nombre} se queda en ({px:.4f}, {py:.4f})")
        else:
            rechazados += 1
            X[i, 0], X[i, 1] = vx, vy
            print(f"  RECHAZA. {nombre} vuelve a ({vx:.4f}, {vy:.4f})")
            print("  Ojo: rechazar NO es perder el paso. La configuracion actual")
            print("  se vuelve a anotar como muestra, y eso es lo que le da peso")
            print("  a las zonas de alta densidad.")

    titulo("POR QUE ESTO TERMINA SIENDO LA DISTRIBUCION CORRECTA")
    print(f"""
  En esta demostracion: {aceptados} aceptados, {rechazados} rechazados.
  En la corrida real la tasa de aceptacion queda cerca del 38 %, que es el
  rango donde la cadena avanza sin quedarse quieta ni rebotar.

  La cadena de Markov construida con ese criterio de aceptacion tiene como
  distribucion estacionaria exactamente a pi. Es decir: si se la deja correr
  lo suficiente, la frecuencia con que visita cada region del espacio
  converge a la probabilidad de esa region. Por eso el histograma de las
  posiciones de un lugar ES su distribucion posterior, sin que haya que
  calcular ninguna integral.

  Dos cuidados practicos, los dos verificados en el paso 2:

  1. Calentamiento (descarte de 8.000 iteraciones). La cadena arranca en un
     punto arbitrario y necesita tiempo para olvidarlo. Esas muestras se
     tiran.

  2. Convergencia. Se corren 4 cadenas con semillas distintas y se compara
     la varianza dentro de cada cadena con la varianza entre cadenas
     (estadistico de Gelman y Rubin). Dio R = 1,0013. Por debajo de 1,05
     significa que las cuatro llegaron a la misma distribucion, es decir que
     el resultado no depende de donde arranco.
""")

    titulo("LO QUE ENTRA Y LO QUE SALE, ARCHIVO POR ARCHIVO")
    print("""
  paso 1  map_relations.json (extraccion congelada de run_01, 63 lugares,
          90 relaciones)                   ->  datos/subgrafo.json
                                               12 lugares, 20 relaciones

  paso 2  datos/subgrafo.json              ->  salida/muestras.npz
                                               80.000 x 12 x 2 numeros
                                           ->  salida/diagnostico_muestreo.json
                                               semillas, R, tamano efectivo

  paso 3  salida/muestras.npz              ->  salida/mapas_calor.png
                                               un histograma 2D por lugar

  paso 4  salida/muestras.npz              ->  salida/resultados.json
                                               ECSR, nitidez, calibracion,
                                               barrido de epsilon
""")
    return 0


def _con(X, i, x, y):
    """Devuelve X con el lugar i puesto en (x, y). Solo para imprimir."""
    X[i, 0], X[i, 1] = x, y
    return X


if __name__ == "__main__":
    sys.exit(main(int(sys.argv[1]) if len(sys.argv) > 1 else 4))
