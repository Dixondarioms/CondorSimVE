import pytest

from app.engine.combat import resolver_combate


def test_ratio_2_a_1_favorece_al_atacante():
    resultado = resolver_combate(
        fuerza_atacante=100,
        tipo_atacante="terrestre",
        fuerza_defensor=50,
        tipo_defensor="terrestre",
    )
    assert resultado.ratio == pytest.approx(2.0)
    assert resultado.perdida_defensor_pct > resultado.perdida_atacante_pct


def test_ratio_desfavorable_perjudica_mas_al_atacante():
    resultado = resolver_combate(
        fuerza_atacante=30,
        tipo_atacante="terrestre",
        fuerza_defensor=100,
        tipo_defensor="terrestre",
    )
    assert resultado.ratio < 0.5
    assert resultado.perdida_atacante_pct > resultado.perdida_defensor_pct


def test_superioridad_aerea_reduce_efectividad_terrestre_sin_cobertura():
    con_cobertura = resolver_combate(
        fuerza_atacante=100,
        tipo_atacante="aerea",
        fuerza_defensor=100,
        tipo_defensor="terrestre",
        cobertura_aerea_defensor=True,
    )
    sin_cobertura = resolver_combate(
        fuerza_atacante=100,
        tipo_atacante="aerea",
        fuerza_defensor=100,
        tipo_defensor="terrestre",
        cobertura_aerea_defensor=False,
    )
    assert sin_cobertura.ratio > con_cobertura.ratio
    assert sin_cobertura.perdida_defensor_pct >= con_cobertura.perdida_defensor_pct


def test_terreno_urbano_favorece_la_defensa():
    en_llano = resolver_combate(
        fuerza_atacante=100,
        tipo_atacante="terrestre",
        fuerza_defensor=100,
        tipo_defensor="terrestre",
        terreno_defensor="llano",
    )
    en_urbano = resolver_combate(
        fuerza_atacante=100,
        tipo_atacante="terrestre",
        fuerza_defensor=100,
        tipo_defensor="terrestre",
        terreno_defensor="urbano",
    )
    assert en_urbano.ratio < en_llano.ratio
    assert en_urbano.perdida_defensor_pct <= en_llano.perdida_defensor_pct


def test_fuerzas_resultantes_quedan_acotadas_0_100():
    resultado = resolver_combate(
        fuerza_atacante=100,
        tipo_atacante="terrestre",
        fuerza_defensor=5,
        tipo_defensor="terrestre",
    )
    assert 0.0 <= resultado.fuerza_defensor_resultante <= 100.0
    assert 0.0 <= resultado.fuerza_atacante_resultante <= 100.0


def test_fuerza_invalida_lanza_error():
    with pytest.raises(ValueError):
        resolver_combate(
            fuerza_atacante=0,
            tipo_atacante="terrestre",
            fuerza_defensor=50,
            tipo_defensor="terrestre",
        )
