from database import Base
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
import models
from database import engine

from routers import auth_router, clientes, contratos, intervencoes, tecnicos, registros_horas, stats, dev, relatorios, relatorio_contratos, relatorio_geral, notificacoes

models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="CLACS API", version="1.0.0")

origins = [
    "http://localhost:5173",
    "https://clacs-frontend.vercel.app",
    "https://suporte.clacstecnologia.com",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.middleware("http")
async def add_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Frame-Options"] = "ALLOWALL"
    response.headers["Content-Security-Policy"] = "frame-ancestors *"
    return response

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
app.include_router(relatorio_geral.router, prefix="/relatorios")
app.include_router(notificacoes.router)

@app.on_event("startup")
def criar_tabelas():
    Base.metadata.create_all(bind=engine)

@app.get("/c")
def health_check():
    return {"status": "ok", "message": "Sistema CLACS Backend Online"}

@app.get("/")
def read_root():
    return {"message": "Servidor rodando"}