"""
Muestreo Monte Carlo de la distribucion sobre configuraciones.

El sistema base entrega una configuracion: la mejor que Z3 alcanzo a
encontrar en 120 segundos. Este modulo entrega una muestra de la
distribucion completa, que es lo que permite despues decir "este lugar
esta aqui con esta confianza" en vez de "este lugar esta aqui".

Metodo: Metropolis-Hastings por bloques. Cada iteracion propone mover un
solo lugar; como la densidad es un producto sobre relaciones, al mover un
lugar solo cambian las relaciones que lo tocan, y el cociente de
aceptacion se evalua sobre esas. En un grafo disperso eso es la
diferencia entre O(m) y O(grado) por paso.
"""

from __future__ import annotations

import numpy as np


def metropolis_bloques(modelo, n_muestras=20000, descarte=5000, salto=0.06,
                       semilla=0, adaptar=True, inicial=None):
    """Cadena de Metropolis-Hastings por bloques sobre las posiciones.

    Parametros
    ----------
    modelo : ModeloMapa
    n_muestras : int
        Muestras a conservar, despues del descarte.
    descarte : int
        Iteraciones de calentamiento que se tiran (burn-in).
    salto : float
        Desviacion de la propuesta gaussiana, en unidades del cuadrado.
    semilla : int
        Semilla del generador. Fijarla es parte del protocolo experimental:
        es justamente lo que el trabajo base no declara.
    adaptar : bool
        Ajusta el salto durante el calentamiento para acercar la tasa de
        aceptacion al 40 por ciento. Se congela antes de muestrear, para
        que la cadena que se conserva sea homogenea.

    Devuelve
    --------
    muestras : (n_muestras, n_lugares, 2)
    diagnostico : dict
    """
    rng = np.random.default_rng(semilla)
    n = modelo.n_lugares

    if inicial is None:
        X = rng.uniform(0.2, 0.8, size=(n, 2))
    else:
        X = np.array(inicial, dtype=float)

    idx_ancla = modelo.indice.get(modelo.ancla) if modelo.ancla else None
    if idx_ancla is not None:
        X[idx_ancla] = modelo.pos_ancla

    moviles = [i for i in range(n) if i != idx_ancla]
    if not moviles:
        raise ValueError("No hay lugares moviles que muestrear.")

    muestras = np.empty((n_muestras, n, 2))
    log_pi_total = np.empty(n_muestras)
    aceptados = 0
    propuestos = 0
    saltos = np.full(n, float(salto))

    total = descarte + n_muestras
    for paso in range(total):
        for i in moviles:
            rel = modelo.relaciones_de[i]
            if not rel:
                # Lugar sin relaciones dentro del subgrafo: su posicion no
                # esta informada por nada, se deja donde este.
                continue
            antes = modelo.log_local(X, i)
            vx, vy = X[i, 0], X[i, 1]
            X[i, 0] = vx + rng.normal(0.0, saltos[i])
            X[i, 1] = vy + rng.normal(0.0, saltos[i])
            propuestos += 1
            if not (0.0 <= X[i, 0] <= 1.0 and 0.0 <= X[i, 1] <= 1.0):
                X[i, 0], X[i, 1] = vx, vy        # rechazo fuera del dominio
                continue
            despues = modelo.log_local(X, i)
            if np.log(rng.uniform()) < despues - antes:
                aceptados += 1
            else:
                X[i, 0], X[i, 1] = vx, vy

        if adaptar and paso < descarte and paso > 0 and paso % 200 == 0:
            tasa = aceptados / max(propuestos, 1)
            factor = 1.15 if tasa > 0.45 else (0.87 if tasa < 0.30 else 1.0)
            saltos *= factor
            saltos = np.clip(saltos, 1e-3, 0.4)
            aceptados = propuestos = 0

        if paso >= descarte:
            k = paso - descarte
            muestras[k] = X
            log_pi_total[k] = modelo.log_total_rapido(X)

    diagnostico = {
        "tasa_aceptacion": aceptados / max(propuestos, 1),
        "salto_final": float(np.mean(saltos)),
        "log_densidad_media": float(np.mean(log_pi_total)),
        "semilla": semilla,
        "n_muestras": n_muestras,
        "descarte": descarte,
    }
    return muestras, diagnostico


def gelman_rubin(cadenas):
    """Estadistico R de Gelman y Rubin por coordenada.

    `cadenas` es una lista de arreglos (n_muestras, n_lugares, 2) obtenidos
    con semillas distintas. Valores cercanos a 1 indican que las cadenas
    convergieron a la misma distribucion. Por encima de 1,1 hay que
    desconfiar: la cadena no mezclo.
    """
    A = np.stack(cadenas)                      # (m, n, lugares, 2)
    m, n = A.shape[0], A.shape[1]
    medias = A.mean(axis=1)                    # (m, lugares, 2)
    varianzas = A.var(axis=1, ddof=1)          # (m, lugares, 2)
    W = varianzas.mean(axis=0)
    B = n * medias.var(axis=0, ddof=1)
    var_post = (n - 1) / n * W + B / n
    with np.errstate(divide="ignore", invalid="ignore"):
        R = np.sqrt(np.where(W > 0, var_post / W, 1.0))
    return R


def tamano_efectivo(cadena_1d, max_rezago=200):
    """Tamano de muestra efectivo de una cadena escalar.

    Cuenta cuantas muestras independientes equivalen a las que hay, dada la
    autocorrelacion. Una cadena de 20.000 muestras muy correlacionada puede
    valer lo mismo que 200 independientes, y conviene saberlo.
    """
    x = np.asarray(cadena_1d, dtype=float)
    x = x - x.mean()
    n = len(x)
    if n < 10 or np.allclose(x, 0):
        return float(n)
    var = np.dot(x, x) / n
    if var <= 0:
        return float(n)
    suma = 0.0
    for k in range(1, min(max_rezago, n - 1)):
        rho = np.dot(x[:-k], x[k:]) / ((n - k) * var)
        if rho < 0.05:
            break
        suma += rho
    return float(n / (1.0 + 2.0 * suma))
