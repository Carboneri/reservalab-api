"""Entradas malformadas devem dar 400 (ou 404), nunca 500.

Cada teste aqui reproduz um bug encontrado ao medir a cobertura.
"""
from datetime import timedelta

import pytest

from app.parsers import MAIOR_INTEIRO
from app.services import relogio

ENORME = MAIOR_INTEIRO + 1
REGISTRO = {"nome": "Bia", "email": "bia@teste.dev", "senha": "segredo1"}
SALA = {"codigo": "LAB-Z1", "nome": "Lab Z", "bloco": "Z", "tipo": "laboratorio", "capacidade": 10}


@pytest.fixture
def admin(token_de):
    return token_de("admin")[1]


@pytest.fixture
def reserva_valida(catalogo):
    dia = (relogio.agora() + timedelta(days=1)).date()
    return {"sala_id": catalogo["LAB-B206"].id, "inicio": f"{dia}T14:00:00",
            "fim": f"{dia}T15:00:00", "participantes": 5, "finalidade": "Estudo"}


# ---- null em campo do corpo (o reqparse aceitava e o código quebrava) ----

@pytest.mark.parametrize("campo", ["nome", "email", "senha"])
def test_null_no_registro_responde_400(client, campo):
    resposta = client.post("/api/v1/auth/registro", json={**REGISTRO, campo: None})

    assert resposta.status_code == 400
    assert campo in resposta.get_json()["message"]


def test_null_na_senha_do_login_responde_400(client):
    resposta = client.post("/api/v1/auth/login", json={"email": "a@teste.dev", "senha": None})

    assert resposta.status_code == 400


@pytest.mark.parametrize("campo", ["codigo", "capacidade", "recursos", "ativa"])
def test_null_na_sala_responde_400(client, admin, campo):
    resposta = client.post("/api/v1/salas", json={**SALA, campo: None}, headers=admin)

    assert resposta.status_code == 400
    assert campo in resposta.get_json()["message"]


def test_null_dentro_da_lista_de_recursos_responde_400(client, admin):
    resposta = client.post("/api/v1/salas", json={**SALA, "recursos": ["projetor", None]}, headers=admin)

    assert resposta.status_code == 400


@pytest.mark.parametrize("campo", ["sala_id", "inicio", "fim", "participantes", "finalidade"])
def test_null_na_reserva_responde_400(client, admin, reserva_valida, campo):
    resposta = client.post("/api/v1/reservas", json={**reserva_valida, campo: None}, headers=admin)

    assert resposta.status_code == 400
    assert campo in resposta.get_json()["message"]


# ---- corpo JSON que não é objeto ----

@pytest.mark.parametrize("corpo", [["nome", "email"], "nome email senha", 42])
@pytest.mark.parametrize("rota", ["/api/v1/auth/registro", "/api/v1/auth/login",
                                  "/api/v1/salas", "/api/v1/reservas"])
def test_corpo_json_que_nao_e_objeto_responde_400(client, admin, rota, corpo):
    resposta = client.post(rota, json=corpo, headers=admin)

    assert resposta.status_code == 400
    assert resposta.get_json() == {
        "message": "Requisição inválida: o corpo deve ser um objeto JSON ({...})."
    }


# ---- inteiros: booleano e decimal não são inteiros ----

@pytest.mark.parametrize("valor", [True, False, 12.7])
def test_capacidade_booleana_ou_decimal_responde_400(client, admin, valor):
    resposta = client.post("/api/v1/salas", json={**SALA, "capacidade": valor}, headers=admin)

    assert resposta.status_code == 400
    assert "capacidade" in resposta.get_json()["message"]


def test_capacidade_decimal_sem_casas_e_aceita(client, admin):
    resposta = client.post("/api/v1/salas", json={**SALA, "capacidade": 12.0}, headers=admin)

    assert resposta.status_code == 201
    assert resposta.get_json()["capacidade"] == 12


@pytest.mark.parametrize("valor", [True, 2.5])
def test_participantes_booleano_ou_decimal_responde_400(client, admin, reserva_valida, valor):
    resposta = client.post("/api/v1/reservas", json={**reserva_valida, "participantes": valor}, headers=admin)

    assert resposta.status_code == 400


# ---- inteiros acima do que o SQLite guarda ----

def test_sala_id_enorme_no_corpo_responde_400(client, admin, reserva_valida):
    resposta = client.post("/api/v1/reservas", json={**reserva_valida, "sala_id": ENORME}, headers=admin)

    assert resposta.status_code == 400
    assert "sala_id" in resposta.get_json()["message"]


def test_capacidade_enorme_responde_400(client, admin):
    resposta = client.post("/api/v1/salas", json={**SALA, "capacidade": ENORME}, headers=admin)

    assert resposta.status_code == 400


@pytest.mark.parametrize("url", [
    f"/api/v1/salas?page={ENORME}",
    f"/api/v1/salas?per_page={ENORME}",
    f"/api/v1/salas?capacidade_min={ENORME}",
    f"/api/v1/reservas?sala_id={ENORME}",
])
def test_inteiro_enorme_na_query_string_responde_400(client, admin, url):
    assert client.get(url, headers=admin).status_code == 400


@pytest.mark.parametrize("url", [f"/api/v1/salas/{ENORME}", f"/api/v1/salas/{ENORME}/disponibilidade",
                                 f"/api/v1/reservas/{ENORME}"])
def test_id_enorme_na_url_responde_404(client, admin, url):
    resposta = client.get(url, headers=admin)

    assert resposta.status_code == 404
    assert resposta.get_json() == {"message": "Recurso não encontrado."}


def test_maior_id_suportado_ainda_chega_ao_recurso(client):
    resposta = client.get(f"/api/v1/salas/{MAIOR_INTEIRO}")

    assert resposta.status_code == 404
    assert resposta.get_json() == {"message": f"Sala {MAIOR_INTEIRO} não encontrada."}


# ---- recursos: vírgula e curingas do LIKE ----

def test_item_de_recurso_com_virgula_responde_400(client, admin):
    resposta = client.post("/api/v1/salas", json={**SALA, "recursos": ["projetor,som"]}, headers=admin)

    assert resposta.status_code == 400
    assert resposta.get_json() == {"message": {"recursos": "Recursos devem ser uma lista de textos sem vírgula."}}


@pytest.mark.parametrize("termo", ["%", "_om", "proj%"])
def test_curingas_do_like_no_filtro_recurso_sao_texto(client, catalogo, termo):
    corpo = client.get("/api/v1/salas", query_string={"recurso": termo}).get_json()

    assert corpo["total"] == 0
