"""
Schemas Pydantic para validação de agentes.
"""
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


class AgenteBase(BaseModel):
    """Schema base para agente."""
    codigo: str = Field(..., description="Código do agente (ex: 01, 02)")
    nome: str = Field(..., description="Nome do agente")
    descricao: Optional[str] = Field(None, description="Descrição do agente")
    agente_papel: str = Field(..., description="Papel do agente")
    agente_objetivo: str = Field(..., description="Objetivo do agente")
    agente_politicas: str = Field(..., description="Políticas do agente")
    agente_tarefa: str = Field(..., description="Tarefa do agente")
    agente_objetivo_explicito: str = Field(..., description="Objetivo explícito do agente")
    agente_publico: str = Field(..., description="Público-alvo do agente")
    agente_restricoes: str = Field(..., description="Restrições do agente")
    modelo_llm: Optional[str] = Field(None, description="Modelo LLM específico")
    temperatura: Optional[str] = Field(None, description="Temperatura do modelo")
    max_tokens: Optional[str] = Field(None, description="Máximo de tokens")
    top_p: Optional[str] = Field(None, description="Top P")
    ativo: bool = Field(default=True, description="Se o agente está ativo")


class AgenteCriar(AgenteBase):
    """Schema para criar novo agente."""
    sessao_id: int


class AgenteAtualizar(BaseModel):
    """Schema para atualizar agente."""
    codigo: Optional[str] = None
    nome: Optional[str] = None
    descricao: Optional[str] = None
    agente_papel: Optional[str] = None
    agente_objetivo: Optional[str] = None
    agente_politicas: Optional[str] = None
    agente_tarefa: Optional[str] = None
    agente_objetivo_explicito: Optional[str] = None
    agente_publico: Optional[str] = None
    agente_restricoes: Optional[str] = None
    modelo_llm: Optional[str] = None
    temperatura: Optional[str] = None
    max_tokens: Optional[str] = None
    top_p: Optional[str] = None
    rag_id: Optional[int] = None
    ativo: Optional[bool] = None


class AgenteResposta(AgenteBase):
    """Schema de resposta com dados completos."""
    id: int
    sessao_id: int
    rag_id: Optional[int] = None
    criado_em: datetime
    atualizado_em: Optional[datetime] = None

    class Config:
        from_attributes = True


class AgenteFerramentaAssociar(BaseModel):
    """Schema para associar/desassociar ferramenta de um agente."""
    ferramenta_id: int
    ativa: bool = True


class AgenteFerramentasAtualizar(BaseModel):
    """Schema para atualizar ferramentas de um agente."""
    ferramentas: List[int] = Field(..., description="Lista de IDs de ferramentas (máximo 20)")


class AgenteTesteBase(BaseModel):
    """Schema base para teste de agente."""
    agente_id: Optional[int] = Field(None, description="ID do agente testado")
    sessao_id: int = Field(..., description="ID da sessão")
    prompt_testado: str = Field(..., description="Prompt que foi testado")
    mensagem_teste: str = Field(..., description="Mensagem de teste enviada")
    resposta_gerada: Optional[str] = Field(None, description="Resposta gerada pelo LLM")
    modelo_usado: Optional[str] = Field(None, description="Modelo LLM utilizado")
    tempo_resposta_ms: Optional[float] = Field(None, description="Tempo de resposta em ms")
    tokens_usados: Optional[int] = Field(None, description="Tokens utilizados")
    avaliacao: Optional[int] = Field(None, ge=1, le=5, description="Avaliação 1-5 estrelas")
    feedback: Optional[str] = Field(None, description="Feedback do usuário")
    sucesso: bool = Field(default=True, description="Se o teste foi bem-sucedido")
    erro_mensagem: Optional[str] = Field(None, description="Mensagem de erro se houver")


class AgenteTesteCriar(AgenteTesteBase):
    """Schema para criar teste de agente."""
    pass


class AgenteTesteResposta(AgenteTesteBase):
    """Schema de resposta com dados completos."""
    id: int
    criado_em: datetime

    class Config:
        from_attributes = True


class AgenteComparacaoResposta(BaseModel):
    """Schema para resposta de comparação entre agentes."""
    agente_1: dict = Field(..., description="Dados do primeiro agente")
    agente_2: dict = Field(..., description="Dados do segundo agente")
    comparacao: dict = Field(..., description="Dados de comparação")
    recomendacao: str = Field(..., description="Recomendação baseada na análise")
