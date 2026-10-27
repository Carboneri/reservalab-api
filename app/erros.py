from flask import request
from flask_restful import Api, abort
from werkzeug.exceptions import HTTPException
from werkzeug.routing import IntegerConverter

from app.parsers import MAIOR_INTEIRO

MENSAGENS_PADRAO = {
    400: "Requisição inválida: verifique se o corpo é um JSON válido.",
    404: "Recurso não encontrado.",
    405: "Método não permitido.",
    415: "Envie o corpo da requisição como JSON (Content-Type: application/json).",
    500: "Erro interno do servidor.",
}


class ApiReservaLab(Api):
    """Api que troca as mensagens padrão (em inglês) do Werkzeug por português.

    Erros levantados dentro de um Resource passam por aqui, não pelos
    errorhandlers do Flask.
    """

    def handle_error(self, e):
        codigo = e.code if isinstance(e, HTTPException) else 500
        # abort(..., message=...) já preenche e.data; essa mensagem tem prioridade.
        if codigo in MENSAGENS_PADRAO and not getattr(e, "data", None):
            e.data = {"message": MENSAGENS_PADRAO[codigo]}
        return super().handle_error(e)


class InteiroLimitado(IntegerConverter):
    """Conversor <int:...> com teto: id maior que o banco suporta não casa com a
    rota (404), em vez de chegar ao SQLite e estourar (500)."""

    def __init__(self, url_map, *args, **kwargs):
        kwargs.setdefault("max", MAIOR_INTEIRO)
        super().__init__(url_map, *args, **kwargs)


def exigir_objeto_json():
    """O reqparse espera um objeto {...}; uma lista ou string no corpo o quebraria."""
    if request.is_json and request.get_data():
        corpo = request.get_json(silent=True)  # malformado → None; o reqparse responde 400 depois
        if corpo is not None and not isinstance(corpo, dict):
            abort(400, message="Requisição inválida: o corpo deve ser um objeto JSON ({...}).")


def registrar_handlers(app):
    """Errorhandlers do Flask para erros fora dos Resources (ex.: rota inexistente)."""

    def responder(erro):
        codigo = erro.code if isinstance(erro, HTTPException) else 500
        return {"message": MENSAGENS_PADRAO[codigo]}, codigo

    for codigo in MENSAGENS_PADRAO:
        app.register_error_handler(codigo, responder)

    # Com PROPAGATE_EXCEPTIONS ligado, exceções sem handler escapariam como HTML;
    # este handler genérico garante o 500 em JSON. Handlers mais específicos
    # (como os do JWT) continuam tendo prioridade.
    @app.errorhandler(Exception)
    def erro_inesperado(erro):
        if isinstance(erro, HTTPException):
            return erro
        app.logger.exception("Erro não tratado")
        return {"message": MENSAGENS_PADRAO[500]}, 500
