from database import Base
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import models
from database import engine

from routers import auth_router, clientes, contratos, intervencoes, tecnicos, registros_horas, stats, dev, relatorios, relatorio_contratos

models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="CLACS API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # Permitir todos durante desenvolvimento
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router.router)
app.include_router(clientes.router)
app.include_router(contratos.router)
app.include_router(intervencoes.router)
app.include_router(tecnicos.router)
app.include_router(registros_horas.router)
app.include_router(stats.router)
app.include_router(relatorios.router, prefix="/relatorios")
app.include_router(dev.router)
app.include_router(relatorio_contratos.router, prefix="/relatorios")
@app.on_event("startup")
def criar_tabelas():
    Base.metadata.create_all(bind=engine)
@app.get("/c")
def health_check():
    return {"status": "ok", "message": "Sistema CLACS Backend Oline"}

@app.get("/")
def read_root():
    return {"message": "Servidor rodando"}

