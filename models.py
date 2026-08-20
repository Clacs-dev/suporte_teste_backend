import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Integer, Float, ForeignKey, DateTime, Boolean
from sqlalchemy.orm import relationship
from database import Base

def generate_uuid():
    return str(uuid.uuid4())

class Usuario(Base):
    __tablename__ = "usuarios"

    id = Column(String, primary_key=True, index=True, default=generate_uuid)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    nome = Column(String, nullable=False)
    perfil = Column(String, nullable=False) # 'admin', 'tecnico', 'cliente'
    telefone = Column(String, nullable=True)
    empresa = Column(String, nullable=True)

class Cliente(Base):
    __tablename__ = "clientes"

    id = Column(String, primary_key=True, index=True, default=generate_uuid)
    nome = Column(String, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    telefone = Column(String, nullable=True)
    empresa = Column(String, nullable=True)
    nif = Column(String, nullable=True)
    endereco = Column(String, nullable=True)
    status = Column(String, default="Ativo")
    tipo_cliente = Column(String, default="Com Contrato")  # "Com Contrato" ou "Sem Contrato"
    usuario_id = Column(String, ForeignKey("usuarios.id"), nullable=True)
    data_criacao = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    contratos = relationship("Contrato", back_populates="cliente", cascade="all, delete-orphan")
    intervencoes = relationship("Intervencao", back_populates="cliente", cascade="all, delete-orphan")
    

class Tecnico(Base):
    __tablename__ = "tecnicos"

    id = Column(String, primary_key=True, index=True, default=generate_uuid)
    nome = Column(String, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    nivel = Column(String, default="Júnior") # Júnior, Pleno, Sênior
    especialidade = Column(String, nullable=True)
    horas_mes = Column(Integer, default=160)
    avaliacao_media = Column(Float, default=0.0)
    usuario_id = Column(String, ForeignKey("usuarios.id"), nullable=True)
    data_criacao = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    intervencoes = relationship("Intervencao", back_populates="tecnico")
    registros_horas = relationship("RegistroHoras", back_populates="tecnico", cascade="all, delete-orphan")

class Contrato(Base):
    __tablename__ = "contratos"

    id = Column(String, primary_key=True, index=True, default=generate_uuid)
    cliente_id = Column(String, ForeignKey("clientes.id"), nullable=False)
    tipo = Column(String, default="Mensal") # Mensal, Anual, Por Hora
    horas_contratadas = Column(Float, default=0)
    horas_usadas = Column(Float, default=0)
    valor_mensal = Column(Float, default=0)
    valor_total = Column(Float, default=0)
    data_inicio = Column(String, nullable=True)
    data_fim = Column(String, nullable=True)
    status = Column(String, default="Ativo")
    observacoes = Column(String, nullable=True)
    data_criacao = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    cliente = relationship("Cliente", back_populates="contratos")

class Intervencao(Base):
    __tablename__ = "intervencoes"

    id = Column(String, primary_key=True, index=True, default=generate_uuid)
    titulo = Column(String, nullable=False)
    descricao = Column(String, nullable=True)
    cliente_id = Column(String, ForeignKey("clientes.id"), nullable=False)
    tecnico_id = Column(String, ForeignKey("tecnicos.id"), nullable=True)
    contrato_id = Column(String, ForeignKey("contratos.id"), nullable=True)
    prioridade = Column(String, default="Média") # Alta, Média, Baixa
    status = Column(String, default="Aberto") # Aberto, Em Andamento, Aguardando Cliente, Concluído
    categoria = Column(String, nullable=True)
    horas_gastas = Column(Float, default=0)
    numero = Column(String, nullable=True) # Ex: INT-2026-001
    data_criacao = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    data_atualizacao = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    data_agendada = Column(DateTime, nullable=True)
    nome_assinatura_tecnico = Column(String, nullable=True)  # ← adiciona
    data_assinatura_tecnico = Column(String, nullable=True)  # ← adiciona
    nome_assinatura_cliente = Column(String, nullable=True)   # ← adiciona
    data_assinatura_cliente = Column(String, nullable=True)   # ← adiciona
    modo_resolucao = Column(String, nullable=True)  # Remoto, Presencial
    data_resolucao = Column(DateTime, nullable=True)
    data_fecho = Column(DateTime, nullable=True)
    solicitante = Column(String, nullable=True)
    




    cliente = relationship("Cliente", back_populates="intervencoes")
    tecnico = relationship("Tecnico", back_populates="intervencoes")
    registros_horas = relationship("RegistroHoras", back_populates="intervencao", cascade="all, delete-orphan")
    anexos = relationship("Anexo", back_populates="intervencao", cascade="all, delete-orphan")
    
class RegistroHoras(Base):
    __tablename__ = "registros_horas"

    id = Column(String, primary_key=True, index=True, default=generate_uuid)
    intervencao_id = Column(String, ForeignKey("intervencoes.id"), nullable=False)
    tecnico_id = Column(String, ForeignKey("tecnicos.id"), nullable=False)
    hora_inicio = Column("horaInicio", String, nullable=True)
    hora_fim = Column("horaFim", String, nullable=True)
    horas = Column(Float, nullable=False)
    descricao = Column(String, nullable=True)
    data = Column(String, nullable=True)
    data_criacao = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    intervencao = relationship("Intervencao", back_populates="registros_horas")
    tecnico = relationship("Tecnico", back_populates="registros_horas")

class Notificacao(Base):
    __tablename__ = "notificacoes"

    id = Column(String, primary_key=True, index=True, default=generate_uuid)
    usuario_id = Column(String, ForeignKey("usuarios.id"), nullable=False)
    titulo = Column(String, nullable=False)
    mensagem = Column(String, nullable=True)
    tipo = Column(String, default="info")  # info, success, warning
    lida = Column(Boolean, default=False)
    intervencao_id = Column(String, ForeignKey("intervencoes.id"), nullable=True)
    data_criacao = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class Anexo(Base):
    __tablename__ = "anexos"

    id = Column(String, primary_key=True, index=True, default=generate_uuid)
    intervencao_id = Column(String, ForeignKey("intervencoes.id"), nullable=False)
    url = Column(String, nullable=False)
    nome = Column(String, nullable=True)
    tipo = Column(String, nullable=True)  # image, pdf, doc
    data_criacao = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    intervencao = relationship("Intervencao", back_populates="anexos")    