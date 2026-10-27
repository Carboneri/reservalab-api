from functools import wraps

from flask_jwt_extended import get_jwt, verify_jwt_in_request
from flask_restful import abort

from app.extensions import jwt


def papel_requerido(*papeis):
    """Libera o método só para os papéis informados; os demais recebem 403."""

    def decorator(funcao):
        @wraps(funcao)
        def wrapper(*args, **kwargs):
            verify_jwt_in_request()  # sem token válido → 401 (callbacks abaixo)
            # O papel vem no próprio token (claim adicional), sem consultar o banco.
            if get_jwt().get("papel") not in papeis:
                abort(403, message=f"Acesso negado: esta ação exige o papel {' ou '.join(papeis)}.")
            return funcao(*args, **kwargs)

        return wrapper

    return decorator


# Callbacks do Flask-JWT-Extended: mesmas regras de erro do resto da API
# (status 401, chave "message", texto em português).
@jwt.unauthorized_loader
def token_ausente(motivo):
    return {"message": "Token de acesso ausente. Envie o cabeçalho Authorization: Bearer <token>."}, 401


@jwt.invalid_token_loader
def token_invalido(motivo):
    return {"message": "Token de acesso inválido."}, 401


@jwt.expired_token_loader
def token_expirado(cabecalho, dados):
    return {"message": "Token de acesso expirado. Faça login novamente."}, 401
