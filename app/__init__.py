import os

from flask import Flask

from app.comandos import init_db, seed
from app.config import configuracoes
from app.erros import ApiReservaLab, InteiroLimitado, exigir_objeto_json, registrar_handlers
from app.extensions import db, jwt
from app.resources.auth import LoginResource, RegistroResource
from app.resources.health import HealthResource
from app.resources.reservas import ReservaListResource, ReservaResource
from app.resources.salas import SalaDisponibilidadeResource, SalaListResource, SalaResource
from app.resources.usuarios import UsuarioMeResource
from app.swagger import configurar_swagger


def create_app(nome_config="desenvolvimento"):
    """Application factory: cada chamada monta um app novo (útil nos testes)."""
    app = Flask(__name__)
    app.config.from_object(configuracoes[nome_config])

    if not app.config.get("SECRET_KEY") or not app.config.get("JWT_SECRET_KEY"):
        raise RuntimeError("Defina SECRET_KEY e JWT_SECRET_KEY no .env (veja .env.example).")

    # Mesmo efeito de RESTFUL_JSON para as respostas que o próprio Flask serializa.
    app.json.ensure_ascii = False
    # <int:...> nas rotas passa a ter teto (ver InteiroLimitado); precisa vir antes das rotas.
    app.url_map.converters["int"] = InteiroLimitado
    app.before_request(exigir_objeto_json)

    os.makedirs(app.instance_path, exist_ok=True)
    db.init_app(app)
    jwt.init_app(app)

    # Importa os modelos (tabelas) e os callbacks do JWT definidos em auth.py.
    from app import auth, models  # noqa: F401

    # Api agrupa os Resources; o prefixo vale para todas as rotas registradas.
    # ApiReservaLab é a Api do Flask-RESTful com mensagens de erro em português.
    api = ApiReservaLab(app, prefix="/api/v1")
    # add_resource liga uma classe Resource a uma URL.
    api.add_resource(HealthResource, "/health")
    api.add_resource(RegistroResource, "/auth/registro")
    api.add_resource(LoginResource, "/auth/login")
    api.add_resource(UsuarioMeResource, "/usuarios/me")
    api.add_resource(SalaListResource, "/salas")
    # endpoint="sala" é o nome usado por url_for e pelo fields.Url.
    api.add_resource(SalaResource, "/salas/<int:sala_id>", endpoint="sala")
    api.add_resource(SalaDisponibilidadeResource, "/salas/<int:sala_id>/disponibilidade")
    api.add_resource(ReservaListResource, "/reservas")
    api.add_resource(ReservaResource, "/reservas/<int:reserva_id>", endpoint="reserva")

    # Sem isto, erros fora dos Resources saem como HTML em inglês.
    registrar_handlers(app)

    configurar_swagger(app)  # documentação interativa em /apidocs

    app.cli.add_command(init_db)
    app.cli.add_command(seed)
    return app
