# Modelo de memória do PlayIA

> Banco SQLite único por instalação, com `sqlite-vec` carregado dinamicamente
> para busca K-NN sobre embeddings. Arquivo vive em
> `platformdirs.user_data_dir("PlayIA")/playia.db` (mac:
> `~/Library/Application Support/PlayIA/`, win: `%APPDATA%/PlayIA/`).

## Por que SQLite

- Embarcado, sem servidor — instala no `.exe` sem dependência externa.
- Transacional + WAL — UI faz polling de status enquanto gravação/treino
  rodam sem bloqueio.
- Extensível: `sqlite-vec` (oficial) traz busca vetorial K-NN como virtual
  table, sem precisar embedar FAISS/Chroma (que duplicariam Python deps
  e quebrariam o build PyInstaller no Windows).
- Backup e debug triviais: o arquivo é o estado, `sqlite3` CLI lê tudo.

## Conexão

`backend/memory/connection.py` mantém **uma conexão por thread**
(`threading.local`). Razão: o FastAPI roda endpoints síncronos no
threadpool do uvicorn; SQLite proíbe que uma `Connection` migre entre
threads. Em vez de passar `check_same_thread=False` (que esconde races
sob WAL writes), cada thread chama `get_connection()` e recebe a sua;
o pool é amortizado porque o uvicorn reusa threads.

PRAGMAs aplicados ao abrir:

| Pragma                 | Valor      | Por quê                                     |
|------------------------|------------|---------------------------------------------|
| `foreign_keys`         | `ON`       | Sem isto, SQLite ignora FKs silenciosamente.|
| `journal_mode`         | `WAL`      | Writer não bloqueia reader.                 |
| `synchronous`          | `NORMAL`   | Durabilidade boa o suficiente; FULL é caro. |
| `enable_load_extension`| (temporário)| Para carregar `sqlite-vec`; desliga após.  |

Builds do Python sem `enable_load_extension` (raros, mas existem) fazem
o módulo levantar `SQLiteExtensionsUnsupportedError` com instrução pra
trocar pelo `uv python install 3.12`.

## Migrations

`backend/memory/migrations/` é um **pacote** que contém:

- `__init__.py` — funções `current_version(conn)` e `apply_pending(conn)`.
- `NNN_descricao.sql` — DDL versionado (3 dígitos zero-padded).

`schema_version (version INTEGER PRIMARY KEY, applied_at TEXT)` é
bootstrap automático. Cada arquivo `NNN_*.sql` é aplicado via
`conn.executescript()` se sua versão > `current_version`. Idempotente:
re-rodar é no-op. O FastAPI chama `apply_pending` no `lifespan` startup.

Limitação: `executescript` faz auto-commit entre statements, então
migration que falhar no meio deixa DB em estado parcial. Para v0.1
greenfield é aceitável; quando houver deploys reais com upgrade
in-place, dividimos cada migration em um único `BEGIN…COMMIT`.

## Seeds

`backend/memory/seeds/__init__.py` expõe `apply_seeds(conn)` idempotente
via `INSERT OR IGNORE`. Roda no lifespan logo após `apply_pending`. O
seed atual (`seeds/games.py`) traz 3 jogos:

- `2048` — `turn_based`/`none` (alvo M3, regressão).
- `chrome-dino` — `fast_realtime`/`none` (alvo M7 seguro).
- `99-nights-in-the-forest` — `fast_realtime`/`hyperion` (alvo de v1;
  `notes` documenta que só roda em Roblox Studio Play Solo).

Edições do usuário via `/games` não são tocadas — IDs distintos do seed.

## Tabelas

### `games`

Catálogo de jogos. ID é slug textual (kebab-case), validado no endpoint.

| Coluna             | Tipo  | Notas                                                  |
|--------------------|-------|--------------------------------------------------------|
| `id`               | TEXT  | PK; slug `^[a-z0-9][a-z0-9-]*$`.                       |
| `name`             | TEXT  | UNIQUE.                                                |
| `url`              | TEXT  | Onde abrir o jogo (`https://…` ou `chrome://…`).       |
| `tempo`            | TEXT  | CHECK `turn_based|slow_realtime|fast_realtime`.        |
| `anti_cheat`       | TEXT  | CHECK `none|unknown|hyperion|eac|battleye|vanguard|other`. |
| `allowed_keys_json`| TEXT  | JSON `list[str]` (convertido no repo).                 |
| `goal`             | TEXT  | Prompt do objetivo pro VLM.                            |
| `notes`            | TEXT? | Avisos opcionais (ex.: Hyperion = ban).                |
| `created_at`       | TEXT  | DEFAULT `datetime('now')`.                             |

### `recordings`

Sessões de watch-me-play (M5). `id` AUTOINCREMENT.

- FK `game_id → games(id)` **ON DELETE RESTRICT** — protege contra
  apagar um jogo e perder gravações sem aviso.
- Índices: `(game_id)`, `(started_at)`.

### `recording_frames`

Frames + estado de inputs por gravação (M5). PK composta
`(recording_id, ts_ms)`.

- FK `recording_id → recordings(id)` **ON DELETE CASCADE** — frames
  fazem parte do ciclo de vida da gravação.
- Colunas JSON: `keys_down_json`, `mouse_buttons_json`.
- **Frame PNG não é BLOB**: `frame_path` aponta para
  `<user_data>/PlayIA/data/recordings/<recording_id>/<ts_ms>.png`.
  Decisão: DB fica leve (~MB pra 9k frames), backup do DB fica viável,
  e o filesystem do SO já é otimizado pra streaming binário; SQLite
  como BLOB store agigantaria o DB e custaria 4× durante o backup
  WAL→main.

### `motor_models`

ONNX treinados por behavioral cloning (M6). `id` AUTOINCREMENT.

- FK `game_id → games(id)` **RESTRICT**, FK `recording_id → recordings(id)`
  **RESTRICT** — proteção dupla pra rastrear proveniência do modelo.
- `onnx_path` aponta pra
  `<user_data>/PlayIA/data/motor_models/<game_id>/<recording_id>.onnx`.

### `episodes`

Eventos de play (estado → ação → recompensa) (M8). `ON DELETE CASCADE`
em `game_id`.

### `skills`

Sequências de ações nomeadas, invocadas pelo estrategista (M8).
`UNIQUE(game_id, name)`. `embedding BLOB` guarda o vetor (384 dims,
serializado como `float[384]` little-endian — o mesmo formato que
`sqlite-vec` espera).

### `knowledge`

Fatos semânticos sobre o jogo (M8). Mesma estrutura de embedding.

### `vec_skills`, `vec_knowledge`

Virtual tables `vec0(embedding float[384])` do `sqlite-vec`. Indexam o
mesmo embedding que está no BLOB da tabela principal; busca K-NN é
feita com `WHERE embedding MATCH ? AND k=N`.

**Convenção de ligação**: o `rowid` da linha em `vec_skills` é o mesmo
`skills.id`. `sqlite-vec` não suporta FK; a manutenção é manual
(inserir/atualizar/apagar em ambas as tabelas dentro da mesma transação).
Os 384 dims vêm de `sentence-transformers/all-MiniLM-L6-v2` (default
para o módulo embeddings que entra em M8).

### `schema_version`

Bootstrap pelo migrator. Uma linha por migration aplicada.

## Esquema visual

```
games (1) ──┬─< (N) recordings ──── (N) recording_frames
            │
            ├─< (N) motor_models     (recording_id → recordings.id RESTRICT)
            │
            ├─< (N) episodes (CASCADE)
            │
            ├─< (N) skills (CASCADE) ── 1:1 ── vec_skills (rowid manual)
            │
            └─< (N) knowledge (CASCADE) ── 1:1 ── vec_knowledge (rowid manual)
```

## Operações por marco

| Marco | O que mexe                                                         |
|-------|---------------------------------------------------------------------|
| M4    | Schema completo + games CRUD + seeds. Outras tabelas ficam vazias.  |
| M5    | Recordings + recording_frames (insert batch ~30/s).                 |
| M6    | Motor models (insert + leitura para inferência).                    |
| M7    | Leitura de games + motor_models (loop hierárquico).                 |
| M8    | Skills + knowledge + busca K-NN em `vec_skills/vec_knowledge`.      |

## Decisões registradas

1. **SQLite cru (`sqlite3` stdlib) + repos explícitos**, sem ORM
   (SQLAlchemy/SQLModel). Justificativa: o schema é pequeno, queries
   são poucas e a auditabilidade do SQL gerado fica óbvia. ORM
   re-introduziria tempo de carga e ambiguidade sob WAL/threads.
2. **Migrations próprias** em vez de Alembic. Overkill pra um
   instalador desktop com tabelas estáveis; o módulo de 60 linhas
   resolve.
3. **`sqlite-vec` em vez de FAISS/Chroma**. Carga única, mesmo arquivo
   de dados, sem servidor de embeddings paralelo, sem dependência
   Python adicional pesada pra empacotar no PyInstaller.
4. **Frames como PNG em disco**, não BLOB. Ver `recording_frames` acima.
5. **`platformdirs` para todos os paths**, nada hardcoded. Garante
   convivência amigável com perfis de usuário no Windows e
   `~/Library/Application Support` no macOS.
