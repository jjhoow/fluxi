# Módulo Mensagem 💬

## 📖 Visão Geral

O módulo `mensagem` armazena e gerencia todas as mensagens recebidas e enviadas no WhatsApp, incluindo histórico, contexto e métricas de processamento.

## 🎯 Objetivo

- Armazenar mensagens recebidas/enviadas
- Suporte a texto, imagens, áudios, vídeos, documentos
- Histórico de conversas por cliente
- Métricas de processamento (tokens, tempo)
- Registro de ferramentas usadas

## 📂 Principais Componentes

### Model (mensagem_model.py)

**Tabela: `mensagens`**

| Campo | Descrição |
|-------|-----------|
| `sessao_id` | FK para sessão |
| `telefone_cliente` | Telefone do cliente |
| `tipo` | texto, imagem, audio, video, documento |
| `direcao` | recebida, enviada |
| `conteudo_texto` | Texto da mensagem |
| `conteudo_imagem_base64` | Imagem em base64 |
| `resposta_texto` | Resposta do agente |
| `resposta_tokens_input/output` | Tokens consumidos |
| `resposta_tempo_ms` | Tempo de processamento |
| `ferramentas_usadas` | Tools executadas (JSON) |
| `processada` | Se foi processada |
| `respondida` | Se foi respondida |

### Service (mensagem_service.py)

**Funções:**
- `listar_por_sessao()` - Lista mensagens da sessão
- `listar_por_cliente()` - Lista conversas de um cliente
- `processar_mensagem_recebida()` - **MAIN**: Processa msg do WhatsApp
- `salvar_imagem()` - Salva e converte imagens

## 🔄 Fluxo de Processamento

```
1. Mensagem chega via WhatsApp
2. Evento MessageEv disparado
3. processar_mensagem_recebida()
   - Extrai dados (texto/imagem)
   - Cria registro no banco
   - Busca histórico (10 últimas)
   - Chama agente_ativo
   - Agente processa com LLM
   - Atualiza resposta_*
   - Marca como processada/respondida
4. Resposta enviada ao cliente
```

## 💡 Exemplo

```python
# Listar mensagens de um cliente
mensagens = MensagemService.listar_por_cliente(
    db,
    sessao_id=1,
    telefone_cliente="+5511999999999",
    limite=50
)

# Resultado inclui:
# - conteudo_texto
# - resposta_texto
# - ferramentas_usadas
# - resposta_tokens_*
# - resposta_tempo_ms
```

---

**Módulo:** mensagem  
**Suporta:** Texto, imagens, áudios, vídeos, documentos

