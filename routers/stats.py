from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
import models, schemas, database

router = APIRouter(prefix="/stats", tags=["stats"])

from typing import Optional

@router.get("/dashboard", response_model=schemas.APIResponse)
def get_dashboard_stats(
    tecnico_id: Optional[str] = None,
    tecnicoId: Optional[str] = None,
    cliente_id: Optional[str] = None,
    clienteId: Optional[str] = None,
    db: Session = Depends(database.get_db)
):
    t_id = tecnico_id or tecnicoId
    c_id = cliente_id or clienteId

    # Clientes
    q_clientes = db.query(models.Cliente)
    if c_id: q_clientes = q_clientes.filter(models.Cliente.id == c_id)
    total_clientes = q_clientes.count()
    clientes_ativos = q_clientes.filter(models.Cliente.status == "Ativo").count()
    
    # Contratos
    q_contratos = db.query(models.Contrato)
    if c_id: q_contratos = q_contratos.filter(models.Contrato.cliente_id == c_id)
    total_contratos = q_contratos.count()
    contratos_ativos = q_contratos.filter(models.Contrato.status == "Ativo").count()
    
    # Intervencoes
    q_intervencoes = db.query(models.Intervencao)
    if t_id: q_intervencoes = q_intervencoes.filter(models.Intervencao.tecnico_id == t_id)
    if c_id: q_intervencoes = q_intervencoes.filter(models.Intervencao.cliente_id == c_id)
    
    total_intervencoes = q_intervencoes.count()
    intervencoes_abertas = q_intervencoes.filter(models.Intervencao.status.in_(["Aberto", "Em Andamento"])).count()
    intervencoes_concluidas = q_intervencoes.filter(models.Intervencao.status == "Concluído").count()
    
    total_tecnicos = db.query(models.Tecnico).count()
    
    # Receita
    contratos_mensais = q_contratos.filter(models.Contrato.status == "Ativo").all()
    receita_mensal = sum(c.valor_mensal for c in contratos_mensais if c.valor_mensal)
    
    return {
        "success": True, 
        "data": {
            "totalClientes": total_clientes,
            "clientesAtivos": clientes_ativos,
            "totalContratos": total_contratos,
            "contratosAtivos": contratos_ativos,
            "totalIntervencoes": total_intervencoes,
            "intervencoesAbertas": intervencoes_abertas,
            "intervencoesConcluidas": intervencoes_concluidas,
            "totalTecnicos": total_tecnicos,
            "receitaMensal": receita_mensal
        }
    }
