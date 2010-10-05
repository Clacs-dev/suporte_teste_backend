from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import or_
import database, models, schemas, auth

router = APIRouter(prefix="/mensagens", tags=["mensagens"])


def _serializar(m):
    d = schemas.MensagemOut.model_validate(m).model_dump(by_alias=True)
    if m.remetente:
        d["remetenteNome"] = m.remetente.nome
        d["remetenteEmail"] = m.remetente.email
    if m.destinatario:
        d["destinatarioNome"] = m.destinatario.nome
        d["destinatarioEmail"] = m.destinatario.email
    return d


def _contactos_permitidos(perfil):
    """Perfis com quem o utilizador pode trocar mensagens."""
    if perfil == "admin":
        return ["admin", "tecnico", "cliente"]
    if perfil == "tecnico":
        return ["admin", "tecnico"]
    return ["admin"]


@router.get("/contactos", response_model=schemas.APIResponse)
def contactos(
    db: Session = Depends(database.get_db),
    current_user: models.Usuario = Depends(auth.get_current_active_user),
):
    permitidos = _contactos_permitidos(current_user.perfil)
    users = (
        db.query(models.Usuario)
        .filter(models.Usuario.id != current_user.id)
        .filter(models.Usuario.perfil.in_(permitidos))
        .order_by(models.Usuario.nome.asc())
        .all()
    )
    return {
        "success": True,
        "data": [
            {"id": u.id, "nome": u.nome, "email": u.email, "perfil": u.perfil}
            for u in users
        ],
    }


@router.get("", response_model=schemas.APIResponse)
def listar_mensagens(
    caixa: str = "entrada",
    db: Session = Depends(database.get_db),
    current_user: models.Usuario = Depends(auth.get_current_active_user),
):
    if caixa == "entrada":
        q = db.query(models.Mensagem).filter(
            models.Mensagem.destinatario_id == current_user.id
        )
    elif caixa == "saida":
        q = db.query(models.Mensagem).filter(
            models.Mensagem.remetente_id == current_user.id
        )
    else:
        q = db.query(models.Mensagem).filter(
            or_(
                models.Mensagem.destinatario_id == current_user.id,
                models.Mensagem.remetente_id == current_user.id,
            )
        )
    mensagens = q.order_by(models.Mensagem.data_criacao.desc()).all()
    return {"success": True, "data": [_serializar(m) for m in mensagens]}


@router.get("/nao-lidas", response_model=schemas.APIResponse)
def contar_nao_lidas(
    db: Session = Depends(database.get_db),
    current_user: models.Usuario = Depends(auth.get_current_active_user),
):
    total = (
        db.query(models.Mensagem)
        .filter(
            models.Mensagem.destinatario_id == current_user.id,
            models.Mensagem.lida.is_(False),
        )
        .count()
    )
    return {"success": True, "data": {"total": total}}


@router.get("/conversa/{outro_usuario_id}", response_model=schemas.APIResponse)
def conversa(
    outro_usuario_id: str,
    db: Session = Depends(database.get_db),
    current_user: models.Usuario = Depends(auth.get_current_active_user),
):
    mensagens = (
        db.query(models.Mensagem)
        .filter(
            or_(
                (models.Mensagem.remetente_id == current_user.id)
                & (models.Mensagem.destinatario_id == outro_usuario_id),
                (models.Mensagem.remetente_id == outro_usuario_id)
                & (models.Mensagem.destinatario_id == current_user.id),
            )
        )
        .order_by(models.Mensagem.data_criacao.asc())
        .all()
    )
    return {"success": True, "data": [_serializar(m) for m in mensagens]}


@router.post("", response_model=schemas.APIResponse)
def enviar_mensagem(
    mensagem: schemas.MensagemCreate,
    db: Session = Depends(database.get_db),
    current_user: models.Usuario = Depends(auth.get_current_active_user),
):
    destinatario = (
        db.query(models.Usuario)
        .filter(models.Usuario.id == mensagem.destinatario_id)
        .first()
    )
    if not destinatario:
        return {"success": False, "error": "Destinatário não encontrado."}
    if destinatario.id == current_user.id:
        return {"success": False, "error": "Não pode enviar uma mensagem a si mesmo."}
    if destinatario.perfil not in _contactos_permitidos(current_user.perfil):
        return {"success": False, "error": "Sem permissão para enviar mensagem a este utilizador."}

    db_mensagem = models.Mensagem(
        remetente_id=current_user.id,
        destinatario_id=destinatario.id,
        assunto=mensagem.assunto,
        conteudo=mensagem.conteudo,
    )
    db.add(db_mensagem)
    db.commit()
    db.refresh(db_mensagem)
    return {"success": True, "data": _serializar(db_mensagem)}


@router.put("/{id}/ler", response_model=schemas.APIResponse)
def marcar_como_lida(
    id: str,
    db: Session = Depends(database.get_db),
    current_user: models.Usuario = Depends(auth.get_current_active_user),
):
    mensagem = db.query(models.Mensagem).filter(models.Mensagem.id == id).first()
    if not mensagem:
        return {"success": False, "error": "Mensagem não encontrada."}
    if mensagem.destinatario_id != current_user.id:
        return {"success": False, "error": "Sem permissão para marcar esta mensagem como lida."}

    mensagem.lida = True
    db.commit()
    db.refresh(mensagem)
    return {"success": True, "data": _serializar(mensagem)}