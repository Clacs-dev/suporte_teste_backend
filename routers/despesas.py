from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session
from datetime import datetime
import database, models, schemas

router = APIRouter(tags=["financeiro"])


def calcular_saldo(db: Session) -> float:
    movimentos = db.query(models.Movimento).all()
    entradas = sum(m.valor for m in movimentos if m.tipo == "Entrada")
    saidas = sum(m.valor for m in movimentos if m.tipo == "Saida")
    return entradas - saidas


def proximo_numero(db: Session) -> str:
    """Nº automático sequencial das despesas (001, 002, ...), continua do maior existente."""
    numeros = [
        m.numero
        for m in db.query(models.Movimento).filter(models.Movimento.tipo == "Saida").all()
        if m.numero
    ]
    inteiros = []
    for n in numeros:
        digitos = "".join(ch for ch in n if ch.isdigit())
        if digitos:
            inteiros.append(int(digitos))
    return f"{(max(inteiros) + 1) if inteiros else 1:03d}"


def proximo_numero_entrada(db: Session) -> str:
    """Nº automático sequencial das entradas (E-001, E-002, ...)."""
    numeros = [
        m.numero
        for m in db.query(models.Movimento).filter(models.Movimento.tipo == "Entrada").all()
        if m.numero
    ]
    inteiros = []
    for n in numeros:
        digitos = "".join(ch for ch in n if ch.isdigit())
        if digitos:
            inteiros.append(int(digitos))
    return f"E-{(max(inteiros) + 1) if inteiros else 1:03d}"


def listar_contas(db: Session) -> list[models.ContaBancaria]:
    return db.query(models.ContaBancaria).order_by(models.ContaBancaria.data_criacao.asc()).all()


def saldo_conta(db: Session, conta: models.ContaBancaria) -> float:
    """Saldo real da conta = saldo_inicial + entradas - despesas ligadas à conta."""
    movimentos = db.query(models.Movimento).filter(
        models.Movimento.conta_bancaria_id == conta.id
    ).all()
    entradas = sum(m.valor for m in movimentos if m.tipo == "Entrada")
    saidas = sum(m.valor for m in movimentos if m.tipo == "Saida")
    return conta.saldo_inicial + entradas - saidas


def _movimento_out(m: models.Movimento) -> dict:
    return schemas.MovimentoOut.model_validate(m).model_dump(by_alias=True)


def _conta_out(db: Session, conta: models.ContaBancaria) -> dict:
    out = schemas.ContaBancariaOut.model_validate(conta).model_dump(by_alias=True)
    out["saldo"] = saldo_conta(db, conta)
    return out


def _saldo_disponivel_antes(db: Session, mov: models.Movimento, novo_conta_id: str | None) -> float:
    """Saldo disponível ignorando o efeito do próprio movimento (para validar edições)."""
    target_id = novo_conta_id if novo_conta_id is not None else mov.conta_bancaria_id
    efeito = mov.valor if mov.tipo == "Saida" else -mov.valor
    if target_id:
        conta = db.query(models.ContaBancaria).filter(models.ContaBancaria.id == target_id).first()
        if not conta:
            return 0.0
        saldo = saldo_conta(db, conta)
        if mov.conta_bancaria_id == target_id:
            saldo -= efeito
        return saldo
    else:
        saldo = calcular_saldo(db)
        if not mov.conta_bancaria_id:
            saldo -= efeito
        return saldo


def _categoria_out(categoria: models.Categoria) -> dict:
    return schemas.CategoriaOut.model_validate(categoria).model_dump(by_alias=True)


def listar_categorias(db: Session) -> list[models.Categoria]:
    return db.query(models.Categoria).order_by(models.Categoria.nome.asc()).all()


@router.get("", response_model=schemas.APIResponse)
def listar_movimentos(db: Session = Depends(database.get_db)):
    movimentos = db.query(models.Movimento).order_by(models.Movimento.data.desc()).all()
    contas = listar_contas(db)
    return {
        "success": True,
        "data": {
            "movimentos": [_movimento_out(m) for m in movimentos],
            "saldo": calcular_saldo(db),
            "saldo_bancario": sum(saldo_conta(db, c) for c in contas),
            "saldo_total": calcular_saldo(db) + sum(c.saldo_inicial for c in contas),
            "contas": [_conta_out(db, c) for c in contas],
            "categorias": [_categoria_out(c) for c in listar_categorias(db)],
        },
    }


@router.post("", response_model=schemas.APIResponse)
def criar_movimento(movimento: schemas.MovimentoCreate, db: Session = Depends(database.get_db)):
    dados = movimento.model_dump()

    # Converter data (string YYYY-MM-DD) para datetime, ou usar hoje
    if dados.get("data"):
        try:
            dados["data"] = datetime.strptime(dados["data"][:10], "%Y-%m-%d")
        except Exception:
            dados.pop("data", None)
    else:
        dados.pop("data", None)

    # Validar a conta bancária escolhida (dropdown de cartões)
    conta = None
    if dados.get("conta_bancaria_id"):
        conta = db.query(models.ContaBancaria).filter(
            models.ContaBancaria.id == dados["conta_bancaria_id"]
        ).first()
        if not conta:
            return {"success": False, "error": "Conta bancária selecionada não encontrada."}
    else:
        dados.pop("conta_bancaria_id", None)

    # Regra do saldo: não permitir saída maior que o saldo disponível na conta escolhida
    if dados["tipo"] == "Saida":
        saldo_disponivel = saldo_conta(db, conta) if conta else calcular_saldo(db)
        if dados["valor"] > saldo_disponivel:
            return {"success": False, "error": f"Saldo insuficiente. Saldo disponível: {saldo_disponivel:,.2f} Kz"}

    # A entrada só tem valor; a descrição é preenchida automaticamente
    if not dados.get("descricao"):
        dados["descricao"] = "Entrada de dinheiro" if dados["tipo"] == "Entrada" else "Despesa"

    # Nº automático sequencial (ignora qualquer valor enviado pelo cliente)
    if dados["tipo"] == "Saida":
        dados["numero"] = proximo_numero(db)
    elif dados["tipo"] == "Entrada":
        dados["numero"] = proximo_numero_entrada(db)
        dados["destinatario"] = None  # destinatário só se aplica a despesas (saídas)

    db_mov = models.Movimento(**dados)
    db.add(db_mov)
    db.commit()
    db.refresh(db_mov)
    return {"success": True, "data": _movimento_out(db_mov)}


# --- Contas bancárias (várias) ---

@router.get("/contas", response_model=schemas.APIResponse)
def listar_contas_route(db: Session = Depends(database.get_db)):
    contas = listar_contas(db)
    return {"success": True, "data": [_conta_out(db, c) for c in contas]}


@router.post("/contas", response_model=schemas.APIResponse)
def criar_conta(payload: schemas.ContaBancariaCreate, db: Session = Depends(database.get_db)):
    conta = models.ContaBancaria(**payload.model_dump())
    db.add(conta)
    db.commit()
    db.refresh(conta)
    return {"success": True, "data": _conta_out(db, conta)}


@router.put("/contas/{id}", response_model=schemas.APIResponse)
def atualizar_conta(id: str, payload: schemas.ContaBancariaCreate, db: Session = Depends(database.get_db)):
    conta = db.query(models.ContaBancaria).filter(models.ContaBancaria.id == id).first()
    if not conta:
        return {"success": False, "error": "Conta bancária não encontrada."}
    dados = payload.model_dump()
    for k, v in dados.items():
        setattr(conta, k, v)
    db.commit()
    db.refresh(conta)
    return {"success": True, "data": _conta_out(db, conta)}


@router.delete("/contas/{id}", response_model=schemas.APIResponse)
def eliminar_conta(id: str, db: Session = Depends(database.get_db)):
    conta = db.query(models.ContaBancaria).filter(models.ContaBancaria.id == id).first()
    if not conta:
        return {"success": False, "error": "Conta bancária não encontrada."}
    ligados = db.query(models.Movimento).filter(
        models.Movimento.conta_bancaria_id == conta.id
    ).count()
    if ligados:
        return {"success": False, "error": f"Não é possível eliminar: existem {ligados} movimento(s) ligados a esta conta."}
    db.delete(conta)
    db.commit()
    return {"success": True, "data": {"id": id}}


# --- Categorias de despesas ---

@router.get("/categorias", response_model=schemas.APIResponse)
def listar_categorias_route(db: Session = Depends(database.get_db)):
    return {"success": True, "data": [_categoria_out(c) for c in listar_categorias(db)]}


@router.post("/categorias", response_model=schemas.APIResponse)
def criar_categoria(payload: schemas.CategoriaCreate, db: Session = Depends(database.get_db)):
    nome = payload.nome.strip()
    if not nome:
        return {"success": False, "error": "Indique o nome da categoria."}
    existe = db.query(models.Categoria).filter(func.lower(models.Categoria.nome) == nome.lower()).first()
    if existe:
        return {"success": False, "error": "Já existe uma categoria com esse nome."}
    categoria = models.Categoria(nome=nome)
    db.add(categoria)
    db.commit()
    db.refresh(categoria)
    return {"success": True, "data": _categoria_out(categoria)}


@router.put("/categorias/{id}", response_model=schemas.APIResponse)
def atualizar_categoria(id: str, payload: schemas.CategoriaCreate, db: Session = Depends(database.get_db)):
    categoria = db.query(models.Categoria).filter(models.Categoria.id == id).first()
    if not categoria:
        return {"success": False, "error": "Categoria não encontrada."}
    nome = payload.nome.strip()
    if not nome:
        return {"success": False, "error": "Indique o nome da categoria."}
    antigo = categoria.nome
    duplicada = db.query(models.Categoria).filter(
        func.lower(models.Categoria.nome) == nome.lower(),
        models.Categoria.id != id,
    ).first()
    if duplicada:
        return {"success": False, "error": "Já existe uma categoria com esse nome."}
    categoria.nome = nome
    # Mantém os movimentos existentes coerentes com o novo nome
    if antigo != nome:
        db.query(models.Movimento).filter(models.Movimento.categoria == antigo).update(
            {models.Movimento.categoria: nome}
        )
    db.commit()
    db.refresh(categoria)
    return {"success": True, "data": _categoria_out(categoria)}


@router.delete("/categorias/{id}", response_model=schemas.APIResponse)
def eliminar_categoria(id: str, db: Session = Depends(database.get_db)):
    categoria = db.query(models.Categoria).filter(models.Categoria.id == id).first()
    if not categoria:
        return {"success": False, "error": "Categoria não encontrada."}
    db.delete(categoria)
    db.commit()
    return {"success": True, "data": {"id": id}}


@router.put("/{id}", response_model=schemas.APIResponse)
def atualizar_movimento(id: str, payload: schemas.MovimentoUpdate, db: Session = Depends(database.get_db)):
    mov = db.query(models.Movimento).filter(models.Movimento.id == id).first()
    if not mov:
        return {"success": False, "error": "Movimento não encontrado"}

    dados = payload.model_dump(exclude_unset=True)

    # O destinatário só se aplica a despesas (saídas); entradas nunca guardam esse valor
    if mov.tipo == "Entrada" and "destinatario" in dados:
        dados["destinatario"] = None

    # Converter data (string YYYY-MM-DD) para datetime
    if "data" in dados:
        if dados.get("data"):
            try:
                dados["data"] = datetime.strptime(dados["data"][:10], "%Y-%m-%d")
            except Exception:
                dados.pop("data", None)
        else:
            dados.pop("data", None)

    # Validar a conta bancária
    novo_conta_id = dados.get("conta_bancaria_id")
    if novo_conta_id:
        conta = db.query(models.ContaBancaria).filter(models.ContaBancaria.id == novo_conta_id).first()
        if not conta:
            return {"success": False, "error": "Conta bancária selecionada não encontrada."}
    else:
        dados.pop("conta_bancaria_id", None)
        novo_conta_id = None

    # Regra do saldo: para despesas, o novo valor não pode ultrapassar o saldo disponível
    if mov.tipo == "Saida":
        novo_valor = dados.get("valor", mov.valor)
        saldo_disponivel = _saldo_disponivel_antes(db, mov, novo_conta_id)
        if novo_valor > saldo_disponivel:
            return {"success": False, "error": f"Saldo insuficiente. Saldo disponível: {saldo_disponivel:,.2f} Kz"}

    for k, v in dados.items():
        setattr(mov, k, v)

    db.commit()
    db.refresh(mov)
    return {"success": True, "data": _movimento_out(mov)}


@router.delete("/{id}", response_model=schemas.APIResponse)
def eliminar_movimento(id: str, db: Session = Depends(database.get_db)):
    db_mov = db.query(models.Movimento).filter(models.Movimento.id == id).first()
    if not db_mov:
        return {"success": False, "error": "Movimento não encontrado"}
    db.delete(db_mov)
    db.commit()
    return {"success": True, "data": {"id": id}}