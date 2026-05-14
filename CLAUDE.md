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

## Ambiente de desenvolvimento vs alvo — LEIA ANTES DE QUALQUER COISA

- **Desenvolvimento**: macOS (arm64, Apple Silicon). É onde o código é escrito,
  os testes unitários rodam, o build do Tauri (cargo + npm) é validado.
- **Alvo de produção**: Windows. É onde o app é instalado e usado de verdade.
- **Como o usuário testa funcionalmente**: baixando a release `.exe` no GitHub
  Releases e rodando no Windows. O usuário **não roda o app nativamente no Mac**
  para testar features Windows-only (captura DirectX, controle DirectInput, etc).

Consequências práticas:

1. **Use abstrações cross-platform por padrão.** Toda funcionalidade dependente
   de SO precisa ter implementação `win32` E uma `darwin`/`linux` que pelo menos
   não quebre o app em dev.
   - Captura: `dxcam` (Windows) + `mss` (macOS/Linux) atrás de um Protocol.
   - Input: `pydirectinput` (Windows) + `pyautogui` (macOS/Linux) atrás de um Protocol.
   - Caminhos do usuário: use `platformdirs`, nunca string hardcoded.
2. **Não trave o desenvolvimento esperando Windows.** Faça stub/fallback que rode
   no Mac, e marque com `# TODO(windows-only)` ou um teste skipado o que precisar
   de validação real lá.
3. **CI roda em `windows-latest`** (via `tauri-action`) — é a fonte da verdade
   para "isso funciona em produção". O Mac é fonte de verdade para "isso compila
   e a arquitetura está sã".
4. **Antes de cortar release**, rode pelo menos `cargo check --target x86_64-pc-windows-msvc`
   localmente (precisa do toolchain Windows no rustup) ou confie no CI.
5. **Quando uma feature for fundamentalmente Windows-only** (ex: hook em DirectX
   overlay), documente isso explicitamente no código e no README, e implemente
   o fallback no Mac como "modo demo" — capturar via mss e logar um aviso.
6. **Releases**: tag `vX.Y.Z` no Mac → GitHub Actions builda no `windows-latest`
   → instalador NSIS aparece no Releases → usuário baixa e instala no Windows.

Se algo só puder ser validado em Windows e bloquear o avanço, **pare e avise** —
nunca improvise um "funciona no Mac, deve funcionar no Windows" sem evidência.

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
