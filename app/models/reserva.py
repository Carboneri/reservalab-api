from app.extensions import db
from app.services import relogio

STATUS_RESERVA = ("confirmada", "cancelada")


class Reserva(db.Model):
    __tablename__ = "reservas"
    __table_args__ = (
        # A checagem de conflito (R4) sempre filtra por sala e horário.
        db.Index("ix_reservas_sala_inicio", "sala_id", "inicio"),
        db.CheckConstraint("participantes > 0", name="ck_reserva_participantes"),
        # Id excluído nunca volta: um Location antigo não aponta para outra reserva.
        {"sqlite_autoincrement": True},
    )

    id = db.Column(db.Integer, primary_key=True)
    sala_id = db.Column(db.Integer, db.ForeignKey("salas.id"), nullable=False)
    usuario_id = db.Column(db.Integer, db.ForeignKey("usuarios.id"), nullable=False)
    inicio = db.Column(db.DateTime, nullable=False)
    fim = db.Column(db.DateTime, nullable=False)
    participantes = db.Column(db.Integer, nullable=False)
    finalidade = db.Column(db.String(120), nullable=False)
    status = db.Column(db.String(20), nullable=False, default="confirmada")
    criado_em = db.Column(db.DateTime, nullable=False, default=lambda: relogio.agora())

    sala = db.relationship("Sala", back_populates="reservas")
    usuario = db.relationship("Usuario", back_populates="reservas")

    def __marshallable__(self):
        # fields.Url chama url_for("reserva", **este_dict); a rota espera "reserva_id".
        return {"reserva_id": self.id}

    def __repr__(self):
        return f"<Reserva {self.id} sala={self.sala_id} {self.inicio:%Y-%m-%d %H:%M}>"
