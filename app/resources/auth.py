from flask import current_app
from flask_jwt_extended import create_access_token
from flask_restful import Resource, abort, marshal_with

from app.campos import usuario_campos
from app.parsers import login_parser, registro_parser
from app.services import usuarios
from app.services.excecoes import EmailJaCadastrado


class RegistroResource(Resource):
    # marshal_with filtra a saída pelos campos declarados em campos.py.
    @marshal_with(usuario_campos)
    def post(self):
        dados = registro_parser.parse_args()  # campo inválido → 400 automático
        try:
            usuario = usuarios.registrar(dados["nome"], dados["email"], dados["senha"])
        except EmailJaCadastrado:
            abort(409, message="E-mail já cadastrado.")
        return usuario, 201


class LoginResource(Resource):
    def post(self):
        dados = login_parser.parse_args()
        usuario = usuarios.autenticar(dados["email"], dados["senha"])
        if usuario is None:
            # Mensagem genérica: não diz se o erro foi no e-mail ou na senha.
            abort(401, message="E-mail ou senha inválidos.")

        token = create_access_token(
            identity=str(usuario.id),  # o "sub" do JWT precisa ser texto
            additional_claims={"papel": usuario.papel},
        )
        expira = current_app.config["JWT_ACCESS_TOKEN_EXPIRES"]
        return {
            "access_token": token,
            "token_type": "Bearer",
            "expira_em_min": int(expira.total_seconds() // 60),
        }
