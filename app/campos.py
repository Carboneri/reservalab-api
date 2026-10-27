from flask_restful import fields

# Formato de saída do usuário: só o que está aqui vai para o JSON.
# senha_hash fica de fora de propósito.
usuario_campos = {
    "id": fields.Integer,
    "nome": fields.String,
    "email": fields.String,
    "papel": fields.String,
    "criado_em": fields.DateTime(dt_format="iso8601"),
}

sala_campos = {
    "id": fields.Integer,
    "codigo": fields.String,
    "nome": fields.String,
    "bloco": fields.String,
    "tipo": fields.String,
    "capacidade": fields.Integer,
    # Lido da propriedade Sala.recursos, que já devolve uma lista.
    "recursos": fields.List(fields.String),
    "ativa": fields.Boolean,
    # Link para a própria sala, gerado com url_for a partir do endpoint "sala".
    "url": fields.Url("sala"),
}


def paginado(campos_item):
    """Envelope da SPEC a partir do objeto Pagination do Flask-SQLAlchemy.

    "attribute" mapeia o nome no JSON para o nome do atributo em Python.
    """
    return {
        "itens": fields.List(fields.Nested(campos_item), attribute="items"),
        "pagina": fields.Integer(attribute="page"),
        "por_pagina": fields.Integer(attribute="per_page"),
        "total": fields.Integer,
        "paginas": fields.Integer(attribute="pages"),
    }


reserva_campos = {
    "id": fields.Integer,
    # Nested: objetos relacionados entram resumidos dentro da reserva.
    "sala": fields.Nested({
        "id": fields.Integer,
        "codigo": fields.String,
        "nome": fields.String,
    }),
    "usuario": fields.Nested({
        "id": fields.Integer,
        "nome": fields.String,
    }),
    "inicio": fields.DateTime(dt_format="iso8601"),
    "fim": fields.DateTime(dt_format="iso8601"),
    "participantes": fields.Integer,
    "finalidade": fields.String,
    "status": fields.String,
    "criado_em": fields.DateTime(dt_format="iso8601"),
    "url": fields.Url("reserva"),
}

# Corpo extra do 409 (R4): o mínimo para o cliente entender o conflito,
# sem expor quem fez a outra reserva.
conflito_campos = {
    "id": fields.Integer,
    "inicio": fields.DateTime(dt_format="iso8601"),
    "fim": fields.DateTime(dt_format="iso8601"),
}


faixa_campos = {
    "inicio": fields.DateTime(dt_format="iso8601"),
    "fim": fields.DateTime(dt_format="iso8601"),
}

disponibilidade_campos = {
    "sala": fields.Nested({
        "id": fields.Integer,
        "codigo": fields.String,
        "nome": fields.String,
        "ativa": fields.Boolean,
        "url": fields.Url("sala"),
    }),
    "data": fields.String,
    "ocupado": fields.List(fields.Nested({**faixa_campos, "reserva_id": fields.Integer})),
    "livre": fields.List(fields.Nested(faixa_campos)),
}
