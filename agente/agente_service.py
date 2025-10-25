"""
Serviço do agente LLM com integração OpenRouter.
"""
from sqlalchemy.orm import Session
from typing import List, Dict, Any, Optional
import httpx
import json
import base64
import time
from datetime import datetime
from config.config_service import ConfiguracaoService
from agente.agente_model import Agente, agente_ferramenta
from agente.agente_schema import AgenteCriar, AgenteAtualizar
from ferramenta.ferramenta_model import Ferramenta
from ferramenta.ferramenta_service import FerramentaService
from llm_providers.llm_integration_service import LLMIntegrationService


class AgenteService:
    """Serviço para gerenciar agentes e processar mensagens com LLM."""

    @staticmethod
    def listar_todos(db: Session) -> List[Agente]:
        """Lista todos os agentes."""
        return db.query(Agente).all()

    @staticmethod
    def listar_por_sessao(db: Session, sessao_id: int) -> List[Agente]:
        """Lista agentes de uma sessão."""
        return db.query(Agente).filter(Agente.sessao_id == sessao_id).order_by(Agente.codigo).all()

    @staticmethod
    def listar_por_sessao_ativos(db: Session, sessao_id: int) -> List[Agente]:
        """Lista agentes ativos de uma sessão."""
        return db.query(Agente).filter(
            Agente.sessao_id == sessao_id,
            Agente.ativo == True
        ).order_by(Agente.codigo).all()

    @staticmethod
    def obter_por_id(db: Session, agente_id: int) -> Optional[Agente]:
        """Obtém um agente pelo ID."""
        return db.query(Agente).filter(Agente.id == agente_id).first()

    @staticmethod
    def obter_por_codigo(db: Session, sessao_id: int, codigo: str) -> Optional[Agente]:
        """Obtém um agente pelo código dentro de uma sessão."""
        return db.query(Agente).filter(
            Agente.sessao_id == sessao_id,
            Agente.codigo == codigo
        ).first()

    @staticmethod
    def criar(db: Session, agente: AgenteCriar) -> Agente:
        """Cria um novo agente."""
        # Verificar se já existe agente com mesmo código na sessão
        existe = AgenteService.obter_por_codigo(db, agente.sessao_id, agente.codigo)
        if existe:
            raise ValueError(f"Já existe um agente com o código '{agente.codigo}' nesta sessão")
        
        db_agente = Agente(**agente.model_dump())
        db.add(db_agente)
        db.commit()
        db.refresh(db_agente)
        return db_agente

    @staticmethod
    def atualizar(db: Session, agente_id: int, agente: AgenteAtualizar) -> Optional[Agente]:
        """Atualiza um agente existente."""
        db_agente = AgenteService.obter_por_id(db, agente_id)
        if not db_agente:
            return None

        update_data = agente.model_dump(exclude_unset=True)
        
        # Verificar se está mudando o código e se já existe outro com esse código
        if "codigo" in update_data and update_data["codigo"] != db_agente.codigo:
            existe = AgenteService.obter_por_codigo(db, db_agente.sessao_id, update_data["codigo"])
            if existe:
                raise ValueError(f"Já existe um agente com o código '{update_data['codigo']}' nesta sessão")
        
        for campo, valor in update_data.items():
            setattr(db_agente, campo, valor)

        db.commit()
        db.refresh(db_agente)
        return db_agente

    @staticmethod
    def deletar(db: Session, agente_id: int) -> bool:
        """Deleta um agente."""
        db_agente = AgenteService.obter_por_id(db, agente_id)
        if not db_agente:
            return False

        db.delete(db_agente)
        db.commit()
        return True

    @staticmethod
    def atualizar_ferramentas(db: Session, agente_id: int, ferramentas_ids: List[int]):
        """
        Atualiza as ferramentas de um agente.
        Máximo de 20 ferramentas por agente.
        """
        if len(ferramentas_ids) > 20:
            raise ValueError("Um agente pode ter no máximo 20 ferramentas ativas")
        
        db_agente = AgenteService.obter_por_id(db, agente_id)
        if not db_agente:
            raise ValueError("Agente não encontrado")
        
        # Remover todas as associações existentes
        db.execute(
            agente_ferramenta.delete().where(agente_ferramenta.c.agente_id == agente_id)
        )
        
        # Adicionar novas associações
        for ferramenta_id in ferramentas_ids:
            # Verificar se a ferramenta existe
            ferramenta = db.query(Ferramenta).filter(Ferramenta.id == ferramenta_id).first()
            if not ferramenta:
                raise ValueError(f"Ferramenta com ID {ferramenta_id} não encontrada")
            
            # Inserir associação
            db.execute(
                agente_ferramenta.insert().values(
                    agente_id=agente_id,
                    ferramenta_id=ferramenta_id,
                    ativa=True
                )
            )
        
        db.commit()

    @staticmethod
    def listar_ferramentas(db: Session, agente_id: int) -> List[Ferramenta]:
        """Lista as ferramentas ativas de um agente."""
        db_agente = AgenteService.obter_por_id(db, agente_id)
        if not db_agente:
            return []
        
        # Buscar ferramentas através da tabela de associação
        ferramentas = db.query(Ferramenta).join(
            agente_ferramenta,
            Ferramenta.id == agente_ferramenta.c.ferramenta_id
        ).filter(
            agente_ferramenta.c.agente_id == agente_id,
            agente_ferramenta.c.ativa == True,
            Ferramenta.ativa == True
        ).all()
        
        return ferramentas

    @staticmethod
    def criar_agente_padrao(db: Session, sessao_id: int) -> Agente:
        """
        Cria um agente padrão para uma sessão.
        Útil ao criar uma nova sessão.
        """
        from config.config_service import ConfiguracaoService
        
        agente_data = AgenteCriar(
            sessao_id=sessao_id,
            codigo="01",
            nome="Assistente Padrão",
            descricao="Agente de atendimento geral",
            agente_papel=ConfiguracaoService.obter_valor(
                db, "agente_papel_padrao", "assistente pessoal"
            ),
            agente_objetivo=ConfiguracaoService.obter_valor(
                db, "agente_objetivo_padrao", "ajudar o usuário com suas dúvidas e tarefas"
            ),
            agente_politicas=ConfiguracaoService.obter_valor(
                db, "agente_politicas_padrao", "ser educado, respeitoso e prestativo"
            ),
            agente_tarefa=ConfiguracaoService.obter_valor(
                db, "agente_tarefa_padrao", "responder perguntas de forma clara e objetiva"
            ),
            agente_objetivo_explicito=ConfiguracaoService.obter_valor(
                db, "agente_objetivo_explicito_padrao", "fornecer informações úteis e precisas"
            ),
            agente_publico=ConfiguracaoService.obter_valor(
                db, "agente_publico_padrao", "usuários em geral"
            ),
            agente_restricoes=ConfiguracaoService.obter_valor(
                db, "agente_restricoes_padrao", "responder em português brasileiro, ser conciso"
            ),
            ativo=True
        )
        
        agente = AgenteService.criar(db, agente_data)
        
        # Associar ferramentas padrão (obter_data_hora_atual e calcular)
        ferramentas_padrao = db.query(Ferramenta).filter(
            Ferramenta.nome.in_(["obter_data_hora_atual", "calcular"])
        ).all()
        
        if ferramentas_padrao:
            ferramentas_ids = [f.id for f in ferramentas_padrao]
            AgenteService.atualizar_ferramentas(db, agente.id, ferramentas_ids)
        
        return agente

    @staticmethod
    def construir_system_prompt(agente: Agente) -> str:
        """
        Constrói o system prompt baseado na configuração do agente.
        Segue o padrão definido em agente.md
        """
        return (
            f"Você é: {agente.agente_papel}.\n"
            f"Objetivo: {agente.agente_objetivo}.\n"
            f"Políticas: {agente.agente_politicas}.\n"
            f"Tarefa: {agente.agente_tarefa}.\n"
            f"Objetivo explícito: {agente.agente_objetivo_explicito}.\n"
            f"Público/usuário-alvo: {agente.agente_publico}.\n"
            f"Restrições e políticas: {agente.agente_restricoes}."
        )

    @staticmethod
    def construir_historico_mensagens(mensagens: List, mensagem_atual) -> List[Dict]:
        """
        Constrói o histórico de mensagens no formato do OpenRouter.
        """
        historico = []
        
        # Adicionar mensagens anteriores (invertido para ordem cronológica)
        for msg in reversed(mensagens[:10]):  # Últimas 10 mensagens
            if msg.id == mensagem_atual.id:
                continue
            
            # Mensagem do usuário
            if msg.direcao == "recebida":
                conteudo = []
                
                # Adicionar texto
                if msg.conteudo_texto:
                    conteudo.append({
                        "type": "text",
                        "text": msg.conteudo_texto
                    })
                
                # Adicionar imagem se houver
                if msg.tipo == "imagem" and msg.conteudo_imagem_base64:
                    mime_type = msg.conteudo_mime_type or "image/jpeg"
                    data_url = f"data:{mime_type};base64,{msg.conteudo_imagem_base64}"
                    conteudo.append({
                        "type": "image_url",
                        "image_url": {
                            "url": data_url
                        }
                    })
                
                if conteudo:
                    historico.append({
                        "role": "user",
                        "content": conteudo if len(conteudo) > 1 else conteudo[0]["text"]
                    })
            
            # Resposta do assistente
            elif msg.direcao == "enviada" and msg.resposta_texto:
                historico.append({
                    "role": "assistant",
                    "content": msg.resposta_texto
                })
        
        return historico

    @staticmethod
    async def processar_mensagem(
        db: Session,
        sessao,
        mensagem,
        historico_mensagens: List,
        agente: Optional[Agente] = None
    ) -> Dict[str, Any]:
        """
        Processa uma mensagem com o agente LLM usando loop principal.
        Suporta múltiplas chamadas de ferramentas em paralelo.
        
        Args:
            db: Sessão do banco de dados
            sessao: Sessão WhatsApp
            mensagem: Mensagem a ser processada
            historico_mensagens: Histórico de mensagens
            agente: Agente a ser usado (se None, usa o agente ativo da sessão)
        
        Returns:
            Dict com: texto, tokens_input, tokens_output, tempo_ms, modelo, ferramentas
        """
        inicio = time.time()
        
        # Se não foi passado agente, usar o agente ativo da sessão
        if agente is None:
            if sessao.agente_ativo_id:
                agente = AgenteService.obter_por_id(db, sessao.agente_ativo_id)
            
            if agente is None:
                raise ValueError("Nenhum agente ativo configurado para esta sessão")
        
        # Obter modelo (do agente, ou padrão)
        modelo = agente.modelo_llm or ConfiguracaoService.obter_valor(
            db, "openrouter_modelo_padrao", "google/gemini-2.0-flash-001"
        )
        
        # Obter parâmetros (do agente, ou padrão)
        temperatura = float(agente.temperatura or ConfiguracaoService.obter_valor(
            db, "openrouter_temperatura", "0.7"
        ))
        max_tokens = int(agente.max_tokens or ConfiguracaoService.obter_valor(
            db, "openrouter_max_tokens", "2000"
        ))
        top_p = float(agente.top_p or ConfiguracaoService.obter_valor(
            db, "openrouter_top_p", "1.0"
        ))
        
        # Construir system prompt
        system_prompt = AgenteService.construir_system_prompt(agente)
        
        # Construir histórico
        historico = AgenteService.construir_historico_mensagens(
            historico_mensagens,
            mensagem
        )
        
        # Construir mensagem atual
        conteudo_atual = []
        
        if mensagem.conteudo_texto:
            conteudo_atual.append({
                "type": "text",
                "text": mensagem.conteudo_texto
            })
        
        # Adicionar imagem se houver
        if mensagem.tipo == "imagem" and mensagem.conteudo_imagem_base64:
            mime_type = mensagem.conteudo_mime_type or "image/jpeg"
            data_url = f"data:{mime_type};base64,{mensagem.conteudo_imagem_base64}"
            conteudo_atual.append({
                "type": "image_url",
                "image_url": {
                    "url": data_url
                }
            })
        
        # Montar mensagens iniciais
        messages = [
            {"role": "system", "content": system_prompt}
        ]
        messages.extend(historico)
        messages.append({
            "role": "user",
            "content": conteudo_atual if len(conteudo_atual) > 1 else (
                conteudo_atual[0]["text"] if conteudo_atual else "..."
            )
        })
        
        # Buscar ferramentas ativas do agente
        ferramentas_disponiveis = AgenteService.listar_ferramentas(db, agente.id)
        
        # Preparar tools no formato OpenAI
        tools = None
        if ferramentas_disponiveis:
            tools = []
            for ferramenta in ferramentas_disponiveis:
                tool_openai = FerramentaService.converter_para_openai_format(ferramenta)
                if tool_openai:  # Apenas ferramentas PRINCIPAL
                    tools.append(tool_openai)
        
        # Buscar clientes MCP ativos do agente
        from mcp_client.mcp_service import MCPService
        mcp_clients = MCPService.listar_ativos_por_agente(db, agente.id)
        
        # Adicionar ferramentas MCP
        for mcp_client in mcp_clients:
            if not mcp_client.conectado:
                continue  # Pular clientes desconectados
            
            mcp_tools = MCPService.listar_tools_ativas(db, mcp_client.id)
            for mcp_tool in mcp_tools:
                if tools is None:
                    tools = []
                tool_openai = MCPService.converter_mcp_tool_para_openai(mcp_client, mcp_tool)
                tools.append(tool_openai)
        
        # Adicionar ferramenta de busca RAG se o agente tiver treinamento vinculado
        if agente.rag_id:
            if tools is None:
                tools = []
            
            # Definir ferramenta de busca na base de conhecimento
            tools.append({
                "type": "function",
                "function": {
                    "name": "buscar_base_conhecimento",
                    "description": "Busca informações relevantes na base de conhecimento do treinamento para responder perguntas do usuário",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {
                                "type": "string",
                                "description": "A pergunta ou consulta para buscar na base de conhecimento"
                            },
                            "num_resultados": {
                                "type": "integer",
                                "description": "Número de resultados a retornar (padrão: 3)",
                                "default": 3
                            }
                        },
                        "required": ["query"]
                    }
                }
            })
        
        # Variáveis de controle
        tokens_input_total = 0
        tokens_output_total = 0
        ferramentas_usadas = []
        texto_resposta_final = ""
        max_iteracoes = 10
        iteracao = 0
        
        # Loop principal de processamento
        try:
            while iteracao < max_iteracoes:
                iteracao += 1
                print(f"🔄 [AGENTE] Iteração {iteracao}/{max_iteracoes}")
                
                # Usar o novo sistema de integração LLM
                print(f"📡 [AGENTE] Chamando LLM com {len(messages)} mensagens...")
                resultado = await LLMIntegrationService.processar_mensagem_com_llm(
                    db=db,
                    messages=messages,
                    modelo=modelo,
                    agente_id=agente.id,
                    temperatura=temperatura,
                    max_tokens=max_tokens,
                    top_p=top_p,
                    tools=tools,
                    stream=False
                )
                
                # Extrair dados da resposta
                message_response = {
                    "role": "assistant",
                    "content": resultado.get("conteudo", ""),
                    "tool_calls": resultado.get("tool_calls")
                }
                
                # Atualizar contadores de tokens
                if resultado.get("tokens_input"):
                    tokens_input_total += resultado["tokens_input"]
                if resultado.get("tokens_output"):
                    tokens_output_total += resultado["tokens_output"]
                
                # Adicionar resposta do assistente ao histórico
                messages.append(message_response)
                
                # Verificar finish_reason
                finish_reason = resultado.get("finish_reason", "stop")
                print(f"✅ [AGENTE] LLM respondeu. finish_reason={finish_reason}")
                
                # Verificar se há tool calls
                tool_calls = message_response.get("tool_calls")
                
                if tool_calls and finish_reason == "tool_calls":
                    print(f"🔧 [AGENTE] LLM chamou {len(tool_calls)} tool(s)")
                    # Processar todas as ferramentas em paralelo
                    for tool_call in tool_calls:
                        function_name = tool_call.get("function", {}).get("name")
                        function_args = tool_call.get("function", {}).get("arguments")
                        args_dict = json.loads(function_args) if isinstance(function_args, str) else function_args
                        
                        # Detectar se é ferramenta MCP (prefixo mcp_)
                        if function_name.startswith("mcp_"):
                            # Extrair: mcp_5_list_repos -> client_id=5, tool_name=list_repos
                            try:
                                parts = function_name.split("_", 2)  # ["mcp", "5", "list_repos"]
                                mcp_client_id = int(parts[1])
                                original_tool_name = parts[2]
                                
                                print(f"🌐 [AGENTE] Executando tool MCP: {original_tool_name} (client {mcp_client_id})")
                                # Executar via MCP
                                resultado_completo = await MCPService.executar_tool_mcp(
                                    db, mcp_client_id, original_tool_name, args_dict
                                )
                                print(f"✅ [AGENTE] Tool MCP executada com sucesso: {resultado_completo.get('tempo_ms', 0)}ms")
                            except Exception as e:
                                print(f"❌ [AGENTE] Erro ao executar tool MCP: {str(e)}")
                                resultado_completo = {
                                    "resultado": {"erro": f"Erro ao executar tool MCP: {str(e)}"},
                                    "output": "llm",
                                    "enviado_usuario": False
                                }
                        
                        # Verificar se é a ferramenta de busca RAG
                        elif function_name == "buscar_base_conhecimento" and agente.rag_id:
                            # Executar busca no RAG
                            from rag.rag_service import RAGService
                            from rag.rag_metrica_service import RAGMetricaService
                            try:
                                query = args_dict.get("query", "")
                                num_resultados = args_dict.get("num_resultados", 3)
                                
                                # Medir tempo de busca
                                tempo_inicio = time.time()
                                
                                # Buscar no RAG
                                resultados_busca = RAGService.buscar(
                                    db, agente.rag_id, query, num_resultados
                                )
                                
                                # Calcular tempo
                                tempo_ms = int((time.time() - tempo_inicio) * 1000)
                                
                                # Registrar métrica
                                RAGMetricaService.registrar_busca(
                                    db=db,
                                    rag_id=agente.rag_id,
                                    query=query,
                                    resultados=resultados_busca,
                                    num_solicitados=num_resultados,
                                    tempo_ms=tempo_ms,
                                    agente_id=agente.id,
                                    sessao_id=sessao.id,
                                    telefone_cliente=mensagem.telefone_cliente
                                )
                                
                                # Formatar resultados para o LLM
                                contextos = []
                                for r in resultados_busca:
                                    contextos.append({
                                        "conteudo": r.get("context", ""),
                                        "fonte": r.get("metadata", {}).get("source", ""),
                                    })
                                
                                resultado_completo = {
                                    "resultado": {
                                        "sucesso": True,
                                        "query": query,
                                        "total_resultados": len(contextos),
                                        "contextos": contextos
                                    },
                                    "output": "llm"
                                }
                            except Exception as e:
                                resultado_completo = {
                                    "resultado": {"erro": f"Erro ao buscar: {str(e)}"},
                                    "output": "llm"
                                }
                        else:
                            # Executar ferramenta normal do banco
                            resultado_completo = await FerramentaService.executar_ferramenta(
                                db,
                                function_name,
                                args_dict,
                                sessao_id=sessao.id,
                                telefone_cliente=mensagem.telefone_cliente
                            )
                        
                        # Extrair resultado para o LLM
                        resultado_llm = resultado_completo.get("resultado", resultado_completo)
                        output_type = resultado_completo.get("output", "llm")
                        enviado_usuario = resultado_completo.get("enviado_usuario", False)
                        post_instruction = resultado_completo.get("post_instruction")
                        
                        # Registrar uso da ferramenta
                        ferramentas_usadas.append({
                            "nome": function_name,
                            "argumentos": function_args,
                            "resultado": resultado_llm,
                            "output": output_type,
                            "enviado_usuario": enviado_usuario
                        })
                        
                        # Preparar conteúdo para o LLM
                        conteudo_tool = json.dumps(resultado_llm, ensure_ascii=False)
                        
                        # Se tem post_instruction, adicionar ao contexto
                        if post_instruction and output_type in ["llm", "both"]:
                            conteudo_tool = f"{conteudo_tool}\n\nInstrução: {post_instruction}"
                        
                        # Adicionar resultado ao histórico apenas se output inclui LLM
                        if output_type in ["llm", "both"]:
                            print(f"📤 [AGENTE] Conteúdo enviado ao LLM (primeiros 500 chars): {conteudo_tool[:500]}")
                            messages.append({
                                "role": "tool",
                                "tool_call_id": tool_call.get("id"),
                                "content": conteudo_tool
                            })
                            print(f"📝 [AGENTE] Resultado da tool adicionado ao histórico (output={output_type})")
                        else:
                            # Se output é apenas USER, informar ao LLM que foi enviado
                            messages.append({
                                "role": "tool",
                                "tool_call_id": tool_call.get("id"),
                                "content": json.dumps({
                                    "status": "enviado_ao_usuario",
                                    "mensagem": "Resultado enviado diretamente ao usuário via WhatsApp"
                                }, ensure_ascii=False)
                            })
                            print(f"📝 [AGENTE] Resultado enviado ao usuário (output={output_type})")
                    
                    # Continuar o loop para processar os resultados das ferramentas
                    print(f"🔁 [AGENTE] Todas as {len(tool_calls)} tool(s) processadas. Voltando ao LLM...")
                    continue
                else:
                    # Não há tool calls - resposta final (texto)
                    texto_resposta_final = message_response.get("content", "")
                    print(f"✅ [AGENTE] Resposta final recebida: {len(texto_resposta_final)} caracteres")
                    break
            
            # Calcular tempo total
            tempo_ms = int((time.time() - inicio) * 1000)
            
            print(f"🎯 [AGENTE] Processamento concluído em {tempo_ms}ms")
            return {
                "texto": texto_resposta_final,
                "tokens_input": tokens_input_total,
                "tokens_output": tokens_output_total,
                "tempo_ms": tempo_ms,
                "modelo": modelo,
                "ferramentas": ferramentas_usadas if ferramentas_usadas else None
            }
                
        except httpx.TimeoutException:
            print(f"❌ [AGENTE] Timeout ao conectar com OpenRouter")
            raise ValueError("Timeout ao conectar com OpenRouter")
        except Exception as e:
            print(f"❌ [AGENTE] Exceção capturada: {type(e).__name__}: {str(e)}")
            import traceback
            traceback.print_exc()
            raise ValueError(f"Erro ao processar com LLM: {str(e)}")

    @staticmethod
    async def testar_prompt(db: Session, agente_id: Optional[int], sessao_id: int, prompt_personalizado: str, mensagem_teste: str):
        """Testa um prompt personalizado antes de aplicar ao agente."""
        from agente.agente_model import AgenteTeste, Agente
        from agente.agente_schema import AgenteTesteCriar
        import time

        # Se tem agente_id, usar configurações do agente
        if agente_id:
            agente = AgenteService.obter_por_id(db, agente_id)
            if not agente:
                raise ValueError("Agente não encontrado")
        else:
            agente = None

        # Garantir sessao_id válido
        if sessao_id is None:
            if agente is not None:
                sessao_id = agente.sessao_id
            else:
                raise ValueError("sessao_id é obrigatório quando nenhum agente é informado")

        # Construir prompt completo (usar o personalizado ou do agente)
        if prompt_personalizado.strip():
            prompt_completo = prompt_personalizado
        elif agente:
            prompt_completo = AgenteService.construir_system_prompt(agente)
        else:
            raise ValueError("É necessário fornecer um prompt personalizado ou ID de agente")

        # Testar com LLM
        inicio = time.time()

        try:
            # Usar integração LLM para testar
            from llm_providers.llm_integration_service import LLMIntegrationService

            # Configurar requisição
            configuracao = None
            if agente:
                configuracao = {
                    "temperatura": float(agente.temperatura or "0.7"),
                    "max_tokens": int(agente.max_tokens or "2000"),
                    "top_p": float(agente.top_p or "1.0"),
                    "stop": None
                }

            modelo = agente.modelo_llm if agente and agente.modelo_llm else "google/gemini-2.0-flash-001"

            # Montar mensagens no formato OpenAI
            messages = [
                {"role": "system", "content": prompt_completo},
                {"role": "user", "content": mensagem_teste}
            ]

            # Chamar integração LLM unificada
            resultado_llm = await LLMIntegrationService.processar_mensagem_com_llm(
                db=db,
                messages=messages,
                modelo=modelo,
                agente_id=agente.id if agente else None,
                temperatura=(configuracao or {}).get("temperatura", 0.7),
                max_tokens=(configuracao or {}).get("max_tokens", 2000),
                top_p=(configuracao or {}).get("top_p", 1.0),
                tools=None,
                stream=False
            )

            tempo_ms = int((time.time() - inicio) * 1000)

            # Normalizar campos retornados
            conteudo_resp = resultado_llm.get("conteudo", "")
            modelo_resp = resultado_llm.get("modelo", modelo)
            tokens_in = resultado_llm.get("tokens_input") or 0
            tokens_out = resultado_llm.get("tokens_output") or 0
            tokens_total = (tokens_in or 0) + (tokens_out or 0)

            # Salvar teste
            teste_data = AgenteTesteCriar(
                agente_id=agente_id,
                sessao_id=sessao_id,
                prompt_testado=prompt_completo,
                mensagem_teste=mensagem_teste,
                resposta_gerada=conteudo_resp,
                modelo_usado=modelo_resp,
                tempo_resposta_ms=tempo_ms,
                tokens_usados=tokens_total,
                sucesso=True
            )

            teste = AgenteTeste(**teste_data.model_dump())
            db.add(teste)
            db.commit()
            db.refresh(teste)

            return {
                "teste_id": teste.id,
                "resposta": conteudo_resp,
                "modelo": modelo_resp,
                "tempo_ms": tempo_ms,
                "tokens": tokens_total,
                "sucesso": True
            }

        except Exception as e:
            tempo_ms = int((time.time() - inicio) * 1000)

            # Salvar teste com erro
            teste_data = AgenteTesteCriar(
                agente_id=agente_id,
                sessao_id=sessao_id,
                prompt_testado=prompt_completo,
                mensagem_teste=mensagem_teste,
                sucesso=False,
                erro_mensagem=str(e),
                tempo_resposta_ms=tempo_ms
            )

            teste = AgenteTeste(**teste_data.model_dump())
            db.add(teste)
            db.commit()
            db.refresh(teste)

            raise ValueError(f"Erro no teste: {str(e)}")

    @staticmethod
    def comparar_agentes(db: Session, agente_id_1: int, agente_id_2: int, mensagem_teste: str):
        """Compara performance entre dois agentes."""
        import asyncio

        async def testar_agente(agente_id):
            try:
                return await AgenteService.testar_prompt(
                    db=db,
                    agente_id=agente_id,
                    sessao_id=None,  # Será definido dentro do método
                    prompt_personalizado="",
                    mensagem_teste=mensagem_teste
                )
            except Exception as e:
                return {"erro": str(e)}

        # Executar testes em paralelo
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            resultado_1, resultado_2 = loop.run_until_complete(
                asyncio.gather(
                    testar_agente(agente_id_1),
                    testar_agente(agente_id_2)
                )
            )
        finally:
            loop.close()

        # Obter dados dos agentes
        agente_1 = AgenteService.obter_por_id(db, agente_id_1)
        agente_2 = AgenteService.obter_por_id(db, agente_id_2)

        if not agente_1 or not agente_2:
            raise ValueError("Um ou ambos agentes não encontrados")

        # Analisar comparação
        comparacao = {
            "mensagem_teste": mensagem_teste,
            "teste_1": {
                "agente": agente_1.nome,
                "sucesso": not resultado_1.get("erro"),
                "tempo_ms": resultado_1.get("tempo_ms"),
                "tokens": resultado_1.get("tokens"),
                "resposta": resultado_1.get("resposta", resultado_1.get("erro"))
            },
            "teste_2": {
                "agente": agente_2.nome,
                "sucesso": not resultado_2.get("erro"),
                "tempo_ms": resultado_2.get("tempo_ms"),
                "tokens": resultado_2.get("tokens"),
                "resposta": resultado_2.get("resposta", resultado_2.get("erro"))
            }
        }

        # Gerar recomendação
        if comparacao["teste_1"]["sucesso"] and not comparacao["teste_2"]["sucesso"]:
            recomendacao = f"Recomendo {agente_1.nome} - funcionou corretamente"
        elif comparacao["teste_2"]["sucesso"] and not comparacao["teste_1"]["sucesso"]:
            recomendacao = f"Recomendo {agente_2.nome} - funcionou corretamente"
        elif comparacao["teste_1"]["sucesso"] and comparacao["teste_2"]["sucesso"]:
            tempo_1 = comparacao["teste_1"]["tempo_ms"] or float('inf')
            tempo_2 = comparacao["teste_2"]["tempo_ms"] or float('inf')
            tokens_1 = comparacao["teste_1"]["tokens"] or float('inf')
            tokens_2 = comparacao["teste_2"]["tokens"] or float('inf')

            if tempo_1 < tempo_2 and tokens_1 <= tokens_2:
                recomendacao = f"Recomendo {agente_1.nome} - mais rápido e eficiente"
            elif tempo_2 < tempo_1 and tokens_2 <= tokens_1:
                recomendacao = f"Recomendo {agente_2.nome} - mais rápido e eficiente"
            else:
                recomendacao = "Ambos funcionaram bem - escolha baseado no estilo de resposta"
        else:
            recomendacao = "Ambos falharam - revise as configurações dos agentes"

        return {
            "agente_1": {
                "id": agente_1.id,
                "nome": agente_1.nome,
                "categoria": "personalizado"
            },
            "agente_2": {
                "id": agente_2.id,
                "nome": agente_2.nome,
                "categoria": "personalizado"
            },
            "comparacao": comparacao,
            "recomendacao": recomendacao
        }

    @staticmethod
    def obter_estatisticas_agente(db: Session, agente_id: int):
        """Obtém estatísticas de performance de um agente."""
        from agente.agente_model import AgenteTeste

        testes = db.query(AgenteTeste).filter(AgenteTeste.agente_id == agente_id).all()

        if not testes:
            return {
                "total_testes": 0,
                "taxa_sucesso": 0,
                "tempo_medio_ms": 0,
                "tokens_medios": 0,
                "avaliacao_media": 0
            }

        total_testes = len(testes)
        testes_sucesso = len([t for t in testes if t.sucesso])
        taxa_sucesso = (testes_sucesso / total_testes) * 100

        tempos = [t.tempo_resposta_ms for t in testes if t.tempo_resposta_ms]
        tempo_medio = sum(tempos) / len(tempos) if tempos else 0

        tokens = [t.tokens_usados for t in testes if t.tokens_usados]
        tokens_medios = sum(tokens) / len(tokens) if tokens else 0

        avaliacoes = [t.avaliacao for t in testes if t.avaliacao]
        avaliacao_media = sum(avaliacoes) / len(avaliacoes) if avaliacoes else 0

        return {
            "total_testes": total_testes,
            "taxa_sucesso": round(taxa_sucesso, 1),
            "tempo_medio_ms": round(tempo_medio, 0),
            "tokens_medios": round(tokens_medios, 0),
            "avaliacao_media": round(avaliacao_media, 1)
        }
