from werkzeug.security import generate_password_hash

from app.extensions import db
from app.models import Usuario
from app.services.excecoes import EmailJaCadastrado

# Hash de uma senha qualquer, usado quando o e-mail não existe (ver autenticar).
_HASH_FICTICIO = generate_password_hash("senha-ficticia")


def registrar(nome, email, senha):
    """Cria um usuário. R11: o registro público sempre gera o papel aluno."""
    if Usuario.query.filter_by(email=email).first():
        raise EmailJaCadastrado()

    usuario = Usuario(nome=nome, email=email, papel="aluno")
    usuario.definir_senha(senha)
    db.session.add(usuario)
    db.session.commit()
    return usuario


def autenticar(email, senha):
    """Devolve o usuário se as credenciais conferem; senão, None."""
    usuario = Usuario.query.filter_by(email=email).first()
    if usuario is None:
        # Verifica um hash mesmo assim: o tempo de resposta não revela
        # se o e-mail está cadastrado.
        Usuario(senha_hash=_HASH_FICTICIO).verificar_senha(senha)
        return None
    return usuario if usuario.verificar_senha(senha) else None


def buscar_por_id(usuario_id):
    return db.session.get(Usuario, usuario_id)
