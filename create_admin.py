import models
import auth
from database import SessionLocal, engine

# Garante que as tabelas existem
models.Base.metadata.create_all(bind=engine)

def create_initial_admin():
    db = SessionLocal()
    try:
        # Verifica se já existe um admin
        admin_email = "admin@clacs.ao"
        existing_admin = db.query(models.Usuario).filter(models.Usuario.email == admin_email).first()
        
        if existing_admin:
            print(f"O usuário {admin_email} já existe.")
            return

        # Cria o admin
        hashed_password = auth.get_password_hash("admin123")
        new_admin = models.Usuario(
            email=admin_email,
            hashed_password=hashed_password,
            nome="Administrador Sistema",
            perfil="admin"
        )
        
        db.add(new_admin)
        db.commit()
        print(f"Usuário admin criado com sucesso!")
        print(f"Email: {admin_email}")
        print(f"Senha: admin123")
        
    except Exception as e:
        print(f"Erro ao criar admin: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    create_initial_admin()
