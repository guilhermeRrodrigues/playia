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
- **M5**: **Watch-me-play recording engine**. Captura simultânea de
  frame (15-30 Hz) + inputs do usuário via `pynput`. Grava em SQLite +
  PNG em disco. UI: rec/stop/listar sessões/preview.
- **M6**: **Behavioral cloning trainer**. PyTorch CNN policy network
  treinada na sessão gravada. Output ONNX salvo em
  `<user_data>/PlayIA/data/motor_models/<game_id>/<recording_id>.onnx`.
  UI: tela `/train` com progress + métricas.
- **M7**: **Loop hierárquico runtime**. `strategist/` coordena VLM
  (1-3 Hz) e motor model (ONNX, 30 Hz) em threads separados. Game
  profile do 99 Nights incluído com aviso de Hyperion. Funciona em
  Roblox Studio playtest local.
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

## Loop hierárquico (M7 — virá)

Será `backend/strategist/`, coordenando VLM lento + motor rápido. Quando
chegar lá, atualize esta seção com a arquitetura concreta.

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
