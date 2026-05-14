-- M4.2 — schema inicial completo.
--
-- Cobre TODAS as tabelas do roadmap (M4 → M8), mesmo as que só serão
-- usadas em M5+. Isso garante que marcos seguintes não precisem mexer em
-- migrations só por dependência cruzada.
--
-- Convenções:
-- - chaves naturais textuais em ``games.id`` (slug), numéricas em
--   ``recordings``/``motor_models``/``episodes``/``skills``/``knowledge``;
-- - tabelas que precisam sobreviver à remoção do jogo (recordings,
--   motor_models) usam ON DELETE RESTRICT — protege o usuário de apagar
--   um jogo e perder gravações sem aviso;
-- - tabelas derivadas (recording_frames, episodes, skills, knowledge)
--   usam ON DELETE CASCADE — fazem parte do ciclo de vida do jogo;
-- - JSON é guardado em colunas TEXT com sufixo ``_json``; consumidores
--   serializam/deserializam (mais leve do que pickle, depura com sqlite3 CLI);
-- - embeddings ficam como BLOB nas tabelas regulares E como linhas em
--   ``vec_*`` virtual tables (sqlite-vec) — a primeira é a verdade
--   persistente, a segunda é o índice K-NN para M8.

CREATE TABLE games (
    id              TEXT PRIMARY KEY,
    name            TEXT NOT NULL UNIQUE,
    url             TEXT NOT NULL,
    tempo           TEXT NOT NULL
                    CHECK(tempo IN ('turn_based','slow_realtime','fast_realtime')),
    anti_cheat      TEXT NOT NULL
                    CHECK(anti_cheat IN ('none','unknown','hyperion','eac',
                                         'battleye','vanguard','other')),
    allowed_keys_json TEXT NOT NULL DEFAULT '[]',
    goal            TEXT NOT NULL,
    notes           TEXT,
    created_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE recordings (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    game_id     TEXT NOT NULL REFERENCES games(id) ON DELETE RESTRICT,
    started_at  TEXT NOT NULL DEFAULT (datetime('now')),
    ended_at    TEXT,
    fps         INTEGER NOT NULL,
    frame_count INTEGER NOT NULL DEFAULT 0,
    notes       TEXT
);

CREATE INDEX idx_recordings_game_id    ON recordings(game_id);
CREATE INDEX idx_recordings_started_at ON recordings(started_at);

CREATE TABLE recording_frames (
    recording_id        INTEGER NOT NULL
                        REFERENCES recordings(id) ON DELETE CASCADE,
    ts_ms               INTEGER NOT NULL,
    frame_path          TEXT NOT NULL,
    keys_down_json      TEXT NOT NULL DEFAULT '[]',
    mouse_x             INTEGER,
    mouse_y             INTEGER,
    mouse_buttons_json  TEXT NOT NULL DEFAULT '[]',
    PRIMARY KEY (recording_id, ts_ms)
);

CREATE INDEX idx_recording_frames_rec_ts
    ON recording_frames(recording_id, ts_ms);

CREATE TABLE motor_models (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    game_id       TEXT NOT NULL REFERENCES games(id) ON DELETE RESTRICT,
    recording_id  INTEGER NOT NULL REFERENCES recordings(id) ON DELETE RESTRICT,
    onnx_path     TEXT NOT NULL,
    accuracy      REAL NOT NULL,
    trained_at    TEXT NOT NULL DEFAULT (datetime('now')),
    version       INTEGER NOT NULL DEFAULT 1
);

CREATE INDEX idx_motor_models_game_id    ON motor_models(game_id);
CREATE INDEX idx_motor_models_trained_at ON motor_models(trained_at);

CREATE TABLE episodes (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    game_id         TEXT NOT NULL REFERENCES games(id) ON DELETE CASCADE,
    ts              TEXT NOT NULL DEFAULT (datetime('now')),
    state_text      TEXT NOT NULL,
    action_json     TEXT NOT NULL,
    reward          REAL,
    screenshot_path TEXT
);

CREATE INDEX idx_episodes_game_id_ts ON episodes(game_id, ts);

CREATE TABLE skills (
    id                   INTEGER PRIMARY KEY AUTOINCREMENT,
    game_id              TEXT NOT NULL REFERENCES games(id) ON DELETE CASCADE,
    name                 TEXT NOT NULL,
    description          TEXT NOT NULL,
    action_sequence_json TEXT NOT NULL,
    success_rate         REAL NOT NULL DEFAULT 0.0,
    times_used           INTEGER NOT NULL DEFAULT 0,
    embedding            BLOB,
    created_at           TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(game_id, name)
);

CREATE INDEX idx_skills_game_id ON skills(game_id);

CREATE TABLE knowledge (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    game_id     TEXT NOT NULL REFERENCES games(id) ON DELETE CASCADE,
    fact        TEXT NOT NULL,
    source      TEXT,
    embedding   BLOB,
    created_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX idx_knowledge_game_id ON knowledge(game_id);

-- sqlite-vec virtual tables para busca K-NN (M8 — skill curation).
-- Embeddings de 384 dims (sentence-transformers/all-MiniLM-L6-v2).
-- A linha de rowid N em vec_skills corresponde a skills.id = N
-- (link manual; sqlite-vec não suporta FK).
CREATE VIRTUAL TABLE vec_skills USING vec0(
    embedding float[384]
);

CREATE VIRTUAL TABLE vec_knowledge USING vec0(
    embedding float[384]
);
