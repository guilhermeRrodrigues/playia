# PlayIA — Project Context

> Este arquivo é lido automaticamente pelo Claude Code ao abrir o repositório.
> Mantenha-o curto, acionável e atualizado conforme o projeto evolui.

## Visão

**PlayIA** é um app desktop (Windows) que assiste uma IA jogando qualquer jogo
e que aprende ao longo do tempo. Dois modos principais:

1. **Play** — a IA joga sozinha, observando a tela e controlando teclado+mouse.
2. **Watch me play** — o usuário joga, a IA observa e memoriza estratégias.

Memória persistente faz com que a IA melhore entre sessões e entre jogos.

Distribuído como instalador `.exe` via GitHub Releases (auto-update embutido).

## Stack obrigatória (não desviar sem discutir)

- **UI**: Tauri 2 (Rust shell + WebView2). Frontend em **SvelteKit**.
- **Backend IA**: sidecar Python (PyInstaller-frozen no release).
- **IPC**: HTTP local (FastAPI no sidecar) entre Tauri e Python.
- **Captura de tela**: `dxcam` (Windows, 240+ FPS). Fallback `mss`.
- **Input**: `pyautogui` (+ `pydirectinput` para jogos AAA com DirectInput).
- **VLM padrão**: Ollama + `qwen2.5vl:7b` (local, gratuito, offline).
- **BYOK opcional**: Gemini, Groq, Claude API, OpenAI, OpenRouter via UI.
- **Memória**: SQLite + `sqlite-vec` (arquivo único `playia.db`).
- **Embeddings**: `sentence-transformers/all-MiniLM-L6-v2` local.
- **CI/CD**: GitHub Actions com `tauri-action` → NSIS installer.
- **Auto-update**: `tauri-plugin-updater` lendo `latest.json` do GitHub Release.

## Estrutura esperada

```
playia/
├── src-tauri/              # Rust shell (Tauri)
│   ├── src/main.rs         # spawn do sidecar Python
│   ├── tauri.conf.json     # config + sidecar binary path
│   └── Cargo.toml
├── src/                    # Frontend SvelteKit
│   ├── routes/
│   ├── lib/
│   └── app.html
├── backend/                # Python sidecar
│   ├── main.py             # entrypoint FastAPI
│   ├── capture/            # dxcam wrapper
│   ├── vision/             # provedores VLM (ollama, gemini, claude, …)
│   ├── memory/             # sqlite-vec, episodes/skills/knowledge
│   ├── planner/            # loop de decisão
│   ├── executor/           # pyautogui
│   ├── watch/              # modo "watch me play"
│   └── pyproject.toml
├── .github/workflows/
│   └── release.yml         # tauri-action
├── CLAUDE.md               # este arquivo
├── README.md
└── docs/
    ├── architecture.md
    └── memory-model.md
```

## Política de commits e push

**Faça commit + push automaticamente** sempre que terminar uma unidade de trabalho.
O usuário liberou push direto na `main` para esta fase inicial (solo dev).

Regras:

- **Conventional Commits** (`feat:`, `fix:`, `chore:`, `docs:`, `refactor:`, `test:`, `ci:`).
- **Mensagens em português**, primeira linha ≤ 72 caracteres, corpo opcional explicando *por quê*.
- **Branch**: trabalhe direto em `main` por enquanto. Quando começar a ter usuários, mude para PRs.
- **Tags de release**: `vMAJOR.MINOR.PATCH` (SemVer). `vX.Y.Z` dispara o workflow do release.
- **Não comite**: segredos, chaves de API, modelos baixados (`*.gguf`, `*.safetensors`), `playia.db` de teste, builds (`target/`, `dist/`, `build/`, `node_modules/`, `__pycache__/`, `*.spec`).

Antes de cada `git push`:

1. Confirme que o repo ainda buila (`cargo check`, `npm run build`, `python -m compileall backend`).
2. Confirme que o `.gitignore` cobre o que você gerou.
3. Mensagem do commit descreve o **resultado**, não os passos (`feat: capture loop entrega frames ao planner` em vez de `mexi no dxcam`).

## Segurança e ética — IMPORTANTE

PlayIA **NÃO PODE** ser usado em jogos multiplayer com anti-cheat
(Vanguard, EAC, BattlEye, Hyperion). Resultado: ban da conta + HWID.

- Adicione um **disclaimer obrigatório** na UI antes da primeira sessão.
- Considere detectar anti-cheats em execução e bloquear automaticamente.
- README precisa ter um aviso grande e claro.
- Foco: single-player, jogos sem anti-cheat, sandboxes, jogos de navegador.

## Marcos (roadmap)

- **M1**: Tauri app + sidecar Python que captura a tela e mostra na UI.
- **M2**: VLM local (Ollama Qwen2.5-VL) descrevendo a tela.
- **M3**: Loop fechado num jogo simples (Tetris web ou similar).
- **M4**: Memória episódica em SQLite-vec.
- **M5**: Skill curation + self-reflection.
- **M6**: Modo watch-me-play.
- **M7**: UI de Settings + BYOK multi-provider.
- **M8**: Release v1.0 via GitHub Actions com auto-update.

Trabalhe um marco por vez. Não pule.

## Convenções de código

- **Python**: 3.12, type hints obrigatórios, `ruff` para lint/format, `pydantic` para schemas.
- **Rust**: edição 2021, `cargo fmt` antes de commit, evite `unwrap()` fora de testes.
- **TS/Svelte**: `prettier` + `eslint`, strict mode no TS, componentes pequenos.
- **Nomes**: pastas e arquivos em `kebab-case`, classes em `PascalCase`, funções em `snake_case` (Python) ou `camelCase` (TS/Rust).
- **Logs**: estruturados (JSON), nível mínimo `INFO` em prod, `DEBUG` em dev. Sem `print()`.

## Como rodar em dev

```bash
# Terminal 1: backend Python
cd backend
uv venv && source .venv/bin/activate  # ou python -m venv
uv pip install -e .
python main.py  # FastAPI em http://127.0.0.1:8765

# Terminal 2: app Tauri
npm install
npm run tauri dev
```

(Comandos exatos vão evoluir — atualize esta seção quando mudarem.)

## Modelo de memória (resumo)

Três tabelas no SQLite, indexadas por `sqlite-vec`:

- **episodes** — cada par (state, action, outcome) durante uma sessão.
- **skills** — sequências de ações curadas que funcionaram repetidamente.
- **knowledge** — fatos semânticos sobre o jogo (regras, atalhos, vocabulário).

Após cada sessão, o agente roda um passo de *self-reflection* e promove
episódios bons para skills, ajusta `success_rate` das skills usadas.

Detalhes em `docs/memory-model.md` (criar no M4).

## Provedores de IA

Abstração em `backend/vision/providers.py`. Interface mínima:

```python
class VLMProvider(Protocol):
    async def describe(self, image: bytes, prompt: str) -> str: ...
    async def decide(self, image: bytes, context: str) -> Action: ...
```

Implementações iniciais: `OllamaProvider`, `GeminiProvider`, `GroqProvider`,
`ClaudeProvider`, `OpenAIProvider`, `OpenRouterProvider`.

Configuração: arquivo `~/.playia/config.toml` + override via UI (Settings).

## Referência rápida

- Pesquisa técnica completa: `/Users/guilherme/PlayIA-Pesquisa.md` (fora do repo).
- Inspiração arquitetural: [Cradle Framework](https://github.com/BAAI-Agents/Cradle).
- Modelo VLM padrão: [Qwen2.5-VL no Ollama](https://ollama.com/library/qwen2.5vl).

---

*Quando alterar arquitetura, stack ou políticas, atualize este arquivo no mesmo commit.*
