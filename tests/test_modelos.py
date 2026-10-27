from datetime import timedelta

import pytest
from sqlalchemy.exc import IntegrityError

from app.models import Reserva, Sala, Usuario


def test_senha_guardada_como_hash(db):
    usuario = Usuario(nome="Teste", email="t@reservalab.dev")
    usuario.definir_senha("segredo")

    assert usuario.senha_hash != "segredo"
    assert usuario.verificar_senha("segredo")
    assert not usuario.verificar_senha("errada")


def test_recursos_viram_lista(db):
    sala = Sala(codigo="X-1", nome="X", bloco="A", tipo="sala_aula", capacidade=10)
    sala.recursos = ["projetor", " ar-condicionado ", ""]

    assert sala.recursos_texto == "projetor,ar-condicionado"
    assert sala.recursos == ["projetor", "ar-condicionado"]


def test_sala_sem_recursos_tem_lista_vazia(db):
    sala = Sala(codigo="X-2", nome="X", bloco="A", tipo="sala_aula", capacidade=10)
    db.session.add(sala)
    db.session.commit()

    assert sala.recursos == []


def test_email_unico(db):
    for _ in range(2):
        usuario = Usuario(nome="Dup", email="dup@reservalab.dev")
        usuario.definir_senha("x")
        db.session.add(usuario)
    with pytest.raises(IntegrityError):
        db.session.commit()


def test_codigo_de_sala_unico(db):
    for _ in range(2):
        db.session.add(Sala(codigo="DUP-1", nome="X", bloco="A", tipo="sala_aula", capacidade=10))
    with pytest.raises(IntegrityError):
        db.session.commit()


def test_r10_excluir_sala_apaga_reservas_passadas_e_canceladas(db, relogio_fixo):
    usuario = Usuario(nome="Prof", email="prof@reservalab.dev", papel="professor")
    usuario.definir_senha("x")
    sala = Sala(codigo="LAB-X1", nome="Lab X", bloco="B", tipo="laboratorio", capacidade=20)
    ontem = relogio_fixo.replace(hour=8) - timedelta(days=1)
    amanha = ontem + timedelta(days=2)
    sala.reservas = [
        Reserva(usuario=usuario, inicio=ontem, fim=ontem + timedelta(hours=2),
                participantes=10, finalidade="Aula passada"),
        Reserva(usuario=usuario, inicio=amanha, fim=amanha + timedelta(hours=2),
                participantes=10, finalidade="Cancelada", status="cancelada"),
    ]
    db.session.add(sala)
    db.session.commit()

    db.session.delete(sala)
    db.session.commit()

    assert Sala.query.count() == 0
    assert Reserva.query.count() == 0
    assert Usuario.query.count() == 1


@pytest.mark.parametrize("tabela", ["usuarios", "salas", "reservas"])
def test_tabelas_usam_autoincrement(db, tabela):
    sql = db.session.execute(
        db.text("SELECT sql FROM sqlite_master WHERE name = :t"), {"t": tabela}).scalar()

    assert "AUTOINCREMENT" in sql


def test_id_de_sala_excluida_nao_e_reaproveitado(client, cabecalho):
    admin = cabecalho("admin")
    dados = {"codigo": "X-1", "nome": "X", "bloco": "A", "tipo": "sala_aula", "capacidade": 10}
    primeira = client.post("/api/v1/salas", json=dados, headers=admin).get_json()["id"]
    assert client.delete(f"/api/v1/salas/{primeira}", headers=admin).status_code == 204

    segunda = client.post("/api/v1/salas", json={**dados, "codigo": "X-2"}, headers=admin).get_json()["id"]

    assert segunda > primeira
