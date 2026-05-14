# Prompt da primeira sessão (cole isso no Claude Code)

> Cole o bloco abaixo como sua **primeira mensagem** ao Claude Code dentro deste repo.
> Ele já vai ter lido `CLAUDE.md` automaticamente.

---

```
Vamos iniciar o desenvolvimento do PlayIA. Você acabou de ler o CLAUDE.md,
então já conhece a stack (Tauri 2 + SvelteKit + sidecar Python + Ollama + sqlite-vec),
a política de commits (Conventional Commits em português, push direto na main
sempre que terminar uma unidade de trabalho) e o roadmap (8 marcos).

**Contexto de ambiente (importante):** Estou desenvolvendo em macOS arm64
(Apple Silicon). O alvo de produção é Windows. Eu testo funcionalmente
baixando o `.exe` da release no GitHub — não rodo o app nativamente no Mac
para validar features Windows-only. Portanto, no Mac queremos que o app
**rode e compile**, mesmo que algumas features usem fallback (mss em vez
de dxcam, pyautogui em vez de pydirectinput). A validação final acontece
no CI (`windows-latest` via `tauri-action`) e na máquina Windows quando eu
baixar o instalador. Veja a seção "Ambiente de desenvolvimento vs alvo"
do CLAUDE.md.

Objetivo desta sessão: entregar o **Marco 1 (M1)** completo e funcionando
**no Mac**, com abstrações cross-platform já no lugar para que a versão
Windows funcione idêntica quando eu gerar a release.

M1 = "Hello world arquitetural":
- App Tauri 2 abre em janela própria.
- UI SvelteKit com 1 botão "Capturar tela" e 1 área que mostra a imagem capturada.
- Sidecar Python (FastAPI) roda automaticamente quando o app abre.
- Endpoint `POST /capture` no sidecar retorna um screenshot PNG via dxcam.
- O botão chama o endpoint e mostra o resultado.
- Não tem IA ainda — só queremos provar que o pipeline Tauri↔Python↔dxcam
  funciona ponta a ponta.

Sub-tarefas que eu sugiro (você pode ajustar):

1. Scaffold do projeto Tauri 2 + SvelteKit + TypeScript.
   - `npm create tauri-app@latest` (Svelte, TypeScript, npm).
   - Conferir que `npm run tauri dev` abre janela vazia.
   - **Commit + push** ("chore: scaffold tauri + sveltekit").

2. Backend Python com FastAPI.
   - Pasta `backend/`, `pyproject.toml` com uv ou poetry.
   - `main.py` com FastAPI rodando em 127.0.0.1:8765.
   - Endpoint `GET /health` retornando `{"ok": true}`.
   - **Commit + push** ("feat: backend FastAPI com endpoint health").

3. Captura de tela cross-platform com Protocol/factory.
   - Estrutura: `backend/capture/base.py` define o `Protocol ScreenCapture`
     (método `grab() -> bytes` retornando PNG).
   - `backend/capture/mss_impl.py` implementa via `mss` (macOS/Linux). **Esta
     é a implementação usada no dev no meu Mac.**
   - `backend/capture/dxcam_impl.py` implementa via `dxcam` (Windows only).
     Pode ficar com um stub mínimo + `# TODO(windows-only)` se a lib não
     instalar no Mac — não tente forçar instalação cross-platform.
   - `backend/capture/factory.py` escolhe baseado em `sys.platform`.
   - Endpoint `POST /capture` consome o factory.
   - Tratamento de erro: log estruturado + 500 com mensagem clara.
   - Teste manual: rodar no Mac e ver um PNG sair.
   - **Commit + push** ("feat: captura cross-platform com factory mss/dxcam").

4. Sidecar wiring no Tauri.
   - Adicionar Python como sidecar no `tauri.conf.json` (por enquanto sem
     PyInstaller — apontar para o `python` do venv do projeto, com path
     relativo ao repo).
   - Em `src-tauri/src/main.rs`, `spawn` do sidecar no startup do app.
   - Ao fechar o app, matar o processo do sidecar (cleanup limpo).
   - Funcionar no Mac (`npm run tauri dev` abre janela + sidecar sobe + porta 8765 responde).
   - **Commit + push** ("feat: tauri spawna sidecar python no startup").

5. UI SvelteKit consumindo a API.
   - Página `/` com botão "Capturar tela".
   - `fetch('http://127.0.0.1:8765/capture', { method: 'POST' })`.
   - Exibir o PNG retornado em um `<img>`.
   - Mostrar status (loading, erro).
   - **Commit + push** ("feat: UI captura e exibe screenshot").

6. README inicial com instruções de dev.
   - Como rodar (pré-requisitos: Node 20+, Rust stable, Python 3.12, Ollama opcional).
   - Aviso sobre anti-cheat (importante).
   - Status do projeto (M1 concluído).
   - **Commit + push** ("docs: README inicial com instruções de dev").

7. `.gitignore` cobrindo: `target/`, `dist/`, `build/`, `node_modules/`,
   `.venv/`, `__pycache__/`, `*.pyc`, `playia.db`, `.env`, `*.spec`.
   - **Commit + push** ("chore: .gitignore").

Regras importantes para esta sessão:

- **Stack é a do CLAUDE.md**. Se quiser trocar algo (ex: SvelteKit por React),
  pergunte primeiro com um motivo concreto.
- **Cross-platform por default**. Dev é Mac, alvo é Windows. Toda dependência
  específica de SO entra atrás de um Protocol/factory. Veja a seção "Ambiente
  de desenvolvimento vs alvo" do CLAUDE.md.
- **Commits pequenos**, um por sub-tarefa. Push após cada commit.
- **Antes de cada push**, rode o build relevante no Mac (`cargo check`,
  `npm run build`, `python -m compileall backend`) e confirme que passa.
  Não tente rodar `cargo check --target x86_64-pc-windows-msvc` agora —
  isso fica para o CI.
- **Não inclua IA ainda**. Sem Ollama, sem VLM, sem prompt engineering.
  M1 é só o esqueleto.
- **Mensagens de commit em português** seguindo Conventional Commits.
- **Documente** decisões não-óbvias no CLAUDE.md (atualize-o no mesmo commit
  da mudança).

Comece pela sub-tarefa 1. Quando terminar, mostre o que fez, confirme que o
build passa, faça o commit + push, e vá para a 2. Pergunte antes de tomar
decisões grandes (ex: gerenciador de pacotes Python — uv vs poetry — me
consulte; em coisas menores, decida você).

Se algo bloquear, pare e me avise — não improvise alternativas silenciosamente.
Caso específico: se `dxcam` falhar na instalação no Mac (esperado, é Windows-only),
deixe a importação opcional dentro de `dxcam_impl.py` (try/except no import,
levantando `NotImplementedError` se chamado fora de Windows) e siga em frente.
Isso é esperado, não é blocker.
```

---

## Lembretes para o usuário (não cole isso)

- O Claude Code deve estar com **MCP do GitHub** ou apenas com `git` no PATH —
  ambos funcionam para push direto.
- Se for o primeiríssimo commit do repo, garanta que a branch local é `main`
  (não `master`). O GitHub cria repos novos em `main` por padrão.
- A primeira `git push -u origin main` precisa ser manual se o repo estiver
  vazio (sem upstream). Depois disso, push simples já funciona.
- Quando chegar no M8, o release dispara automaticamente via tag — basta
  `git tag v1.0.0 && git push --tags`.
