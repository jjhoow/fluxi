"""
Rotas do frontend para agentes.
"""
from fastapi import APIRouter, Depends, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from typing import Optional
from database import get_db
from agente.agente_service import AgenteService
from agente.agente_schema import AgenteCriar, AgenteAtualizar
from sessao.sessao_service import SessaoService
from ferramenta.ferramenta_service import FerramentaService
from config.config_service import ConfiguracaoService

router = APIRouter(prefix="/agentes", tags=["Frontend - Agentes"])
templates = Jinja2Templates(directory="templates")


@router.get("/sessao/{sessao_id}", response_class=HTMLResponse)
def pagina_agentes_sessao(sessao_id: int, request: Request, db: Session = Depends(get_db)):
    """Página de listagem de agentes de uma sessão."""
    sessao = SessaoService.obter_por_id(db, sessao_id)
    if not sessao:
        return templates.TemplateResponse("shared/erro.html", {
            "request": request,
            "mensagem": "Sessão não encontrada",
            "titulo": "Erro"
        })
    
    agentes = AgenteService.listar_por_sessao(db, sessao_id)
    
    return templates.TemplateResponse("agente/lista.html", {
        "request": request,
        "sessao": sessao,
        "agentes": agentes,
        "titulo": f"Agentes - {sessao.nome}"
    })


@router.get("/sessao/{sessao_id}/novo", response_class=HTMLResponse)
def pagina_novo_agente(sessao_id: int, request: Request, db: Session = Depends(get_db)):
    """Página para criar novo agente."""
    sessao = SessaoService.obter_por_id(db, sessao_id)
    if not sessao:
        return templates.TemplateResponse("shared/erro.html", {
            "request": request,
            "mensagem": "Sessão não encontrada",
            "titulo": "Erro"
        })
    
    # Buscar configurações padrão
    config_agente = {
        "papel": ConfiguracaoService.obter_valor(db, "agente_papel_padrao", "assistente pessoal"),
        "objetivo": ConfiguracaoService.obter_valor(db, "agente_objetivo_padrao", "ajudar o usuário"),
        "politicas": ConfiguracaoService.obter_valor(db, "agente_politicas_padrao", "ser educado e prestativo"),
        "tarefa": ConfiguracaoService.obter_valor(db, "agente_tarefa_padrao", "responder perguntas"),
        "objetivo_explicito": ConfiguracaoService.obter_valor(db, "agente_objetivo_explicito_padrao", "fornecer informações úteis"),
        "publico": ConfiguracaoService.obter_valor(db, "agente_publico_padrao", "usuários em geral"),
        "restricoes": ConfiguracaoService.obter_valor(db, "agente_restricoes_padrao", "responder em português")
    }
    
    # Sugerir próximo código
    agentes_existentes = AgenteService.listar_por_sessao(db, sessao_id)
    proximo_codigo = str(len(agentes_existentes) + 1).zfill(2)
    
    return templates.TemplateResponse("agente/form.html", {
        "request": request,
        "sessao": sessao,
        "config_agente": config_agente,
        "proximo_codigo": proximo_codigo,
        "titulo": "Novo Agente",
        "acao": "criar"
    })


@router.get("/{agente_id}/editar", response_class=HTMLResponse)
def pagina_editar_agente(agente_id: int, request: Request, db: Session = Depends(get_db)):
    """Página para editar agente."""
    agente = AgenteService.obter_por_id(db, agente_id)
    if not agente:
        return templates.TemplateResponse("shared/erro.html", {
            "request": request,
            "mensagem": "Agente não encontrado",
            "titulo": "Erro"
        })
    
    sessao = SessaoService.obter_por_id(db, agente.sessao_id)
    
    # Buscar RAGs disponíveis para vincular
    from rag.rag_service import RAGService
    rags_disponiveis = RAGService.listar_ativos(db)
    
    return templates.TemplateResponse("agente/form.html", {
        "request": request,
        "sessao": sessao,
        "agente": agente,
        "rags_disponiveis": rags_disponiveis,
        "titulo": f"Editar Agente - {agente.nome}",
        "acao": "editar"
    })


@router.post("/sessao/{sessao_id}/criar")
def criar_agente(
    sessao_id: int,
    request: Request,
    codigo: str = Form(...),
    nome: str = Form(...),
    descricao: str = Form(""),
    agente_papel: str = Form(...),
    agente_objetivo: str = Form(...),
    agente_politicas: str = Form(...),
    agente_tarefa: str = Form(...),
    agente_objetivo_explicito: str = Form(...),
    agente_publico: str = Form(...),
    agente_restricoes: str = Form(...),
    modelo_llm: Optional[str] = Form(None),
    temperatura: Optional[str] = Form(None),
    max_tokens: Optional[str] = Form(None),
    top_p: Optional[str] = Form(None),
    ativo: bool = Form(True),
    db: Session = Depends(get_db)
):
    """Cria um novo agente."""
    try:
        agente_data = AgenteCriar(
            sessao_id=sessao_id,
            codigo=codigo,
            nome=nome,
            descricao=descricao,
            agente_papel=agente_papel,
            agente_objetivo=agente_objetivo,
            agente_politicas=agente_politicas,
            agente_tarefa=agente_tarefa,
            agente_objetivo_explicito=agente_objetivo_explicito,
            agente_publico=agente_publico,
            agente_restricoes=agente_restricoes,
            modelo_llm=modelo_llm if modelo_llm else None,
            temperatura=temperatura if temperatura else None,
            max_tokens=max_tokens if max_tokens else None,
            top_p=top_p if top_p else None,
            ativo=ativo
        )
        
        AgenteService.criar(db, agente_data)
        return RedirectResponse(url=f"/agentes/sessao/{sessao_id}", status_code=303)
    except ValueError as e:
        return templates.TemplateResponse("shared/erro.html", {
            "request": request,
            "mensagem": str(e),
            "titulo": "Erro ao criar agente"
        })


@router.post("/{agente_id}/atualizar")
def atualizar_agente(
    agente_id: int,
    request: Request,
    codigo: str = Form(...),
    nome: str = Form(...),
    descricao: str = Form(""),
    agente_papel: str = Form(...),
    agente_objetivo: str = Form(...),
    agente_politicas: str = Form(...),
    agente_tarefa: str = Form(...),
    agente_objetivo_explicito: str = Form(...),
    agente_publico: str = Form(...),
    agente_restricoes: str = Form(...),
    modelo_llm: Optional[str] = Form(None),
    temperatura: Optional[str] = Form(None),
    max_tokens: Optional[str] = Form(None),
    top_p: Optional[str] = Form(None),
    ativo: bool = Form(True),
    db: Session = Depends(get_db)
):
    """Atualiza um agente."""
    agente = AgenteService.obter_por_id(db, agente_id)
    if not agente:
        return templates.TemplateResponse("shared/erro.html", {
            "request": request,
            "mensagem": "Agente não encontrado",
            "titulo": "Erro"
        })
    
    try:
        agente_data = AgenteAtualizar(
            codigo=codigo,
            nome=nome,
            descricao=descricao,
            agente_papel=agente_papel,
            agente_objetivo=agente_objetivo,
            agente_politicas=agente_politicas,
            agente_tarefa=agente_tarefa,
            agente_objetivo_explicito=agente_objetivo_explicito,
            agente_publico=agente_publico,
            agente_restricoes=agente_restricoes,
            modelo_llm=modelo_llm if modelo_llm else None,
            temperatura=temperatura if temperatura else None,
            max_tokens=max_tokens if max_tokens else None,
            top_p=top_p if top_p else None,
            ativo=ativo
        )
        
        AgenteService.atualizar(db, agente_id, agente_data)
        return RedirectResponse(url=f"/agentes/sessao/{agente.sessao_id}", status_code=303)
    except ValueError as e:
        return templates.TemplateResponse("shared/erro.html", {
            "request": request,
            "mensagem": str(e),
            "titulo": "Erro ao atualizar agente"
        })


@router.get("/{agente_id}/ferramentas", response_class=HTMLResponse)
def pagina_ferramentas_agente(agente_id: int, request: Request, db: Session = Depends(get_db)):
    """Página para gerenciar ferramentas do agente."""
    agente = AgenteService.obter_por_id(db, agente_id)
    if not agente:
        return templates.TemplateResponse("shared/erro.html", {
            "request": request,
            "mensagem": "Agente não encontrado",
            "titulo": "Erro"
        })
    
    sessao = SessaoService.obter_por_id(db, agente.sessao_id)
    
    # Buscar todas as ferramentas disponíveis
    todas_ferramentas = FerramentaService.listar_ferramentas_ativas(db)
    
    # Buscar ferramentas já associadas ao agente
    ferramentas_agente = AgenteService.listar_ferramentas(db, agente_id)
    ferramentas_agente_ids = [f.id for f in ferramentas_agente]
    
    return templates.TemplateResponse("agente/ferramentas.html", {
        "request": request,
        "sessao": sessao,
        "agente": agente,
        "todas_ferramentas": todas_ferramentas,
        "ferramentas_agente_ids": ferramentas_agente_ids,
        "total_selecionadas": len(ferramentas_agente_ids),
        "titulo": f"Ferramentas - {agente.nome}"
    })


@router.post("/{agente_id}/ferramentas/atualizar")
async def atualizar_ferramentas_agente(
    agente_id: int,
    request: Request,
    db: Session = Depends(get_db)
):
    """Atualiza as ferramentas do agente."""
    agente = AgenteService.obter_por_id(db, agente_id)
    if not agente:
        return templates.TemplateResponse("shared/erro.html", {
            "request": request,
            "mensagem": "Agente não encontrado",
            "titulo": "Erro"
        })
    
    # Obter ferramentas selecionadas do form
    form_data = await request.form()
    ferramentas_ids = []
    
    for key in form_data.keys():
        if key.startswith("ferramenta_"):
            ferramenta_id = int(key.replace("ferramenta_", ""))
            ferramentas_ids.append(ferramenta_id)
    
    try:
        AgenteService.atualizar_ferramentas(db, agente_id, ferramentas_ids)
        return RedirectResponse(url=f"/agentes/{agente_id}/ferramentas", status_code=303)
    except ValueError as e:
        return templates.TemplateResponse("shared/erro.html", {
            "request": request,
            "mensagem": str(e),
            "titulo": "Erro ao atualizar ferramentas"
        })


@router.post("/{agente_id}/deletar")
def deletar_agente(agente_id: int, db: Session = Depends(get_db)):
    """Deleta um agente."""
    agente = AgenteService.obter_por_id(db, agente_id)
    if agente:
        sessao_id = agente.sessao_id
        AgenteService.deletar(db, agente_id)
        return RedirectResponse(url=f"/agentes/sessao/{sessao_id}", status_code=303)
    return RedirectResponse(url="/sessoes", status_code=303)


@router.post("/{agente_id}/ativar")
def ativar_agente(agente_id: int, db: Session = Depends(get_db)):
    """Define este agente como ativo na sessão."""
    agente = AgenteService.obter_por_id(db, agente_id)
    if agente:
        sessao = SessaoService.obter_por_id(db, agente.sessao_id)
        if sessao:
            from sessao.sessao_schema import SessaoAtualizar
            SessaoService.atualizar(db, sessao.id, SessaoAtualizar(agente_ativo_id=agente_id))
        return RedirectResponse(url=f"/agentes/sessao/{agente.sessao_id}", status_code=303)
    return RedirectResponse(url="/sessoes", status_code=303)


@router.get("/comparar-agentes", response_class=HTMLResponse)
def pagina_comparar_agentes(request: Request, db: Session = Depends(get_db)):
    """Página para comparar agentes."""
    sessoes = SessaoService.listar_todas(db, apenas_ativas=True)
    agentes = AgenteService.listar_todos(db)

    return templates.TemplateResponse("comparar-agentes.html", {
        "request": request,
        "sessoes": sessoes,
        "agentes": agentes,
        "titulo": "Comparar Agentes"
    })
