# Prompt da maratona — versão testável + release v0.1.0

> Cole o bloco abaixo como sua **primeira mensagem** ao Claude Code dentro deste repo.
> É uma sessão longa (estimo 10-20h efetivas de Claude Code). Ele vai trabalhar
> M4 → M5 → M6 → M7 → M10 commitando e empurrando em cada sub-tarefa, parando
> só se algo bloquear de verdade. Você pode interromper, fechar o Claude Code,
> reabrir e mandar "continue" — o estado vive no git.

> **Não cole isso antes** de:
> 1. Instalar Ollama + `ollama pull qwen2.5vl:3b` (já feito se você terminou M2).
> 2. Liberar Accessibility pro Terminal/Tauri no Mac (System Settings →
>    Privacy & Security → Accessibility).
> 3. Ter o Chrome aberto pelo menos uma vez em `chrome://dino` (vai ser
>    nosso jogo de teste do loop hierárquico, sem riscos legais).
> 4. Empurrar este RELEASE_PROMPT.md pra main (pra ele referenciá-lo).

---

```
Esta é a sessão de maratona pra fechar a v0.1.0 testável do PlayIA e
publicar o primeiro release no GitHub. Você vai trabalhar de forma
autônoma através de M4, M5, M6, M7 e M10, commitando + empurrando a
cada sub-tarefa concluída. M8 (skill curation) e M9 (BYOK) ficam pra
v0.2+ e NÃO entram nesta sessão.

Leia o CLAUDE.md inteiro antes de qualquer coisa. Ele tem o norte novo
(foco em ação via behavioral cloning + loop hierárquico), o roadmap
M1-M10, o esquema de memória, os avisos de Hyperion/Roblox, e os
padrões de código que você precisa herdar.

═══════════════════════════════════════════════════════════════════
ESCOPO DA v0.1.0 (FECHADO — não amplie sem perguntar)
═══════════════════════════════════════════════════════════════════

DENTRO:
  • M4: Memória SQLite + sqlite-vec (fundação)
  • M5: Watch-me-play recording engine (15-30 Hz)
  • M6: Behavioral cloning trainer (PyTorch → ONNX)
  • M7: Loop hierárquico (VLM estrategista + motor ONNX 30 Hz)
  • M10: Release v0.1.0 via GitHub Actions (NSIS installer + auto-update)

FORA (v0.2+):
  • M8: Skill curation
  • M9: BYOK / multi-provider (Ollama hardcoded basta pra v0.1)
  • Suporte real ao 99 Nights in the Forest jogando em servidor Roblox
    (Hyperion = ban). O profile ENTRA no DB com aviso, mas o teste
    final do loop hierárquico é com Chrome Dino (chrome://dino),
    que é seguro, fácil de gravar e não tem anti-cheat.

Critério de "testável": após o release, eu baixo o .exe no Windows,
instalo, rodo, e consigo:
  1. Jogar 2048 com a IA (turn-based, fluxo M3 — já funciona).
  2. Gravar uma sessão de Chrome Dino jogando manualmente.
  3. Treinar um motor model em cima da gravação.
  4. Assistir a IA jogando Chrome Dino sozinha em modo hierárquico.

═══════════════════════════════════════════════════════════════════
REGRAS GERAIS PARA TODA A SESSÃO
═══════════════════════════════════════════════════════════════════

1. Trabalhe MARCO POR MARCO, na ordem M4 → M5 → M6 → M7 → M10. Não
   pule, não embaralhe. Quando fechar um marco, atualize o CLAUDE.md
   (marcar [concluído]) e siga.

2. SUB-TAREFA = 1 COMMIT. Cada commit empurra direto pra main com
   Conventional Commits em pt-br. Antes do push: `cargo check`,
   `npm run build`, `uv run python -m compileall backend` precisam
   passar.

3. Se um build falhar, **conserte antes de seguir**. Não acumule
   débito técnico entre sub-tarefas. Se não conseguir consertar em
   3 tentativas, pare e me avise com o erro completo.

4. PADRÃO DE MÓDULO: `base.py` (Protocol + dataclasses) + `errors.py`
   + `factory.py` + `<impl>_impl.py`. Todo módulo backend novo segue
   isso. Veja `backend/capture/`, `vision/`, `executor/`, `planner/`
   como referência.

5. PYDANTIC para schemas de request/response. Erros tipados →
   HTTPException com mensagem prescritiva em pt-br ("Inicie com:
   ollama serve").

6. LOGGING JSON estruturado, sem `print()`. Use `logging.getLogger(
   "playia.<modulo>")`.

7. CROSS-PLATFORM por default. macOS é dev, Windows é prod. Toda
   feature Windows-only fica atrás de factory; macOS tem fallback
   funcional ou `# TODO(windows-only)` explícito.

8. PATHS sempre via `platformdirs`. Nada de string hardcoded fora
   de testes.

9. SE BLOQUEAR: pare, descreva o problema em pt-br, mostre o erro,
   sugira 2-3 caminhos, e me espere. NÃO improvise arquitetura.
   Bloqueios típicos: sqlite-vec não carrega no macOS arm64,
   PyTorch MPS quebra com certa op, ONNX Runtime não exporta um
   layer, Tauri sidecar não inicia no Windows release. Cada um
   desses é "pare e me avise".

10. ENTRE MARCOS: faça um commit final de marco
    ("docs: atualiza CLAUDE.md com M<n> concluído") e SIGA pro
    próximo marco sem pedir confirmação. Você só para se eu mandar
    "para" ou se aparecer um bloqueio real.

═══════════════════════════════════════════════════════════════════
MARCO 4 — MEMÓRIA SQLITE (FUNDAÇÃO)
═══════════════════════════════════════════════════════════════════

Objetivo: SQLite + sqlite-vec ativo, schema completo, repos pra
games (ativos) e stubs pros outros (recordings, motor_models,
episodes, skills, knowledge), migração do dict de games pro DB,
gatekeeping de tempo/anti-cheat, UI /games e rota /play filtrada.

Detalhamento exato: leia o FOURTH_PROMPT.md já existente no repo
e siga as 10 sub-tarefas dele. Cada uma vira 1 commit. Não pule
a sub-tarefa 9 (docs/memory-model.md) — é importante pra M5/M6.

Diferenças que precisam ficar ALÉM do que o FOURTH_PROMPT.md diz:

  • Adicione no seed um terceiro jogo: "chrome-dino" com
    tempo=FAST_REALTIME, anti_cheat=NONE,
    allowed_keys=[Space, ArrowDown], url="chrome://dino",
    goal_template="Sobreviva o máximo possível ao corredor
    infinito. Pule cactos (Space) e abaixe das aves
    (ArrowDown). Não morra."
  • O seed do "99-nights-in-the-forest" entra mas com
    `notes` deixando claro: "JOGO COM HYPERION. v0.1 só roda em
    Roblox Studio Play Solo. Em servidor real = ban."
  • Quando o marco fechar, commit final + push: continue pra M5.

═══════════════════════════════════════════════════════════════════
MARCO 5 — WATCH-ME-PLAY RECORDING ENGINE
═══════════════════════════════════════════════════════════════════

Objetivo: usuário clica "Gravar", joga 5-30 min, PlayIA captura
frame + inputs simultaneamente a 15-30 Hz e salva em disco + DB.

Stack adicional pra adicionar no pyproject:
  • pynput >= 1.7   (cross-platform global keyboard/mouse listener)
  • numpy >= 1.26   (manipulação de arrays de frame)
  • imageio[ffmpeg] >= 2.34   (preview MP4 da gravação, opcional)

Sub-tarefas (1 commit cada):

5.1 Módulo `backend/recording/`.
    • base.py: Protocol `Recorder` (start, stop, status), dataclass
      `RecordingStatus` (running, recording_id, fps_real,
      frames_captured, started_at).
    • pynput_impl.py: implementação que usa pynput.keyboard.Listener
      e pynput.mouse.Listener pra manter um snapshot do estado atual
      (keys_down: set[str], mouse_x/y, mouse_buttons: set[str]).
      Uma thread separada (ou asyncio task) faz o loop de captura:
        cada ~33-66ms (configurável):
          png = capture.grab(region)
          state = listener.snapshot()
          path = recordings_dir / rec_id / f"{ts_ms}.png"
          escreve png em disco
          insere row em recording_frames
      Use `mss` no Mac (já existe). No Windows fica `dxcam` quando
      a release rodar (factory já lida).
    • factory.py: get_recorder() retorna PynputRecorder().
    • errors.py: RecorderPermissionError (mac sem Input Monitoring),
      RecorderBusyError.
    Commit: "feat: módulo recording com pynput + capture sync".

5.2 Tabelas ativas + repos.
    • Implementar `recordings_repo` (create, get, list, end,
      list_by_game) e `recording_frames_repo` (insert_many em
      batch — performance importa, ~30 inserts/s).
    • Migrations: confirmar que `001_initial.sql` já criou as
      tabelas no M4. Se não, criar `002_recording_indices.sql`
      com índices em recording_id + ts_ms.
    Commit: "feat: repos de recordings e recording_frames".

5.3 Endpoints.
    • POST /recording/start  body: {game_id, fps, region}.
      Inicia o recorder. 409 se já gravando.
    • POST /recording/stop  retorna RecordingStatus final.
    • GET /recording/status  snapshot atual.
    • GET /recordings  lista todas (filter ?game_id=).
    • GET /recordings/{id}  detalhe + path do diretório de frames.
    • DELETE /recordings/{id}  apaga DB rows + dir de frames (com
      confirmação no body: {"confirm": true}).
    Commit: "feat: endpoints /recording e /recordings".

5.4 UI: rota /record.
    • Dropdown de jogos.
    • Botão verde gigante "GRAVAR" / botão vermelho "PARAR".
    • Display ao vivo: FPS real, frames capturados, tempo decorrido,
      tamanho em disco.
    • Painel lateral: lista de gravações existentes (botão "Apagar"
      com confirmação).
    • Aviso fixo no topo se o jogo escolhido tiver anti_cheat != none.
    Commit: "feat: rota /record com gravação live".

5.5 Permissões macOS adicionais.
    • pynput global listener precisa de "Input Monitoring" no Mac
      (separado do Accessibility do pyautogui). Detectar falha e
      levantar RecorderPermissionError com mensagem prescritiva
      apontando System Settings → Privacy & Security →
      Input Monitoring.
    • README ganha seção atualizada com AMBAS as permissões.
    Commit: "docs: permissão de Input Monitoring no macOS".

5.6 CLAUDE.md atualiza, marca M5 concluído.
    Commit: "docs: atualiza CLAUDE.md com M5 concluído".

═══════════════════════════════════════════════════════════════════
MARCO 6 — BEHAVIORAL CLONING TRAINER
═══════════════════════════════════════════════════════════════════

Objetivo: pegar uma gravação de M5 e treinar um motor model
pequeno (CNN) que recebe frame e devolve ações. Output: ONNX file
salvo em data/motor_models/<game_id>/<recording_id>.onnx.

Stack adicional:
  • torch >= 2.4   (com suporte a MPS no Mac)
  • torchvision >= 0.19
  • onnx >= 1.16
  • onnxruntime >= 1.18   (cross-platform CPU)

Sub-tarefas:

6.1 Módulo `backend/training/`.
    • base.py: dataclass `TrainConfig` (epochs, batch_size, lr,
      img_size=128, device="mps"|"cuda"|"cpu" detectado),
      dataclass `TrainResult` (motor_model_id, accuracy_keys,
      mse_mouse, training_time_s, onnx_path, loss_curve).
    • dataset.py: PyTorch Dataset que lê recording_frames do DB,
      abre o PNG, redimensiona pra 128x128, converte pra tensor,
      e devolve (frame_tensor, action_tensor).
      action_tensor = concat([one_hot_keys, mouse_dx, mouse_dy,
                              click_left, click_right]).
      allowed_keys vêm do GameProfile.
    • model.py: `PolicyNet` PyTorch — 3 conv (32, 64, 64) + 2 FC
      (256, action_dim). ReLU. Dropout 0.2. Pequeno: ~500k params.
    • trainer.py: função `train(recording_id) -> TrainResult` que
      carrega dataset, treina por N épocas (default 20), valida em
      um split 80/20, calcula accuracy/mse, exporta ONNX, registra
      em motor_models_repo.
    • onnx_export.py: helpers pra `torch.onnx.export` com opset 17,
      input_shape (1, 3, 128, 128).
    Commit: "feat: módulo training com PyTorch + ONNX export".

6.2 Endpoints + UI /train.
    • POST /training/start  body: {recording_id, config?}. Roda
      em asyncio.Task em background. 409 se já tem treino rodando.
    • GET /training/status  snapshot: progress_epochs, loss atual,
      accuracy_atual, eta_s.
    • POST /training/cancel.
    • UI /train: dropdown de recordings (filtrado por jogo), botão
      "Treinar", gráfico de loss ao vivo (use Chart.js via CDN ou
      um SVG simples), botão de cancelar. Quando termina, mostra
      accuracy final + link pro motor_model criado.
    Commit: "feat: endpoints + UI /train com progress live".

6.3 Repositório motor_models.
    • Implementar motor_models_repo com create, get, list_by_game,
      get_latest_for_game, delete.
    • Endpoint GET /motor-models e DELETE /motor-models/{id}.
    Commit: "feat: repo e endpoints de motor_models".

6.4 Inferência ONNX (preparação pro M7).
    • Módulo `backend/motor/`:
      base.py: Protocol `Motor` (load_for_game(game_id),
              predict(frame_png) -> Action).
      onnx_impl.py: carrega ONNX file via onnxruntime, faz
                   pré-processamento (resize, normalize), inferência,
                   pós-processamento (one_hot → keys, threshold em
                   clicks).
      factory.py: get_motor(game_id).
      errors.py: MotorNotFoundError (game não tem modelo treinado),
                 MotorInferenceError.
    • Endpoint GET /motor/test/{game_id}: captura 1 frame e roda
      inferência, devolve a Action prevista (sem executar). Útil
      pra debug.
    Commit: "feat: módulo motor com inferência ONNX".

6.5 CLAUDE.md atualiza, marca M6 concluído.
    Commit: "docs: atualiza CLAUDE.md com M6 concluído".

NOTAS DE M6:
  • Treinar 20 épocas num dataset de 5min @ 30Hz (~9k frames) num
    Mac M1/M2/M3 com MPS leva 3-10min. Aceitável.
  • O ONNX final fica ~5-20MB.
  • Se MPS quebrar com alguma op (acontece com PyTorch ainda),
    fallback automático pra CPU + warning. Documente.

═══════════════════════════════════════════════════════════════════
MARCO 7 — LOOP HIERÁRQUICO (VLM + MOTOR)
═══════════════════════════════════════════════════════════════════

Objetivo: dois loops em threads/tasks separados:
  • Estrategista (VLM): a cada 3-10s decide INTENÇÃO em pt-br.
  • Motor (ONNX): a cada 33-66ms decide a ação atômica,
    condicionado pela intenção corrente.

Game alvo de teste do M7: Chrome Dino (chrome://dino).
  • Anti_cheat = none. Tempo = fast_realtime. Mecânica simples
    (2 teclas). Perfeito pra validar o loop sem riscos.
  • Você grava 5min jogando manualmente (via /record), treina
    (via /train), e roda o loop hierárquico (via /play
    "hierárquico" — nova subrota).

Sub-tarefas:

7.1 Módulo `backend/strategist/`.
    • base.py: dataclass `Intention` (text, params: dict,
      issued_at, ttl_s=10). Dataclass `HierarchicalState` (status,
      game, current_intention, intentions_history (cap 50),
      actions_per_second, last_frame_b64, started_at,
      stop_reason, error).
    • engine.py: `HierarchicalEngine` com duas asyncio.Task:
        loop_strategist():
          while not stop:
            png = capture.grab(region)
            intention = await vlm_strategist.decide(png, goal,
                                                    intentions_history)
            state.current_intention = intention
            await sleep(intention.ttl_s)  # próximo refresh
        loop_motor():
          while not stop:
            png = capture.grab(region)
            action = motor.predict(png, current_intention)
            executor.dispatch(action)
            await sleep(1/target_fps)  # default 30 Hz
      Stop via asyncio.Event. Limites hard: max_duration_s,
      failsafe pyautogui.
    • errors.py: StrategistError, MotorNotTrainedError.
    Commit: "feat: módulo strategist com loop hierárquico".

7.2 Strategist VLM provider.
    • Reusa `vision/ollama_impl.py`. Função nova
      `vlm_strategist.decide(png, goal, history) -> Intention`
      que monta um prompt diferente do /describe e do planner:
        "Você é o estrategista. Veja a tela. Defina UMA intenção
         de alto nível em pt-br pra o motor seguir nos próximos
         5-10s. Não escolha teclas. Escolha objetivos."
        + few-shots: "evitar obstáculo à frente", "coletar item
         à esquerda", "esperar parado".
      Output: JSON {text, ttl_s}.
    • Pode ficar em `backend/strategist/vlm_strategist.py`.
    Commit: "feat: strategist VLM que define intenções".

7.3 Motor condicionado por intenção.
    • Estender `motor/onnx_impl.py` pra aceitar intention como
      input adicional (text → embedding leve, ou one-hot de
      um vocabulário fechado de intenções por jogo).
    • Para v0.1, simplifique: a intention é só registrada no log,
      o motor não a usa diretamente como input (o frame contém
      contexto suficiente em jogos simples como Dino). Documente
      isso como limitação conhecida do v0.1.
    Commit: "feat: motor registra intention sem usar como input (v0.1)".

7.4 Endpoints + UI /play hierárquico.
    • POST /hsession/start  body: {game_id, region,
      max_duration_s, acknowledge_ban_risk?}. 412 se game não
      tem motor_model treinado. 403 se anti_cheat != none sem
      acknowledge_ban_risk.
    • POST /hsession/stop.
    • GET /hsession/status.
    • UI /play ganha duas tabs: "Turn-based (M3)" e
      "Hierárquico (M7)". A tab hierárquico mostra:
        - dropdown filtrado por jogos fast_realtime com motor
          treinado;
        - intenção atual (texto grande);
        - frame ao vivo;
        - actions/s do motor;
        - histórico de intenções (últimas 5);
        - botão PARAR enorme.
    Commit: "feat: endpoints + UI /play hierárquico".

7.5 Health-check do motor + descoberta automática.
    • Endpoint GET /motor/health/{game_id}: retorna se há motor
      treinado, latência média de inferência, tamanho ONNX.
    • UI /play hierárquico chama isso antes de habilitar Iniciar.
    Commit: "feat: health-check de motor por jogo".

7.6 CLAUDE.md atualiza, marca M7 concluído. Inclui diagrama
    atualizado e descreve o loop com os parâmetros usados.
    Commit: "docs: atualiza CLAUDE.md com M7 concluído".

NOTAS DE M7:
  • Antes de testar Chrome Dino, abra-o em uma janela do Chrome
    e use o campo "region" pra recortar só a parte do jogo.
  • Latência VLM no Mac com qwen2.5vl:3b: 5-15s. Tudo bem — só
    define intenção, não decide cada tecla.
  • Latência motor ONNX em CPU: 5-20ms. Roda fácil a 30 Hz.
  • Se o motor model for muito ruim (acuracy <60%), o app
    funciona MAS joga mal. Documente isso como "depende da
    qualidade do dataset".

═══════════════════════════════════════════════════════════════════
PAUSA OBRIGATÓRIA — TESTES MANUAIS ANTES DO M10
═══════════════════════════════════════════════════════════════════

Quando M7 fechar, ANTES de seguir pro release: faça commit
"chore: bloqueia para teste manual antes da v0.1.0" e PARE.

Espere eu testar manualmente:
  1. 2048 jogando em turn-based — deve continuar funcionando.
  2. Gravar 5min de Chrome Dino.
  3. Treinar motor model.
  4. Rodar /play hierárquico e ver a IA jogando Chrome Dino.

Eu te dou OK ou bugs. Quando der OK, siga pro M10. Se der bugs,
você conserta dentro dessa mesma sessão (commits "fix:") e me
chama de novo.

═══════════════════════════════════════════════════════════════════
MARCO 10 — RELEASE v0.1.0
═══════════════════════════════════════════════════════════════════

Objetivo: tag `v0.1.0` no repo → GitHub Actions builda no
windows-latest → NSIS installer + auto-updater funcionando →
publicado no GitHub Releases.

Sub-tarefas:

10.1 PyInstaller do sidecar Python.
    • Criar `backend/build.spec` (ou usar flags inline) que
      empacota main.py + todas as deps em um único exe.
      Use --onefile, --windowed, --name playia-backend.
      Inclua sqlite-vec extension binary como data file.
    • Testar localmente no Mac que o exe gera (não precisa rodar —
      só validar que o comando funciona). No release real, o CI
      roda no Windows e gera o .exe certo.
    • Script `scripts/build-sidecar.sh` (mac) e
      `scripts/build-sidecar.ps1` (win).
    Commit: "build: configuração PyInstaller do sidecar".

10.2 Tauri sidecar config.
    • `src-tauri/tauri.conf.json` ganha:
        bundle.externalBin: ["binaries/playia-backend"]
      (Tauri busca `playia-backend-<target_triple>.exe`).
    • `src-tauri/src/lib.rs` muda o spawn pra usar
      tauri-plugin-shell + `app.shell().sidecar("playia-backend")`
      em produção, e mantém `uv run python` em dev (detecte via
      `cfg!(debug_assertions)` ou env var).
    • Adicionar dependência `tauri-plugin-shell` no Cargo.toml +
      registrar em `tauri::Builder`.
    Commit: "feat: tauri usa sidecar bundled em produção".

10.3 Auto-update.
    • Adicionar `tauri-plugin-updater` em Cargo.toml.
    • Gerar chave de signing local: `cargo tauri signer generate`.
      Salvar a private key em `~/.tauri/playia.key` (NÃO commit).
      Public key vai no tauri.conf.json.
    • Configurar `tauri.conf.json.plugins.updater`:
        endpoints: ["https://github.com/guilhermeRrodrigues/playia/releases/latest/download/latest.json"]
        pubkey: "<a chave pública gerada>"
    • Inicializar plugin no `lib.rs` + checagem no startup
      (`app.updater().check().await` opcional).
    • README explica que a private key precisa estar no GitHub
      Secrets como TAURI_SIGNING_PRIVATE_KEY +
      TAURI_SIGNING_PRIVATE_KEY_PASSWORD pro CI assinar.
    Commit: "feat: auto-update via tauri-plugin-updater".

10.4 GitHub Actions workflow.
    • Criar `.github/workflows/release.yml`:

        name: Release
        on:
          push:
            tags: ['v*']

        jobs:
          build:
            runs-on: windows-latest
            steps:
              - uses: actions/checkout@v4

              - uses: actions/setup-python@v5
                with: { python-version: '3.12' }

              - name: Install uv
                run: pip install uv

              - name: Build Python sidecar
                shell: pwsh
                run: |
                  cd backend
                  uv sync
                  uv run pyinstaller build.spec
                  $triple = "x86_64-pc-windows-msvc"
                  $dest = "..\src-tauri\binaries"
                  New-Item -ItemType Directory -Force -Path $dest
                  Copy-Item dist\playia-backend.exe "$dest\playia-backend-$triple.exe"

              - uses: actions/setup-node@v4
                with: { node-version: '20' }

              - uses: dtolnay/rust-toolchain@stable

              - run: npm ci

              - uses: tauri-apps/tauri-action@v0
                env:
                  GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
                  TAURI_SIGNING_PRIVATE_KEY: ${{ secrets.TAURI_SIGNING_PRIVATE_KEY }}
                  TAURI_SIGNING_PRIVATE_KEY_PASSWORD: ${{ secrets.TAURI_SIGNING_PRIVATE_KEY_PASSWORD }}
                with:
                  tagName: ${{ github.ref_name }}
                  releaseName: 'PlayIA ${{ github.ref_name }}'
                  releaseBody: |
                    PlayIA v0.1.0 — primeira release testável.

                    Recursos:
                    - Modo turn-based (2048 funciona out of the box).
                    - Watch-me-play recording.
                    - Treino de motor model (behavioral cloning).
                    - Modo hierárquico (VLM + motor) — testado com Chrome Dino.

                    Pré-requisitos:
                    - Windows 10+ x64.
                    - Ollama instalado e modelo qwen2.5vl:3b baixado
                      (ollama pull qwen2.5vl:3b).
                    - Aviso: anti-cheats detectam o app. Use single-player.

                  releaseDraft: false
                  prerelease: true
                  includeUpdaterJson: true

    Commit: "ci: workflow de release com tauri-action".

10.5 Documentação de release no README.
    • Seção "Releases" explicando:
        - Como o usuário baixa e instala (link pro Releases).
        - Pré-requisito Ollama + modelo (com comandos).
        - Permissões Windows (firewall, antivírus pode flaggar
          PyInstaller-built exe — orientar).
        - Limitações conhecidas da v0.1 (sem skill curation, sem
          BYOK, motor model precisa ser treinado por jogo, etc.).
    • Seção "Aviso anti-cheat" reforçada.
    Commit: "docs: README com instruções de release".

10.6 Bumpar versão.
    • `src-tauri/Cargo.toml`: version = "0.1.0"
    • `src-tauri/tauri.conf.json`: version = "0.1.0"
    • `backend/pyproject.toml`: version = "0.1.0"
    • `package.json`: version = "0.1.0"
    Commit: "chore: bumpa versão para 0.1.0".

10.7 PARE aqui e me chame.
    Eu vou gerar a tag manualmente com:
      git tag -a v0.1.0 -m "PlayIA v0.1.0 — primeira release testável"
      git push origin v0.1.0
    (isso dispara o CI e cria a release no GitHub).
    Antes disso, confirme comigo que:
      ✓ Todos os builds locais passam.
      ✓ A signing key foi gerada e adicionada ao GitHub Secrets
        (essa parte EU faço — você só me passa o passo-a-passo).
      ✓ O workflow .github/workflows/release.yml está válido (lint
        com act ou similar se conseguir, ou só revisão visual).

    Commit final: "docs: prepara documentação para v0.1.0".

═══════════════════════════════════════════════════════════════════
CHECKLIST FINAL ANTES DA TAG
═══════════════════════════════════════════════════════════════════

Verifique antes de me passar o OK para tagar:

  [ ] cargo check passa
  [ ] npm run build passa
  [ ] uv run python -m compileall backend passa
  [ ] uv run pytest passa (se houver testes; criar smoke tests
      mínimos pra cada módulo é ideal — mas opcional pra v0.1)
  [ ] App abre no Mac sem erro
  [ ] 2048 turn-based funciona (regressão)
  [ ] /record grava Chrome Dino sem erro
  [ ] /train treina ONNX sem erro
  [ ] /play hierárquico controla Chrome Dino (mesmo que mal)
  [ ] /games mostra 99-nights com aviso vermelho de Hyperion
  [ ] CLAUDE.md tem M4-M7 e M10 marcados [concluído]
  [ ] README atualizado com instruções e avisos
  [ ] .gitignore cobre data/, *.onnx, *.spec, build/, dist/,
      ~/.tauri/, .venv/
  [ ] Nenhum segredo commitado

═══════════════════════════════════════════════════════════════════
PERGUNTAS QUE VOCÊ DEVE FAZER ANTES (NÃO DEPOIS)
═══════════════════════════════════════════════════════════════════

Antes de começar o M4, confirme comigo:

  1. Você tem o `qwen2.5vl:3b` rodando localmente? (necessário pra
     testar /describe entre marcos)
  2. Você concorda em pular M8 e M9 nesta release?
  3. Você tem o Chrome instalado e abriu chrome://dino pelo menos
     uma vez?

Se a resposta for SIM pra os 3, começa. Se algum for NÃO, pare e
me explique.

═══════════════════════════════════════════════════════════════════
COMECE AGORA
═══════════════════════════════════════════════════════════════════

Confirme com uma mensagem curta ("OK, começando pelo M4 sub-tarefa
1") e siga. Sem narração extra entre commits — eu vou acompanhar
pelo git log. Só me fale quando: (a) pausa obrigatória após M7,
(b) PARE final após M10.6, ou (c) bloqueio real.

Boa maratona.
```

---

## Lembretes para o usuário (não cole)

- Esta sessão é longa. Se o Claude Code travar ou você quiser pausar,
  feche e reabra. Mande "continue do último commit" — o git carrega o
  estado.
- A signing key do Tauri (`TAURI_SIGNING_PRIVATE_KEY`) você gera UMA
  VEZ com `cargo tauri signer generate` localmente, e adiciona no
  GitHub Secrets do repo (`Settings → Secrets and variables → Actions`).
  **A private key não vai pro git.** Sem isso o auto-update não funciona,
  mas o release ainda sai.
- Quando ele te chamar pra teste manual após M7, separe 1h:
  abrir chrome://dino, gravar 5min, treinar (3-10min), e rodar
  hierárquico testando.
- Quando ele finalizar M10.6 e te der OK, você roda:
  ```bash
  cd ~/dev/playia
  git tag -a v0.1.0 -m "PlayIA v0.1.0 — primeira release testável"
  git push origin v0.1.0
  ```
  Isso dispara o workflow e em ~15-30min você tem o `.exe` pronto pra
  baixar no Releases.
