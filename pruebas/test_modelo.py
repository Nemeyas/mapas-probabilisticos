"""
Pruebas del modelo.

La prueba que importa es `test_epsilon_rescata_la_bimodalidad`: es la que
justifica el termino de robustez, y es la condicion A1 del diseno
experimental del informe. Si esa prueba falla, el aporte central del
modelo no se sostiene.

Ejecutar:  python -m pytest pruebas -q      (o)   python pruebas/test_modelo.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from mapa_probabilistico.modelo import (  # noqa: E402
    ModeloMapa, compatibilidad_direccion, compatibilidad_distancia,
    compatibilidad_relacion, robustecer, satisface_dura,
)


# ---------------------------------------------------------------------------
# Compatibilidades
# ---------------------------------------------------------------------------

def test_distancia_vale_un_medio_en_d0():
    assert abs(float(compatibilidad_distancia(0.08, d0=0.08)) - 0.5) < 1e-9


def test_distancia_es_monotona_decreciente():
    d = np.linspace(0.0, 0.5, 50)
    mu = compatibilidad_distancia(d)
    assert np.all(np.diff(mu) <= 1e-12)


def test_suavidad_cero_recupera_la_restriccion_dura():
    """Con s -> 0 la sigmoide degenera en el escalon del sistema base.

    Es la afirmacion de la lamina 9: la restriccion dura es el caso limite
    de la blanda, no al reves.
    """
    for s in (1e-2, 1e-3, 1e-4):
        cerca = float(compatibilidad_distancia(0.05, d0=0.08, s=s))
        lejos = float(compatibilidad_distancia(0.11, d0=0.08, s=s))
        assert cerca > 0.5 and lejos < 0.5
    assert float(compatibilidad_distancia(0.05, d0=0.08, s=1e-4)) > 0.999
    assert float(compatibilidad_distancia(0.11, d0=0.08, s=1e-4)) < 0.001


def test_cono_maximo_en_la_direccion_pedida():
    assert abs(float(compatibilidad_direccion([0.0, 1.0], "NORTE_DE")) - 1.0) < 1e-12
    assert float(compatibilidad_direccion([0.0, -1.0], "NORTE_DE")) == 0.0
    # A 60 grados del norte todavia hay compatibilidad, pero baja: eso es
    # lo que significa "graduado".
    v = [np.sin(np.pi / 3), np.cos(np.pi / 3)]
    mu = float(compatibilidad_direccion(v, "NORTE_DE"))
    assert 0.0 < mu < 0.5


def test_desplazamiento_nulo_no_satisface_ninguna_direccion():
    for d in ("NORTE_DE", "SUR_DE", "ESTE_DE", "OESTE_DE"):
        assert float(compatibilidad_direccion([0.0, 0.0], d)) == 0.0


def test_robustecer_pone_piso_sin_tocar_el_techo():
    assert abs(robustecer(0.0, 0.05) - 0.05) < 1e-12
    assert abs(robustecer(1.0, 0.05) - 1.0) < 1e-12


def test_compatibilidad_nunca_sale_del_rango():
    rng = np.random.default_rng(0)
    for tipo in ("CERCA_DE", "CONECTA", "NORTE_DE", "SUR_DE", "ESTE_DE", "OESTE_DE"):
        a, b = rng.uniform(0, 1, (200, 2)), rng.uniform(0, 1, (200, 2))
        mu = compatibilidad_relacion(a, b, tipo)
        assert np.all(mu >= 0.05 - 1e-12) and np.all(mu <= 1.0 + 1e-12)


# ---------------------------------------------------------------------------
# La prueba central
# ---------------------------------------------------------------------------

def _perfil_contradiccion(epsilon, separacion=0.30, n=1201):
    """Densidad de X sobre el eje, con dos referencias contradictorias.

    El texto dice que X esta cerca de A y tambien cerca de C, y A y C estan
    lejos entre si. Se recorre X por el segmento AC y se mide la densidad.
    """
    A = np.array([0.5 - separacion / 2, 0.5])
    C = np.array([0.5 + separacion / 2, 0.5])
    xs = np.linspace(A[0], C[0], n)
    log_pi = []
    for x in xs:
        X = np.array([x, 0.5])
        mu_a = float(compatibilidad_relacion(X, A, "CERCA_DE", epsilon=epsilon))
        mu_c = float(compatibilidad_relacion(X, C, "CERCA_DE", epsilon=epsilon))
        log_pi.append(np.log(mu_a) + np.log(mu_c))
    return xs, np.array(log_pi), A, C


def test_sin_epsilon_gana_el_punto_medio():
    """Sin termino de robustez, el maximo esta donde no hay ninguna evidencia.

    Las colas de las dos sigmoides se multiplican y el punto medio, que no
    satisface ninguna de las dos referencias, termina ganandole a las dos
    posiciones que si satisfacen una. Es un artefacto de la formulacion.
    """
    xs, log_pi, A, C = _perfil_contradiccion(epsilon=0.0)
    i_max = int(np.argmax(log_pi))
    medio = len(xs) // 2
    assert abs(i_max - medio) < 0.02 * len(xs), (
        "se esperaba el maximo espurio en el punto medio")


def test_epsilon_rescata_la_bimodalidad():
    """Con el termino de robustez reaparecen los dos modos verdaderos.

    El piso epsilon acota lo que cuesta violar una restriccion, de modo que
    estar junto a A (satisfaciendo una, violando la otra) vuelve a ser mejor
    que estar en el medio (violando las dos a medias). La distribucion pasa
    a tener dos modos, que es lo que el texto realmente dice.

    Esta es la condicion A1 del diseno experimental.
    """
    xs, log_pi, A, C = _perfil_contradiccion(epsilon=0.05)
    medio = len(xs) // 2
    izq = int(np.argmax(log_pi[: medio - 10]))
    der = medio + 10 + int(np.argmax(log_pi[medio + 10:]))

    # Los dos modos laterales le ganan al punto medio.
    assert log_pi[izq] > log_pi[medio]
    assert log_pi[der] > log_pi[medio]
    # Y estan efectivamente junto a cada referencia.
    assert abs(xs[izq] - A[0]) < 0.05
    assert abs(xs[der] - C[0]) < 0.05
    # El valle del medio es real, no ruido numerico.
    assert min(log_pi[izq], log_pi[der]) - log_pi[medio] > 0.5


# ---------------------------------------------------------------------------
# Predicado duro y modelo
# ---------------------------------------------------------------------------

def test_predicado_duro_coincide_con_el_criterio_del_sistema_base():
    assert bool(satisface_dura([0.0, 0.0], [0.05, 0.0], "CERCA_DE")[0])
    assert not bool(satisface_dura([0.0, 0.0], [0.50, 0.0], "CERCA_DE")[0])
    assert bool(satisface_dura([0.0, 1.0], [0.0, 0.0], "NORTE_DE")[0])
    assert not bool(satisface_dura([0.0, -1.0], [0.0, 0.0], "NORTE_DE")[0])


def test_modelo_descarta_relaciones_fuera_del_subgrafo():
    rel = [
        {"origen": "A", "tipo": "CERCA_DE", "destino": "B"},
        {"origen": "A", "tipo": "CERCA_DE", "destino": "Z"},   # Z no esta
    ]
    m = ModeloMapa(["A", "B"], rel)
    assert m.n_relaciones == 1


def test_log_densidad_por_bloques_suma_el_total():
    rel = [
        {"origen": "A", "tipo": "CERCA_DE", "destino": "B"},
        {"origen": "B", "tipo": "NORTE_DE", "destino": "C"},
    ]
    m = ModeloMapa(["A", "B", "C"], rel)
    X = np.array([[0.4, 0.5], [0.45, 0.5], [0.45, 0.3]])
    total = m.log_densidad(X)
    parcial = sum(m.log_densidad(X, solo=[j]) for j in range(m.n_relaciones))
    assert abs(total - parcial) < 1e-12


def test_fraccion_satisfecha_esta_entre_cero_y_uno():
    rel = [{"origen": "A", "tipo": "CERCA_DE", "destino": "B"}]
    m = ModeloMapa(["A", "B"], rel)
    assert m.fraccion_satisfecha(np.array([[0.0, 0.0], [0.01, 0.0]])) == 1.0
    assert m.fraccion_satisfecha(np.array([[0.0, 0.0], [0.90, 0.0]])) == 0.0


def test_camino_rapido_coincide_con_la_definicion():
    """El camino rapido del muestreo no puede separarse de la definicion.

    `log_densidad` es la definicion de referencia, legible y vectorizada.
    `log_local` y `log_total_rapido` son la version con aritmetica escalar
    que usa el muestreo. Esta prueba las ata: si alguien toca una y no la
    otra, falla aqui y no en silencio dentro de la cadena.
    """
    rel = [
        {"origen": "A", "tipo": "CERCA_DE", "destino": "B"},
        {"origen": "B", "tipo": "CONECTA", "destino": "C"},
        {"origen": "A", "tipo": "NORTE_DE", "destino": "C"},
        {"origen": "C", "tipo": "ESTE_DE", "destino": "B"},
        {"origen": "B", "tipo": "OESTE_DE", "destino": "A"},
        {"origen": "C", "tipo": "SUR_DE", "destino": "A"},
    ]
    m = ModeloMapa(["A", "B", "C"], rel)
    rng = np.random.default_rng(7)
    for _ in range(50):
        X = rng.uniform(0.0, 1.0, size=(3, 2))
        assert abs(m.log_densidad(X) - m.log_total_rapido(X)) < 1e-9
        for i in range(3):
            esperado = m.log_densidad(X, solo=m.relaciones_de[i])
            assert abs(esperado - m.log_local(X, i)) < 1e-9


if __name__ == "__main__":
    fallos = 0
    for nombre, fn in sorted(globals().items()):
        if nombre.startswith("test_") and callable(fn):
            try:
                fn()
                print(f"  ok    {nombre}")
            except AssertionError as e:
                fallos += 1
                print(f"  FALLA {nombre}: {e}")
    print()
    print("Todas las pruebas pasaron." if not fallos else f"{fallos} prueba(s) fallaron.")
    sys.exit(1 if fallos else 0)
