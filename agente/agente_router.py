"""
Rotas da API para agentes.
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from database import get_db
from agente.agente_schema import (
    AgenteResposta,
    AgenteCriar,
    AgenteAtualizar,
    AgenteFerramentasAtualizar
)
from agente.agente_service import AgenteService

router = APIRouter(prefix="/api/agentes", tags=["Agentes"])


@router.get("/", response_model=List[AgenteResposta])
def listar_agentes(
    sessao_id: Optional[int] = Query(None),
    apenas_ativos: bool = Query(False),
    db: Session = Depends(get_db)
):
    """Lista todos os agentes."""
    if sessao_id is not None:
        if apenas_ativos:
            return AgenteService.listar_por_sessao_ativos(db, sessao_id)
        return AgenteService.listar_por_sessao(db, sessao_id)
    return AgenteService.listar_todos(db)


@router.get("/{agente_id}", response_model=AgenteResposta)
def obter_agente(agente_id: int, db: Session = Depends(get_db)):
    """Obtém um agente específico."""
    agente = AgenteService.obter_por_id(db, agente_id)
    if not agente:
        raise HTTPException(status_code=404, detail="Agente não encontrado")
    return agente


@router.post("/", response_model=AgenteResposta)
def criar_agente(agente: AgenteCriar, db: Session = Depends(get_db)):
    """Cria um novo agente."""
    try:
        return AgenteService.criar(db, agente)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.put("/{agente_id}", response_model=AgenteResposta)
def atualizar_agente(
    agente_id: int,
    agente: AgenteAtualizar,
    db: Session = Depends(get_db)
):
    """Atualiza um agente existente."""
    try:
        agente_atualizado = AgenteService.atualizar(db, agente_id, agente)
        if not agente_atualizado:
            raise HTTPException(status_code=404, detail="Agente não encontrado")
        return agente_atualizado
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/{agente_id}")
def deletar_agente(agente_id: int, db: Session = Depends(get_db)):
    """Deleta um agente."""
    sucesso = AgenteService.deletar(db, agente_id)
    if not sucesso:
        raise HTTPException(status_code=404, detail="Agente não encontrado")
    return {"mensagem": "Agente deletado com sucesso"}


@router.post("/{agente_id}/ferramentas")
def atualizar_ferramentas_agente(
    agente_id: int,
    ferramentas: AgenteFerramentasAtualizar,
    db: Session = Depends(get_db)
):
    """Atualiza as ferramentas de um agente (máximo 20)."""
    try:
        AgenteService.atualizar_ferramentas(db, agente_id, ferramentas.ferramentas)
        return {"mensagem": "Ferramentas atualizadas com sucesso"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{agente_id}/ferramentas")
def listar_ferramentas_agente(agente_id: int, db: Session = Depends(get_db)):
    """Lista as ferramentas ativas de um agente."""
    ferramentas = AgenteService.listar_ferramentas(db, agente_id)
    return ferramentas


@router.post("/{agente_id}/vincular-treinamento")
def vincular_treinamento_agente(
    agente_id: int,
    request: dict,
    db: Session = Depends(get_db)
):
    """Vincula ou desvincula um treinamento (RAG) de um agente."""
    try:
        rag_id = request.get("rag_id")
        
        # Validar que o agente existe
        agente = AgenteService.obter_por_id(db, agente_id)
        if not agente:
            raise HTTPException(status_code=404, detail="Agente não encontrado")
        
        # Se rag_id foi fornecido, validar que o RAG existe
        if rag_id is not None and rag_id != "":
            from rag.rag_service import RAGService
            rag = RAGService.obter_por_id(db, int(rag_id))
            if not rag:
                raise HTTPException(status_code=404, detail="RAG não encontrado")
        else:
            rag_id = None
        
        # Atualizar o agente com o novo rag_id
        AgenteService.atualizar(db, agente_id, AgenteAtualizar(rag_id=rag_id))
        
        if rag_id:
            return {"mensagem": "Treinamento vinculado com sucesso"}
        else:
            return {"mensagem": "Treinamento desvinculado com sucesso"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{agente_id}/testar-prompt")
async def testar_prompt_agente(
    agente_id: int,
    mensagem_teste: str = Query(..., description="Mensagem de teste para o prompt"),
    prompt_personalizado: Optional[str] = Query("", description="Prompt personalizado (opcional)"),
    db: Session = Depends(get_db)
):
    """Testa um prompt antes de aplicar ao agente."""
    try:
        # Obter sessão do agente
        agente = AgenteService.obter_por_id(db, agente_id)
        if not agente:
            raise HTTPException(status_code=404, detail="Agente não encontrado")

        resultado = await AgenteService.testar_prompt(
            db=db,
            agente_id=agente_id,
            sessao_id=agente.sessao_id,
            prompt_personalizado=prompt_personalizado,
            mensagem_teste=mensagem_teste
        )

        return {
            "teste_id": resultado["teste_id"],
            "resposta": resultado["resposta"],
            "modelo": resultado["modelo"],
            "tempo_ms": resultado["tempo_ms"],
            "tokens": resultado["tokens"],
            "sucesso": resultado["sucesso"]
        }

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/testar-prompt-personalizado")
async def testar_prompt_personalizado(
    prompt_personalizado: str = Query(..., description="Prompt personalizado para testar"),
    mensagem_teste: str = Query(..., description="Mensagem de teste"),
    sessao_id: int = Query(..., description="ID da sessão"),
    db: Session = Depends(get_db)
):
    """Testa um prompt personalizado sem agente específico."""
    try:
        resultado = await AgenteService.testar_prompt(
            db=db,
            agente_id=None,
            sessao_id=sessao_id,
            prompt_personalizado=prompt_personalizado,
            mensagem_teste=mensagem_teste
        )

        return {
            "teste_id": resultado["teste_id"],
            "resposta": resultado["resposta"],
            "modelo": resultado["modelo"],
            "tempo_ms": resultado["tempo_ms"],
            "tokens": resultado["tokens"],
            "sucesso": resultado["sucesso"]
        }

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/comparar/{agente_id_1}/{agente_id_2}")
def comparar_agentes(
    agente_id_1: int,
    agente_id_2: int,
    mensagem_teste: str = Query(..., description="Mensagem para testar ambos os agentes"),
    db: Session = Depends(get_db)
):
    """Compara performance entre dois agentes."""
    try:
        resultado = AgenteService.comparar_agentes(db, agente_id_1, agente_id_2, mensagem_teste)
        return resultado
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{agente_id}/estatisticas")
def obter_estatisticas_agente(agente_id: int, db: Session = Depends(get_db)):
    """Obtém estatísticas de performance de um agente."""
    try:
        agente = AgenteService.obter_por_id(db, agente_id)
        if not agente:
            raise HTTPException(status_code=404, detail="Agente não encontrado")

        estatisticas = AgenteService.obter_estatisticas_agente(db, agente_id)
        return estatisticas

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
