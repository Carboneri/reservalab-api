"""Swagger UI em /apidocs, montado a partir dos YAML em docs/swagger/.

A documentação fica fora dos Resources de propósito: o código HTTP continua
curto e legível, e cada arquivo YAML cobre uma tag (Saúde, Salas...).
"""
from pathlib import Path

import yaml
from flasgger import Swagger

PASTA = Path(__file__).resolve().parent.parent / "docs" / "swagger"
ARQUIVOS_DE_CAMINHOS = ("saude.yml", "autenticacao.yml", "salas.yml", "reservas.yml")


def _ler(nome):
    with open(PASTA / nome, encoding="utf-8") as arquivo:
        return yaml.safe_load(arquivo)


def montar_especificacao():
    especificacao = {"openapi": "3.0.3", **_ler("base.yml"), "paths": {}}
    for nome in ARQUIVOS_DE_CAMINHOS:
        especificacao["paths"].update(_ler(nome))
    return especificacao


def configurar_swagger(app):
    config = {
        **Swagger.DEFAULT_CONFIG,
        "openapi": "3.0.3",
        "title": "ReservaLab API",
        # Só os caminhos dos YAML; nada é lido das docstrings dos Resources.
        "specs": [{"endpoint": "apispec", "route": "/apispec.json",
                   "rule_filter": lambda regra: False, "model_filter": lambda tag: False}],
    }
    Swagger(app, config=config, template=montar_especificacao())
