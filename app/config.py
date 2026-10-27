import os
import secrets
from datetime import timedelta

from dotenv import load_dotenv

# Lê o .env da raiz do projeto; segredos nunca ficam no código.
load_dotenv()


class Config:
    # Mantém acentos legíveis no JSON: "Auditório", e não "Audit\u00f3rio".
    RESTFUL_JSON = {"ensure_ascii": False}
    # Desliga a dica em inglês que o Flask-RESTful anexa aos erros 404.
    ERROR_404_HELP = False
    # Sem isto o Flask-RESTful captura as exceções do JWT antes dos handlers
    # do Flask-JWT-Extended e responde 500 em vez de 401.
    PROPAGATE_EXCEPTIONS = True
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(minutes=int(os.environ.get("JWT_EXPIRA_MIN", "60")))


class Desenvolvimento(Config):
    DEBUG = True
    SECRET_KEY = os.environ.get("SECRET_KEY")
    JWT_SECRET_KEY = os.environ.get("JWT_SECRET_KEY")
    # Caminho relativo: o Flask-SQLAlchemy cria o arquivo na pasta instance/.
    SQLALCHEMY_DATABASE_URI = "sqlite:///reservalab.db"


class Teste(Config):
    TESTING = True
    # Chaves aleatórias a cada execução: os testes não dependem do .env.
    SECRET_KEY = secrets.token_hex(32)
    JWT_SECRET_KEY = secrets.token_hex(32)
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"


configuracoes = {
    "desenvolvimento": Desenvolvimento,
    "teste": Teste,
}
