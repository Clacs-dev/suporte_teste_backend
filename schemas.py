from pydantic import BaseModel, EmailStr, ConfigDict, Field
from pydantic.alias_generators import to_camel
from typing import Optional, List
from datetime import datetime

# --- Pydantic Base Models ---

class BaseSchema(BaseModel):
    model_config = ConfigDict(
        populate_by_name=True,
        from_attributes=True,
        extra='ignore'
    )

class UsuarioBase(BaseSchema):
    email: EmailStr
    nome: str
    perfil: str
    telefone: Optional[str] = None
    empresa: Optional[str] = None

class UsuarioCreate(UsuarioBase):
    password: str

class UsuarioLogin(BaseSchema):
    email: EmailStr
    password: str

class UsuarioOut(UsuarioBase):
    id: str

class Token(BaseSchema):
    access_token: str
    refresh_token: str
    token_type: str

class TokenData(BaseSchema):
    email: Optional[str] = None

class ClienteBase(BaseSchema):
    nome: str
    email: EmailStr
    telefone: Optional[str] = None
    empresa: Optional[str] = None
    nif: Optional[str] = None
    endereco: Optional[str] = None
    status: Optional[str] = "Ativo"

class ClienteCreate(ClienteBase):
    senha: Optional[str] = None

class ClienteUpdate(BaseSchema):
    nome: Optional[str] = None
    email: Optional[str] = None
    telefone: Optional[str] = None
    empresa: Optional[str] = None
    senha: Optional[str] = None
    nif: Optional[str] = None
    endereco: Optional[str] = None
    status: Optional[str] = None

class ClienteOut(ClienteBase):
    id: str
    usuario_id: Optional[str] = None
    data_criacao: datetime

class TecnicoBase(BaseSchema):
    nome: str
    email: EmailStr
    nivel: Optional[str] = "Júnior"
    especialidade: Optional[str] = None

class TecnicoCreate(TecnicoBase):
    senha: Optional[str] = None

class TecnicoUpdate(BaseSchema):
    nome: Optional[str] = None
    email: Optional[str] = None
    nivel: Optional[str] = None
    especialidade: Optional[str] = None
    horas_mes: Optional[int] = None
    senha: Optional[str] = None

class TecnicoOut(TecnicoBase):
    id: str
    horas_mes: int
    avaliacao_media: float
    usuario_id: Optional[str] = None
    data_criacao: datetime

class ContratoBase(BaseSchema):
    cliente_id: str
    tipo: str
    horas_contratadas: Optional[float] = 0
    valor_mensal: Optional[float] = 0
    valor_total: Optional[float] = 0
    data_inicio: Optional[str] = None
    data_fim: Optional[str] = None
    observacoes: Optional[str] = None

class ContratoCreate(ContratoBase):
    pass

class ContratoUpdate(BaseSchema):
    horas_contratadas: Optional[float] = None
    horas_usadas: Optional[float] = None
    valor_mensal: Optional[float] = None
    valor_total: Optional[float] = None
    data_fim: Optional[str] = None
    status: Optional[str] = None
    observacoes: Optional[str] = None

class ContratoOut(ContratoBase):
    id: str
    horas_usadas: float
    status: str
    data_criacao: datetime

class IntervencaoBase(BaseSchema):
    titulo: str
    descricao: Optional[str] = None
    cliente_id: str
    tecnico_id: Optional[str] = None
    contrato_id: Optional[str] = None
    prioridade: Optional[str] = "Média"
    categoria: Optional[str] = None
    data_agendada: Optional[datetime] = None

class IntervencaoCreate(IntervencaoBase):
    anexos: Optional[List[dict]] = None

class IntervencaoUpdate(BaseSchema):
    titulo: Optional[str] = None
    descricao: Optional[str] = None
    tecnico_id: Optional[str] = None
    status: Optional[str] = None
    prioridade: Optional[str] = None
    categoria: Optional[str] = None
   


class IntervencaoStatusUpdate(BaseSchema):
    status: str

# ✅ IntervencaoOut usa alias_generator para converter snake_case → camelCase
#    automaticamente em todos os campos, sem model_post_init nem Field(alias=...) manuais.
#    No router, usar sempre .model_dump(by_alias=True) para activar os aliases.
class IntervencaoOut(BaseModel):
    model_config = ConfigDict(
        populate_by_name=True,
        from_attributes=True,
        extra='ignore',
        alias_generator=to_camel
    )

    id: str
    titulo: str
    descricao: Optional[str] = None
    cliente_id: str
    tecnico_id: Optional[str] = None
    contrato_id: Optional[str] = None
    prioridade: Optional[str] = "Média"
    categoria: Optional[str] = None
    numero: Optional[str] = None
    status: str
    horas_gastas: float
    data_criacao: datetime
    data_atualizacao: datetime
    data_agendada: Optional[datetime] = None
    cliente_nome: Optional[str] = None
    tecnico_nome: Optional[str] = None
    empresa_nome: Optional[str] = None


    
class RegistroHorasBase(BaseSchema):
    intervencao_id: str
    tecnico_id: str
    horas: float
    # ✅ Corrigido: snake_case consistente com o resto do modelo
    hora_inicio: Optional[str] = None
    hora_fim: Optional[str] = None
    descricao: Optional[str] = None
    data: Optional[str] = None

class RegistroHorasCreate(RegistroHorasBase):
    pass

class RegistroHorasOut(RegistroHorasBase):
    id: str
    data_criacao: datetime

# --- API Response Wrappers ---

class APIResponse(BaseSchema):
    success: bool
    data: Optional[dict | list | str | int | float | bool] = None
    error: Optional[str] = None
