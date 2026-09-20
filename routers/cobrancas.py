from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
import database, models, schemas
from datetime import datetime

router = APIRouter(prefix="/cobrancas", tags=["cobrancas"])


@router.get("", response_model=schemas.APIResponse)
def listar_cobrancas(mes: int = None, ano: int = None, db: Session = Depends(database.get_db)):
    q = db.query(models.Cobranca)
    if mes is not None:
        q = q.filter(models.Cobranca.mes == mes)
    if ano is not None:
        q = q.filter(models.Cobranca.ano == ano)
    cobrancas = q.order_by(models.Cobranca.ano.desc(), models.Cobranca.mes.desc()).all()
    return {
        "success": True,
        "data": [schemas.CobrancaOut.model_validate(c).model_dump(by_alias=True) for c in cobrancas],
    }


@router.get("/mapa", response_model=schemas.APIResponse)
def mapa_cobrancas(mes: int, ano: int, db: Session = Depends(database.get_db)):
    clientes = (
        db.query(models.Cliente)
        .filter(models.Cliente.status == "Ativo")
        .order_by(models.Cliente.nome.asc())
        .all()
    )
    registos = {
        c.cliente_id: c
        for c in db.query(models.Cobranca).filter(
            models.Cobranca.mes == mes, models.Cobranca.ano == ano
        ).all()
    }

    lista = []
    for cli in clientes:
        cob = registos.get(cli.id)
        lista.append({
            "id": cli.id,
            "nome": cli.nome,
            "email": cli.email,
            "empresa": cli.empresa,
            "pago": bool(cob.pago) if cob else False,
            "valor": cob.valor if cob else 0.0,
            "data_pagamento": cob.data_pagamento if cob else None,
            "observacao": cob.observacao if cob else None,
        })

    pagantes = sum(1 for x in lista if x["pago"])
    return {
        "success": True,
        "data": {
            "mes": mes,
            "ano": ano,
            "clientes": lista,
            "stats": {
                "total_clientes": len(lista),
                "pagantes": pagantes,
                "nao_pagantes": len(lista) - pagantes,
                "total_cobrado": sum(x["valor"] for x in lista),
                "total_pago": sum(x["valor"] for x in lista if x["pago"]),
            },
        },
    }


@router.get("/historico")
def historico_cobrancas(db: Session = Depends(database.get_db)):
    clientes = (
        db.query(models.Cliente)
        .filter(models.Cliente.status == "Ativo")
        .order_by(models.Cliente.nome.asc())
        .all()
    )
    registos = db.query(models.Cobranca).all()
    por_cliente = {}
    for c in registos:
        por_cliente.setdefault(c.cliente_id, []).append(c)

    hoje = datetime.now().replace(day=1)

    # Mês a mês desde o primeiro registo até ao mais recente (incluindo o mês atual)
    ano_meses = sorted({(c.ano, c.mes) for c in registos})
    if ano_meses:
        inicio = (ano_meses[0][1], ano_meses[0][0])
        fim = (ano_meses[-1][1], ano_meses[-1][0])
    else:
        inicio = fim = (hoje.month, hoje.year)

    atual = (hoje.month, hoje.year)
    if fim < atual:
        fim = atual

    meses = []
    m, a = inicio
    while (m, a) <= fim:
        meses.append({"mes": m, "ano": a})
        m += 1
        if m > 12:
            m = 1
            a += 1

    lista = []
    for cli in clientes:
        regs = {(c.mes, c.ano): c for c in por_cliente.get(cli.id, [])}
        lista.append({
            "id": cli.id,
            "nome": cli.nome,
            "email": cli.email,
            "empresa": cli.empresa,
            "historico": [
                {
                    "mes": m["mes"],
                    "ano": m["ano"],
                    "pago": bool(regs[(m["mes"], m["ano"])].pago) if (m["mes"], m["ano"]) in regs else False,
                    "valor": float(regs[(m["mes"], m["ano"])].valor or 0) if (m["mes"], m["ano"]) in regs else 0.0,
                    "data_pagamento": regs[(m["mes"], m["ano"])].data_pagamento if (m["mes"], m["ano"]) in regs else None,
                    "observacao": regs[(m["mes"], m["ano"])].observacao if (m["mes"], m["ano"]) in regs else None,
                }
                for m in meses
            ],
        })

    return {"success": True, "data": {"clientes": lista, "meses": meses}}


@router.post("", response_model=schemas.APIResponse)
def salvar_cobranca(payload: schemas.CobrancaCreate, db: Session = Depends(database.get_db)):
    cliente = db.query(models.Cliente).filter(models.Cliente.id == payload.cliente_id).first()
    if not cliente:
        return {"success": False, "error": "Cliente não encontrado."}

    cob = (
        db.query(models.Cobranca)
        .filter(
            models.Cobranca.cliente_id == payload.cliente_id,
            models.Cobranca.mes == payload.mes,
            models.Cobranca.ano == payload.ano,
        )
        .first()
    )

    if cob:
        cob.pago = payload.pago
        cob.valor = payload.valor or 0.0
        cob.data_pagamento = payload.data_pagamento
        cob.observacao = payload.observacao
    else:
        cob = models.Cobranca(
            cliente_id=payload.cliente_id,
            mes=payload.mes,
            ano=payload.ano,
            pago=payload.pago,
            valor=payload.valor or 0.0,
            data_pagamento=payload.data_pagamento,
            observacao=payload.observacao,
        )
        db.add(cob)

    db.commit()
    db.refresh(cob)
    return {"success": True, "data": schemas.CobrancaOut.model_validate(cob).model_dump(by_alias=True)}


@router.delete("/{id}", response_model=schemas.APIResponse)
def eliminar_cobranca(id: str, db: Session = Depends(database.get_db)):
    cob = db.query(models.Cobranca).filter(models.Cobranca.id == id).first()
    if not cob:
        return {"success": False, "error": "Cobrança não encontrada."}
    db.delete(cob)
    db.commit()
    return {"success": True, "data": {"id": id}}