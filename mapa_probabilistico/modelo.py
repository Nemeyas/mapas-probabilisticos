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
    """Predicado duro, el mismo criterio que usa el sistema base.

    Se usa solo para medir: permite calcular un CSR comparable cifra a cifra
    con el del trabajo base, sobre configuraciones que el modelo blando
    produjo. El modelo no optimiza esto.
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
                 ancla=None, pos_ancla=(0.5, 0.5)):
        self.lugares = list(lugares)
        self.indice = {nombre: i for i, nombre in enumerate(self.lugares)}
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
        self.relaciones_de = {i: [] for i in range(len(self.lugares))}
        for j, r in enumerate(self.relaciones):
            self.relaciones_de[self.indice[r["origen"]]].append(j)
            self.relaciones_de[self.indice[r["destino"]]].append(j)

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

    def _preparar_rapido(self):
        self._rapido = []
        for j, r in enumerate(self.relaciones):
            cod = self._COD[r["tipo"]]
            d0 = D0_CERCA if cod == 0 else D0_CONECTA
            self._rapido.append((
                self.indice[r["origen"]], self.indice[r["destino"]],
                cod, d0, float(self.pesos[j]),
            ))
        self._rapido_de = {i: [self._rapido[j] for j in js]
                           for i, js in self.relaciones_de.items()}

    def log_local(self, X, i):
        """Log densidad de las relaciones que tocan al lugar i. Aritmetica escalar."""
        from math import exp, log, sqrt
        eps, s, k = self.epsilon, SUAVIDAD, DUREZA_CONO
        total = 0.0
        for io, id_, cod, d0, w in self._rapido_de[i]:
            dx = X[io, 0] - X[id_, 0]
            dy = X[io, 1] - X[id_, 1]
            if cod < 2:
                z = (sqrt(dx * dx + dy * dy) - d0) / s
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
                    mu = c ** k if c > 0.0 else 0.0
            total += w * log(eps + (1.0 - eps) * mu)
        return total

    def log_total_rapido(self, X):
        """Log densidad completa por el camino rapido."""
        from math import exp, log, sqrt
        eps, s, k = self.epsilon, SUAVIDAD, DUREZA_CONO
        total = 0.0
        for io, id_, cod, d0, w in self._rapido:
            dx = X[io, 0] - X[id_, 0]
            dy = X[io, 1] - X[id_, 1]
            if cod < 2:
                z = (sqrt(dx * dx + dy * dy) - d0) / s
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
                    mu = c ** k if c > 0.0 else 0.0
            total += w * log(eps + (1.0 - eps) * mu)
        return total

    @staticmethod
    def _clave(r):
        return (r["origen"], r["tipo"], r["destino"])

    @property
    def n_lugares(self):
        return len(self.lugares)

    @property
    def n_relaciones(self):
        return len(self.relaciones)

    def log_densidad(self, X, solo=None):
        """Log densidad no normalizada de la configuracion X, de forma (n, 2).

        `solo` restringe la suma a un subconjunto de indices de relacion, que
        es lo que hace eficiente el muestreo por bloques: al mover un lugar,
        solo cambian las relaciones que lo tocan.
        """
        X = np.asarray(X, dtype=float)
        indices = range(self.n_relaciones) if solo is None else solo
        total = 0.0
        for j in indices:
            r = self.relaciones[j]
            mu = compatibilidad_relacion(
                X[self.indice[r["origen"]]], X[self.indice[r["destino"]]],
                r["tipo"], epsilon=self.epsilon)
            total += self.pesos[j] * np.log(mu)
        return total

    def fraccion_satisfecha(self, X):
        """Fraccion de relaciones que el predicado duro da por satisfechas.

        Esto es el CSR del trabajo base, calculado sobre una configuracion
        cualquiera. Promediado sobre la posterior da el ECSR.
        """
        X = np.asarray(X, dtype=float)
        if self.n_relaciones == 0:
            return float("nan")
        ok = 0
        for r in self.relaciones:
            ok += bool(satisface_dura(X[self.indice[r["origen"]]],
                                      X[self.indice[r["destino"]]], r["tipo"])[0])
        return ok / self.n_relaciones

    def detalle_satisfaccion(self, X):
        """Lista de (relacion, satisface) para una configuracion."""
        X = np.asarray(X, dtype=float)
        salida = []
        for r in self.relaciones:
            ok = bool(satisface_dura(X[self.indice[r["origen"]]],
                                     X[self.indice[r["destino"]]], r["tipo"])[0])
            salida.append((r, ok))
        return salida
