from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
import models, schemas, database, auth

router = APIRouter(prefix="/tecnicos", tags=["tecnicos"])

@router.get("", response_model=schemas.APIResponse)
def get_tecnicos(db: Session = Depends(database.get_db)):
    tecnicos = db.query(models.Tecnico).all()
    results = []
    for t in tecnicos:
        t_dict = schemas.TecnicoOut.model_validate(t).model_dump()
        t_dict['intervencoesAtivas'] = sum(1 for i in t.intervencoes if i.status not in ["Concluído", "Fechado"])
        t_dict['horasMes'] = t.horas_mes
        results.append(t_dict)
    return {"success": True, "data": results}

@router.post("", response_model=schemas.APIResponse)
def create_tecnico(tecnico: schemas.TecnicoCreate, db: Session = Depends(database.get_db)):
    usuario_id = None
    if tecnico.senha:
        db_user = db.query(models.Usuario).filter(models.Usuario.email == tecnico.email).first()
        if not db_user:
            hashed_password = auth.get_password_hash(tecnico.senha)
            db_user = models.Usuario(
                email=tecnico.email,
                hashed_password=hashed_password,
                nome=tecnico.nome,
                perfil="tecnico",
            )
            db.add(db_user)
            db.commit()
            db.refresh(db_user)
        usuario_id = db_user.id

    db_tecnico = models.Tecnico(
        nome=tecnico.nome,
        email=tecnico.email,
        nivel=tecnico.nivel,
        especialidade=tecnico.especialidade,
        usuario_id=usuario_id
    )
    db.add(db_tecnico)
    db.commit()
    db.refresh(db_tecnico)
    return {"success": True, "data": {"id": db_tecnico.id, "usuario_id": usuario_id}}

@router.put("/{id}", response_model=schemas.APIResponse)
def update_tecnico(id: str, tecnico: schemas.TecnicoUpdate, db: Session = Depends(database.get_db)):
    db_tecnico = db.query(models.Tecnico).filter(models.Tecnico.id == id).first()
    if not db_tecnico:
        return {"success": False, "error": "Técnico não encontrado"}
    
    update_data = tecnico.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_tecnico, key, value)
    
    db.commit()
    db.refresh(db_tecnico)
    return {"success": True, "data": schemas.TecnicoOut.model_validate(db_tecnico).model_dump()}

@router.get("/usuario/{usuario_id}", response_model=schemas.APIResponse)
def get_tecnico_por_usuario(usuario_id: str, db: Session = Depends(database.get_db)):
    tecnico = db.query(models.Tecnico).filter(models.Tecnico.usuario_id == usuario_id).first()
    if not tecnico:
        return {"success": False, "error": "Técnico não encontrado para este usuário"}
    return {"success": True, "data": schemas.TecnicoOut.model_validate(tecnico).model_dump()}


@router.delete("/{id}", response_model=schemas.APIResponse)
def delete_tecnico(id: str, db: Session = Depends(database.get_db)):
    db_tecnico = db.query(models.Tecnico).filter(models.Tecnico.id == id).first()

    if not db_tecnico:
        return {"success": False, "error": "Técnico não encontrado"}

    intervencoes = db.query(models.Intervencao).filter(
        models.Intervencao.tecnico_id == id
    ).all()

    for intervencao in intervencoes:
        intervencao.tecnico_id = None

    db.delete(db_tecnico)
    db.commit()

    return {"success": True, "data": {"id": id}}