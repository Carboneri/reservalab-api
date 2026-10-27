class ErroDeNegocio(Exception):
    """Base das regras violadas; o Resource decide qual código HTTP devolver."""


class EmailJaCadastrado(ErroDeNegocio):
    pass


class CodigoSalaJaCadastrado(ErroDeNegocio):
    pass


class SalaComReservasFuturas(ErroDeNegocio):
    pass


class RegraViolada(ErroDeNegocio):
    """Regra de reserva violada. status é o código que a SPEC associa à regra;
    o serviço só o informa, quem monta a resposta HTTP é o Resource."""

    def __init__(self, status, mensagem):
        super().__init__(mensagem)
        self.status = status
        self.mensagem = mensagem


class ConflitoReserva(ErroDeNegocio):
    """R4: o horário pedido sobrepõe uma reserva confirmada da mesma sala."""

    def __init__(self, reserva_existente):
        super().__init__("Conflito de horário")
        self.reserva_existente = reserva_existente
