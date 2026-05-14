# Prompt da segunda sessão — M2 (cole no Claude Code)

> Cole o bloco abaixo como sua **primeira mensagem** ao Claude Code dentro deste repo.
> Você já tem o M1 fechado e empurrado na `main`.

---

```
M1 está fechado e na main. App roda no meu Mac, botão "Capturar tela"
funciona ponta a ponta (Tauri → sidecar Python → mss → PNG → UI).

Continuamos como antes: dev no macOS arm64, alvo Windows, política de
commits do CLAUDE.md (Conventional Commits em português, push direto na
main a cada unidade de trabalho). Stack confirmada inclui `uv` como
gerenciador Python.

Objetivo desta sessão: entregar o **Marco 2 (M2)** completo.

M2 = "A IA enxerga a tela":
- Backend ganha módulo `backend/vision/` com a mesma arquitetura do `capture/`
  (Protocol + implementações + factory).
- Provider padrão: **Ollama com Qwen2.5-VL 7B** rodando local. Comunicação via
  HTTP no endpoint do Ollama (`http://127.0.0.1:11434/api/generate`).
- Novo endpoint `POST /describe` no FastAPI que (1) captura a tela usando o
  pipeline do M1, (2) manda pro VLM, (3) devolve a descrição em texto.
- UI ganha um segundo botão "Descrever tela" que mostra o texto abaixo da
  imagem capturada. Loading state precisa aguentar 5-30s (inferência no
  Mac sem GPU dedicada é lenta).
- Mensagens de erro claras quando Ollama não estiver rodando ou o modelo
  não estiver baixado — o usuário precisa saber EXATAMENTE o que fazer.

Continuamos sem memória persistente e sem ação automática. M2 é "olhos +
linguagem", não decisão.

Sub-tarefas sugeridas (você pode ajustar):

1. README/docs: instruções para o pré-requisito Ollama.
   - Atualizar README com seção "Pré-requisitos" explicando como instalar
     Ollama no Mac (`brew install ollama` ou download), iniciar
     (`ollama serve`), e baixar o modelo (`ollama pull qwen2.5vl:7b`).
   - Criar `scripts/setup-ollama.sh` (cross-platform: detecta SO e dá
     instruções diferentes; no Mac roda o `brew install` se faltar; em
     Windows pede pra instalar manual).
   - Pre-checks: o script confirma que `ollama serve` responde em :11434
     e que `qwen2.5vl:7b` está disponível (`ollama list`).
   - **Commit + push** ("docs: pré-requisitos e setup script do Ollama").

2. Estrutura `backend/vision/`.
   - `base.py`: Protocol `VLMProvider` com `async describe(image_png: bytes,
     prompt: str) -> str`. Acrescentar comentário no Protocol que descreve
     o contrato (prompt em pt-br, descrição em pt-br por padrão).
   - `ollama_impl.py`: `OllamaProvider(model: str = "qwen2.5vl:7b",
     host: str = "http://127.0.0.1:11434", timeout_s: float = 60.0)`.
     Usa `httpx.AsyncClient` (adicionar `httpx` ao pyproject). Envia o PNG
     em base64 no campo `images` do payload do Ollama. Retorna o texto
     puro.
   - `factory.py`: `get_vlm() -> VLMProvider` que por enquanto retorna
     sempre `OllamaProvider()`. Deixe a estrutura pronta para adicionar
     `GeminiProvider`, `ClaudeProvider`, `OpenAIProvider`, etc. no M7
     (pode dropar `# TODO(M7)` comentando isso).
   - `errors.py`: exceções tipadas (`VLMUnavailableError`,
     `VLMModelMissingError`, `VLMTimeoutError`) que o endpoint converte
     em mensagens HTTP úteis.
   - **Commit + push** ("feat: módulo vision com provider Ollama").

3. Endpoint `POST /describe` no `backend/main.py`.
   - Body opcional: `{"prompt": string}`. Default: "Descreva em
     português o que está acontecendo nesta tela. Liste elementos visuais
     importantes (janelas, botões, texto, jogo em foco). Seja conciso."
   - Resposta JSON: `{"description": string, "latency_ms": int,
     "model": string}`.
   - Internamente: chama `_capture.grab()` + `await _vlm.describe(png, prompt)`.
   - Logging: log da latência, do tamanho do PNG, do modelo usado.
   - Tratamento dos erros tipados → HTTP 503 com mensagem clara
     ("Ollama não está rodando. Inicie com `ollama serve`."),
     HTTP 404 ("Modelo qwen2.5vl:7b não encontrado. Rode:
     ollama pull qwen2.5vl:7b"), HTTP 504 (timeout).
   - **Commit + push** ("feat: endpoint /describe com VLM ollama").

4. Endpoint `GET /vlm/status` para health-check do VLM.
   - Retorna `{"ready": bool, "model": string, "issue": string | null}`.
   - `ready=false` com `issue` explicando o motivo (ollama offline,
     modelo faltando, etc.). Não dá throw — devolve estado.
   - **Commit + push** ("feat: endpoint /vlm/status para health-check").

5. UI: segundo botão e exibição da descrição.
   - Manter o botão "Capturar tela" do M1.
   - Adicionar botão "Descrever tela" que faz POST em `/describe`.
   - Mostrar a descrição abaixo da imagem em uma `<section>` separada,
     com latência exibida discretamente.
   - Loading state: spinner ou texto "Pensando…" enquanto espera (até 60s).
   - Ao abrir o app, chamar `/vlm/status` uma vez e mostrar um badge
     ("VLM pronto" verde ou "VLM indisponível" vermelho clicável que
     expande a `issue`).
   - **Commit + push** ("feat: UI exibe descrição da tela pelo VLM").

6. Atualizar CLAUDE.md.
   - Documentar que `vision/` segue o mesmo padrão de `capture/`.
   - Adicionar Ollama + Qwen2.5-VL aos pré-requisitos de dev.
   - Marcar M2 como concluído no roadmap.
   - **Commit + push** ("docs: atualiza CLAUDE.md com M2 concluído").

Regras importantes para esta sessão:

- **Use `httpx` async** para falar com Ollama. FastAPI é async — não bloqueie
  o event loop com `requests`.
- **Não baixe o modelo dentro do app**. O script de setup orienta; o app só
  verifica e dá mensagem clara se estiver faltando. Modelos VLM têm 5-10GB
  e o download é responsabilidade do usuário/ambiente.
- **Não persista nada ainda** (sem SQLite, sem memória). Cada `/describe`
  é stateless. Memória entra no M4.
- **Não tente trocar de provider via UI agora**. Só Ollama, hardcoded.
  Settings + BYOK é M7.
- **Tempos**: no meu Mac arm64 com Qwen2.5-VL 7B esperar ~5-15s por
  descrição é normal. Não otimize prematuramente. Se ficar inviável,
  documente e seguimos com modelo menor (`qwen2.5vl:3b`).
- **Commits pequenos**, um por sub-tarefa, push após cada um.
- **Antes de cada push**: `cargo check`, `npm run build`, `uv run python
  -m compileall backend`, e teste manual no `npm run tauri dev`.
- **Se Ollama estiver offline durante o dev**, a UI ainda precisa abrir
  e mostrar mensagem útil. Não trave o app por dependência externa.

Comece pela sub-tarefa 1. Pergunte antes de tomar decisões grandes
(ex: trocar `httpx` por `aiohttp`, mudar o modelo padrão, criar abstração
diferente). Coisas pequenas decide você.

Se algo bloquear (ex: Ollama não responde mesmo com `ollama serve` rodando,
modelo VLM trava o Mac), pare e me avise — não improvise.
```

---

## Lembretes para o usuário (não cole isso)

- **Antes de rodar o prompt**, instale o Ollama e baixe o modelo:
  ```bash
  brew install ollama
  ollama serve &        # deixa rodando em background
  ollama pull qwen2.5vl:7b
  ```
  O download tem ~5GB. Em Mac M1/M2/M3 com 16GB+ RAM roda de boas.
- Se seu Mac tiver pouca RAM (8GB), troque por `qwen2.5vl:3b` no prompt
  (substitua nas duas menções do modelo).
- Quando este M2 fechar, o app já vai estar **descrevendo a tela em
  português via VLM local**. Próximo passo (M3) é fechar o loop de ação:
  IA decide o que fazer e o `pyautogui` executa.
