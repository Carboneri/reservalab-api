from datetime import datetime


def agora():
    """Único ponto que lê o relógio. Chame sempre relogio.agora(): assim os
    testes trocam esta função e controlam o "agora" sem esperar o tempo passar."""
    return datetime.now()
