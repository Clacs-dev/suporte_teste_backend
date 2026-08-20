from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
import models, schemas, database, auth

router = APIRouter(prefix="/clientes", tags=["clientes"])

# A dependência de usuário não é obrigatória para métodos GET (simulando PUBLIC_READ_ROUTES do frontend original)
# Mas para o novo design é melhor que a aplicação toda passe o token.
# No código atual de frontend (api.ts) clientes faz GET com publicAnonKey, 
# Então, para compatibilidade sem re-escrever todo front-end auth agora:
def get_db():
    return database.SessionLocal()

@router.get("", response_model=schemas.APIResponse)
def get_clientes(db: Session = Depends(database.get_db)):
    clientes = db.query(models.Cliente).all()
    # Conta contratos ativos
    results = []
    for c in clientes:
        c_dict = schemas.ClienteOut.model_validate(c).model_dump()
        c_dict['contratosAtivos'] = sum(1 for con in c.contratos if con.status == "Ativo")
        # Compatibilidade com campos vindos do frontend camelCase/snake_case
        c_dict['dataCriacao'] = c.data_criacao.isoformat()
        results.append(c_dict)
    return {"success": True, "data": results}


@router.get("/usuario/{usuario_id}", response_model=schemas.APIResponse)
def get_cliente_por_usuario(usuario_id: str, db: Session = Depends(database.get_db)):
    cliente = db.query(models.Cliente).filter(models.Cliente.usuario_id == usuario_id).first()
    if not cliente:
        return {"success": False, "error": "Cliente não encontrado para este usuário"}
    return {"success": True, "data": schemas.ClienteOut.model_validate(cliente).model_dump()}

@router.get("/{id}", response_model=schemas.APIResponse)
def get_cliente(id: str, db: Session = Depends(database.get_db)):
    cliente = db.query(models.Cliente).filter(models.Cliente.id == id).first()
    if not cliente:
        return {"success": False, "error": "Cliente não encontrado"}
    return {"success": True, "data": schemas.ClienteOut.model_validate(cliente).model_dump()}



@router.post("", response_model=schemas.APIResponse)
def create_cliente(cliente: schemas.ClienteCreate, db: Session = Depends(database.get_db)):
    try:
        # Criar usuário associado se houver senha
        usuario_id = None
        if cliente.senha:
            db_user = db.query(models.Usuario).filter(models.Usuario.email == cliente.email).first()
            if not db_user:
                hashed_password = auth.get_password_hash(cliente.senha)
                db_user = models.Usuario(
                    email=cliente.email,
                    hashed_password=hashed_password,
                    nome=cliente.nome,
                    perfil="cliente",
                    telefone=cliente.telefone,
                    empresa=cliente.empresa
                )
                db.add(db_user)
                db.commit()
                db.refresh(db_user)
            usuario_id = db_user.id

        db_cliente = models.Cliente(
            nome=cliente.nome,
            email=cliente.email,
            telefone=cliente.telefone,
            empresa=cliente.empresa,
            nif=cliente.nif,
            endereco=cliente.endereco,
            status=cliente.status,
            tipo_cliente=cliente.tipo_cliente,
            usuario_id=usuario_id
        )
        db.add(db_cliente)
        db.commit()
        db.refresh(db_cliente)
        
        # Preparar retorno completo para o frontend
        c_dict = schemas.ClienteOut.model_validate(db_cliente).model_dump()
        c_dict['contratosAtivos'] = 0
        c_dict['dataCriacao'] = db_cliente.data_criacao.isoformat()
        
        return {"success": True, "data": c_dict}
    except Exception as e:
        db.rollback()
        error_msg = str(e)
        if "UNIQUE constraint failed" in error_msg or "already exists" in error_msg:
            return {"success": False, "error": "Já existe um cliente cadastrado com este e-mail."}
        print(f"Erro ao criar cliente: {e}")
        return {"success": False, "error": f"Erro interno ao criar cliente: {error_msg}"}

@router.put("/{id}", response_model=schemas.APIResponse)
def update_cliente(id: str, cliente: schemas.ClienteUpdate, db: Session = Depends(database.get_db)):
    db_cliente = db.query(models.Cliente).filter(models.Cliente.id == id).first()
    if not db_cliente:
        return {"success": False, "error": "Cliente não encontrado"}

    update_data = cliente.model_dump(exclude_unset=True)

    # Tratar senha separadamente — atualizar o utilizador associado
    senha = update_data.pop("senha", None)
    if senha:
        db_usuario = db.query(models.Usuario).filter(
            models.Usuario.id == db_cliente.usuario_id
        ).first()
        if db_usuario:
            db_usuario.hashed_password = auth.get_password_hash(senha)

        # Impedir marcar como "Sem Contrato" se o cliente tem contratos reais
    if update_data.get("tipo_cliente") == "Sem Contrato":
        tem_contrato = db.query(models.Contrato).filter(
            models.Contrato.cliente_id == id
        ).first()
        if tem_contrato:
            return {"success": False, "error": "Não é possível marcar como 'Sem Contrato': o cliente tem contrato(s) associado(s). Remova o(s) contrato(s) primeiro."}

    for key, value in update_data.items():
        setattr(db_cliente, key, value)        

    for key, value in update_data.items():
        setattr(db_cliente, key, value)

    db.commit()
    db.refresh(db_cliente)
    return {"success": True, "data": schemas.ClienteOut.model_validate(db_cliente).model_dump()}

@router.delete("/{id}", response_model=schemas.APIResponse)
def delete_cliente(id: str, db: Session = Depends(database.get_db)):
    db_cliente = db.query(models.Cliente).filter(models.Cliente.id == id).first()
    if not db_cliente:
        return {"success": False, "error": "Cliente não encontrado"}

    # Bloquear exclusão se houver intervenções associadas
    tem_intervencoes = db.query(models.Intervencao).filter(
        models.Intervencao.cliente_id == id
    ).first()
    if tem_intervencoes:
        return {
            "success": False,
            "error": "Não é possível eliminar este cliente porque existem intervenções associadas. Elimine primeiro as intervenções."
        }

    # Bloquear exclusão se houver contratos associados
    tem_contratos = db.query(models.Contrato).filter(
        models.Contrato.cliente_id == id
    ).first()
    if tem_contratos:
        return {
            "success": False,
            "error": "Não é possível eliminar este cliente porque existem contratos associados. Elimine primeiro os contratos."
        }

    db.delete(db_cliente)
    db.commit()
    return {"success": True, "message": "Cliente deletado com sucesso"}