from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func
import models, schemas, database

router = APIRouter(prefix="/contratos", tags=["contratos"])

from typing import Optional

@router.get("", response_model=schemas.APIResponse)
def get_contratos(
    cliente_id: Optional[str] = None, 
    clienteId: Optional[str] = None,
    db: Session = Depends(database.get_db)
):
    query = db.query(models.Contrato)
    
    c_id = cliente_id or clienteId
    if c_id:
        query = query.filter(models.Contrato.cliente_id == c_id)
        
    contratos = query.all()
    results = []
    for c in contratos:
        c_dict = schemas.ContratoOut.model_validate(c).model_dump()
        c_dict['clienteNome'] = c.cliente.nome if c.cliente else 'Desconhecido'
        c_dict['clienteId'] = c.cliente_id
        
        # Calcular horas_usadas dinamicamente para garantir que o progresso é 100% real e funcional
        total_horas_usadas = db.query(func.sum(models.RegistroHoras.horas)).\
            select_from(models.RegistroHoras).\
            join(models.Intervencao).\
            filter(
                (models.Intervencao.contrato_id == c.id) | 
                ((models.Intervencao.contrato_id == None) & (models.Intervencao.cliente_id == c.cliente_id))
            ).\
            scalar() or 0.0
            
        c_dict['horas_usadas'] = total_horas_usadas
        
        # compat (Pydantic schema now handles camelCase, but manual overrides are safe)
        c_dict['horasContratadas'] = c.horas_contratadas
        c_dict['horasUsadas'] = total_horas_usadas
        c_dict['valorMensal'] = c.valor_mensal
        c_dict['dataInicio'] = c.data_inicio
        c_dict['dataFim'] = c.data_fim
        results.append(c_dict)
    return {"success": True, "data": results}

@router.get("/cliente/{cliente_id}", response_model=schemas.APIResponse)
def get_contratos_cliente(cliente_id: str, db: Session = Depends(database.get_db)):
    contratos = db.query(models.Contrato).filter(models.Contrato.cliente_id == cliente_id).all()
    results = []
    for c in contratos:
        c_dict = schemas.ContratoOut.model_validate(c).model_dump()
        
        # Calcular horas_usadas dinamicamente para garantir que o progresso é 100% real e funcional
        total_horas_usadas = db.query(func.sum(models.RegistroHoras.horas)).\
            select_from(models.RegistroHoras).\
            join(models.Intervencao).\
            filter(
                (models.Intervencao.contrato_id == c.id) | 
                ((models.Intervencao.contrato_id == None) & (models.Intervencao.cliente_id == c.cliente_id))
            ).\
            scalar() or 0.0
            
        c_dict['horas_usadas'] = total_horas_usadas
        
        # compat
        c_dict['horasContratadas'] = c.horas_contratadas
        c_dict['horasUsadas'] = total_horas_usadas
        c_dict['valorMensal'] = c.valor_mensal
        c_dict['dataInicio'] = c.data_inicio
        c_dict['dataFim'] = c.data_fim
        results.append(c_dict)
    return {"success": True, "data": results}

@router.post("", response_model=schemas.APIResponse)
def create_contrato(contrato: schemas.ContratoCreate, db: Session = Depends(database.get_db)):
    db_contrato = models.Contrato(**contrato.model_dump())
    db.add(db_contrato)
    db.commit()
    db.refresh(db_contrato)
    return {"success": True, "data": {"id": db_contrato.id, "status": db_contrato.status}}

@router.put("/{id}", response_model=schemas.APIResponse)
def update_contrato(id: str, contrato: schemas.ContratoUpdate, db: Session = Depends(database.get_db)):
    db_contrato = db.query(models.Contrato).filter(models.Contrato.id == id).first()
    if not db_contrato:
        return {"success": False, "error": "Contrato não encontrado"}
    
    update_data = contrato.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_contrato, key, value)
    
    db.commit()
    db.refresh(db_contrato)
    return {"success": True, "data": {"id": db_contrato.id, "status": db_contrato.status}}

@router.delete("/{id}", response_model=schemas.APIResponse)
def delete_contrato(id: str, db: Session = Depends(database.get_db)):
    try:
        db_contrato = db.query(models.Contrato).filter(
            models.Contrato.id == id
        ).first()

        if not db_contrato:
            return {
                "success": False,
                "error": "Contrato não encontrado"
            }

        db.delete(db_contrato)
        db.commit()

        return {
            "success": True,
            "message": "Contrato eliminado com sucesso"
        }

    except Exception as e:
        db.rollback()

        return {
            "success": False,
            "error": str(e)
        }