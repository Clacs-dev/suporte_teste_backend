from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
import models, schemas, database, auth

router = APIRouter(tags=["dev"])

@router.post("/seed-data", response_model=schemas.APIResponse)
def seed_data(db: Session = Depends(database.get_db)):
    # Criar um Admin de teste
    hashed_password = auth.get_password_hash("123456")
    admin = models.Usuario(email="admin@clacs.ao", hashed_password=hashed_password, nome="Administrador", perfil="admin")
    db.add(admin)
    
    # Criar Clientes de teste
    cliente1 = models.Cliente(nome="Cliente A", email="contato@clientea.com", empresa="Empresa A", status="Ativo")
    cliente2 = models.Cliente(nome="Cliente B", email="contato@clienteb.com", empresa="Empresa B", status="Ativo")
    db.add(cliente1)
    db.add(cliente2)
    
    # Criar Técnicos
    tecnico1 = models.Tecnico(nome="Técnico João", email="joao@clacs.ao", nivel="Sênior", especialidade="Redes")
    tecnico2 = models.Tecnico(nome="Técnico Maria", email="maria@clacs.ao", nivel="Pleno", especialidade="Sistemas")
    db.add(tecnico1)
    db.add(tecnico2)
    db.commit()
    
    # Criar Contratos
    contrato1 = models.Contrato(cliente_id=cliente1.id, tipo="Mensal", horas_contratadas=40, valor_mensal=250000)
    db.add(contrato1)
    db.commit()
    
    return {"success": True, "message": "Banco de dados populado com sucesso!"}

@router.delete("/clear-data", response_model=schemas.APIResponse)
def clear_data(db: Session = Depends(database.get_db)):
    db.query(models.RegistroHoras).delete()
    db.query(models.Intervencao).delete()
    db.query(models.Contrato).delete()
    db.query(models.Tecnico).delete()
    db.query(models.Cliente).delete()
    db.query(models.Usuario).delete()
    db.commit()
    return {"success": True, "message": "Dados deletados com sucesso!"}
