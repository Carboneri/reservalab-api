from datetime import datetime, timedelta
from itertools import count

import pytest
from flask_jwt_extended import create_access_token

from app import create_app
from app.extensions import db as _db
from app.models import Reserva, Sala, Usuario
from app.services import relogio

SENHA_PADRAO = "senha123"


@pytest.fixture
def app():
    app = create_app("teste")  # SQLite em memória, chaves aleatórias
    with app.app_context():
        _db.create_all()
        yield app
        _db.session.remove()
        _db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def db(app):
    return _db


# ---- fábricas de usuário e token ----

@pytest.fixture
def criar_usuario(db):
    """criar_usuario("professor") → Usuario salvo, com e-mail único e SENHA_PADRAO."""
    numeros = count(1)

    def criar(papel="aluno", nome=None):
        n = next(numeros)
        usuario = Usuario(nome=nome or f"{papel.title()} {n}", email=f"{papel}{n}@teste.dev", papel=papel)
        usuario.definir_senha(SENHA_PADRAO)
        db.session.add(usuario)
        db.session.commit()
        return usuario

    return criar


@pytest.fixture
def token_de(client, criar_usuario):
    """token_de("admin") → (usuario, cabeçalho Authorization), via login de verdade."""

    def obter(papel="aluno", usuario=None):
        usuario = usuario or criar_usuario(papel)
        resposta = client.post("/api/v1/auth/login", json={"email": usuario.email, "senha": SENHA_PADRAO})
        return usuario, {"Authorization": f"Bearer {resposta.get_json()['access_token']}"}

    return obter


@pytest.fixture
def cabecalho(app):
    """Atalho sem banco: cabecalho("admin") → cabeçalho com token desse papel."""

    def gerar(papel, usuario_id=1):
        token = create_access_token(identity=str(usuario_id), additional_claims={"papel": papel})
        return {"Authorization": f"Bearer {token}"}

    return gerar


# ---- tempo ----

@pytest.fixture
def relogio_fixo(monkeypatch):
    """Congela relogio.agora() numa segunda-feira, 09/11/2026 às 09:00."""
    agora = datetime(2026, 11, 9, 9, 0)
    monkeypatch.setattr(relogio, "agora", lambda: agora)
    return agora


# ---- catálogo de salas (independente do flask seed) ----

SALAS_EXEMPLO = [
    # (codigo, bloco, tipo, capacidade, recursos, ativa)
    ("LAB-B204", "B", "laboratorio", 40, ["computadores", "projetor", "ar-condicionado"], True),
    ("LAB-B206", "B", "laboratorio", 30, ["computadores", "projetor"], True),
    ("LAB-C101", "C", "laboratorio", 25, ["bancadas", "projetor"], True),
    ("SALA-A101", "A", "sala_aula", 45, ["projetor", "quadro-branco"], True),
    ("SALA-A102", "A", "sala_aula", 45, ["quadro-branco", "ar-condicionado"], True),
    ("SALA-B110", "B", "sala_aula", 15, ["quadro-branco"], True),
    ("SALA-C203", "C", "sala_aula", 35, ["projetor"], False),
    ("AUD-A001", "A", "auditorio", 200, ["projetor", "som", "ar-condicionado"], True),
]


@pytest.fixture
def catalogo(db, criar_usuario):
    """8 salas em 3 blocos (1 auditório, 1 inativa) e uma reserva confirmada
    amanhã no LAB-B204, com data relativa ao relógio."""
    salas = {}
    for codigo, bloco, tipo, capacidade, recursos, ativa in SALAS_EXEMPLO:
        salas[codigo] = Sala(codigo=codigo, nome=f"Sala {codigo}", bloco=bloco, tipo=tipo,
                             capacidade=capacidade, recursos=recursos, ativa=ativa)
        db.session.add(salas[codigo])

    amanha = (relogio.agora() + timedelta(days=1)).replace(hour=10, minute=0, second=0, microsecond=0)
    db.session.add(Reserva(sala=salas["LAB-B204"], usuario=criar_usuario("professor"),
                           inicio=amanha, fim=amanha + timedelta(hours=2),
                           participantes=20, finalidade="Aula"))
    db.session.commit()
    return salas
