# PlayIA

Desktop app (Windows) que **aprende a jogar um jogo específico
observando você jogar 30-60 min**, e depois joga sozinho via
behavioral cloning + um VLM estrategista. Quatro fases: **Watch me
play** → **Train** → **Play** → **Improve**. Memória persistente em
SQLite faz cada jogo ter seu motor model + skills + histórico.

---

## ⚠️ Aviso obrigatório — anti-cheat

**NÃO USE** o PlayIA em jogos multiplayer com anti-cheat
(Vanguard, Easy Anti-Cheat, BattlEye, Hyperion, FACEIT AC, ...).
Resultado: **banimento da conta e do hardware (HWID)**.

PlayIA foi pensado para:

- Single-player.
- Jogos sem anti-cheat (puzzles, narrativas, plataforma, retro, etc.).
- Sandboxes e jogos de navegador.

O time não tem nenhuma forma de te ajudar a recuperar uma conta banida
por usar este app fora do escopo acima.

---

## Status

- **Marco 1**: "Hello world arquitetural". App Tauri 2 + sidecar
  Python FastAPI + captura de tela cross-platform funcionando ponta a
  ponta.
- **Marco 2**: A IA enxerga a tela. VLM local (Ollama + `qwen2.5vl:3b`)
  descreve em português o que está acontecendo na tela capturada.
- **Marco 3**: Loop turn-based fechado captura → planner (VLM decide a
  próxima tecla) → executor (pyautogui). Jogo alvo: **2048**.
- **Marco 4**: Memória SQLite + `sqlite-vec`. Schema completo (games,
  recordings, recording_frames, motor_models, episodes, skills,
  knowledge) versionado por migrations. CRUD `/games` na UI. Gate de
  `tempo`/`anti_cheat` no `/session/start`.
- **Marco 5** (atual): Watch-me-play engine. Captura frame + estado de
  teclado/mouse (pynput) sincronizado a 15-30 Hz em PNGs + linhas no
  DB. Rota `/record` com gravação live, contador de FPS real, tamanho
  em disco e lista de gravações.
- Próximos marcos (M6, M7, M10): behavioral cloning trainer (PyTorch →
  ONNX), loop hierárquico (VLM estrategista + motor ONNX 30 Hz),
  release v0.1.0 no GitHub via Actions + auto-update. Detalhes em
  `CLAUDE.md`.

## Stack

- **UI**: Tauri 2 (Rust shell + WebView2) + SvelteKit (adapter-static).
- **Backend IA**: sidecar Python 3.12 gerenciado por [uv](https://docs.astral.sh/uv/).
  Em dev: `uv run python main.py`. Em prod (M8): binário PyInstaller.
- **IPC**: HTTP local em `127.0.0.1:8765` (FastAPI).
- **Captura**: `dxcam` no Windows, `mss` no macOS/Linux, escolhido por
  factory em `backend/capture/factory.py`.

## Pré-requisitos

| Ferramenta | Versão | Como instalar (macOS) |
|---|---|---|
| Node | ≥ 20 | `brew install node` |
| Rust (rustup) | stable | `curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs \| sh` |
| uv | recente | `brew install uv` |
| Python | 3.12 | `uv python install 3.12` |
| Ollama | recente | `brew install ollama` (ou https://ollama.com/download) |
| Modelo `qwen2.5vl:3b` | — | `ollama pull qwen2.5vl:3b` (~3GB) |

Se você usa **zsh**, garanta que `~/.cargo/env` é sourceado no seu
shell startup (a instalação do rustup só escreve em `~/.profile`, que
zsh ignora):

```sh
echo '. "$HOME/.cargo/env"' >> ~/.zshrc
```

### Setup do VLM (Ollama)

A partir do M2 o app usa um VLM local (`qwen2.5vl:3b` via Ollama) para
descrever a tela. Antes de rodar o app pela primeira vez:

```sh
# 1. Subir o daemon (deixe rodando em background, em outro terminal)
ollama serve

# 2. Baixar o modelo (~3GB; alguns minutos)
ollama pull qwen2.5vl:3b

# 3. Verificar tudo de uma vez
bash scripts/setup-ollama.sh
```

O `setup-ollama.sh` detecta o SO, confirma que o daemon está respondendo
em `:11434` e que o modelo está disponível. Sai com código `0` quando
está tudo certo; `1` se o daemon estiver offline; `2` se o modelo
faltar. O app abre normalmente sem o Ollama, mas mostra a IA como
indisponível.

## Como rodar em dev

```sh
# 1. Instalar deps Node (uma vez)
npm install

# 2. Subir o app — Tauri spawna o sidecar Python automaticamente
npm run tauri dev
```

A primeira execução de `cargo` baixa e compila ~300 crates (alguns
minutos). As próximas são incrementais e rápidas.

### Permissões no macOS

O macOS exige **três** permissões manuais antes do app funcionar
plenamente — uma por funcionalidade (capturar tela, controlar input,
escutar input). Conceda todas para o **processo pai** do sidecar
Python — em dev é tipicamente o seu terminal (Terminal.app, iTerm, VS
Code, Warp); no app empacotado é o binário Tauri (`PlayIA.app`). Se
trocar de terminal, as permissões precisam ser reconcedidas. **Depois
de conceder, encerre o terminal e abra de novo** — o macOS só relê a
lista no startup do processo.

#### Screen Recording (a partir do M1)

A primeira chamada de `/capture` pede permissão. Autorize em:

> System Settings → Privacy & Security → Screen Recording

Sem isso, `mss` devolve uma imagem preta.

#### Accessibility (a partir do M3, modo Play)

Quando a IA começar a apertar teclas / clicar (rota `/play`), o macOS exige
**Accessibility**. Autorize em:

> System Settings → Privacy & Security → Accessibility

Adicione o mesmo app que rodou o `npm run tauri dev` (Terminal, iTerm, VS
Code…) ou, na release empacotada, o `PlayIA.app`. Sem isso o `pyautogui`
falha silenciosamente ou levanta `ExecutorPermissionError` com uma frase
prescritiva — abra o painel `Status` em `/play` para vê-la.

#### Input Monitoring (a partir do M5, modo Gravar)

Quando você for **gravar** (rota `/record`), o pynput precisa ler
teclas/mouse que acontecem fora da janela do PlayIA. Autorize em:

> System Settings → Privacy & Security → Input Monitoring

Adicione o mesmo app que rodou o sidecar (Terminal, iTerm, VS Code… ou
`PlayIA.app`). Sem isso, a gravação **roda mas captura `keys_down=[]`
e `mouse_buttons=[]`** — você vê na rota `/record` o contador de FPS
subindo mas nenhum input no dataset. É o sinal pra abrir as
configurações.

Accessibility e Input Monitoring são **diferentes**: a primeira deixa
o app *enviar* eventos, a segunda deixa o app *receber* eventos
globais.

#### Failsafe do pyautogui

Sempre que uma sessão de Play estiver rodando, mover o mouse para o
**canto superior esquerdo da tela** aborta imediatamente — `pyautogui`
levanta `FailSafeException` e o engine marca a sessão como
`status="error"` com `stop_reason="error"`. É o seu botão de pânico físico.

## Ambiente de desenvolvimento vs alvo

- **Dev**: macOS arm64 (Apple Silicon). Compila e roda com fallback
  `mss` para captura.
- **Alvo de produção**: Windows. Usa `dxcam` (DXGI, 240+ FPS) e é
  empacotado como `.exe` (NSIS) via GitHub Actions no M8.
- **Validação Windows**: por enquanto, baixar o `.exe` da release.
  A partir do M8, CI em `windows-latest` faz o build de cada tag.

Mais detalhes em `CLAUDE.md`, seção "Ambiente de desenvolvimento vs
alvo".

## Estrutura

```
playia/
├── src/                 # Frontend SvelteKit (TypeScript)
│   ├── lib/http.ts      # BACKEND + humanizeError
│   └── routes/
│       ├── +page.svelte           # home (cards Play/Gravar/Jogos/Inspect)
│       ├── inspect/+page.svelte   # debug do VLM (M2)
│       ├── play/+page.svelte      # controle da sessão (M3)
│       ├── games/+page.svelte     # CRUD do catálogo (M4)
│       └── record/+page.svelte    # watch-me-play live (M5)
├── src-tauri/           # Shell Rust + spawn do sidecar
│   └── src/lib.rs
├── backend/             # Sidecar Python (FastAPI + uv)
│   ├── main.py
│   ├── capture/         # Protocol + mss/dxcam (com region)
│   ├── vision/          # VLMProvider + OllamaProvider (M2)
│   ├── executor/        # InputExecutor + pyautogui (M3)
│   ├── planner/         # Planner + VLMPlanner + Action (M3)
│   ├── session/         # SessionEngine turn-based (M3)
│   ├── memory/          # SQLite + sqlite-vec (M4)
│   │   ├── paths.py            # platformdirs.user_data_dir("PlayIA")
│   │   ├── connection.py       # conexão thread-local, WAL, vec0
│   │   ├── migrations/         # NNN_*.sql versionado
│   │   ├── models.py           # pydantic Game/Recording/...
│   │   ├── repos/              # games_repo ativo, demais stubs
│   │   └── seeds/              # 2048, chrome-dino, 99-nights
│   └── recording/       # watch-me-play engine (M5)
│       ├── base.py             # Protocol Recorder
│       ├── pynput_impl.py      # captura + listeners
│       ├── factory.py
│       └── errors.py
├── docs/
│   └── memory-model.md  # detalhe das tabelas, FKs, decisões
├── CLAUDE.md            # Contexto e regras para o Claude Code
└── README.md
```

## Endpoints do sidecar

Base: `http://127.0.0.1:8765`.

| Método | Path | Descrição |
|---|---|---|
| GET    | `/health`              | `{"ok": true}` |
| GET    | `/vlm/status`          | Health do VLM: `{ready, model, issue}`. |
| POST   | `/capture`             | PNG do monitor primário. Body opcional `{"region": [x,y,w,h]}`. |
| POST   | `/describe`            | Descrição em pt-br: `{description, latency_ms, model}`. |
| GET    | `/session/games`       | `dict[str, Game]` (compat M3). |
| POST   | `/session/start`       | Loop turn-based. 400 se `tempo != turn_based`; 403 se `anti_cheat != none` sem `acknowledge_ban_risk: "estou ciente do risco"`. |
| POST   | `/session/stop`        | Encerra loop em ≤1 ciclo. |
| GET    | `/session/status`      | Snapshot `SessionState`. |
| GET    | `/games`               | M4 — lista (filtros `?tempo=&anti_cheat=`). |
| GET    | `/games/{id}`          | M4 — detalhe (404 se não existe). |
| POST   | `/games`               | M4 — cria (id é slug `^[a-z0-9][a-z0-9-]*$`). |
| PUT    | `/games/{id}`          | M4 — atualiza. |
| DELETE | `/games/{id}`          | M4 — 409 se houver recordings/motor_models. |
| POST   | `/recording/start`     | M5 — inicia watch-me-play. Body: `{game_id, fps, region?}`. |
| POST   | `/recording/stop`      | M5 — idempotente. |
| GET    | `/recording/status`    | M5 — `{running, fps_real, frames_captured, ...}`. |
| GET    | `/recordings`          | M5 — lista `[{recording, disk_size_bytes}]`. |
| GET    | `/recordings/{id}`     | M5 — detalhe + `frames_dir` absoluto. |
| DELETE | `/recordings/{id}`     | M5 — body `{"confirm": true}` obrigatório; 409 com motor_models. |

## Verificar manualmente

```sh
# Terminal 1: subir só o backend (sem Tauri)
cd backend && uv run python main.py

# Terminal 2: testar M1+M2
curl http://127.0.0.1:8765/health
# {"ok":true}

curl -X POST http://127.0.0.1:8765/capture --output /tmp/t.png
file /tmp/t.png
# /tmp/t.png: PNG image data, ...

# Testar M3 (precisa de Ollama rodando + qwen2.5vl:3b baixado)
curl http://127.0.0.1:8765/session/games
curl -X POST http://127.0.0.1:8765/session/start \
  -H 'Content-Type: application/json' \
  -d '{"game":"2048","max_actions":3,"max_duration_s":120,"step_delay_ms":300}'
curl http://127.0.0.1:8765/session/status
curl -X POST http://127.0.0.1:8765/session/stop
```

Ou: rodar `npm run tauri dev` na raiz, abrir https://play2048.co/ em
outra janela e usar a rota `/play`.

## Licença

A definir.
