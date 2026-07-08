from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from typing import Optional
import models, schemas, database

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

    # Validar que o técnico existe antes de atribuir
    if update_data.get("tecnico_id"):
        tecnico = db.query(models.Tecnico).filter(
            models.Tecnico.id == update_data["tecnico_id"]
        ).first()
        if not tecnico:
            return {"success": False, "error": "Técnico não encontrado"}

    for key, value in update_data.items():
        setattr(db_intervencao, key, value)

    db.commit()
    db.refresh(db_intervencao)

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
