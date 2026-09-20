import os
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker, declarative_base

DATABASE_URL = os.environ.get("DATABASE_URL")

if DATABASE_URL:
    # Render fornece URLs com o prefixo "postgres://" (legado),
    # mas SQLAlchemy 1.4+ exige "postgresql://". Corrigimos aqui.
    if DATABASE_URL.startswith("postgresql://clacs_db_user:oInC5qGSAdmdNzXTrRzeH30eYDv2IKwX@dpg-d8bda6mq1p3s738oera0-a/clacs_db"):
        DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://clacs_db_user:oInC5qGSAdmdNzXTrRzeH30eYDv2IKwX@dpg-d8bda6mq1p3s738oera0-a.frankfurt-postgres.render.com/clacs_db", 1)

    engine = create_engine(
        DATABASE_URL,
        pool_pre_ping=True,
        pool_size=5,
        max_overflow=10,
    )
else:
    # Desenvolvimento local — SQLite
    DATABASE_URL = "sqlite:///./clacs.db"
    engine = create_engine(
        DATABASE_URL,
        connect_args={"check_same_thread": False},
    )

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

# Micro-migrações idempotentes (thais colunas em tabelas existentes)
def migrar():
    insp = inspect(engine)
    tabelas = set(insp.get_table_names())
    if "movimentos" in tabelas:
        colunas = {c["name"] for c in insp.get_columns("movimentos")}
        if "destinatario" not in colunas:
            with engine.begin() as conn:
                conn.execute(text("ALTER TABLE movimentos ADD COLUMN destinatario VARCHAR NULL"))

# Dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()