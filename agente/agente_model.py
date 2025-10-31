"""
Modelo de dados para agentes.
"""
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, ForeignKey, Table, Float
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from database import Base


# Tabela de associação Agente-Ferramenta (many-to-many)
agente_ferramenta = Table(
    'agente_ferramenta',
    Base.metadata,
    Column('agente_id', Integer, ForeignKey('agentes.id', ondelete='CASCADE'), primary_key=True),
    Column('ferramenta_id', Integer, ForeignKey('ferramentas.id', ondelete='CASCADE'), primary_key=True),
    Column('ativa', Boolean, default=True),  # Se a ferramenta está ativa para este agente
    Column('criado_em', DateTime(timezone=True), server_default=func.now())
)


class Agente(Base):
    """
    Tabela de agentes.
    Cada agente tem seu próprio system prompt e pode ter até 20 ferramentas ativas.
    """
    __tablename__ = "agentes"

    id = Column(Integer, primary_key=True, index=True)
    sessao_id = Column(Integer, ForeignKey("sessoes.id", ondelete='CASCADE'), nullable=False, index=True)
    
    # Identificação
    codigo = Column(String(10), nullable=False, index=True)  # Ex: "01", "02", etc.
    nome = Column(String(100), nullable=False)
    descricao = Column(Text, nullable=True)
    
    # System Prompt (campos do agente)
    agente_papel = Column(Text, nullable=False)
    agente_objetivo = Column(Text, nullable=False)
    agente_politicas = Column(Text, nullable=False)
    agente_tarefa = Column(Text, nullable=False)
    agente_objetivo_explicito = Column(Text, nullable=False)
    agente_publico = Column(Text, nullable=False)
    agente_restricoes = Column(Text, nullable=False)
    
    # Configurações LLM específicas do agente
    modelo_llm = Column(String(100), nullable=True)
    temperatura = Column(String(10), nullable=True)
    max_tokens = Column(String(10), nullable=True)
    top_p = Column(String(10), nullable=True)
    
    # RAG (Base de Conhecimento)
    rag_id = Column(Integer, ForeignKey("rags.id", ondelete='SET NULL'), nullable=True, index=True)
    
    # Status
    ativo = Column(Boolean, default=True)
    
    # Timestamps
    criado_em = Column(DateTime(timezone=True), server_default=func.now())
    atualizado_em = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relacionamentos
    sessao = relationship("Sessao", back_populates="agentes", foreign_keys=[sessao_id])
    ferramentas = relationship(
        "Ferramenta",
        secondary=agente_ferramenta,
        back_populates="agentes",
        lazy="dynamic"
    )
    rag = relationship("RAG", back_populates="agentes", foreign_keys=[rag_id])
    mcp_clients = relationship("MCPClient", back_populates="agente", cascade="all, delete-orphan")
    testes = relationship("AgenteTeste", back_populates="agente", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Agente(codigo='{self.codigo}', nome='{self.nome}', sessao_id={self.sessao_id})>"


class AgenteTeste(Base):
    """
    Testes de prompts realizados pelos usuários.
    """
    __tablename__ = "agente_testes"

    id = Column(Integer, primary_key=True, index=True)
    
    # Relacionamentos
    agente_id = Column(Integer, ForeignKey("agentes.id", ondelete='CASCADE'), nullable=True)
    sessao_id = Column(Integer, ForeignKey("sessoes.id", ondelete='CASCADE'), nullable=False)
    usuario_id = Column(String(100), nullable=True)  # Para multi-usuário futuro
    
    # Dados do teste
    prompt_testado = Column(Text, nullable=False)
    mensagem_teste = Column(Text, nullable=False)
    
    # Resposta gerada
    resposta_gerada = Column(Text, nullable=True)
    modelo_usado = Column(String(100), nullable=True)
    
    # Métricas
    tempo_resposta_ms = Column(Float, nullable=True)
    tokens_usados = Column(Integer, nullable=True)
    
    # Avaliação
    avaliacao = Column(Integer, nullable=True)  # 1-5 estrelas
    feedback = Column(Text, nullable=True)
    
    # Status
    sucesso = Column(Boolean, default=True)
    erro_mensagem = Column(Text, nullable=True)
    
    # Timestamps
    criado_em = Column(DateTime(timezone=True), server_default=func.now())

    # Relacionamentos
    agente = relationship("Agente", back_populates="testes")
    sessao = relationship("Sessao", foreign_keys=[sessao_id])

    def __repr__(self):
        return f"<AgenteTeste(agente_id={self.agente_id}, sucesso={self.sucesso})>"
