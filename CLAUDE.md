# PlayIA — Project Context

> Este arquivo é lido automaticamente pelo Claude Code ao abrir o repositório.
> Mantenha-o curto, acionável e atualizado conforme o projeto evolui.

## Visão

**PlayIA** é um app desktop (Windows) que **aprende a jogar um jogo específico
observando você jogar por 30-60 minutos**, e depois joga sozinho com qualidade
suficiente para ser útil.

**Alvo concreto da v1**: jogos de ação no Roblox, especificamente
**99 Nights in the Forest**. A arquitetura é genérica — qualquer jogo
single-player ou sandbox onde automação seja permitida funciona da mesma forma.

Como funciona, em quatro fases:

1. **Watch me play** — você joga 30-60 min, PlayIA grava `(frame, inputs)` a
   15-30 Hz e salva como dataset.
2. **Train** — um modelo pequeno (CNN policy network) é treinado por
   *behavioral cloning* naquela gravação. Saída: arquivo ONNX, ~5-20MB, por jogo.
3. **Play** — IA joga em **modo hierárquico**:
   - **VLM estrategista** (1-30s/decisão): define a INTENÇÃO em pt-br
     ("coletar madeira", "fugir do lobo", "construir abrigo").
   - **Motor model** (5-30ms/decisão): traduz a intenção em teclas+mouse
     em tempo real, condicionado pelo frame atual.
4. **Improve** — episódios bem-sucedidos viram *skills* nomeadas que o
   VLM passa a invocar diretamente, sem re-decidir do zero.

Memória persistente em SQLite faz com que cada jogo tenha seu próprio
motor model + skills + histórico, e melhore ao longo do tempo.

Distribuído como instalador `.exe` via GitHub Releases (auto-update embutido).

## Segurança e ética — RISCO REAL DE BAN, LEIA

PlayIA controla teclado e mouse de fora do jogo. **Anti-cheats modernos
detectam isso e banem a conta + HWID.** Nenhuma técnica aqui é segura
contra anti-cheat. Esse não é o projeto.

Anti-cheats que detectam PlayIA hoje:
- **Hyperion (Roblox)** — padrão em todos os jogos Roblox desde 2024.
  Detecta `pyautogui`, `pydirectinput`, AutoHotkey, injeção de processo,
  leitura de memória, e tem detecções pra muitas VMs. **Bans afetam a
  conta inteira do Roblox e podem afetar o HWID.**
- **Vanguard (Valorant)**, **EAC**, **BattlEye**, **PunkBuster** — mesmo
  risco em jogos PC.

Política do projeto:

1. **`GameProfile.anti_cheat`** é coluna obrigatória no schema.
   Valores: `none | unknown | hyperion | eac | battleye | vanguard | other`.
2. **UI bloqueia** sessões em jogos com `anti_cheat != "none"` por padrão.
   Bypass exige checkbox "Eu entendo o risco de ban" + digitar a frase
   "estou ciente do risco" no campo de confirmação. Não há jeito de pular.
3. **Para Roblox especificamente**, o aviso é em vermelho e recomenda:
   conta descartável (alt), Roblox Studio em playtest local (sem login),
   ou jogos não-Roblox sem anti-cheat para desenvolvimento da arquitetura.
4. **README** tem uma seção grande sobre isso, em pt-br.
5. **Modo seguro recomendado pra dev**: 99 Nights pode rodar dentro do
   Roblox Studio em "Play Solo" (não conecta ao servidor de produção,
   Hyperion não roda nesse modo). Use isso para iterar.

Nunca tente burlar Hyperion, ofuscar o app pra escapar de detecção,
hookar driver de kernel, nada disso. Se um caminho técnico for nessa
direção, **pare e me avise**.

## Ambiente de desenvolvimento vs alvo

- **Desenvolvimento**: macOS (arm64, Apple Silicon).
- **Alvo de produção**: Windows. Roblox roda em Windows; Hyperion roda em
  Windows; a release final é `.exe`.
- **Como o usuário testa funcionalmente**: baixando o `.exe` no GitHub
  Releases e instalando no Windows.

Consequências práticas:

1. **Cross-platform por default**. Toda dep específica de SO atrás de
   Protocol/factory. Captura, input, paths (use `platformdirs`).
2. **Não trave o desenvolvimento esperando Windows**. Fallback no Mac,
   `# TODO(windows-only)` quando necessário.
3. **CI roda em `windows-latest`** (via `tauri-action`) — fonte da verdade
   pra "isso funciona em produção". Mac é fonte de verdade pra
   "isso compila e a arquitetura está sã".
4. **Treino de motor model**: PyTorch com MPS no Mac (Apple Silicon) ou
   CUDA no Windows. Treina onde a release vai rodar quando possível.
5. **Inferência ONNX**: cross-platform por design, CPU é suficiente.

Se algo só puder ser validado em Windows e bloquear, **pare e avise** —
nunca improvise um "deve funcionar no Windows" sem evidência.

## Stack obrigatória (não desviar sem discutir)

- **UI**: Tauri 2 (Rust shell + WebView2). Frontend em **SvelteKit**.
- **Backend IA**: sidecar Python (PyInstaller-frozen no release).
- **IPC**: HTTP local (FastAPI no sidecar) entre Tauri e Python.
- **HTTP client**: `httpx` (async) para falar com providers de VLM/LLM.
- **Captura de tela**: `dxcam` (Windows, 240+ FPS). Fallback `mss`.
- **Input (executor)**: `pyautogui` (+ `pydirectinput` no Windows pra
  DirectInput).
- **Captura de input do usuário** (watch-me-play): `pynput` (cross-platform).
- **VLM estrategista padrão**: Ollama + `qwen2.5vl:3b` (local, gratuito,
  offline; o 7b spilla pro CPU no Mac 16GB e fica inviável).
- **BYOK opcional (M9)**: Gemini, Groq, Claude API, OpenAI, OpenRouter.
- **Memória**: SQLite + `sqlite-vec` (arquivo único em
  `platformdirs.user_data_dir("PlayIA")`).
- **Embeddings**: `sentence-transformers/all-MiniLM-L6-v2` local.
- **Treino do motor model**: PyTorch (MPS no Mac / CUDA no Windows).
  Pequenas CNN policy networks (~1-5M params).
- **Inferência do motor model**: ONNX Runtime (CPU funciona; GPU opcional).
- **CI/CD**: GitHub Actions com `tauri-action` → NSIS installer.
- **Auto-update**: `tauri-plugin-updater` lendo `latest.json` do Release.

## Arquitetura de dois andares — POR QUE EXISTE

VLM-no-loop (M3 atual, 2048) **não consegue jogar ação**. Latência local
fica em 5-30s/decisão e jogos de ação rodam a 30-60 Hz. Sem milagre.

A solução universal é separar **estratégia** (lenta) de **motor** (rápido):

```
┌────────────────────────────────────────────────────────────┐
│ Loop estratégico (0.1 – 1 Hz)                              │
│   captura frame → VLM define INTENÇÃO em pt-br → publica   │
│   ex.: "coletar madeira da árvore à frente"                │
└──────────────────────────┬─────────────────────────────────┘
                           │ intenção (string + parâmetros)
                           ▼
┌────────────────────────────────────────────────────────────┐
│ Loop motor (30 – 60 Hz)                                    │
│   captura frame → motor model (ONNX) → teclas/mouse        │
│   motor treinado por jogo via behavioral cloning           │
└────────────────────────────────────────────────────────────┘
```

Quando usar cada um:

- **`turn_based`** (xadrez, 2048, RPG de turno) — só VLM. Motor model não
  é necessário.
- **`slow_realtime`** (Stardew, RPG isométrico, jogo de browser lento) —
  só VLM, com loop em 1-2 Hz (Groq na nuvem ajuda muito).
- **`fast_realtime`** (Roblox de ação, platformers, FPS) — **hierárquico
  obrigatório**. Precisa de motor model treinado pro jogo específico.

O `GameProfile` declara `tempo` no schema. O runtime de play recusa
iniciar sessão de `fast_realtime` sem motor model treinado pra aquele jogo.

## Estrutura esperada

```
playia/
├── src-tauri/              # Rust shell (Tauri)
├── src/                    # Frontend SvelteKit
│   └── routes/
│       ├── +page.svelte    # home (cards Play / Record / Train / Inspect)
│       ├── inspect/        # debug M2 (capturar + descrever)
│       ├── play/           # M3 turn-based; M7 fast-realtime hierárquico
│       ├── record/         # M5 watch-me-play
│       ├── train/          # M6 treino do motor model
│       ├── games/          # M4 catálogo de jogos (CRUD)
│       └── settings/       # M9 BYOK
├── backend/
│   ├── main.py
│   ├── capture/            # M1 — screen capture cross-platform
│   ├── vision/             # M2 — VLM providers
│   ├── executor/           # M3 — keyboard/mouse output
│   ├── planner/            # M3 — VLM-no-loop (turn_based)
│   ├── session/            # M3 — turn-based session engine
│   ├── memory/             # M4 — SQLite + sqlite-vec, repositories
│   ├── recording/          # M5 — watch-me-play engine (pynput + capture)
│   ├── training/           # M6 — behavioral cloning trainer (PyTorch)
│   ├── motor/              # M6 — motor model inference (ONNX)
│   ├── strategist/         # M7 — hierarchical loop coordinator
│   └── pyproject.toml
├── .github/workflows/
│   └── release.yml         # M10
├── CLAUDE.md
├── README.md
└── docs/
    ├── architecture.md
    └── memory-model.md
```

Padrão de cada módulo backend: `base.py` (Protocol + dataclasses) +
`errors.py` + `factory.py` + `<impl>_impl.py`. Vale para todos.

## Política de commits e push

**Faça commit + push automaticamente** sempre que terminar uma unidade
de trabalho. Push direto na `main` está liberado nesta fase (solo dev).

Regras:

- **Conventional Commits** (`feat:`, `fix:`, `chore:`, `docs:`, `refactor:`,
  `test:`, `ci:`).
- **Mensagens em português**, primeira linha ≤ 72 caracteres, corpo
  opcional explicando *por quê*.
- **Branch**: trabalhe direto em `main`. Quando começar a ter usuários
  externos, mude para PRs.
- **Tags de release**: `vMAJOR.MINOR.PATCH` (SemVer). `vX.Y.Z` dispara
  o workflow.
- **Não comite**: segredos, chaves de API, modelos baixados
  (`*.gguf`, `*.safetensors`, `*.onnx`), `playia.db` de teste, gravações
  (`data/recordings/`), builds (`target/`, `dist/`, `build/`,
  `node_modules/`, `__pycache__/`, `*.spec`).

Antes de cada `git push`:

1. Confirme que o repo ainda buila (`cargo check`, `npm run build`,
   `uv run python -m compileall backend`).
2. Confirme que o `.gitignore` cobre o que você gerou.
3. Mensagem do commit descreve o **resultado**, não os passos.

## Marcos (roadmap)

- **M1** [concluído]: Tauri app + sidecar Python + captura na UI.
- **M2** [concluído]: VLM local (Ollama Qwen2.5-VL 3B) descrevendo a tela.
- **M3** [concluído]: Loop turn-based fechado (captura → planner →
  executor) com 2048. Valida o pipeline; é a base do modo `turn_based`.
- **M4** [concluído]: **Memória SQLite + sqlite-vec**. Schema completo
  versionado por migrations (`backend/memory/migrations/001_initial.sql`)
  cobrindo todas as tabelas (`games`, `recordings`, `recording_frames`,
  `motor_models`, `episodes`, `skills`, `knowledge`, + virtuais
  `vec_skills`, `vec_knowledge`). Conexão thread-local com WAL + FK on.
  `games_repo` ativo; outros repos ficam como stub com `TODO(MX)`.
  Seeds idempotentes: 2048, chrome-dino, 99-nights-in-the-forest.
  CRUD `/games` na UI com badge vermelho de anti-cheat. Gate de
  `tempo`/`anti_cheat` no `/session/start`.
- **M5** [concluído]: **Watch-me-play recording engine**. Captura
  simultânea de frame (15-30 Hz) + inputs do usuário via `pynput` em
  threads dedicadas (kb listener, mouse listener, capture loop).
  Frames como PNG em
  `<user_data>/PlayIA/data/recordings/<rec_id>/<ts_ms>.png`; linhas em
  `recording_frames` via `insert_many` em batch (~1 batch/s). UI
  `/record` com botão GRAVAR / PARAR pulsante, FPS real, frames
  capturados, tamanho em MB e lista de gravações. Endpoints
  `/recording/start|stop|status`, `/recordings`, `/recordings/{id}`,
  `DELETE /recordings/{id}` (body `{"confirm": true}` obrigatório, 409
  se houver motor_models treinados). macOS exige Input Monitoring
  (separado de Accessibility) — documentado no README.
- **M6** [concluído]: **Behavioral cloning trainer + inferência ONNX**.
  `backend/training/` PyTorch CNN policy network (~350k params: 3 conv
  strided + AdaptiveAvgPool 4x4 + FC 256). BCE_with_logits em
  keys+clicks + MSE em mouse_dx/dy. Split 80/20, ETA por epoch,
  cancel via `threading.Event`. Probe MPS no startup com fallback CPU
  automático. ONNX export via `dynamo=False` (exporter legado, sem dep
  `onnxscript`). `backend/motor/` carrega o ONNX via `onnxruntime`
  CPUExecutionProvider, latência ~7-20ms. UI `/train` com chart inline
  SVG (sem CDN). Endpoints `/training/{start,status,cancel}`,
  `/motor-models[?game_id=]`, `/motor-models/{id}` (GET/DELETE),
  `/motor/test/{game_id}` (debug, 412 se sem motor).
- **M7** [concluído]: **Loop hierárquico runtime**. `strategist/`
  coordena VLM estrategista (5-15s/decisão no Mac) e motor model ONNX
  (30 Hz alvo, latência 5-20ms) em dois `asyncio.Task` cooperativos.
  HierarchicalEngine com `_held_keys` faz diff por tick e emite
  press/release no executor — cleanup CRÍTICO no finally libera todas
  as teclas que ficaram seguradas. UI `/play/hierarchical` com tab
  shared com /play, dropdown filtrado por (fast_realtime ∩
  motor_available), banner red de acknowledge_ban_risk para anti-cheat,
  intenção atual em destaque + histórico. Endpoints `/hsession/{start,
  stop,status}`, `/motor/health/{game_id}`. Game profile do 99 Nights
  e Chrome Dino já no DB; ban warning explícito.
- **M8**: **Skill curation + self-reflection**. Episódios viram skills
  nomeadas; VLM invoca skills diretamente quando reconhece o cenário.
- **M9**: **BYOK + Settings UI**. Multi-provider (Gemini, Groq, Claude,
  OpenAI, OpenRouter) com cloud opcional pro VLM estrategista.
- **M10**: **Release v1.0**. GitHub Actions, NSIS installer, auto-update,
  README polido, demo gif.

Trabalhe um marco por vez. Não pule.

## Convenções de código

- **Python**: 3.12, type hints obrigatórios, `ruff` para lint/format,
  `pydantic` para schemas. `print()` proibido — use `logging`.
- **Rust**: edição 2021, `cargo fmt` antes de commit, evite `unwrap()`
  fora de testes.
- **TS/Svelte**: `prettier` + `eslint`, strict mode no TS, componentes
  pequenos. Svelte 5 com runes (`$state`, `$derived`).
- **Nomes**: pastas e arquivos em `kebab-case`, classes em `PascalCase`,
  funções em `snake_case` (Python) ou `camelCase` (TS/Rust).
- **Logs**: estruturados (JSON), nível mínimo `INFO` em prod, `DEBUG`
  em dev.

## Como rodar em dev

Pré-requisito do M2 em diante: Ollama instalado + `qwen2.5vl:3b` baixado.
Rode `bash scripts/setup-ollama.sh` pra validar antes de subir o app.

```bash
# Em outro terminal, daemon do VLM:
ollama serve

# App (Tauri spawna o sidecar Python automaticamente):
npm install
npm run tauri dev
```

Para subir só o backend sem Tauri:

```bash
cd backend
uv run python main.py  # FastAPI em http://127.0.0.1:8765
```

**macOS Accessibility**: o executor (pyautogui) precisa de permissão em
*System Settings → Privacy & Security → Accessibility*. Sem isso o
input falha silenciosamente. O endpoint `/session/start` levanta
`ExecutorPermissionError` com mensagem prescritiva.

## Modelo de memória

SQLite + `sqlite-vec`, arquivo único em
`platformdirs.user_data_dir("PlayIA")/playia.db` (mac:
`~/Library/Application Support/PlayIA/`, win: `%APPDATA%/PlayIA/`).

Estrutura em `backend/memory/`:

- `paths.py` — `data_dir`, `db_path`, `recordings_dir`, `motor_models_dir`
  via `platformdirs`.
- `connection.py` — `get_connection()` thread-local com `sqlite-vec`
  carregado, WAL + FK on.
- `migrations/__init__.py` — `apply_pending(conn)` idempotente.
- `migrations/001_initial.sql` — schema inicial.
- `models.py` — pydantic `Game/Recording/RecordingFrame/MotorModel/Episode/
  Skill/Knowledge` + enums `Tempo`, `AntiCheat`.
- `repos/games_repo.py` — ativo (M4).
- `repos/{recordings,recording_frames,motor_models,episodes,skills,
  knowledge}_repo.py` — stubs com `TODO(MX)`.
- `seeds/__init__.py` + `seeds/games.py` — `apply_seeds(conn)` com 3
  jogos iniciais.

Tabelas principais:

- **games** — perfis de jogo (id, name, url, `tempo`, `anti_cheat`,
  `allowed_keys_json`, goal, notes, created_at). `tempo` ∈ `turn_based |
  slow_realtime | fast_realtime`. `anti_cheat` ∈ `none | unknown |
  hyperion | eac | battleye | vanguard | other`.
- **recordings** — sessões de watch-me-play (M5; tabela já existe).
- **recording_frames** — frames + inputs por gravação (M5).
- **motor_models** — ONNX treinados (M6).
- **episodes** — eventos de play (M8).
- **skills** — sequências nomeadas com embedding (M8). Espelhada em
  `vec_skills(embedding float[384])` para busca K-NN.
- **knowledge** — fatos semânticos (M8). Espelhada em `vec_knowledge`.
- **schema_version** — controle de migrations (bootstrap automático).

**Frames brutos NÃO vão como BLOB no SQLite** — viram arquivos PNG
separados, e a coluna `frame_path` aponta pra eles. DB fica leve, storage
pesado em `<user_data>/PlayIA/data/recordings/<recording_id>/<ts_ms>.png`.

Detalhes em [`docs/memory-model.md`](docs/memory-model.md).

## Provedores de IA

Abstração em `backend/vision/` (padrão Protocol + Factory + impl):

- `vision/base.py` — `VLMProvider` Protocol + `VLMStatus` dataclass.
- `vision/factory.py` — `get_vlm()` (hoje Ollama; multi-provider no M9).
- `vision/ollama_impl.py` — `OllamaProvider` via `httpx` async.
- `vision/errors.py` — `VLMUnavailableError`/`ModelMissing`/`Timeout`.

Interface atual:

```python
class VLMProvider(Protocol):
    model: str
    async def describe(self, image_png: bytes, prompt: str) -> str: ...
    async def status(self) -> VLMStatus: ...
```

Implementações futuras (M9): `GeminiProvider`, `GroqProvider`,
`ClaudeProvider`, `OpenAIProvider`, `OpenRouterProvider`.

## Loop turn-based (M3 — existe)

Three módulos com padrão Protocol + Factory + impl:

- **`backend/executor/`** — input.
- **`backend/planner/`** — VLM decide action a partir da tela.
- **`backend/session/`** — orquestra captura → plan → exec em
  `asyncio.Task`, com limites hard de ações/tempo e stop via
  `asyncio.Event`.

Engine lê o `Game` via `games_repo.get(conn, id)`; `session/games.py`
foi removido em M4.

Endpoints do M3 (turn-based):
| Método | Path | Descrição |
|---|---|---|
| GET | `/session/games` | dict `{id: Game}` via repo (compat M3). |
| POST | `/session/start` | inicia loop turn-based. 409 se já houver sessão; 422 se jogo desconhecido; **400 se `tempo != turn_based`**; **403 se `anti_cheat != none` sem `acknowledge_ban_risk: "estou ciente do risco"` no body**. |
| POST | `/session/stop` | seta o Event, retorna estado. |
| GET | `/session/status` | snapshot do `SessionState`. |

Endpoints CRUD do catálogo (M4):
| Método | Path | Descrição |
|---|---|---|
| GET | `/games` | lista `list[Game]`, filtros opcionais `?tempo=&anti_cheat=`. |
| GET | `/games/{id}` | detalhe (404). |
| POST | `/games` | cria; 409 em id/nome conflitante; id é slug `^[a-z0-9][a-z0-9-]*$`. |
| PUT | `/games/{id}` | atualiza. |
| DELETE | `/games/{id}` | apaga; **409 se houver `recordings` ou `motor_models` associados** (`games_repo.has_dependents` antecipa a mensagem antes do FK RESTRICT). |

## Watch-me-play (M5 — existe)

Módulo `backend/recording/` no padrão da casa:

- `base.py` — `Recorder` Protocol + `RecordingStatus` dataclass
  (running, recording_id, fps_real, frames_captured, started_at,
  finished_at, region, error).
- `pynput_impl.py` — `PynputRecorder` orquestra 3 threads:
  `pynput.keyboard.Listener` e `pynput.mouse.Listener` mantêm
  snapshot protegido por lock; thread dedicada `recorder-<id>` faz o
  loop de captura (grab → escreve PNG → buffer → `insert_many` cada
  `BATCH_SIZE=30` frames).
- `factory.py` — `get_recorder(capture)` → `PynputRecorder`.
- `errors.py` — `RecorderBusyError`, `RecorderPermissionError`.

`recordings_repo` e `recording_frames_repo` são ativos (no
`memory/repos/`). Cada thread usa sua conexão SQLite (thread-local).

Endpoints (M5):
| Método | Path | Descrição |
|---|---|---|
| POST | `/recording/start` | body `{game_id, fps, region?}`. 422 se game desconhecido; 409 `RecorderBusyError`; 403 `RecorderPermissionError`. |
| POST | `/recording/stop` | idempotente. |
| GET | `/recording/status` | snapshot vivo do `RecordingStatus`. |
| GET | `/recordings` | `list[{recording, disk_size_bytes}]`, filtro `?game_id=`. |
| GET | `/recordings/{id}` | detalhe + `frames_dir` absoluto. |
| DELETE | `/recordings/{id}` | exige body `{"confirm": true}` (400 se faltar); 409 com motor_models; ordem DB→disco. |

UI `/record` (Svelte 5): dropdown de games (qualquer tempo), FPS
input (1-60), toggle de região, botão verde GRAVAR / vermelho PARAR
pulsante, métricas live (FPS real, frames, tempo decorrido, rec_id),
painel lateral com lista de gravações + apagar.

Permissões macOS: além de Accessibility (pyautogui para Play),
`pynput` precisa de **Input Monitoring** em System Settings → Privacy
& Security. Sem isso, a gravação roda mas `keys_down=[]` — diagnóstico
documentado no README.

## Training + Motor (M6 — existe)

Dois módulos no padrão da casa:

- `backend/training/` (PyTorch):
  - `base.py` — `TrainConfig` (epochs, batch_size, lr, img_size,
    val_split, device, dropout, mouse_loss_weight) e `TrainResult`.
  - `action_encoding.py` — `encode/decode_keys/decode_mouse` para o
    vetor de ação `[one_hot_keys | mouse_dx_norm, mouse_dy_norm |
    click_left, click_right]`. `MOUSE_NORM=200` clipa dx/dy em
    `[-1, 1]`.
  - `model.py` — `PolicyNet` (~350k params).
  - `dataset.py` — `RecordingDataset` lê PNGs via PIL, pré-computa
    mouse deltas em `__init__`; `num_workers=0` no DataLoader pra
    reusar conexão thread-local.
  - `trainer.py` — `Trainer` singleton; `start(recording_id, config)`
    cria `asyncio.Task` que delega a `asyncio.to_thread`. Status
    publicado em `_Status` (lock); cancelamento via
    `threading.Event`. Probe MPS no init.
  - `onnx_export.py` — `dynamo=False` (exporter legado).
  - `errors.py` — `TrainerBusyError`/`TrainerCancelledError`/
    `TrainerDatasetError`.

- `backend/motor/` (onnxruntime):
  - `base.py` — `Motor` Protocol + `MotorAction`/`MotorMeta`.
  - `onnx_impl.py` — `ONNXMotor` mantém uma `InferenceSession` por
    processo (`CPUExecutionProvider`); `predict(png)` replica o
    preprocess do training.dataset e usa
    `training.action_encoding.decode_*` no postprocess.
  - `factory.py`/`errors.py` (`MotorNotFoundError` 412,
    `MotorInferenceError` 500).

Endpoints (M6):
| Método | Path | Descrição |
|---|---|---|
| GET | `/motor-models[?game_id=]` | lista ordenada DESC por trained_at. |
| GET | `/motor-models/{id}` | detalhe (404). |
| DELETE | `/motor-models/{id}` | apaga DB + .onnx em disco. |
| POST | `/training/start` | `{recording_id, config?}` — 404 rec inexistente, 409 já roda. |
| GET | `/training/status` | progress live + loss_curve. |
| POST | `/training/cancel` | idempotente. |
| GET | `/motor/test/{game_id}` | 1 frame + inferência, sem dispatch. 412 se sem motor model. |

UI `/train` (Svelte 5): dropdown game→recording filtrado, sliders
epochs/batch/img_size/device, botões Treinar/Cancelar, painel live
com 6 métricas + chart inline SVG (train/val polylines), banner verde
de "concluído" com motor_model_id, accuracy_keys, path do `.onnx`.

Notas conhecidas:
- ONNX final ~1-5MB pra `PolicyNet` default.
- Treino de 9k frames @ 30fps no M1/M2/M3 com MPS leva 3-10 min;
  fallback CPU multiplica por ~3.
- Accuracy < 60% em qualquer dataset = sinal pra refazer a gravação
  ou aumentar `epochs`; o motor model funciona mas joga mal.

## Loop hierárquico (M7 — existe)

`backend/strategist/` é a nova frente: dois `asyncio.Task` cooperativos
coordenam VLM estrategista (lento) + motor ONNX (rápido) sob o mesmo
`asyncio.Event` de stop.

```
┌─────────────────────────────────────────────────────────────────┐
│ hsession-strategist  (lento; ~0.05-0.1 Hz no Mac com qwen2.5vl) │
│   while not stop:                                               │
│     png = capture.grab(region)                                  │
│     intention = await vlm_strategist.decide(png, goal, history) │
│     state.current_intention = intention                         │
│     append intentions_history (cap 50)                          │
│     await wait_for(stop, intention.ttl_s)                       │
└──────────────────────────┬──────────────────────────────────────┘
                           │ Intention publicada (texto pt-br + ttl_s)
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│ hsession-motor  (rápido; alvo 30 Hz; latência típica 5-20 ms)   │
│   while not stop and elapsed < max_duration_s:                  │
│     png = capture.grab(region)                                  │
│     action = motor.predict(png)        # v0.1 NÃO usa intention │
│     diff vs _held_keys → executor.key_press/key_release         │
│     state.last_frame_b64 = b64(png); total_actions++            │
│     await wait_for(stop, period - elapsed_tick)                 │
│   finally:                                                      │
│     executor.key_release(*_held_keys)  # CRÍTICO                │
└─────────────────────────────────────────────────────────────────┘
```

Módulo `backend/strategist/`:

- `base.py` — `Intention(text, params, issued_at, ttl_s)` e
  `HierarchicalState(status, game, region, motor_model_id,
  motor_accuracy, current_intention, intentions_history,
  actions_per_second, total_actions, last_frame_b64, ...)`.
- `vlm_strategist.py` — `VLMStrategist.decide(png, goal, history)`
  reusa `VLMProvider` com prompt focado em INTENÇÃO de alto nível
  em pt-br + few-shots (Chrome Dino + survival). Parser tolerante
  extrai primeiro `{...}` se vier com preâmbulo; `ttl_s` clampado em
  `[2, 30]`.
- `engine.py` — `HierarchicalEngine` com `start/stop/status`. Stop
  via `asyncio.Event` mais `await asyncio.gather(motor_task,
  strategist_task)`. FAILSAFE do pyautogui segue ativo.
- `errors.py` — `HSessionAlreadyRunningError` (409),
  `MotorNotTrainedError` (412), `StrategistError` (500).

Endpoints (M7):
| Método | Path | Descrição |
|---|---|---|
| POST | `/hsession/start` | `{game_id, region?, max_duration_s, target_fps, acknowledge_ban_risk?}` — 422 game desconhecido, 412 sem motor_model, 403 anti_cheat sem ack, 409 já roda. |
| POST | `/hsession/stop` | idempotente; aguarda ambas as tasks via `asyncio.gather`. |
| GET | `/hsession/status` | snapshot vivo + history. |
| GET | `/motor/health/{game_id}` | sempre 200; payload `{game_exists, motor_available, motor_model_id?, accuracy?, onnx_size_bytes?, onnx_exists?, reason?}`. |

UI: tab `/play` ↔ `/play/hierarchical`. Hierárquico mostra dropdown
filtrado por (fast_realtime ∩ motor treinado), intenção atual em 1.4rem
(verde), histórico das últimas 5 com timestamps, frame ao vivo e botão
PARAR enorme. Anti-cheat → box vermelho com input texto exigindo
exatamente "estou ciente do risco" antes de habilitar Iniciar (a
mesma frase que o backend valida).

**Simplificação v0.1**: `motor.predict()` recebe SÓ o frame; a intenção
atual fica no state e nos logs mas não entra como input do modelo.
Comentário explícito no `engine._loop_motor` marca onde plugar o
condicionamento por texto quando isso entrar (M+). Para Chrome Dino o
frame já carrega contexto suficiente.

**Parâmetros típicos no Mac (qwen2.5vl:3b)**:
- VLM strategist: 5-15s por intenção; ttl_s default 10s.
- Motor: 5-20 ms por inferência CPU; target_fps default 30; FPS real
  fica em 25-30 Hz quando o capture não é o gargalo.

## Referência rápida

- Pesquisa técnica completa: `/Users/guilherme/PlayIA-Pesquisa.md` (fora do repo).
- Inspiração: [Cradle Framework](https://github.com/BAAI-Agents/Cradle),
  [DeepMind SIMA](https://deepmind.google/blog/sima-generalist-ai-agent-for-3d-virtual-environments/).
- VLM padrão: [Qwen2.5-VL no Ollama](https://ollama.com/library/qwen2.5vl).
- 99 Nights in the Forest (alvo da v1):
  [roblox.com/games/...](https://www.roblox.com/games/) — usar
  Roblox Studio em playtest local pra dev.

---

*Quando alterar arquitetura, stack ou políticas, atualize este arquivo
no mesmo commit.*
