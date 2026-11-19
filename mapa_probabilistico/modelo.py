"""
Modelo de restricciones espaciales blandas.

Cada relacion del texto no fija una posicion: fija un grado de
compatibilidad en [0, 1] para cada posicion posible. Este modulo
implementa esas funciones de compatibilidad y la densidad objetivo
que resulta de combinarlas.

Convencion de coordenadas
-------------------------
Espacio de trabajo: el cuadrado unitario [0, 1] x [0, 1].
El eje y crece hacia el NORTE (convencion matematica, no de imagen).
El grafo oficial de la Tierra Media usa y creciente hacia el sur, asi
que al cargarlo se invierte. Ver datos.py.

Referencias
-----------
Cono direccional graduado: Frank (1996).
Termino de robustez: ver seccion 5 del informe.
"""

from __future__ import annotations

import numpy as np

from .geometria import (CURVA, PUNTO, RADIO_REGION, REGION, distancia_formas,
                        representante)

# ---------------------------------------------------------------------------
# Parametros del modelo
# ---------------------------------------------------------------------------

#: Distancia caracteristica de "cerca de", en unidades del cuadrado unitario.
#: Es el punto donde la compatibilidad vale 0,5.
D0_CERCA = 0.08

#: Distancia caracteristica de "conecta con". Dos lugares conectados por un
#: camino pueden estar bastante mas lejos que dos lugares "cercanos".
D0_CONECTA = 0.20

#: Suavidad de la sigmoide. Con s -> 0 la restriccion blanda degenera en la
#: restriccion dura del sistema base: ese es el caso limite, no el caso base.
SUAVIDAD = 0.030

#: Exponente del cono direccional. Mas alto = cono mas estrecho.
DUREZA_CONO = 2.0

#: Termino de robustez. Piso de la compatibilidad: violar una restriccion
#: cuesta caro, no cuesta infinito. Sin esto, dos referencias contradictorias
#: producen un maximo espurio en el punto medio. Ver pruebas/test_modelo.py.
EPSILON = 0.05

#: Relaciones de distancia (vagas) y relaciones direccionales (cardinales).
RELACIONES_DISTANCIA = {"CERCA_DE", "CONECTA"}
RELACIONES_DIRECCION = {"NORTE_DE", "SUR_DE", "ESTE_DE", "OESTE_DE"}

#: Vector unitario de cada direccion cardinal, con y creciente al norte.
VECTOR_CARDINAL = {
    "NORTE_DE": np.array([0.0, 1.0]),
    "SUR_DE": np.array([0.0, -1.0]),
    "ESTE_DE": np.array([1.0, 0.0]),
    "OESTE_DE": np.array([-1.0, 0.0]),
}


# ---------------------------------------------------------------------------
# Funciones de compatibilidad
# ---------------------------------------------------------------------------

def compatibilidad_distancia(d, d0=D0_CERCA, s=SUAVIDAD):
    """Compatibilidad logistica de una relacion de distancia vaga.

    Vale ~1 cuando d << d0, 0,5 exactamente en d = d0, y decae hacia 0
    cuando d >> d0. No tiene un corte: por eso es blanda.

        mu(d) = 1 / (1 + exp((d - d0) / s))

    Con s -> 0 se recupera el escalon duro d <= d0, que es lo que usa el
    sistema base. La restriccion dura es el caso limite de esta, no al reves.
    """
    z = (np.asarray(d, dtype=float) - d0) / s
    # Forma numericamente estable de 1/(1+exp(z)) para |z| grande.
    return np.where(z >= 0, np.exp(-z) / (1.0 + np.exp(-z)), 1.0 / (1.0 + np.exp(z)))


def compatibilidad_direccion(delta, direccion, k=DUREZA_CONO):
    """Compatibilidad de una relacion cardinal, como cono graduado.

    `delta` es el vector que va de B hacia A, para la relacion "A esta al
    <direccion> de B". La compatibilidad es maxima cuando delta apunta
    exactamente en la direccion pedida y cae suavemente hasta 0 a 90 grados.

        mu(theta) = max(0, cos(theta)) ** k

    Esto es un cono graduado en el sentido de Frank (1996): "al norte de"
    no fija una posicion, fija un conjunto difuso de posiciones compatibles.
    Dos lugares en la misma posicion no satisfacen ninguna direccion, asi
    que la compatibilidad de un desplazamiento nulo se define como 0.
    """
    bruto = np.asarray(delta, dtype=float)
    delta = np.atleast_2d(bruto)
    objetivo = VECTOR_CARDINAL[direccion]
    norma = np.linalg.norm(delta, axis=-1)
    with np.errstate(invalid="ignore", divide="ignore"):
        coseno = (delta @ objetivo) / norma
    coseno = np.where(norma > 1e-12, coseno, 0.0)
    mu = np.clip(coseno, 0.0, None) ** k
    return mu[0] if bruto.ndim == 1 else mu


def robustecer(mu, epsilon=EPSILON):
    """Aplica el termino de robustez: mu_tilde = epsilon + (1 - epsilon) * mu.

    Sube el piso de la compatibilidad de 0 a epsilon. El efecto es que violar
    una restriccion deja de costar infinito en escala logaritmica y pasa a
    costar log(epsilon), que es caro pero finito.

    Esto es lo que permite que dos referencias contradictorias produzcan dos
    modos separados en vez de un unico maximo espurio en el punto medio.
    """
    return epsilon + (1.0 - epsilon) * np.asarray(mu, dtype=float)


# ---------------------------------------------------------------------------
# Evaluacion de una relacion
# ---------------------------------------------------------------------------

def compatibilidad_relacion(pos_origen, pos_destino, tipo, epsilon=EPSILON, **kw):
    """Compatibilidad robustecida de una relacion, en [epsilon, 1].

    La relacion se lee "origen <tipo> destino": para NORTE_DE, el origen
    esta al norte del destino.
    """
    a = np.asarray(pos_origen, dtype=float)
    b = np.asarray(pos_destino, dtype=float)
    escalar = (a.ndim == 1 and b.ndim == 1)
    delta = np.atleast_2d(a) - np.atleast_2d(b)

    if tipo in RELACIONES_DISTANCIA:
        d0 = kw.get("d0", D0_CERCA if tipo == "CERCA_DE" else D0_CONECTA)
        mu = compatibilidad_distancia(np.linalg.norm(delta, axis=-1), d0=d0,
                                      s=kw.get("s", SUAVIDAD))
    elif tipo in RELACIONES_DIRECCION:
        mu = compatibilidad_direccion(delta, tipo, k=kw.get("k", DUREZA_CONO))
    else:
        raise ValueError(f"Tipo de relacion desconocido: {tipo}")

    mu = np.atleast_1d(robustecer(mu, epsilon))
    return float(mu[0]) if escalar else mu


def satisface_dura(pos_origen, pos_destino, tipo, d0_cerca=D0_CERCA,
                   d0_conecta=D0_CONECTA):
    """Predicado duro DECLARADO, usado como vara comun para medir.

    ATENCION: este criterio NO es el del trabajo base. El suyo, definido en
    `pipeline/2_generar_inecuaciones.py`, es distinto en los tres tipos:

      CERCA_DE   ellos: circulo de radio 0,5 del lienzo si no hay distancia
                 explicita.          aqui: circulo de radio d0_cerca = 0,08.
      CONECTA    ellos: caja de Chebyshev de medio lado 0,4.
                 aqui: circulo de radio d0_conecta = 0,20.
      Direccion  ellos: semiplano con margen 0,036 MAS una caja de 0,333 de
                 lado, en avance y en deriva lateral.
                 aqui: cono de 45 grados, sin cota de alcance.

    Por eso el CSR que calcula este modulo no es el CSR que publica el
    trabajo base, y las dos cifras no deben presentarse como la misma cosa.
    Lo que si vale es comparar candidatos ENTRE SI bajo este criterio, que
    es como se usa: ambos sistemas se evaluan con el mismo predicado, el
    mismo marco y el mismo subconjunto de relaciones.

    El modelo blando no optimiza este predicado; solo se usa para medir.
    """
    a = np.asarray(pos_origen, dtype=float)
    b = np.asarray(pos_destino, dtype=float)
    delta = np.atleast_2d(a) - np.atleast_2d(b)

    if tipo in RELACIONES_DISTANCIA:
        d0 = d0_cerca if tipo == "CERCA_DE" else d0_conecta
        return np.linalg.norm(delta, axis=-1) <= d0
    if tipo in RELACIONES_DIRECCION:
        objetivo = VECTOR_CARDINAL[tipo]
        proyeccion = delta @ objetivo
        # Satisface si la componente en la direccion pedida domina a la
        # perpendicular: el mismo criterio de semiplano con margen que usa
        # el sistema base, expresado en forma vectorial.
        perpendicular = np.abs(delta @ np.array([-objetivo[1], objetivo[0]]))
        return proyeccion > perpendicular
    raise ValueError(f"Tipo de relacion desconocido: {tipo}")


# ---------------------------------------------------------------------------
# Densidad objetivo
# ---------------------------------------------------------------------------

class ModeloMapa:
    """Densidad no normalizada sobre todas las configuraciones del mapa.

    Una configuracion X asigna una posicion en [0,1]^2 a cada lugar. La
    densidad objetivo es el producto de las compatibilidades robustecidas
    de todas las relaciones, elevadas a su peso de confianza:

        pi(X)  proporcional a  prod_r  mu_tilde_r(X) ** w_r

    Se trabaja siempre en logaritmo, que es donde el termino de robustez
    se lee bien: cada relacion violada resta como maximo -w_r * log(1/epsilon).
    """

    def __init__(self, lugares, relaciones, pesos=None, epsilon=EPSILON,
                 ancla=None, pos_ancla=(0.5, 0.5), d0_cerca=D0_CERCA,
                 d0_conecta=D0_CONECTA, suavidad=SUAVIDAD, dureza_cono=DUREZA_CONO,
                 tipos=None, radios=None):
        # Los parametros geometricos viven en la instancia, no en el modulo,
        # para que se puedan cambiar desde config.json sin tocar el codigo.
        self.d0_cerca = float(d0_cerca)
        self.d0_conecta = float(d0_conecta)
        self.suavidad = float(suavidad)
        self.dureza_cono = float(dureza_cono)
        self.lugares = list(lugares)

        # --- tipado geometrico ---------------------------------------------
        #
        # Una curva ocupa DOS filas de X, sus dos extremos; un punto y una
        # region ocupan una. El muestreo sigue operando sobre una matriz de
        # posiciones, sin saber nada de formas: lo unico que cambia es que
        # algunas entidades tienen dos posiciones en vez de una. Esa decision
        # evita introducir parametros de otra naturaleza, como longitudes u
        # orientaciones, que habria que muestrear con propuestas distintas.
        self.tipos = {n: (tipos or {}).get(n, PUNTO) for n in self.lugares}
        self.radios = {n: (radios or {}).get(n, RADIO_REGION) for n in self.lugares}
        self.ranuras = {}
        k = 0
        for n in self.lugares:
            if self.tipos[n] == CURVA:
                self.ranuras[n] = (k, k + 1)
                k += 2
            else:
                self.ranuras[n] = (k, k)
                k += 1
        self.n_ranuras = k
        self.tipado_activo = any(t != PUNTO for t in self.tipos.values())

        # `indice` apunta a la primera ranura de cada entidad. Se conserva
        # con ese nombre porque el resto del codigo lo usa asi, y para una
        # entidad puntual, que es el caso por defecto, coincide con antes.
        self.indice = {n: self.ranuras[n][0] for n in self.lugares}
        self.relaciones = [r for r in relaciones
                           if r["origen"] in self.indice and r["destino"] in self.indice]
        self.epsilon = epsilon

        # Peso de confianza por relacion. Hoy es 1 para todas, porque la
        # extraccion congelada del trabajo base no publica confianza. Cuando
        # OE2 produzca M extracciones, w_r pasa a ser la frecuencia con que
        # la relacion r aparece entre ellas. La formulacion ya lo admite.
        if pesos is None:
            pesos = {}
        self.pesos = np.array([pesos.get(self._clave(r), 1.0) for r in self.relaciones])

        # Ancla: las relaciones son todas relativas, asi que la densidad es
        # invariante a traslaciones. Se fija un lugar para quitar esa
        # libertad. La rotacion ya queda fijada por las relaciones
        # cardinales, y la escala por d0.
        self.ancla = ancla
        self.pos_ancla = np.array(pos_ancla, dtype=float)

        # Para el muestreo por bloques: que relaciones toca cada lugar.
        self.relaciones_de = {i: [] for i in range(self.n_ranuras)}
        for j, r in enumerate(self.relaciones):
            for nombre in (r["origen"], r["destino"]):
                a, b = self.ranuras[nombre]
                self.relaciones_de[a].append(j)
                if b != a:
                    self.relaciones_de[b].append(j)

        self._preparar_rapido()

    # -- camino rapido para el muestreo -------------------------------------
    #
    # El muestreo evalua la densidad millones de veces sobre subconjuntos de
    # dos o tres relaciones. A esa escala el costo no esta en la aritmetica
    # sino en el despacho de numpy, asi que se precompilan las relaciones a
    # tuplas de enteros y flotantes y se evaluan con aritmetica escalar.
    # `log_densidad` sigue siendo la definicion de referencia, y
    # test_camino_rapido_coincide_con_la_definicion comprueba que no se
    # separan.

    _COD = {"CERCA_DE": 0, "CONECTA": 1,
            "NORTE_DE": 2, "SUR_DE": 3, "ESTE_DE": 4, "OESTE_DE": 5}

    @staticmethod
    def _clave(r):
        return (r["origen"], r["tipo"], r["destino"])

    @property
    def n_lugares(self):
        return len(self.lugares)

    @property
    def n_relaciones(self):
        return len(self.relaciones)

    def _preparar_rapido(self):
        self._rapido = []
        for j, r in enumerate(self.relaciones):
            cod = self._COD[r["tipo"]]
            d0 = self.d0_cerca if cod == 0 else self.d0_conecta
            o, d = r["origen"], r["destino"]
            self._rapido.append((
                self.ranuras[o], self.ranuras[d], cod, d0, float(self.pesos[j]),
                self.tipos[o], self.tipos[d],
                self.radios[o] if self.tipos[o] == REGION else 0.0,
                self.radios[d] if self.tipos[d] == REGION else 0.0,
            ))
        self._rapido_de = {i: [self._rapido[j] for j in js]
                           for i, js in self.relaciones_de.items()}

    def _forma(self, X, ranuras, tipo, radio):
        a, b = ranuras
        return (tipo, X[a, 0], X[a, 1], X[b, 0], X[b, 1], radio)

    def representantes(self, X):
        """Un punto por entidad: la posicion, el centro o el medio de la curva.

        Es la vista que usan las figuras y las metricas, que razonan en
        terminos de una ubicacion por lugar.
        """
        X = np.asarray(X, dtype=float)
        salida = np.empty((len(self.lugares), 2))
        for i, n in enumerate(self.lugares):
            salida[i] = representante(
                self._forma(X, self.ranuras[n], self.tipos[n], self.radios[n]))
        return salida

    def representantes_lote(self, M):
        """Representantes de un lote de configuraciones, de forma (m, r, 2).

        Devuelve (m, n_lugares, 2). Es la vista que consumen las figuras y
        las metricas, que razonan con una ubicacion por entidad.
        """
        M = np.asarray(M, dtype=float)
        salida = np.empty((M.shape[0], len(self.lugares), 2))
        for i, n in enumerate(self.lugares):
            a, b = self.ranuras[n]
            salida[:, i, :] = M[:, a, :] if a == b else 0.5 * (M[:, a, :] + M[:, b, :])
        return salida

    def _log_mu_tupla(self, X, t):
        """Log de la compatibilidad robustecida de una relacion compilada.

        Camino general, con formas. Se usa cuando hay tipado geometrico
        activo. Cuando todas las entidades son puntos se usa en cambio el
        camino escalar de `_log_mu_punto`, que evita construir las tuplas de
        forma y es sensiblemente mas rapido.
        """
        from math import exp, log
        ro, rd, cod, d0, w, to, td, rao, rad = t
        fa = self._forma(X, ro, to, rao)
        fb = self._forma(X, rd, td, rad)
        if cod < 2:
            z = (distancia_formas(fa, fb) - d0) / self.suavidad
            if z >= 0:
                e = exp(-z)
                mu = e / (1.0 + e)
            else:
                mu = 1.0 / (1.0 + exp(z))
        else:
            ox, oy = representante(fa)
            dx_, dy_ = representante(fb)
            dx, dy = ox - dx_, oy - dy_
            n = (dx * dx + dy * dy) ** 0.5
            if n <= 1e-12:
                mu = 0.0
            else:
                c = (dy / n) if cod == 2 else (-dy / n) if cod == 3 else \
                    (dx / n) if cod == 4 else (-dx / n)
                mu = c ** self.dureza_cono if c > 0.0 else 0.0
        return w * log(self.epsilon + (1.0 - self.epsilon) * mu)

    def _log_mu_punto(self, X, t):
        """Camino escalar para el caso en que toda entidad es un punto."""
        from math import exp, log, sqrt
        ro, rd, cod, d0, w = t[0], t[1], t[2], t[3], t[4]
        io_, id_ = ro[0], rd[0]
        dx = X[io_, 0] - X[id_, 0]
        dy = X[io_, 1] - X[id_, 1]
        if cod < 2:
            z = (sqrt(dx * dx + dy * dy) - d0) / self.suavidad
            if z >= 0:
                e = exp(-z)
                mu = e / (1.0 + e)
            else:
                mu = 1.0 / (1.0 + exp(z))
        else:
            n = sqrt(dx * dx + dy * dy)
            if n <= 1e-12:
                mu = 0.0
            else:
                c = (dy / n) if cod == 2 else (-dy / n) if cod == 3 else \
                    (dx / n) if cod == 4 else (-dx / n)
                mu = c ** self.dureza_cono if c > 0.0 else 0.0
        return w * log(self.epsilon + (1.0 - self.epsilon) * mu)

    def log_local(self, X, i):
        """Log densidad de las relaciones que tocan a la ranura i."""
        f = self._log_mu_tupla if self.tipado_activo else self._log_mu_punto
        return sum(f(X, t) for t in self._rapido_de[i])

    def log_total_rapido(self, X):
        """Log densidad completa."""
        f = self._log_mu_tupla if self.tipado_activo else self._log_mu_punto
        return sum(f(X, t) for t in self._rapido)

    def log_densidad(self, X, solo=None):
        """Log densidad no normalizada de la configuracion X, de forma (n, 2).

        `solo` restringe la suma a un subconjunto de indices de relacion, que
        es lo que hace eficiente el muestreo por bloques: al mover un lugar,
        solo cambian las relaciones que lo tocan.
        """
        X = np.asarray(X, dtype=float)
        indices = range(self.n_relaciones) if solo is None else solo
        return float(sum(self._log_mu_tupla(X, self._rapido[j]) for j in indices))

    def fraccion_satisfecha(self, X):
        """Fraccion de relaciones que el predicado duro da por satisfechas.

        Esto es el CSR del trabajo base, calculado sobre una configuracion
        cualquiera. Promediado sobre la posterior da el ECSR.
        """
        X = np.asarray(X, dtype=float)
        if self.n_relaciones == 0:
            return float("nan")
        return sum(self.satisface(X, j) for j in range(self.n_relaciones)) \
            / self.n_relaciones

    def satisface(self, X, j):
        """Predicado duro de la relacion j, con la geometria de cada entidad."""
        ro, rd, cod, d0, _, to, td, rao, rad = self._rapido[j]
        fa = self._forma(X, ro, to, rao)
        fb = self._forma(X, rd, td, rad)
        if cod < 2:
            return distancia_formas(fa, fb) <= d0
        ox, oy = representante(fa)
        px, py = representante(fb)
        dx, dy = ox - px, oy - py
        proy = (dy, -dy, dx, -dx)[cod - 2]
        perp = abs(dx) if cod in (2, 3) else abs(dy)
        return proy > perp

    def detalle_satisfaccion(self, X):
        """Lista de (relacion, satisface) para una configuracion."""
        X = np.asarray(X, dtype=float)
        return [(r, self.satisface(X, j))
                for j, r in enumerate(self.relaciones)]
