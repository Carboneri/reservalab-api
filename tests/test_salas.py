from datetime import timedelta

import pytest

from app.models import Reserva, Sala

URL = "/api/v1/salas"
NOVA = {
    "codigo": "lab-d301",
    "nome": "Laboratório de IA",
    "bloco": "D",
    "tipo": "laboratorio",
    "capacidade": 30,
    "recursos": ["computadores", "GPU"],
}


def sala_id(codigo):
    return Sala.query.filter_by(codigo=codigo).one().id


# ---- listagem ----

def test_lista_paginada_com_envelope(client, catalogo):
    resposta = client.get(URL)

    assert resposta.status_code == 200
    corpo = resposta.get_json()
    assert set(corpo) == {"itens", "pagina", "por_pagina", "total", "paginas"}
    assert (corpo["pagina"], corpo["por_pagina"], corpo["total"], corpo["paginas"]) == (1, 10, 8, 1)
    primeira = corpo["itens"][0]
    assert isinstance(primeira["recursos"], list)
    assert primeira["url"] == f"{URL}/{primeira['id']}"


@pytest.mark.parametrize("filtro, codigos", [
    ("tipo=laboratorio", {"LAB-B204", "LAB-B206", "LAB-C101"}),
    ("bloco=a", {"SALA-A101", "SALA-A102", "AUD-A001"}),
    ("capacidade_min=45", {"SALA-A101", "SALA-A102", "AUD-A001"}),
    ("recurso=som", {"AUD-A001"}),
    ("recurso=Projetor&bloco=C", {"LAB-C101", "SALA-C203"}),
    ("ativa=false", {"SALA-C203"}),
])
def test_filtros(client, catalogo, filtro, codigos):
    corpo = client.get(f"{URL}?{filtro}").get_json()

    assert {s["codigo"] for s in corpo["itens"]} == codigos


def test_per_page_acima_do_maximo_e_reduzido_a_50(client, catalogo):
    corpo = client.get(f"{URL}?per_page=999").get_json()

    assert corpo["por_pagina"] == 50


def test_paginacao_divide_os_itens(client, catalogo):
    corpo = client.get(f"{URL}?page=2&per_page=3").get_json()

    assert (corpo["pagina"], corpo["paginas"], len(corpo["itens"])) == (2, 3, 3)


@pytest.mark.parametrize("parametro, campo", [
    ("page=0", "page"),
    ("page=abc", "page"),
    ("per_page=0", "per_page"),
    ("tipo=cozinha", "tipo"),
    ("capacidade_min=-1", "capacidade_min"),
    ("ativa=talvez", "ativa"),
])
def test_parametro_invalido_responde_400(client, catalogo, parametro, campo):
    resposta = client.get(f"{URL}?{parametro}")

    assert resposta.status_code == 400
    assert campo in resposta.get_json()["message"]


# ---- leitura ----

def test_detalhe_da_sala(client, catalogo):
    sid = sala_id("AUD-A001")

    corpo = client.get(f"{URL}/{sid}").get_json()

    assert corpo["codigo"] == "AUD-A001"
    assert corpo["recursos"] == ["projetor", "som", "ar-condicionado"]


def test_sala_inexistente_responde_404(client):
    resposta = client.get(f"{URL}/999")

    assert resposta.status_code == 404
    assert resposta.get_json() == {"message": "Sala 999 não encontrada."}


# ---- criação ----

def test_admin_cria_sala_com_201_e_location(client, cabecalho):
    resposta = client.post(URL, json=NOVA, headers=cabecalho("admin"))

    assert resposta.status_code == 201
    corpo = resposta.get_json()
    assert corpo["codigo"] == "LAB-D301"  # normalizado em maiúsculas
    assert corpo["ativa"] is True  # padrão
    assert corpo["recursos"] == ["computadores", "GPU"]
    assert resposta.headers["Location"].endswith(f"{URL}/{corpo['id']}")


@pytest.mark.parametrize("papel", ["aluno", "professor"])
def test_somente_admin_cria_sala(client, cabecalho, papel):
    resposta = client.post(URL, json=NOVA, headers=cabecalho(papel))

    assert resposta.status_code == 403
    assert resposta.get_json() == {"message": "Acesso negado: esta ação exige o papel admin."}


def test_criar_sem_token_responde_401(client):
    assert client.post(URL, json=NOVA).status_code == 401


def test_codigo_repetido_responde_409(client, catalogo, cabecalho):
    resposta = client.post(URL, json={**NOVA, "codigo": "lab-b204"}, headers=cabecalho("admin"))

    assert resposta.status_code == 409
    assert resposta.get_json() == {"message": "Já existe uma sala com o código LAB-B204."}


@pytest.mark.parametrize("campo, valor", [
    ("tipo", "cozinha"),
    ("capacidade", 0),
    ("capacidade", "muitos"),
    ("codigo", ""),
    ("ativa", "talvez"),
])
def test_campo_invalido_na_criacao_responde_400(client, cabecalho, campo, valor):
    resposta = client.post(URL, json={**NOVA, campo: valor}, headers=cabecalho("admin"))

    assert resposta.status_code == 400
    assert campo in resposta.get_json()["message"]


# ---- substituição (PUT) ----

def test_put_substitui_todos_os_campos(client, catalogo, cabecalho):
    sid = sala_id("SALA-B110")

    resposta = client.put(f"{URL}/{sid}", json={**NOVA, "ativa": False}, headers=cabecalho("admin"))

    assert resposta.status_code == 200
    corpo = resposta.get_json()
    assert (corpo["id"], corpo["codigo"], corpo["capacidade"], corpo["ativa"]) == (sid, "LAB-D301", 30, False)


def test_put_mantendo_o_proprio_codigo_e_permitido(client, catalogo, cabecalho):
    sid = sala_id("SALA-B110")
    dados = {**NOVA, "codigo": "SALA-B110", "capacidade": 20}

    assert client.put(f"{URL}/{sid}", json=dados, headers=cabecalho("admin")).status_code == 200


def test_put_com_codigo_de_outra_sala_responde_409(client, catalogo, cabecalho):
    sid = sala_id("SALA-B110")

    resposta = client.put(f"{URL}/{sid}", json={**NOVA, "codigo": "AUD-A001"}, headers=cabecalho("admin"))

    assert resposta.status_code == 409


def test_put_sem_campo_obrigatorio_responde_400(client, catalogo, cabecalho):
    sid = sala_id("SALA-B110")
    dados = {k: v for k, v in NOVA.items() if k != "capacidade"}

    resposta = client.put(f"{URL}/{sid}", json=dados, headers=cabecalho("admin"))

    assert resposta.status_code == 400


def test_put_somente_admin(client, catalogo, cabecalho):
    sid = sala_id("SALA-B110")

    assert client.put(f"{URL}/{sid}", json=NOVA, headers=cabecalho("professor")).status_code == 403


# ---- exclusão (R10) ----

def test_r10_excluir_sala_com_reserva_futura_responde_409(client, db, catalogo, cabecalho):
    sid = sala_id("LAB-B204")  # tem reserva futura no catálogo

    resposta = client.delete(f"{URL}/{sid}", headers=cabecalho("admin"))

    assert resposta.status_code == 409
    assert db.session.get(Sala, sid) is not None


def test_r10_reserva_em_andamento_tambem_bloqueia(client, db, cabecalho, relogio_fixo):
    sala = Sala(codigo="X-1", nome="X", bloco="A", tipo="sala_aula", capacidade=10)
    agora = relogio_fixo
    sala.reservas = [Reserva(usuario_id=1, inicio=agora - timedelta(minutes=30),
                             fim=agora + timedelta(minutes=30), participantes=2, finalidade="Aula")]
    db.session.add(sala)
    db.session.commit()

    assert client.delete(f"{URL}/{sala.id}", headers=cabecalho("admin")).status_code == 409


def test_r10_excluir_sala_sem_reservas_futuras_responde_204(client, db, cabecalho, relogio_fixo):
    sala = Sala(codigo="X-2", nome="X", bloco="A", tipo="sala_aula", capacidade=10)
    ontem = relogio_fixo - timedelta(days=1)
    sala.reservas = [
        Reserva(usuario_id=1, inicio=ontem, fim=ontem + timedelta(hours=1),
                participantes=2, finalidade="Passada"),
        Reserva(usuario_id=1, inicio=ontem + timedelta(days=2), fim=ontem + timedelta(days=2, hours=1),
                participantes=2, finalidade="Cancelada", status="cancelada"),
    ]
    db.session.add(sala)
    db.session.commit()

    resposta = client.delete(f"{URL}/{sala.id}", headers=cabecalho("admin"))

    assert resposta.status_code == 204
    assert resposta.data == b""
    assert Sala.query.count() == 0
    assert Reserva.query.count() == 0


def test_excluir_somente_admin(client, catalogo, cabecalho):
    sid = sala_id("SALA-B110")

    assert client.delete(f"{URL}/{sid}", headers=cabecalho("aluno")).status_code == 403


def test_excluir_sala_inexistente_responde_404(client, cabecalho):
    assert client.delete(f"{URL}/999", headers=cabecalho("admin")).status_code == 404
