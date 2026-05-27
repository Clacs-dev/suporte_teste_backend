from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
import models, schemas, database

router = APIRouter(prefix="/registros-horas", tags=["registros-horas"])

@router.get("", response_model=schemas.APIResponse)
def get_registros(db: Session = Depends(database.get_db)):
    registros = db.query(models.RegistroHoras).all()
    results = [schemas.RegistroHorasOut.model_validate(r).model_dump() for r in registros]
    return {"success": True, "data": results}

@router.get("/tecnico/{tecnico_id}", response_model=schemas.APIResponse)
def get_registros_tecnico(tecnico_id: str, db: Session = Depends(database.get_db)):
    registros = db.query(models.RegistroHoras).filter(models.RegistroHoras.tecnico_id == tecnico_id).all()
    results = [schemas.RegistroHorasOut.model_validate(r).model_dump() for r in registros]
    return {"success": True, "data": results}

@router.get("/intervencao/{intervencao_id}", response_model=schemas.APIResponse)
def get_registros_intervencao(intervencao_id: str, db: Session = Depends(database.get_db)):
    registros = db.query(models.RegistroHoras).filter(models.RegistroHoras.intervencao_id == intervencao_id).all()
    results = [schemas.RegistroHorasOut.model_validate(r).model_dump() for r in registros]
    return {"success": True, "data": results}

@router.post("", response_model=schemas.APIResponse)
def create_registro(registro: schemas.RegistroHorasCreate, db: Session = Depends(database.get_db)):
    db_registro = models.RegistroHoras(**registro.model_dump())
    db.add(db_registro)
    
    # Atualiza as horas na intervenção e contrato se necessário
    intervencao = db.query(models.Intervencao).filter(models.Intervencao.id == registro.intervencao_id).first()
    if intervencao:
        intervencao.horas_gastas += registro.horas
        
        # Atualiza horas_usadas no contrato
        if intervencao.contrato_id:
            contrato = db.query(models.Contrato).filter(models.Contrato.id == intervencao.contrato_id).first()
            if contrato:
                contrato.horas_usadas += registro.horas
                
    db.commit()
    db.refresh(db_registro)
    return {"success": True, "data": {"id": db_registro.id}}
