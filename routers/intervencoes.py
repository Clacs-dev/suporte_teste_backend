from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from typing import Optional
import models, schemas, database
from routers.notificacoes import criar_notificacao
router = APIRouter(prefix="/intervencoes", tags=["intervencoes"])


def serialize_intervencao(i: models.Intervencao) -> dict:
    """Serializa uma intervenção com camelCase e nomes de cliente/técnico."""
    i_dict = schemas.IntervencaoOut.model_validate(i).model_dump(by_alias=True)
    i_dict['clienteNome'] = i.cliente.nome if i.cliente else 'Desconhecido'
    i_dict['tecnicoNome'] = i.tecnico.nome if i.tecnico else 'Não atribuído'
    i_dict['empresaNome'] = i.cliente.empresa if i.cliente else None
    ultimo_registo = sorted(i.registros_horas, key=lambda r: r.data_criacao, reverse=True)[0] if i.registros_horas else None
    i_dict['horaInicio'] = ultimo_registo.hora_inicio if ultimo_registo else None
    i_dict['horaFim'] = ultimo_registo.hora_fim if ultimo_registo else None
    i_dict['anexos'] = [
        {"id": a.id, "url": a.url, "nome": a.nome, "tipo": a.tipo}
        for a in i.anexos
    ]
    return i_dict


@router.get("", response_model=schemas.APIResponse)
def get_intervencoes(
    tecnico_id: Optional[str] = None,
    cliente_id: Optional[str] = None,
    status: Optional[str] = None,
    db: Session = Depends(database.get_db)
):
    query = db.query(models.Intervencao)
    if tecnico_id:
        query = query.filter(models.Intervencao.tecnico_id == tecnico_id)
    if cliente_id:
        query = query.filter(models.Intervencao.cliente_id == cliente_id)
    if status:
        query = query.filter(models.Intervencao.status == status)

    intervencoes = query.all()
    results = [serialize_intervencao(i) for i in intervencoes]
    return {"success": True, "data": results}


@router.get("/tecnico/{tecnico_id}", response_model=schemas.APIResponse)
def get_intervencoes_tecnico(tecnico_id: str, db: Session = Depends(database.get_db)):
    intervencoes = db.query(models.Intervencao).filter(
        models.Intervencao.tecnico_id == tecnico_id
    ).all()
    results = [serialize_intervencao(i) for i in intervencoes]
    return {"success": True, "data": results}


@router.get("/cliente/{cliente_id}", response_model=schemas.APIResponse)
def get_intervencoes_cliente(cliente_id: str, db: Session = Depends(database.get_db)):
    intervencoes = db.query(models.Intervencao).filter(
        models.Intervencao.cliente_id == cliente_id
    ).all()
    results = [serialize_intervencao(i) for i in intervencoes]
    return {"success": True, "data": results}


@router.get("/{id}", response_model=schemas.APIResponse)
def get_intervencao(id: str, db: Session = Depends(database.get_db)):
    i = db.query(models.Intervencao).filter(models.Intervencao.id == id).first()
    if not i:
        return {"success": False, "error": "Intervenção não encontrada"}
    return {"success": True, "data": serialize_intervencao(i)}


@router.post("", response_model=schemas.APIResponse)
def create_intervencao(intervencao: schemas.IntervencaoCreate, db: Session = Depends(database.get_db)):
    count = db.query(models.Intervencao).count()
    numero = f"INT-{2026}-{(count + 1):03d}"

    db_intervencao = models.Intervencao(
        **intervencao.model_dump(exclude={'anexos'}),
        numero=numero
    )
    db.add(db_intervencao)
    db.commit()
    db.refresh(db_intervencao)

    # Guardar anexos (URLs do Cloudinary)
    if intervencao.anexos:
        for a in intervencao.anexos:
            if a.get("url"):
                db.add(models.Anexo(
                    intervencao_id=db_intervencao.id,
                    url=a.get("url"),
                    nome=a.get("nome"),
                    tipo=a.get("tipo")
                ))
        db.commit()

    # Notificar todos os admins de que há uma nova intervenção
    admins = db.query(models.Usuario).filter(models.Usuario.perfil == "admin").all()
    cliente_nome = db_intervencao.cliente.nome if db_intervencao.cliente else "Cliente"
    for admin in admins:
        criar_notificacao(
            db, admin.id,
            titulo="Nova intervenção aberta",
            mensagem=f"{cliente_nome} abriu a intervenção \"{db_intervencao.titulo}\" ({db_intervencao.numero})",
            tipo="info",
            intervencao_id=db_intervencao.id
        )
     

    return {"success": True, "data": {
        "id": db_intervencao.id,
        "numero": db_intervencao.numero,
        "status": db_intervencao.status
    }}


@router.put("/{id}", response_model=schemas.APIResponse)
def update_intervencao(id: str, intervencao: schemas.IntervencaoUpdate, db: Session = Depends(database.get_db)):
    db_intervencao = db.query(models.Intervencao).filter(models.Intervencao.id == id).first()
    if not db_intervencao:
        return {"success": False, "error": "Intervenção não encontrada"}

    update_data = intervencao.model_dump(exclude_unset=True)

    # Tratar string vazia como None para evitar FK inválida
    if "tecnico_id" in update_data and update_data["tecnico_id"] == "":
        update_data["tecnico_id"] = None

    tecnico_novo = None
    if update_data.get("tecnico_id"):
        tecnico_novo = db.query(models.Tecnico).filter(
            models.Tecnico.id == update_data["tecnico_id"]
        ).first()
        if not tecnico_novo:
            return {"success": False, "error": "Técnico não encontrado"}

    tecnico_id_anterior = db_intervencao.tecnico_id
    status_anterior = db_intervencao.status

    for key, value in update_data.items():
        setattr(db_intervencao, key, value)

    db.commit()
    db.refresh(db_intervencao)

    # Notificar o técnico se acabou de ser atribuído a esta intervenção
    if tecnico_novo and tecnico_novo.id != tecnico_id_anterior and tecnico_novo.usuario_id:
        criar_notificacao(
            db, tecnico_novo.usuario_id,
            titulo="Nova intervenção atribuída",
            mensagem=f"Foi-lhe atribuída a intervenção \"{db_intervencao.titulo}\" ({db_intervencao.numero})",
            tipo="info",
            intervencao_id=db_intervencao.id
        )

    # Notificar admins, cliente e técnico quando a intervenção é concluída/resolvida
    status_concluidos = ["Concluído", "Resolvido", "Fechado"]
    if db_intervencao.status in status_concluidos and status_anterior not in status_concluidos:
        destinatarios_ids = set()

        admins = db.query(models.Usuario).filter(models.Usuario.perfil == "admin").all()
        for admin in admins:
            destinatarios_ids.add(admin.id)

        if db_intervencao.cliente and db_intervencao.cliente.usuario_id:
            destinatarios_ids.add(db_intervencao.cliente.usuario_id)

        if db_intervencao.tecnico and db_intervencao.tecnico.usuario_id:
            destinatarios_ids.add(db_intervencao.tecnico.usuario_id)

        for usuario_id in destinatarios_ids:
            criar_notificacao(
                db, usuario_id,
                titulo="Intervenção concluída",
                mensagem=f"A intervenção \"{db_intervencao.titulo}\" ({db_intervencao.numero}) foi marcada como {db_intervencao.status}",
                tipo="success",
                intervencao_id=db_intervencao.id
            )
    # Notificar admins e técnico quando o CLIENTE fecha a intervenção
    if db_intervencao.status == "Fechado" and status_anterior != "Fechado":
        destinatarios_fecho = set()
        admins = db.query(models.Usuario).filter(models.Usuario.perfil == "admin").all()
        for admin in admins:
            destinatarios_fecho.add(admin.id)
        if db_intervencao.tecnico and db_intervencao.tecnico.usuario_id:
            destinatarios_fecho.add(db_intervencao.tecnico.usuario_id)
        for usuario_id in destinatarios_fecho:
            criar_notificacao(
                db, usuario_id,
                titulo="Intervenção fechada pelo cliente",
                mensagem=f"O cliente fechou a intervenção \"{db_intervencao.titulo}\" ({db_intervencao.numero})",
                tipo="info",
                intervencao_id=db_intervencao.id
            )

    return {"success": True, "data": serialize_intervencao(db_intervencao)}


@router.post("/{id}/comentarios", response_model=schemas.APIResponse)
def add_comentario(id: str, comentario: dict, db: Session = Depends(database.get_db)):
    return {"success": True, "data": {"id": "mock-comentario-id", "intervencao_id": id}}


@router.delete("/{id}", response_model=schemas.APIResponse)
def delete_intervencao(id: str, db: Session = Depends(database.get_db)):
    db_intervencao = db.query(models.Intervencao).filter(models.Intervencao.id == id).first()
    if not db_intervencao:
        return {"success": False, "error": "Intervenção não encontrada"}

    # REGRA: Não permitir eliminar intervenção já resolvida/concluída
    status_finais = ["Concluído", "Resolvido", "Fechado"]
    if db_intervencao.status in status_finais:
        return {
            "success": False,
            "error": "Intervenção já foi resolvida ou tratada. Não é possível eliminá-la."
        }

    # Bloquear se já houver horas registadas
    tem_horas = db.query(models.RegistroHoras).filter(
        models.RegistroHoras.intervencao_id == id
    ).first()
    if tem_horas:
        return {
            "success": False,
            "error": "Não é possível eliminar: existem horas registadas nesta intervenção."
        }

    db.delete(db_intervencao)
    db.commit()
    return {"success": True, "message": "Intervenção eliminada com sucesso"}


@router.delete("/cliente/{cliente_id}/todas", response_model=schemas.APIResponse)
def delete_intervencoes_cliente(cliente_id: str, db: Session = Depends(database.get_db)):
    intervencoes = db.query(models.Intervencao).filter(
        models.Intervencao.cliente_id == cliente_id
    ).all()

    count = len(intervencoes)
    for i in intervencoes:
        db.delete(i)
    db.commit()

    return {"success": True, "message": f"{count} intervenção(ões) eliminada(s) com sucesso"}
