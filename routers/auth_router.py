from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from datetime import timedelta
import models, schemas, database, auth

router = APIRouter(prefix="/auth", tags=["auth"])

@router.post("/signup", response_model=schemas.APIResponse)
def register_user(user: schemas.UsuarioCreate, db: Session = Depends(database.get_db)):
    db_user = db.query(models.Usuario).filter(models.Usuario.email == user.email).first()
    if db_user:
        return {"success": False, "error": "Email already registered"}
    
    hashed_password = auth.get_password_hash(user.password)
    db_user = models.Usuario(
        email=user.email,
        hashed_password=hashed_password,
        nome=user.nome,
        perfil=user.perfil,
        telefone=user.telefone,
        empresa=user.empresa
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    
    return {
        "success": True, 
        "data": {"usuario_id": db_user.id, "email": db_user.email, "perfil": db_user.perfil}
    }

@router.post("/login", response_model=schemas.APIResponse)
def login_for_access_token(user_cred: schemas.UsuarioLogin, db: Session = Depends(database.get_db)):
    user = db.query(models.Usuario).filter(models.Usuario.email == user_cred.email).first()
    if not user or not auth.verify_password(user_cred.password, user.hashed_password):
        return {"success": False, "error": "Email ou senha incorretos"}
    
    access_token_expires = timedelta(minutes=auth.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = auth.create_access_token(
        data={"sub": user.email, "perfil": user.perfil}, expires_delta=access_token_expires
    )
    
    # Busca IDs relacionados se existirem
    tecnico_id = None
    cliente_id = None
    if user.perfil == "tecnico":
        tecnico = db.query(models.Tecnico).filter(models.Tecnico.usuario_id == user.id).first()
        if tecnico:
            tecnico_id = tecnico.id
    elif user.perfil == "cliente":
        cliente = db.query(models.Cliente).filter(models.Cliente.usuario_id == user.id).first()
        if cliente:
            cliente_id = cliente.id

    return {
        "success": True,
        "data": {
            "session": {
                "access_token": access_token,
                "refresh_token": access_token,
            },
            "profile": {
                "id": user.id,
                "email": user.email,
                "nome": user.nome,
                "tipo": user.perfil
            },
            "tecnicoId": tecnico_id,
            "clienteId": cliente_id
        }
    }

@router.post("/logout", response_model=schemas.APIResponse)
def logout(current_user: models.Usuario = Depends(auth.get_current_active_user)):
    return {"success": True, "message": "Logout realizado com sucesso"}

@router.get("/profile", response_model=schemas.APIResponse)
def read_users_me(current_user: models.Usuario = Depends(auth.get_current_active_user)):
    return {"success": True, "data": schemas.UsuarioOut.model_validate(current_user).model_dump()}

@router.put("/profile", response_model=schemas.APIResponse)
def update_users_me(
    dados: schemas.UsuarioUpdateSelf,
    current_user: models.Usuario = Depends(auth.get_current_active_user),
    db: Session = Depends(database.get_db)
):
    if dados.email and dados.email != current_user.email:
        existente = db.query(models.Usuario).filter(models.Usuario.email == dados.email).first()
        if existente:
            return {"success": False, "error": "Este email já está em uso por outro utilizador"}
        current_user.email = dados.email

    if dados.nome:
        current_user.nome = dados.nome

    if dados.nova_senha:
        current_user.hashed_password = auth.get_password_hash(dados.nova_senha)

    db.commit()
    db.refresh(current_user)
    return {"success": True, "data": schemas.UsuarioOut.model_validate(current_user).model_dump()}
