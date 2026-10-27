from datetime import date, time, timedelta

from app.comandos import proximo_dia_util, seed
from app.models import Reserva, Sala, Usuario
from app.services import relogio


def test_seed_e_idempotente(app, relogio_fixo):
    runner = app.test_cli_runner()

    assert runner.invoke(seed).exit_code == 0
    assert runner.invoke(seed).exit_code == 0

    assert Usuario.query.count() == 3
    assert Sala.query.count() == 8
    assert Reserva.query.count() == 6


def test_seed_respeita_regras_basicas(app, relogio_fixo):
    app.test_cli_runner().invoke(seed)

    for r in Reserva.query.all():
        assert r.inicio > relogio_fixo  # R2
        assert r.inicio.date() == r.fim.date()  # R3
        assert time(7, 30) <= r.inicio.time() and r.fim.time() <= time(22, 30)  # R3
        assert 30 * 60 <= (r.fim - r.inicio).total_seconds() <= 4 * 3600  # R1
        assert r.participantes <= r.sala.capacidade  # R5
        assert r.sala.ativa  # R6
        if r.sala.tipo == "auditorio":
            assert r.usuario.papel in ("professor", "admin")  # R7


def test_proximo_dia_util_pula_fim_de_semana():
    sexta = date(2026, 10, 23)

    assert proximo_dia_util(1, hoje=sexta) == date(2026, 10, 26)  # segunda
    assert proximo_dia_util(5, hoje=sexta) == date(2026, 10, 30)


def test_seed_informa_o_dia_da_demo(app, relogio_fixo):
    saida = app.test_cli_runner().invoke(seed).output

    assert f"Dia da demo: {proximo_dia_util(1).isoformat()}" in saida
    lab = Sala.query.filter_by(codigo="LAB-B204").one()
    assert {r.inicio.date() for r in lab.reservas} == {proximo_dia_util(1)}


def test_seed_em_outro_dia_nao_cria_outro_conjunto_de_reservas(app, relogio_fixo, monkeypatch):
    runner = app.test_cli_runner()
    runner.invoke(seed)
    dia_demo = proximo_dia_util(1)

    monkeypatch.setattr(relogio, "agora", lambda: relogio_fixo + timedelta(days=1))
    saida = runner.invoke(seed).output

    assert Reserva.query.count() == 6
    assert f"Dia da demo: {dia_demo.isoformat()}" in saida  # continua o dia das reservas existentes


def test_seed_avisa_quando_o_dia_da_demo_ja_passou(app, relogio_fixo, monkeypatch):
    runner = app.test_cli_runner()
    runner.invoke(seed)

    monkeypatch.setattr(relogio, "agora", lambda: relogio_fixo + timedelta(days=30))
    saida = runner.invoke(seed).output

    assert "esse dia já passou" in saida
