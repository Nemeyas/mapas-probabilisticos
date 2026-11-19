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

def test_se_colapsan_las_relaciones_reciprocas():
    """Una afirmacion y su reciproca son una sola restriccion.

    "A al este de B" y "B al oeste de A" son la misma frase del texto. Si
    entran las dos, el factor se multiplica dos veces y la posterior sale
    mas angosta de lo que la evidencia justifica.
    """
    from mapa_probabilistico.datos import colapsar_reciprocas
    rel = [{"origen": "A", "tipo": "ESTE_DE", "destino": "B"},
           {"origen": "B", "tipo": "OESTE_DE", "destino": "A"},
           {"origen": "A", "tipo": "CERCA_DE", "destino": "C"},
           {"origen": "C", "tipo": "CERCA_DE", "destino": "A"}]
    unicas, pares = colapsar_reciprocas(rel)
    assert len(unicas) == 2
    assert len(pares) == 2
    # una direccion contraria entre OTRO par de lugares si es informacion nueva
    rel2 = rel[:1] + [{"origen": "A", "tipo": "OESTE_DE", "destino": "C"}]
    assert len(colapsar_reciprocas(rel2)[0]) == 2


def test_predicado_duro_se_comporta_segun_lo_declarado():
    """El predicado de medicion es el declarado, NO el del sistema base.

    El nombre anterior de esta prueba afirmaba que coincidia con el criterio
    del trabajo base. Es falso: ellos usan radio 0,5 para CERCA_DE, una caja
    de Chebyshev para CONECTA y un semiplano acotado para las direcciones.
    Ver la documentacion de satisface_dura.
    """
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


def test_predicado_del_modelo_usa_sus_propios_umbrales():
    """El predicado debe responder al d0 configurado, no al del modulo.

    Antes, las metricas llamaban a satisface_dura con sus valores por
    omision, de modo que el ECSR daba lo mismo con d0 = 0,02 que con
    d0 = 0,50. Esta prueba ata el predicado a la configuracion.
    """
    rel = [{"origen": "A", "tipo": "CERCA_DE", "destino": "B"}]
    X = np.array([[0.0, 0.0], [0.30, 0.0]])
    estricto = ModeloMapa(["A", "B"], rel, d0_cerca=0.10)
    laxo = ModeloMapa(["A", "B"], rel, d0_cerca=0.50)
    assert not estricto.satisface(X, 0)
    assert laxo.satisface(X, 0)


def test_region_creible_cuenta_la_masa_que_se_escapa():
    """El area no puede subestimarse por masa fuera de la ventana.

    Si una parte de la nube cae fuera de la ventana de medicion, esa masa
    tiene que seguir en el denominador. Normalizar solo por lo de adentro
    hacia parecer mas nitidas justo a las entidades mas inciertas.
    """
    from mapa_probabilistico.metricas import VENTANA, region_creible
    rng = np.random.default_rng(0)
    dentro = rng.normal(0.5, 0.05, size=(4000, 2))
    lejos = np.full((4000, 2), VENTANA[1] + 5.0)
    a_sin_fuga, _, _ = region_creible(dentro, nivel=0.80)
    a_con_fuga, _, _ = region_creible(np.vstack([dentro, lejos]), nivel=0.80)
    assert a_con_fuga > a_sin_fuga


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


# ---------------------------------------------------------------------------
# Tipado geometrico
# ---------------------------------------------------------------------------

def test_distancia_a_curva_usa_el_segmento_no_el_extremo():
    """Lo central del tipado: un rio se mide por su punto mas cercano.

    Un punto frente al centro de un segmento esta cerca del segmento aunque
    este lejos de sus dos extremos. Tratar la curva como un punto, que es lo
    que hace el sistema base, da una distancia mucho mayor.
    """
    from mapa_probabilistico.geometria import (CURVA, PUNTO, distancia_formas,
                                               dist_punto_segmento)
    curva = (CURVA, 0.0, 0.0, 1.0, 0.0, 0.0)
    punto = (PUNTO, 0.5, 0.1, 0.0, 0.0, 0.0)
    assert abs(distancia_formas(curva, punto) - 0.1) < 1e-12
    # contra cualquiera de los extremos la distancia seria mucho mayor
    assert dist_punto_segmento(0.5, 0.1, 0.0, 0.0, 0.0, 0.0) > 0.5


def test_distancia_a_region_es_cero_adentro():
    from mapa_probabilistico.geometria import PUNTO, REGION, distancia_formas
    region = (REGION, 0.5, 0.5, 0.0, 0.0, 0.1)
    dentro = (PUNTO, 0.52, 0.5, 0.0, 0.0, 0.0)
    fuera = (PUNTO, 0.8, 0.5, 0.0, 0.0, 0.0)
    assert distancia_formas(region, dentro) == 0.0
    assert abs(distancia_formas(region, fuera) - 0.2) < 1e-12


def test_segmentos_que_se_cruzan_estan_a_distancia_cero():
    from mapa_probabilistico.geometria import dist_segmento_segmento
    d = dist_segmento_segmento(0.0, 0.0, 1.0, 1.0, 0.0, 1.0, 1.0, 0.0)
    assert d == 0.0


def test_una_curva_ocupa_dos_posiciones():
    from mapa_probabilistico.geometria import CURVA
    rel = [{"origen": "A", "tipo": "CERCA_DE", "destino": "R"}]
    m = ModeloMapa(["A", "R"], rel, tipos={"R": CURVA})
    assert m.n_ranuras == 3
    assert m.ranuras["R"][0] != m.ranuras["R"][1]
    assert m.ranuras["A"][0] == m.ranuras["A"][1]
    X = np.array([[0.5, 0.1], [0.0, 0.0], [1.0, 0.0]])
    # el representante de la curva es el punto medio de sus extremos
    assert np.allclose(m.representantes(X)[1], [0.5, 0.0])


def test_sin_tipado_el_modelo_se_comporta_igual_que_antes():
    """El tipado es opcional y no debe alterar el caso por defecto."""
    rel = [
        {"origen": "A", "tipo": "CERCA_DE", "destino": "B"},
        {"origen": "B", "tipo": "NORTE_DE", "destino": "C"},
    ]
    m = ModeloMapa(["A", "B", "C"], rel)
    assert not m.tipado_activo and m.n_ranuras == 3
    rng = np.random.default_rng(3)
    for _ in range(20):
        X = rng.uniform(0, 1, size=(3, 2))
        assert abs(m.log_densidad(X) - m.log_total_rapido(X)) < 1e-9
        for i in range(3):
            assert abs(m.log_densidad(X, solo=m.relaciones_de[i])
                       - m.log_local(X, i)) < 1e-9


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
