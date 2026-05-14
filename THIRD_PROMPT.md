# Prompt da terceira sessão — M3 (cole no Claude Code)

> Cole o bloco abaixo como sua **primeira mensagem** ao Claude Code dentro deste repo.
> M1 e M2 estão fechados na `main`. Você já está no `qwen2.5vl:3b` (latência ~24s no Mac).

---

```
M1 e M2 estão fechados na main. App enxerga a tela e descreve em pt-br
usando Ollama + Qwen2.5-VL 3B. Padrões da casa que você vai herdar do M2:

  • Cada módulo do backend segue base.py (Protocol + dataclasses) +
    errors.py + factory.py + <impl>_impl.py
  • Endpoints com pydantic schemas tipados, response_model declarado
  • Erros tipados → HTTPException com código específico + mensagem
    prescritiva em pt-br (estilo "Inicie com: ollama serve")
  • Async para chamadas externas, sync para captura
  • `_capture` e `_vlm` instanciados no module-level do main.py

Contexto de ambiente segue: dev macOS arm64, alvo Windows, testo a
release no Windows depois. Política de commits do CLAUDE.md
(Conventional Commits em pt-br, push direto na main a cada unidade
de trabalho).

Objetivo desta sessão: entregar o **Marco 3 (M3)** completo.

M3 = "A IA fecha o loop e joga sozinha um jogo simples":
- Backend ganha `executor/` (input) e `planner/` (decisão), espelhando
  o padrão de `capture/` e `vision/`.
- Novo módulo `session/` orquestra o loop captura → planner → executor.
- Endpoints novos: `POST /session/start`, `POST /session/stop`,
  `GET /session/status`.
- UI ganha uma rota `/play` separada da `/` (que vira `/inspect`,
  mantendo capturar/descrever do M2 para debug).
- **Jogo alvo do M3: 2048** (browser, 4 teclas, estado simples,
  perfeito pra validar o loop sem complexidade gráfica).
- Captura passa a aceitar **região** (crop) para a VLM enxergar só o
  jogo — sem isso a inferência fica lenta e ruidosa.

Continuamos sem memória persistente (M4). Aqui é só fechar o loop.

Sub-tarefas sugeridas (você pode ajustar a ordem se fizer sentido):

1. Captura com região.
   - Estender `ScreenCapture.grab()` para aceitar `region: tuple[int,int,int,int] | None`
     (x, y, largura, altura). `None` = tela inteira (comportamento atual).
   - Implementar em `MssCapture` (mss aceita `monitor` dict customizado).
   - `DxCamCapture`: TODO com fallback que ignora a região por enquanto.
   - Endpoint `POST /capture` ganha body opcional `{"region": [x,y,w,h]}`.
   - **Commit + push** ("feat: captura aceita região (crop) opcional").

2. Schema de ações.
   - Criar `backend/planner/actions.py` com `Action` pydantic:
       kind: Literal["key", "click", "wait", "stop"]
       key: str | None         # nome estilo "ArrowUp", "Space", "a"
       x: int | None           # coordenadas relativas à região
       y: int | None
       duration_ms: int | None # para wait
       reason: str             # justificativa da IA (logging/debug)
   - Validação cruzada (ex: kind=key exige key não-nulo).
   - **Commit + push** ("feat: schema Action para o planner").

3. Módulo `backend/executor/`.
   - `base.py`: Protocol `InputExecutor` com:
       def key_tap(self, key: str) -> None
       def click(self, x: int, y: int) -> None
       def wait(self, ms: int) -> None
   - `errors.py`: `ExecutorPermissionError` (macOS sem Accessibility),
     `ExecutorBlockedError` (anti-cheat detectado — fica TODO para M+).
   - `pyautogui_impl.py`: implementação default. Configure
     `pyautogui.FAILSAFE = True` (mouse no canto = aborta).
   - `directinput_impl.py`: stub Windows-only com TODO.
   - `factory.py`: escolhe por `sys.platform` (pyautogui no Mac, e
     escolha futura entre pyautogui/pydirectinput no Windows).
   - **Commit + push** ("feat: módulo executor com pyautogui").

4. Módulo `backend/planner/`.
   - `base.py`: Protocol `Planner` com:
       async def decide(self, image_png: bytes, goal: str,
                        history: list[Action], allowed_keys: list[str]) -> Action
   - `errors.py`: `PlannerParseError` (VLM devolveu JSON inválido),
     `PlannerNoActionError`.
   - `vlm_planner.py`: implementação que usa `VLMProvider`.
     Estratégia: prompt instrui a VLM a devolver SÓ um JSON com o
     schema do Action. Faz parse + validação pydantic. Se falhar,
     tenta de novo uma vez com prompt corrigido; se falhar de novo,
     levanta `PlannerParseError`.
     Inclua few-shot no prompt: 1 exemplo de "key ArrowUp" e 1 de
     "stop" para encerrar quando o jogo acabou.
   - `factory.py`: por enquanto só `VLMPlanner(get_vlm())`.
   - **Commit + push** ("feat: planner com VLM e structured output").

5. Módulo `backend/session/`.
   - `base.py`: dataclass `SessionState` com:
       status: Literal["idle", "running", "paused", "stopped", "error"]
       game: str | None
       region: tuple[int,int,int,int] | None
       started_at: datetime | None
       actions_taken: int
       last_action: Action | None
       last_reason: str | None
       history: list[Action]   # cap em 20
       last_screenshot_b64: str | None  # cap em 1, base64 PNG
       error: str | None
   - `engine.py`: `SessionEngine` rodando em uma `asyncio.Task`.
     Loop:
       a) captura (com região)
       b) planner.decide(...)
       c) registra no history (cap 20)
       d) se action.kind == "stop" → encerra
       e) executor.executa
       f) sleep curto (200-500ms — configurável)
     Respeita:
       • limite hard de ações (default 200)
       • limite hard de tempo (default 600s = 10min)
       • flag `stop_requested` (botão pra parar)
       • pyautogui failsafe (já configurado no executor)
   - `games.py`: dicionário com perfis. Inicialmente só `"2048"`:
       {
         "name": "2048",
         "url": "https://play2048.co/",
         "goal": "Você está jogando 2048. Combine peças iguais
                  movendo todas as peças com setas. Maximize o
                  número da maior peça. Termine (action stop) se
                  aparecer 'Game over' ou se nenhuma jogada for útil.",
         "allowed_keys": ["ArrowUp", "ArrowDown", "ArrowLeft", "ArrowRight"]
       }
     Estrutura aberta pra adicionar mais jogos depois.
   - **Commit + push** ("feat: session engine com loop captura→plan→exec").

6. Endpoints de sessão.
   - `POST /session/start`:
       body: { game: str, region: [int,int,int,int] | None,
               max_actions: int = 200, max_duration_s: int = 600,
               step_delay_ms: int = 300 }
       422 se já houver sessão rodando.
   - `POST /session/stop`: pede pra encerrar, retorna estado.
   - `GET /session/status`: retorna `SessionState` (com `last_screenshot_b64`
     incluído pra UI mostrar). Polling de 1-2Hz pela UI.
   - Logs estruturados em cada ação com latência da decide().
   - **Commit + push** ("feat: endpoints session/start, stop, status").

7. UI — nova rota `/play`.
   - Mover o conteúdo atual de `/` para `/inspect` (renomear; é o painel
     de debug do M2).
   - `/` vira uma home simples com 2 cards: "Play" e "Inspect".
   - `/play`:
       a) Seletor de jogo (dropdown alimentado por `/session/games`
          — adicione esse endpoint que lista os perfis disponíveis).
       b) Campo opcional "Região do jogo" (4 inputs x/y/w/h por agora;
          UI de seleção visual fica para M3.5).
       c) Limites configuráveis (max ações, max duração, delay).
       d) Botão verde "Iniciar" → POST /session/start.
       e) Botão vermelho gigante "PARAR" → POST /session/stop.
       f) Painel ao vivo: status, screenshot atual (do
          last_screenshot_b64), última ação + reason, contador,
          tempo decorrido.
       g) Polling a cada 1s enquanto running.
   - Aviso vermelho fixo no topo de /play: "Não use em jogos online
     com anti-cheat. Single-player / browser apenas."
   - **Commit + push** ("feat: rota /play com controle da sessão").

8. Permissões macOS + docs.
   - Adicionar ao README seção "Permissões no macOS": pyautogui pede
     Accessibility (System Settings → Privacy & Security → Accessibility)
     e Screen Recording. Documentar o caminho exato.
   - No primeiro `key_tap`/`click`, capturar `osascript`/`PermissionError`
     e levantar `ExecutorPermissionError` com instrução clara.
   - **Commit + push** ("docs: permissões de Accessibility no macOS").

9. Atualizar CLAUDE.md.
   - Marcar M3 concluído. Documentar a estrutura `executor/`, `planner/`,
     `session/`. Adicionar perfis de jogo como ponto de extensão.
   - **Commit + push** ("docs: atualiza CLAUDE.md com M3 concluído").

Regras importantes para esta sessão:

- **Structured output via prompt**, não via tool calling. Ollama não tem
  function calling estável para todos os modelos VLM. Estratégia:
  prompt termina com "RESPONDA APENAS COM UM JSON VÁLIDO no formato:
  {\"kind\": \"...\", \"key\": \"...\", \"reason\": \"...\"}". Faça
  parse robusto (regex pra extrair o primeiro `{...}` se a VLM
  introduzir prefácio).
- **Failsafe é sagrado**. `pyautogui.FAILSAFE = True` SEMPRE.
  Documente que mover o mouse pro canto superior esquerdo aborta.
- **2048 antes de qualquer outro jogo**. Não tente generalizar pra
  Tetris/Snake/etc neste marco — perfis de jogo são extensão futura.
- **Não memorize estratégias entre sessões** (M4). Cada sessão começa
  do zero, `history` é só context window do loop atual.
- **Loop precisa parar de verdade**. Confirme que `POST /session/stop`
  realmente mata a task em ≤ 1 ciclo. Use `asyncio.Event` ou flag.
- **Latência**: cada decisão vai levar 5-30s com qwen2.5vl:3b.
  Está OK — 2048 é turn-based. Apenas garanta que o `step_delay_ms`
  some à latência, não substitua.
- **Não toque na captura DXcam** além do TODO de região. Validar dxcam
  é responsabilidade do M8.
- **Commits pequenos**, um por sub-tarefa, push após cada um.
- **Antes de cada push**: `cargo check`, `npm run build`, `uv run python
  -m compileall backend`. Teste manual no `npm run tauri dev` quando
  fizer sentido.

Comece pela sub-tarefa 1. Pergunte antes de:
  - trocar 2048 por outro jogo (motivo concreto)
  - introduzir lib nova além de pyautogui (ex: pynput)
  - mudar o schema de Action de forma incompatível
Coisas pequenas decide você.

Se algo bloquear (ex: pyautogui não consegue mandar tecla mesmo com
permissão, VLM nunca retorna JSON válido em 5 tentativas seguidas,
2048 detecta automação), pare e me avise.
```

---

## Lembretes para o usuário (não cole isso)

- **Antes de rodar M3**, conceda permissão de Accessibility ao Terminal
  ou ao binário do Tauri em `System Settings → Privacy & Security →
  Accessibility`. Sem isso, `pyautogui` falha silenciosamente.
- Abra o 2048 em https://play2048.co/ em um Chrome/Firefox janela
  separada **antes** de clicar "Iniciar" no /play.
- Reserve um canto da tela pra deixar a janela do PlayIA acessível pro
  botão "PARAR" — emergência acontece.
- Quando o M3 fechar: app pega um jogo simples e tenta jogá-lo de
  verdade. Não vai ser bom (o 3B é fraco), mas o **pipeline está
  fechado**. Próximo passo M4 = memória persistente (skills, episódios).
