from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
import models, schemas, database, auth

router = APIRouter(prefix="/notificacoes", tags=["notificacoes"])


def criar_notificacao(db: Session, usuario_id: str, titulo: str, mensagem: str, tipo: str = "info", intervencao_id: str = None):
    """Função auxiliar para criar notificações a partir de outros routers."""
    if not usuario_id:
        return
    notif = models.Notificacao(
        usuario_id=usuario_id,
        titulo=titulo,
        mensagem=mensagem,
        tipo=tipo,
        intervencao_id=intervencao_id
    )
    db.add(notif)
    db.commit()


@router.get("", response_model=schemas.APIResponse)
def listar_notificacoes(
    current_user: models.Usuario = Depends(auth.get_current_active_user),
    db: Session = Depends(database.get_db)
):
    notifs = db.query(models.Notificacao)\
        .filter(models.Notificacao.usuario_id == current_user.id)\
        .order_by(models.Notificacao.data_criacao.desc())\
        .limit(50)\
        .all()
    results = [schemas.NotificacaoOut.model_validate(n).model_dump(by_alias=True) for n in notifs]
    nao_lidas = db.query(models.Notificacao).filter(
        models.Notificacao.usuario_id == current_user.id,
        models.Notificacao.lida == False
    ).count()
    return {"success": True, "data": {"notificacoes": results, "naoLidas": nao_lidas}}


@router.post("/{id}/marcar-lida", response_model=schemas.APIResponse)
def marcar_lida(
    id: str,
    current_user: models.Usuario = Depends(auth.get_current_active_user),
    db: Session = Depends(database.get_db)
):
    notif = db.query(models.Notificacao).filter(
        models.Notificacao.id == id,
        models.Notificacao.usuario_id == current_user.id
    ).first()
    if not notif:
        return {"success": False, "error": "Notificação não encontrada"}
    notif.lida = True
    db.commit()
    return {"success": True}


@router.post("/marcar-todas-lidas", response_model=schemas.APIResponse)
def marcar_todas_lidas(
    current_user: models.Usuario = Depends(auth.get_current_active_user),
    db: Session = Depends(database.get_db)
):
    db.query(models.Notificacao).filter(
        models.Notificacao.usuario_id == current_user.id,
        models.Notificacao.lida == False
    ).update({"lida": True})
    db.commit()
    return {"success": True}