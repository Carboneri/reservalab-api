"""Testes unitários puros: sem HTTP, sem banco, sem relógio.

Base de comparação em todos os casos: uma reserva existente das 10:00 às 12:00.
"""
from datetime import date, datetime

import pytest

from app.services.disponibilidade import calcular_faixas
from app.services.reservas import sobrepoe

DIA = date(2030, 1, 8)
EXISTENTE = ("10:00", "12:00")


def h(hora):
    return datetime.combine(DIA, datetime.strptime(hora, "%H:%M").time())


# (nome do caso, novo intervalo, sobrepõe?, faixas livres esperadas com as duas reservas)
CASOS = [
    ("encostado antes",       ("08:00", "10:00"), False, [("07:30", "08:00"), ("12:00", "22:30")]),
    ("encostado depois",      ("12:00", "14:00"), False, [("07:30", "10:00"), ("14:00", "22:30")]),
    ("sobreposicao no inicio", ("09:00", "11:00"), True, [("07:30", "09:00"), ("12:00", "22:30")]),
    ("sobreposicao no fim",   ("11:00", "13:00"), True,  [("07:30", "10:00"), ("13:00", "22:30")]),
    ("contida",               ("10:30", "11:30"), True,  [("07:30", "10:00"), ("12:00", "22:30")]),
    ("contendo",              ("09:00", "13:00"), True,  [("07:30", "09:00"), ("13:00", "22:30")]),
    ("identica",              ("10:00", "12:00"), True,  [("07:30", "10:00"), ("12:00", "22:30")]),
]
IDS = [caso[0] for caso in CASOS]


@pytest.mark.parametrize("nome, novo, esperado, _livre", CASOS, ids=IDS)
def test_r4_sobrepoe(nome, novo, esperado, _livre):
    assert sobrepoe(h(novo[0]), h(novo[1]), h(EXISTENTE[0]), h(EXISTENTE[1])) is esperado


@pytest.mark.parametrize("nome, novo, _esperado, _livre", CASOS, ids=IDS)
def test_r4_sobrepoe_e_simetrica(nome, novo, _esperado, _livre):
    # A ordem dos argumentos não importa: A sobrepõe B ⇔ B sobrepõe A.
    a = (h(novo[0]), h(novo[1]))
    b = (h(EXISTENTE[0]), h(EXISTENTE[1]))
    assert sobrepoe(*a, *b) == sobrepoe(*b, *a)


def test_r4_intervalos_distantes_nao_se_sobrepoem():
    assert not sobrepoe(h("07:30"), h("08:00"), h("20:00"), h("22:30"))


@pytest.mark.parametrize("nome, novo, _esperado, livre", CASOS, ids=IDS)
def test_disponibilidade_com_duas_reservas(nome, novo, _esperado, livre):
    # Sobreposições não chegam ao banco (R4), mas a função continua correta
    # se receber intervalos sobrepostos: o "cursor" nunca anda para trás.
    ocupacoes = [(h(EXISTENTE[0]), h(EXISTENTE[1]), 1), (h(novo[0]), h(novo[1]), 2)]

    ocupado, faixas_livres = calcular_faixas(DIA, ocupacoes)

    assert [(f["inicio"], f["fim"]) for f in faixas_livres] == [(h(i), h(f)) for i, f in livre]
    assert len(ocupado) == 2
    assert ocupado == sorted(ocupado, key=lambda f: f["inicio"])


def test_disponibilidade_ignora_e_recorta_o_que_esta_fora_da_janela():
    ocupacoes = [
        (h("06:00"), h("07:00"), 1),  # inteira antes da abertura: ignorada
        (h("07:00"), h("08:00"), 2),  # começa antes da abertura: recortada para 07:30
    ]

    ocupado, livre = calcular_faixas(DIA, ocupacoes)

    assert ocupado == [{"inicio": h("07:30"), "fim": h("08:00"), "reserva_id": 2}]
    assert livre == [{"inicio": h("08:00"), "fim": h("22:30")}]
