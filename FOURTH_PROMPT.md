# Prompt da quarta sessão — M4 (cole no Claude Code)

> Cole o bloco abaixo como sua **primeira mensagem** ao Claude Code dentro deste repo.
> M1, M2, M3 estão fechados na main. O CLAUDE.md foi reescrito com um
> norte novo (foco em jogos de ação, especificamente 99 Nights in the
> Forest, via behavioral cloning + loop hierárquico).

---

```
Mudou o norte. O CLAUDE.md foi reescrito — leia inteiro antes de
começar, especialmente as seções "Visão", "Segurança e ética (RISCO
REAL DE BAN)", "Arquitetura de dois andares" e "Marcos (roadmap)".

Resumo da pivotagem: M3 (VLM-no-loop com 2048) ficou pronto e prova o
pipeline básico, mas não escala pra ação. O alvo da v1 agora é
**99 Nights in the Forest** (Roblox), via:

  1. Watch-me-play grava (frame, inputs) — M5
  2. Behavioral cloning treina motor model por jogo — M6
  3. Loop hierárquico: VLM estrategista lento + motor model rápido — M7

Pra tudo isso, precisamos da **base de memória persistente** antes.
M4 = fundação. Sem skips.

Objetivo desta sessão: entregar o **Marco 4 (M4)** completo.

M4 = "Memória persistente como fundação":
- SQLite + sqlite-vec inicializado no startup do sidecar.
- Schema completo com migrations versionadas: games, recordings,
  recording_frames, motor_models, episodes, skills, knowledge.
- Repositórios (pattern Repository) pra cada tabela ativa em M4.
- Migra o dict `session/games.py` → tabela `games` no DB.
- Game profile ganha colunas `tempo` e `anti_cheat`, validadas.
- Session engine refeito pra LER do DB em vez do dict, e RECUSAR
  combinações perigosas (fast_realtime sem motor, anti_cheat != none
  sem bypass explícito).
- Endpoints CRUD pra `games` (UI vai consumir no /games).
- Rota nova `/games` na UI: lista, adicionar, remover, ver detalhes
  com aviso vermelho quando anti_cheat != none.
- Seed inicial: 2048 (turn_based, none) + 99 Nights in the Forest
  (fast_realtime, hyperion) — o segundo já entra no DB pra a gente
  ter o profile pronto pro M7, mas com warning grande.

Padrões da casa (vêm do M1-M3, herde):
- Cada módulo do backend: base.py (Protocol + dataclasses) + errors.py
  + factory.py + <impl>_impl.py.
- Endpoints com pydantic schemas tipados, response_model declarado.
- Erros tipados → HTTPException com código específico + mensagem
  prescritiva em pt-br.
- Async para I/O externo, sync para CPU/DB local.
- Logging JSON estruturado.

Sub-tarefas sugeridas (ordem importa):

1. Setup do storage e SQLite.
   - Adicionar `platformdirs` e `sqlite-vec` ao pyproject.
   - Criar `backend/memory/paths.py` com:
       data_dir() -> Path   # platformdirs.user_data_dir("PlayIA")
       db_path() -> Path    # data_dir() / "playia.db"
       recordings_dir() -> Path
       motor_models_dir() -> Path
     Cria os diretórios se não existirem.
   - Criar `backend/memory/connection.py`:
       def get_connection() -> sqlite3.Connection
     Habilita foreign keys, WAL mode, carrega extensão sqlite-vec.
     Connection por-thread (thread-local) ou usa um pool simples —
     decida e justifique no commit.
   - **Commit + push** ("feat: storage paths e conexão SQLite com sqlite-vec").

2. Migrations.
   - `backend/memory/migrations/__init__.py` + arquivos
     `001_initial.sql`, etc.
   - Tabela `schema_version` com (version int PRIMARY KEY, applied_at
     datetime).
   - `backend/memory/migrations.py` com:
       def current_version(conn) -> int
       def apply_pending(conn) -> list[int]
   - 001_initial.sql cria TODAS as tabelas (mesmo as que só vão ser
     usadas em M5+): games, recordings, recording_frames, motor_models,
     episodes, skills, knowledge. E os índices vec_*.
   - Rodar `apply_pending` no startup do FastAPI (lifespan).
   - **Commit + push** ("feat: sistema de migrations e schema inicial").

3. Schemas pydantic + repositórios.
   - `backend/memory/models.py` com pydantic models (Game, Recording,
     RecordingFrame, MotorModel, Episode, Skill, Knowledge) — modelos
     de dados, NÃO de request/response.
   - Enums tipados:
       class Tempo(StrEnum): TURN_BASED, SLOW_REALTIME, FAST_REALTIME
       class AntiCheat(StrEnum): NONE, UNKNOWN, HYPERION, EAC,
                                 BATTLEYE, VANGUARD, OTHER
   - Repositórios em `backend/memory/repos/`:
       games_repo.py: list_all, get, create, update, delete, get_by_name
     Outros (recordings_repo, etc.) ficam como stub vazio com TODO(M5/M6)
     — só queremos a estrutura no lugar agora.
   - **Commit + push** ("feat: schemas pydantic e repos da memória").

4. Migração do dict de games para o DB.
   - Renomear `session/games.py` → mover catálogo pra
     `memory/seeds/games.py` (lista de dicts) e ter
     `memory/seeds.py: apply_seeds(conn)` que insere se a tabela
     estiver vazia.
   - Seeds incluem:
       • 2048 (tempo=TURN_BASED, anti_cheat=NONE,
         allowed_keys=ArrowUp/Down/Left/Right, url=https://play2048.co/)
       • 99-nights-in-the-forest (tempo=FAST_REALTIME,
         anti_cheat=HYPERION, allowed_keys=[W,A,S,D,Space,LShift,1,2,3,
         MouseLeft,MouseRight], url= roblox 99 nights url,
         goal_template="Sobreviva noites coletando recursos e construindo
         abrigo. Foco no objetivo atual.")
   - Atualizar `backend/session/engine.py` e `backend/main.py` para
     puxarem o profile via `games_repo` em vez do dict importado.
     Mantenha API backward-compatible (`/session/games` ainda devolve
     dict por id).
   - Apagar `session/games.py` antigo se estiver redundante.
   - **Commit + push** ("feat: catálogo de games migrado para SQLite").

5. Validação de tempo + anti-cheat no /session/start.
   - Em `session/engine.py` (ou no endpoint), antes de iniciar:
     • se `game.tempo != TURN_BASED`: HTTP 400 com mensagem clara
       "Este modo (M3 turn-based) só suporta jogos turn_based.
        Jogos slow_realtime e fast_realtime serão suportados a partir
        do M7 (loop hierárquico)."
     • se `game.anti_cheat != NONE`: HTTP 403 com mensagem
       "ATENÇÃO: Este jogo usa <anti_cheat>. Automação detectada =
        ban. Para prosseguir mesmo assim, envie acknowledge_ban_risk:
        'estou ciente do risco' no body da requisição."
     • aceitar bypass: body `{"acknowledge_ban_risk": "estou ciente
       do risco"}` libera. Logar warning. Não dê opção de salvar
       esse opt-in.
   - **Commit + push** ("feat: gatekeeping de tempo e anti-cheat no start").

6. Endpoints CRUD em `backend/main.py` para games.
   - GET /games — lista (com filtros opcionais ?tempo=&anti_cheat=).
   - GET /games/{id} — detalhe.
   - POST /games — cria (body validado contra schema).
   - PUT /games/{id} — update.
   - DELETE /games/{id} — apaga (impedir delete se houver recordings
     ou motor_models associados, 409 Conflict).
   - Manter compat: GET /session/games chama internamente o repo
     (sem duplicar lógica).
   - **Commit + push** ("feat: endpoints CRUD /games").

7. UI: rota /games.
   - Nova rota `/games` no SvelteKit (use +page.svelte).
   - Lista as games em uma tabela: nome, tempo, anti_cheat (badge
     vermelho se != none), url, ações (editar/apagar).
   - Botão "+ Novo jogo" abre um modal/form simples.
   - Selecionar um jogo na lista mostra detalhes em painel lateral
     com o aviso de anti-cheat em VERMELHO se aplicável (texto fixo
     baseado no enum).
   - Adicionar link "Jogos" no menu/home.
   - **Commit + push** ("feat: rota /games com CRUD na UI").

8. Atualizar /play (M3 existente) pra refletir o gatekeeping.
   - Dropdown de jogos lê de GET /games?tempo=turn_based — só mostra
     turn_based no M3.
   - Se selecionar um jogo com anti_cheat != none (não vai aparecer
     no filtro mas defensive), mostrar aviso e desabilitar Iniciar.
   - **Commit + push** ("refactor: /play filtra games por tempo turn_based").

9. docs/memory-model.md.
   - Documento curto descrevendo cada tabela, FKs, índices vec,
     decisões (PNG em disco vs blob no DB, sqlite-vec em vez de
     extensão externa).
   - **Commit + push** ("docs: memory-model.md").

10. Atualizar CLAUDE.md.
   - Marcar M4 concluído.
   - Documentar a estrutura `backend/memory/` no lugar correto.
   - Atualizar a seção "Modelo de memória" com o estado real
     (tabelas implementadas vs stub).
   - **Commit + push** ("docs: atualiza CLAUDE.md com M4 concluído").

Regras importantes para esta sessão:

- **NÃO toque em PyTorch, ONNX, recording engine, training loop**. Tudo
  isso é M5+. M4 é só fundação de dados.
- **Tabelas que ainda não vão ser usadas (recordings, motor_models,
  etc.) precisam estar no schema mesmo assim**, com stubs de repos
  com TODO(MX) — isso garante que o M5/M6 não vai precisar mexer em
  migrations de novo.
- **sqlite-vec é extensão**. Carregue dinamicamente (`conn.enable_load_extension(True)`
  + `conn.load_extension("vec0")`). Empacotamento pro release Windows
  cuidamos no M10.
- **platformdirs sempre**. Nenhum path hardcoded fora dos testes.
- **Migrações idempotentes**. Rodar `apply_pending` num DB já atualizado
  deve ser no-op.
- **Não persista de fato as gravações nem motor models neste marco** —
  só o schema e os caminhos prontos.
- **Commits pequenos**, um por sub-tarefa, push após cada um.
- **Antes de cada push**: `cargo check`, `npm run build`, `uv run python
  -m compileall backend`. Se mexer no DB, rode o sidecar localmente
  uma vez e confirme que ele inicializa sem erro e cria as tabelas.

Comece pela sub-tarefa 1. Pergunte antes de:
  - introduzir ORM (SQLAlchemy etc) — eu prefiro sqlite3 cru + repos
    explícitos, mas se você achar que vale, traga argumento concreto.
  - mudar a estratégia de migrations (ex: alembic) — overkill pra v1.
  - alterar o schema proposto de forma incompatível.

Coisas pequenas decide você.

Se algo bloquear (ex: sqlite-vec não carrega no macOS arm64), pare e
me avise. Não improvise um vector store alternativo (FAISS, Chroma,
etc.) sem alinhar.
```

---

## Lembretes para o usuário (não cole isso)

- Quando o M4 fechar, o app tem todas as tabelas no SQLite e os jogos
  vivem no DB em vez de hardcoded. O `/play` continua funcionando com
  2048 turn-based, mas agora você pode adicionar mais jogos pelo
  `/games` sem mexer em código.
- 99 Nights já vai estar no DB depois deste marco, com aviso de
  Hyperion. Tentar dar Start vai dar 403 educado — esperado, até o
  M7 não tem como jogar ele de qualquer jeito.
- M5 (próximo) é onde o "watch me play" entra. Aí começa o trabalho
  específico pro Roblox de verdade.
- Antes de rodar M4, considere atualizar Ollama e o modelo se fizer
  sentido — não é obrigatório pra essa sessão.
