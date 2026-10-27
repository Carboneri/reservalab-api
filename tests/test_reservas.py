"""Reservas: R1–R9, ordem de validação, listagem e cancelamento.

O relógio está congelado em segunda, 09/11/2026 09:00 (fixture relogio_fixo).
"""
from datetime import datetime
from types import SimpleNamespace

import pytest

from app.models import Reserva, Sala, Usuario

URL = "/api/v1/reservas"
AMANHA = "2026-11-10"


@pytest.fixture
def cenario(db, relogio_fixo, cabecalho):
    def usuario(nome, papel):
        u = Usuario(nome=nome, email=f"{nome.lower()}@reservalab.dev", papel=papel)
        u.definir_senha("x")
        db.session.add(u)
        return u

    def sala(codigo, tipo="laboratorio", capacidade=20, ativa=True):
        s = Sala(codigo=codigo, nome=f"Sala {codigo}", bloco="B", tipo=tipo,
                 capacidade=capacidade, ativa=ativa)
        db.session.add(s)
        return s

    c = SimpleNamespace(
        admin=usuario("Ana", "admin"), prof=usuario("Paulo", "professor"),
        aluno=usuario("Alice", "aluno"), aluno2=usuario("Bruno", "aluno"),
        lab=sala("LAB-1"), aud=sala("AUD-1", tipo="auditorio", capacidade=100),
        inativa=sala("SALA-X", tipo="sala_aula", ativa=False),
        aud_inativo=sala("AUD-X", tipo="auditorio", capacidade=100, ativa=False),
    )
    db.session.commit()
    c.h = lambda u: cabecalho(u.papel, u.id)
    return c


def corpo(sala, inicio="14:00", fim="16:00", dia=AMANHA, participantes=5, **extra):
    return {"sala_id": sala.id, "inicio": f"{dia}T{inicio}:00", "fim": f"{dia}T{fim}:00",
            "participantes": participantes, "finalidade": "Estudo", **extra}


def reservar(client, c, usuario, sala, **kw):
    return client.post(URL, json=corpo(sala, **kw), headers=c.h(usuario))


# ---- criação feliz ----

def test_cria_reserva_201_com_location_e_aninhados(client, cenario):
    c = cenario
    resposta = reservar(client, c, c.aluno, c.lab)

    assert resposta.status_code == 201
    r = resposta.get_json()
    assert r["status"] == "confirmada"
    assert r["inicio"] == f"{AMANHA}T14:00:00"
    assert r["sala"] == {"id": c.lab.id, "codigo": "LAB-1", "nome": "Sala LAB-1"}
    assert r["usuario"] == {"id": c.aluno.id, "nome": "Alice"}
    assert r["url"] == f"{URL}/{r['id']}"
    assert resposta.headers["Location"].endswith(r["url"])


def test_criar_sem_token_responde_401(client, cenario):
    assert client.post(URL, json=corpo(cenario.lab)).status_code == 401


# ---- formato (reqparse) ----

@pytest.mark.parametrize("campo, valor", [
    ("inicio", "10/11/2026 14:00"),
    ("inicio", "2026-11-10T14:00:00-03:00"),  # com fuso
    ("participantes", 0),
    ("sala_id", "abc"),
    ("finalidade", ""),
    ("finalidade", "x" * 121),
])
def test_formato_invalido_responde_400_no_campo(client, cenario, campo, valor):
    c = cenario
    resposta = client.post(URL, json={**corpo(c.lab), campo: valor}, headers=c.h(c.aluno))

    assert resposta.status_code == 400
    assert campo in resposta.get_json()["message"]


# ---- R1, R2, R3 ----

@pytest.mark.parametrize("inicio, fim, trecho", [
    ("14:00", "14:00", "depois do início"),   # R1 fim igual
    ("14:00", "13:00", "depois do início"),   # R1 fim antes
    ("14:00", "14:29", "30 minutos"),         # R1 curta
    ("14:00", "18:01", "4 horas"),            # R1 longa
    ("07:00", "08:00", "07:30"),              # R3 antes da abertura
    ("21:30", "22:31", "07:30"),              # R3 depois do fechamento
])
def test_r1_r3_horario_invalido_responde_400(client, cenario, inicio, fim, trecho):
    c = cenario
    resposta = reservar(client, c, c.prof, c.lab, inicio=inicio, fim=fim)

    assert resposta.status_code == 400
    assert trecho in resposta.get_json()["message"]


def test_r1_limites_exatos_sao_aceitos(client, cenario):
    c = cenario
    assert reservar(client, c, c.prof, c.lab, inicio="08:00", fim="08:30").status_code == 201
    assert reservar(client, c, c.prof, c.lab, inicio="09:00", fim="13:00").status_code == 201


def test_r3_janela_completa_e_fim_as_22_30_sao_aceitos(client, cenario):
    c = cenario
    assert reservar(client, c, c.prof, c.lab, inicio="07:30", fim="09:00").status_code == 201
    assert reservar(client, c, c.prof, c.lab, inicio="19:00", fim="22:30").status_code == 201


def test_r3_inicio_e_fim_em_dias_diferentes_responde_400(client, cenario):
    c = cenario
    dados = {**corpo(c.lab), "inicio": "2026-11-10T22:00:00", "fim": "2026-11-11T00:30:00"}

    assert client.post(URL, json=dados, headers=c.h(c.prof)).status_code == 400


def test_r2_reserva_no_passado_responde_400(client, cenario):
    c = cenario
    resposta = reservar(client, c, c.prof, c.lab, dia="2026-11-09", inicio="08:00", fim="09:00")

    assert resposta.status_code == 400
    assert resposta.get_json() == {"message": "Não é possível reservar no passado."}


# ---- sala, R6, R7, R5, R8 ----

def test_sala_inexistente_responde_404(client, cenario):
    c = cenario
    resposta = client.post(URL, json={**corpo(c.lab), "sala_id": 999}, headers=c.h(c.prof))

    assert resposta.status_code == 404
    assert resposta.get_json() == {"message": "Sala 999 não encontrada."}


def test_r6_sala_inativa_responde_422(client, cenario):
    c = cenario
    resposta = reservar(client, c, c.prof, c.inativa)

    assert resposta.status_code == 422
    assert "inativa" in resposta.get_json()["message"]


def test_r7_aluno_nao_reserva_auditorio_403(client, cenario):
    c = cenario
    resposta = reservar(client, c, c.aluno, c.aud)

    assert resposta.status_code == 403
    assert "Auditórios" in resposta.get_json()["message"]


@pytest.mark.parametrize("quem", ["prof", "admin"])
def test_r7_professor_e_admin_reservam_auditorio(client, cenario, quem):
    c = cenario
    assert reservar(client, c, getattr(c, quem), c.aud).status_code == 201


def test_r5_participantes_acima_da_capacidade_responde_422(client, cenario):
    c = cenario
    resposta = reservar(client, c, c.prof, c.lab, participantes=21)

    assert resposta.status_code == 422
    assert "comporta 20" in resposta.get_json()["message"]


def test_r5_lotacao_exata_e_aceita(client, cenario):
    c = cenario
    assert reservar(client, c, c.prof, c.lab, participantes=20).status_code == 201


def test_r8_quarta_reserva_futura_do_aluno_responde_422(client, cenario):
    c = cenario
    for inicio, fim in [("08:00", "09:00"), ("10:00", "11:00"), ("12:00", "13:00")]:
        assert reservar(client, c, c.aluno, c.lab, inicio=inicio, fim=fim).status_code == 201

    resposta = reservar(client, c, c.aluno, c.lab, inicio="15:00", fim="16:00")

    assert resposta.status_code == 422
    assert "no máximo 3" in resposta.get_json()["message"]


def test_r8_reserva_cancelada_libera_vaga_do_aluno(client, cenario):
    c = cenario
    ids = [reservar(client, c, c.aluno, c.lab, inicio=i, fim=f).get_json()["id"]
           for i, f in [("08:00", "09:00"), ("10:00", "11:00"), ("12:00", "13:00")]]
    client.delete(f"{URL}/{ids[0]}", headers=c.h(c.aluno))

    assert reservar(client, c, c.aluno, c.lab, inicio="15:00", fim="16:00").status_code == 201


def test_r8_nao_se_aplica_a_professor(client, cenario):
    c = cenario
    for hora in ("08", "10", "12", "14"):
        resposta = reservar(client, c, c.prof, c.lab, inicio=f"{hora}:00", fim=f"{hora}:30")
        assert resposta.status_code == 201


# ---- R4 conflito ----

@pytest.mark.parametrize("inicio, fim", [
    ("12:00", "14:00"),  # termina quando a existente começa
    ("16:00", "18:00"),  # começa quando a existente termina
])
def test_r4_horarios_encostados_nao_conflitam(client, cenario, inicio, fim):
    c = cenario
    reservar(client, c, c.prof, c.lab)  # 14:00–16:00

    assert reservar(client, c, c.admin, c.lab, inicio=inicio, fim=fim).status_code == 201


@pytest.mark.parametrize("inicio, fim", [
    ("13:00", "15:00"),  # sobrepõe o início
    ("15:00", "17:00"),  # sobrepõe o fim
    ("14:30", "15:30"),  # contida na existente
    ("13:00", "17:00"),  # contém a existente
    ("14:00", "16:00"),  # idêntica
])
def test_r4_sobreposicao_responde_409_com_a_reserva_conflitante(client, cenario, inicio, fim):
    c = cenario
    existente = reservar(client, c, c.prof, c.lab).get_json()

    resposta = reservar(client, c, c.admin, c.lab, inicio=inicio, fim=fim)

    assert resposta.status_code == 409
    assert resposta.get_json() == {
        "message": "A sala já está reservada nesse horário.",
        "conflito": {"id": existente["id"], "inicio": f"{AMANHA}T14:00:00",
                     "fim": f"{AMANHA}T16:00:00"},
    }


def test_r4_outra_sala_no_mesmo_horario_nao_conflita(client, cenario):
    c = cenario
    reservar(client, c, c.prof, c.lab)

    assert reservar(client, c, c.prof, c.aud).status_code == 201


def test_r4_reserva_cancelada_nao_bloqueia_o_horario(client, cenario):
    c = cenario
    existente = reservar(client, c, c.prof, c.lab).get_json()
    client.delete(f"{URL}/{existente['id']}", headers=c.h(c.prof))

    assert reservar(client, c, c.admin, c.lab).status_code == 201


# ---- ordem de validação ----

def test_ordem_horario_vem_antes_da_sala(client, cenario):
    c = cenario
    dados = {**corpo(c.lab, dia="2026-11-09", inicio="08:00", fim="09:00"), "sala_id": 999}

    assert client.post(URL, json=dados, headers=c.h(c.aluno)).status_code == 400  # R2, não 404


def test_ordem_r6_antes_de_r7(client, cenario):
    c = cenario
    assert reservar(client, c, c.aluno, c.aud_inativo).status_code == 422  # inativa, não 403


def test_ordem_r7_antes_de_r5(client, cenario):
    c = cenario
    assert reservar(client, c, c.aluno, c.aud, participantes=500).status_code == 403


def test_ordem_r5_antes_de_r8(client, cenario):
    c = cenario
    for inicio, fim in [("08:00", "09:00"), ("10:00", "11:00"), ("12:00", "13:00")]:
        reservar(client, c, c.aluno, c.lab, inicio=inicio, fim=fim)

    resposta = reservar(client, c, c.aluno, c.lab, participantes=99)

    assert resposta.status_code == 422
    assert "comporta" in resposta.get_json()["message"]  # R5, não o limite do R8


def test_ordem_r8_antes_de_r4(client, cenario):
    c = cenario
    for inicio, fim in [("08:00", "09:00"), ("10:00", "11:00"), ("12:00", "13:00")]:
        reservar(client, c, c.aluno, c.lab, inicio=inicio, fim=fim)

    # Mesmo horário de uma reserva existente: o limite (422) aparece antes do conflito (409).
    assert reservar(client, c, c.aluno, c.lab, inicio="08:00", fim="09:00").status_code == 422


# ---- listagem ----

@pytest.fixture
def varias(client, cenario):
    c = cenario
    reservar(client, c, c.aluno, c.lab, inicio="10:00", fim="11:00")
    reservar(client, c, c.aluno, c.lab, inicio="08:00", fim="09:00")
    reservar(client, c, c.aluno2, c.lab, dia="2026-11-11", inicio="08:00", fim="09:00")
    reservar(client, c, c.prof, c.aud)
    return c


def test_aluno_lista_so_as_proprias_em_ordem_de_inicio(client, varias):
    c = varias
    r = client.get(URL, headers=c.h(c.aluno)).get_json()

    assert r["total"] == 2
    assert [i["inicio"][11:16] for i in r["itens"]] == ["08:00", "10:00"]
    assert {i["usuario"]["nome"] for i in r["itens"]} == {"Alice"}


def test_professor_lista_so_as_proprias(client, varias):
    c = varias
    r = client.get(URL, headers=c.h(c.prof)).get_json()

    assert [i["sala"]["codigo"] for i in r["itens"]] == ["AUD-1"]


def test_admin_lista_todas(client, varias):
    c = varias
    assert client.get(URL, headers=c.h(c.admin)).get_json()["total"] == 4


@pytest.mark.parametrize("filtro, total", [
    ("data=2026-11-11", 1),
    ("data=2026-11-10", 3),
    ("status=cancelada", 0),
    ("status=confirmada", 4),
])
def test_filtros_da_listagem(client, varias, filtro, total):
    c = varias
    assert client.get(f"{URL}?{filtro}", headers=c.h(c.admin)).get_json()["total"] == total


def test_filtro_por_sala(client, varias):
    c = varias
    r = client.get(f"{URL}?sala_id={c.aud.id}", headers=c.h(c.admin)).get_json()

    assert r["total"] == 1


@pytest.mark.parametrize("filtro", ["data=10-11-2026", "status=pendente", "sala_id=0", "page=0"])
def test_filtro_invalido_responde_400(client, varias, filtro):
    c = varias
    assert client.get(f"{URL}?{filtro}", headers=c.h(c.admin)).status_code == 400


def test_listar_sem_token_responde_401(client, cenario):
    assert client.get(URL).status_code == 401


# ---- detalhe ----

def test_dono_e_admin_veem_a_reserva(client, cenario):
    c = cenario
    rid = reservar(client, c, c.aluno, c.lab).get_json()["id"]

    assert client.get(f"{URL}/{rid}", headers=c.h(c.aluno)).status_code == 200
    assert client.get(f"{URL}/{rid}", headers=c.h(c.admin)).status_code == 200


def test_reserva_de_outro_usuario_responde_404_igual_a_inexistente(client, cenario):
    c = cenario
    rid = reservar(client, c, c.aluno, c.lab).get_json()["id"]

    de_outro = client.get(f"{URL}/{rid}", headers=c.h(c.aluno2))
    inexistente = client.get(f"{URL}/999", headers=c.h(c.aluno2))

    assert de_outro.status_code == inexistente.status_code == 404
    assert de_outro.get_json() == {"message": f"Reserva {rid} não encontrada."}


# ---- cancelamento (R9) ----

def test_r9_dono_cancela_com_204_e_reserva_continua_no_banco(client, cenario, db):
    c = cenario
    rid = reservar(client, c, c.aluno, c.lab).get_json()["id"]

    resposta = client.delete(f"{URL}/{rid}", headers=c.h(c.aluno))

    assert resposta.status_code == 204
    assert resposta.data == b""
    assert db.session.get(Reserva, rid).status == "cancelada"


def test_r9_admin_cancela_reserva_de_outro(client, cenario):
    c = cenario
    rid = reservar(client, c, c.aluno, c.lab).get_json()["id"]

    assert client.delete(f"{URL}/{rid}", headers=c.h(c.admin)).status_code == 204


def test_r9_outro_usuario_recebe_404_e_nada_muda(client, cenario, db):
    c = cenario
    rid = reservar(client, c, c.aluno, c.lab).get_json()["id"]

    assert client.delete(f"{URL}/{rid}", headers=c.h(c.prof)).status_code == 404
    assert db.session.get(Reserva, rid).status == "confirmada"


def test_r9_reserva_ja_cancelada_responde_409(client, cenario):
    c = cenario
    rid = reservar(client, c, c.aluno, c.lab).get_json()["id"]
    client.delete(f"{URL}/{rid}", headers=c.h(c.aluno))

    resposta = client.delete(f"{URL}/{rid}", headers=c.h(c.aluno))

    assert resposta.status_code == 409
    assert resposta.get_json() == {"message": "A reserva já está cancelada."}


def test_r9_reserva_ja_iniciada_responde_409(client, cenario, db, relogio_fixo):
    c = cenario
    em_andamento = Reserva(sala_id=c.lab.id, usuario_id=c.aluno.id,
                           inicio=datetime(2026, 11, 9, 8, 30), fim=datetime(2026, 11, 9, 10, 0),
                           participantes=3, finalidade="Começou às 08:30")
    db.session.add(em_andamento)
    db.session.commit()

    resposta = client.delete(f"{URL}/{em_andamento.id}", headers=c.h(c.aluno))

    assert resposta.status_code == 409
    assert "já começou" in resposta.get_json()["message"]
