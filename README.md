# PlayIA

Desktop app (Windows) que **assiste uma IA jogando** qualquer jogo e
**aprende** ao longo do tempo. Dois modos: Play (a IA joga) e Watch me
play (a IA observa o usuário e memoriza estratégias).

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
- **Marco 2** (atual): A IA enxerga a tela. VLM local (Ollama +
  `qwen2.5vl:3b`) descreve em português o que está acontecendo na
  tela capturada. Continua stateless.
- Próximos marcos (M3–M8): loop fechado num jogo simples, memória
  episódica em SQLite-vec, skill curation, modo watch-me-play,
  Settings + BYOK multi-provider, release v1.0 via GitHub Actions
  com auto-update. Detalhes em `CLAUDE.md`.

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

O macOS exige duas permissões manuais antes do app funcionar plenamente.
Conceda para o **processo pai** do sidecar Python — em dev é tipicamente o
seu terminal (Terminal.app, iTerm, VS Code, Warp); no app empacotado é o
binário Tauri (`PlayIA.app`). Se trocar de terminal, a permissão precisa ser
reconcedida.

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

Dica: depois de conceder, **encerre completamente** o terminal e abra de
novo. O macOS só relê a lista de Accessibility no startup do processo.

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
│   └── routes/
├── src-tauri/           # Shell Rust + spawn do sidecar
│   └── src/lib.rs
├── backend/             # Sidecar Python (FastAPI + uv)
│   ├── main.py
│   └── capture/         # Protocol + mss/dxcam implementations
├── CLAUDE.md            # Contexto e regras para o Claude Code
└── README.md
```

## Endpoints do sidecar (M1)

| Método | Path | Descrição |
|---|---|---|
| GET | `/health` | `{"ok": true}` |
| POST | `/capture` | Devolve PNG do monitor primário |

## Verificar M1 manualmente

```sh
# Terminal 1: subir só o backend (sem Tauri)
cd backend && uv run python main.py

# Terminal 2: testar
curl http://127.0.0.1:8765/health
# {"ok":true}

curl -X POST http://127.0.0.1:8765/capture --output /tmp/t.png
file /tmp/t.png
# /tmp/t.png: PNG image data, ...
```

Ou: rodar `npm run tauri dev` na raiz e clicar em **"Capturar tela"**.

## Licença

A definir.
