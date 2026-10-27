from datetime import date, datetime

from app.models import Reserva, Sala
from app.services.disponibilidade import calcular_faixas

DIA = date(2026, 11, 10)


def h(hora):
    return datetime.fromisoformat(f"2026-11-10T{hora}")


# ---- função pura ----

def test_dia_sem_reservas_esta_todo_livre():
    ocupado, livre = calcular_faixas(DIA, [])

    assert ocupado == []
    assert livre == [{"inicio": h("07:30"), "fim": h("22:30")}]


def test_reservas_dividem_a_janela_em_faixas():
    ocupado, livre = calcular_faixas(DIA, [
        (h("14:00"), h("15:00"), 2),  # fora de ordem de propósito
        (h("08:00"), h("10:00"), 1),
    ])

    assert ocupado == [
        {"inicio": h("08:00"), "fim": h("10:00"), "reserva_id": 1},
        {"inicio": h("14:00"), "fim": h("15:00"), "reserva_id": 2},
    ]
    assert livre == [
        {"inicio": h("07:30"), "fim": h("08:00")},
        {"inicio": h("10:00"), "fim": h("14:00")},
        {"inicio": h("15:00"), "fim": h("22:30")},
    ]


def test_reservas_encostadas_nao_geram_faixa_livre_vazia():
    _, livre = calcular_faixas(DIA, [
        (h("07:30"), h("10:00"), 1),
        (h("10:00"), h("22:30"), 2),
    ])

    assert livre == []


# ---- endpoint ----

def test_disponibilidade_endpoint(client, db):
    sala = Sala(codigo="LAB-1", nome="Lab", bloco="B", tipo="laboratorio", capacidade=10)
    db.session.add(sala)
    db.session.flush()
    db.session.add_all([
        Reserva(sala_id=sala.id, usuario_id=1, inicio=h("08:00"), fim=h("10:00"),
                participantes=5, finalidade="Aula"),
        Reserva(sala_id=sala.id, usuario_id=1, inicio=h("13:00"), fim=h("14:00"),
                participantes=5, finalidade="Cancelada", status="cancelada"),
    ])
    db.session.commit()

    resposta = client.get(f"/api/v1/salas/{sala.id}/disponibilidade?data=2026-11-10")

    assert resposta.status_code == 200
    corpo = resposta.get_json()
    assert corpo["data"] == "2026-11-10"
    assert corpo["sala"]["codigo"] == "LAB-1"
    assert corpo["sala"]["url"] == f"/api/v1/salas/{sala.id}"
    # A reserva cancelada não ocupa a sala.
    assert corpo["ocupado"] == [{"inicio": "2026-11-10T08:00:00", "fim": "2026-11-10T10:00:00",
                                 "reserva_id": 1}]
    assert corpo["livre"] == [
        {"inicio": "2026-11-10T07:30:00", "fim": "2026-11-10T08:00:00"},
        {"inicio": "2026-11-10T10:00:00", "fim": "2026-11-10T22:30:00"},
    ]


def test_sala_inativa_nao_tem_faixa_livre(client, db):
    sala = Sala(codigo="X-9", nome="X", bloco="C", tipo="sala_aula", capacidade=10, ativa=False)
    db.session.add(sala)
    db.session.commit()

    corpo = client.get(f"/api/v1/salas/{sala.id}/disponibilidade?data=2026-11-10").get_json()

    assert corpo["livre"] == []
    assert corpo["sala"]["ativa"] is False


def test_disponibilidade_sem_data_ou_data_invalida_responde_400(client, catalogo):
    for url in ("/api/v1/salas/1/disponibilidade", "/api/v1/salas/1/disponibilidade?data=10/11/2026"):
        resposta = client.get(url)
        assert resposta.status_code == 400
        assert resposta.get_json() == {"message": {"data": "Informe a data no formato AAAA-MM-DD."}}


def test_disponibilidade_de_sala_inexistente_responde_404(client):
    resposta = client.get("/api/v1/salas/999/disponibilidade?data=2026-11-10")

    assert resposta.status_code == 404
