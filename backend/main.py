"""PlayIA sidecar — FastAPI app que expõe captura de tela e VLM (M2)."""

from __future__ import annotations

import json
import logging
import sqlite3
import sys
import time
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import Any

import uvicorn
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from pydantic import BaseModel, Field, field_validator

from capture.base import Region
from capture.factory import get_capture
from executor.factory import get_executor
from memory.connection import get_connection
from memory.migrations import apply_pending
from memory.models import AntiCheat, Game, MotorModel, Recording, Tempo
from memory.paths import motor_models_dir, recordings_dir
from memory.repos import games_repo, motor_models_repo, recordings_repo
from memory.seeds import apply_seeds
from planner.actions import Action
from planner.factory import get_planner
from recording.errors import RecorderBusyError, RecorderError, RecorderPermissionError
from recording.factory import get_recorder
from session.base import SessionState
from session.engine import SessionAlreadyRunningError, SessionEngine
from vision.errors import (
    VLMModelMissingError,
    VLMTimeoutError,
    VLMUnavailableError,
)
from vision.factory import get_vlm

HOST = "127.0.0.1"
PORT = 8765


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S"),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


def configure_logging() -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(logging.INFO)


configure_logging()
log = logging.getLogger("playia.backend")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    # Aplica migrations pendentes do SQLite + seeds idempotentes no startup.
    conn = get_connection()
    applied = apply_pending(conn)
    if applied:
        log.info("schema atualizado: migrations aplicadas %s", applied)
    seeded = apply_seeds(conn)
    if seeded:
        log.info("seeds inseridos: games %s", seeded)
    yield


app = FastAPI(title="PlayIA Backend", version="0.1.0", lifespan=lifespan)

# UI roda em http://localhost:1420 (Tauri dev) ou tauri://localhost (produção).
# Em M1 liberamos qualquer origem local — restringir no M7 quando tivermos Settings.
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"^(https?|tauri)://(localhost|127\.0\.0\.1)(:\d+)?$",
    allow_methods=["*"],
    allow_headers=["*"],
)

_capture = get_capture()
_vlm = get_vlm()
_planner = get_planner()
_executor = get_executor()
_engine = SessionEngine(_capture, _planner, _executor)
_recorder = get_recorder(_capture)

DEFAULT_DESCRIBE_PROMPT = (
    "Descreva em português o que está acontecendo nesta tela. "
    "Liste elementos visuais importantes (janelas, botões, texto, "
    "jogo em foco). Seja conciso."
)


class CaptureRequest(BaseModel):
    region: list[int] | None = Field(
        default=None,
        description="Recorte [x, y, largura, altura]. None = tela inteira.",
    )

    @field_validator("region")
    @classmethod
    def _validate_region(cls, v: list[int] | None) -> list[int] | None:
        if v is None:
            return None
        if len(v) != 4:
            raise ValueError("region deve ter 4 inteiros: [x, y, largura, altura]")
        x, y, w, h = v
        if w <= 0 or h <= 0:
            raise ValueError("região com largura/altura <= 0 é inválida")
        if x < 0 or y < 0:
            raise ValueError("região com x/y negativos é inválida")
        return v


class DescribeRequest(BaseModel):
    prompt: str | None = None
    region: list[int] | None = Field(
        default=None,
        description="Recorte [x, y, largura, altura] para a VLM enxergar só uma parte da tela.",
    )

    @field_validator("region")
    @classmethod
    def _validate_region(cls, v: list[int] | None) -> list[int] | None:
        if v is None:
            return None
        if len(v) != 4:
            raise ValueError("region deve ter 4 inteiros: [x, y, largura, altura]")
        x, y, w, h = v
        if w <= 0 or h <= 0:
            raise ValueError("região com largura/altura <= 0 é inválida")
        if x < 0 or y < 0:
            raise ValueError("região com x/y negativos é inválida")
        return v


def _region_tuple(req_region: list[int] | None) -> Region | None:
    if req_region is None:
        return None
    return (req_region[0], req_region[1], req_region[2], req_region[3])


class DescribeResponse(BaseModel):
    description: str
    latency_ms: int
    model: str


class VLMStatusResponse(BaseModel):
    ready: bool
    model: str
    issue: str | None


ACK_BAN_RISK_TOKEN = "estou ciente do risco"


class StartSessionRequest(BaseModel):
    game: str
    region: list[int] | None = Field(
        default=None,
        description="Recorte [x, y, largura, altura] do jogo na tela. None = tela inteira.",
    )
    max_actions: int = Field(default=200, ge=1, le=10_000)
    max_duration_s: int = Field(default=600, ge=1, le=86_400)
    step_delay_ms: int = Field(default=300, ge=0, le=60_000)
    acknowledge_ban_risk: str | None = Field(
        default=None,
        description=(
            "Frase literal 'estou ciente do risco' libera sessão em jogos com "
            "anti_cheat != none. Não é persistida — todo /session/start exige "
            "envio novo."
        ),
    )

    @field_validator("region")
    @classmethod
    def _validate_region(cls, v: list[int] | None) -> list[int] | None:
        if v is None:
            return None
        if len(v) != 4:
            raise ValueError("region deve ter 4 inteiros: [x, y, largura, altura]")
        x, y, w, h = v
        if w <= 0 or h <= 0:
            raise ValueError("região com largura/altura <= 0 é inválida")
        if x < 0 or y < 0:
            raise ValueError("região com x/y negativos é inválida")
        return v


class SessionStateResponse(BaseModel):
    """Espelho serializável de :class:`session.base.SessionState`."""

    model_config = {"from_attributes": True}

    status: str
    game: str | None = None
    region: list[int] | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    actions_taken: int = 0
    last_action: Action | None = None
    last_reason: str | None = None
    history: list[Action] = Field(default_factory=list)
    last_screenshot_b64: str | None = None
    stop_reason: str | None = None
    error: str | None = None


def _serialize_state(state: SessionState) -> SessionStateResponse:
    return SessionStateResponse(
        status=state.status,
        game=state.game,
        region=list(state.region) if state.region else None,
        started_at=state.started_at,
        finished_at=state.finished_at,
        actions_taken=state.actions_taken,
        last_action=state.last_action,
        last_reason=state.last_reason,
        history=list(state.history),
        last_screenshot_b64=state.last_screenshot_b64,
        stop_reason=state.stop_reason,
        error=state.error,
    )


@app.get("/health")
def health() -> dict[str, bool]:
    return {"ok": True}


@app.get("/vlm/status", response_model=VLMStatusResponse)
async def vlm_status() -> VLMStatusResponse:
    s = await _vlm.status()
    return VLMStatusResponse(ready=s.ready, model=s.model, issue=s.issue)


@app.post("/capture")
def capture(body: CaptureRequest | None = None) -> Response:
    region = _region_tuple(body.region) if body else None
    try:
        png = _capture.grab(region)
    except Exception as e:
        log.exception("falha ao capturar tela")
        raise HTTPException(status_code=500, detail=str(e)) from e
    return Response(content=png, media_type="image/png")


@app.post("/describe", response_model=DescribeResponse)
async def describe(body: DescribeRequest | None = None) -> DescribeResponse:
    prompt = body.prompt if body and body.prompt else DEFAULT_DESCRIBE_PROMPT
    region = _region_tuple(body.region) if body else None
    try:
        png = _capture.grab(region)
    except Exception as e:
        log.exception("falha ao capturar tela")
        raise HTTPException(status_code=500, detail=str(e)) from e

    t0 = time.monotonic()
    try:
        text = await _vlm.describe(png, prompt)
    except VLMUnavailableError as e:
        log.warning("VLM indisponível: %s", e)
        raise HTTPException(
            status_code=503,
            detail="Ollama não está rodando. Inicie com: ollama serve",
        ) from e
    except VLMModelMissingError as e:
        log.warning("VLM modelo faltando: %s", e)
        raise HTTPException(
            status_code=404,
            detail=f"Modelo {_vlm.model} não encontrado. Rode: ollama pull {_vlm.model}",
        ) from e
    except VLMTimeoutError as e:
        log.warning("VLM timeout: %s", e)
        raise HTTPException(
            status_code=504,
            detail="VLM demorou demais para responder (>60s).",
        ) from e
    except Exception as e:
        log.exception("falha inesperada no VLM")
        raise HTTPException(status_code=502, detail=str(e)) from e

    latency_ms = int((time.monotonic() - t0) * 1000)
    log.info(
        "describe ok model=%s latency_ms=%d png_bytes=%d",
        _vlm.model,
        latency_ms,
        len(png),
    )
    return DescribeResponse(
        description=text,
        latency_ms=latency_ms,
        model=_vlm.model,
    )


@app.get("/session/games", response_model=dict[str, Game])
def session_games() -> dict[str, Game]:
    """Lista games conhecidos, indexados pelo id (slug).

    Mantido como dict-por-id por compat com o frontend M3; o endpoint
    canônico para a UI de catálogo é :http:get:`/games` (lista plana).
    """
    conn = get_connection()
    return {g.id: g for g in games_repo.list_all(conn)}


# --- /games CRUD --------------------------------------------------------------


class GameInput(BaseModel):
    """Body para PUT /games/{id} (id vem do path).

    Para POST, usa :class:`GameCreate` que herda + exige o id no body.
    """

    name: str = Field(min_length=1)
    url: str = Field(min_length=1)
    tempo: Tempo
    anti_cheat: AntiCheat
    allowed_keys: list[str] = Field(default_factory=list)
    goal: str = Field(min_length=1)
    notes: str | None = None


class GameCreate(GameInput):
    id: str = Field(min_length=1, pattern=r"^[a-z0-9][a-z0-9-]*$")


@app.get("/games", response_model=list[Game])
def games_list(
    tempo: Tempo | None = Query(default=None),
    anti_cheat: AntiCheat | None = Query(default=None),
) -> list[Game]:
    conn = get_connection()
    return games_repo.list_all(conn, tempo=tempo, anti_cheat=anti_cheat)


@app.get("/games/{game_id}", response_model=Game)
def games_get(game_id: str) -> Game:
    conn = get_connection()
    g = games_repo.get(conn, game_id)
    if g is None:
        raise HTTPException(status_code=404, detail=f"jogo desconhecido: {game_id!r}")
    return g


@app.post("/games", response_model=Game, status_code=201)
def games_create(body: GameCreate) -> Game:
    conn = get_connection()
    try:
        return games_repo.create(conn, Game(**body.model_dump()))
    except sqlite3.IntegrityError as e:
        raise HTTPException(
            status_code=409,
            detail=(
                f"Conflito ao criar o jogo (id ou nome já existem): {e}. "
                f"Use PUT /games/{body.id} se quer atualizar."
            ),
        ) from e


@app.put("/games/{game_id}", response_model=Game)
def games_update(game_id: str, body: GameInput) -> Game:
    conn = get_connection()
    game = Game(id=game_id, **body.model_dump())
    try:
        return games_repo.update(conn, game)
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@app.delete("/games/{game_id}", status_code=204)
def games_delete(game_id: str) -> None:
    conn = get_connection()
    if games_repo.get(conn, game_id) is None:
        raise HTTPException(status_code=404, detail=f"jogo desconhecido: {game_id!r}")
    if games_repo.has_dependents(conn, game_id):
        raise HTTPException(
            status_code=409,
            detail=(
                f"O jogo {game_id!r} tem recordings ou motor_models associados; "
                f"apague-os primeiro pela API de gravações/treinos."
            ),
        )
    games_repo.delete(conn, game_id)


# --- /recording e /recordings (M5) -------------------------------------------


class StartRecordingRequest(BaseModel):
    game_id: str = Field(min_length=1)
    fps: int = Field(default=30, ge=1, le=60)
    region: list[int] | None = Field(
        default=None,
        description="Recorte [x, y, largura, altura] do jogo. None = tela inteira.",
    )

    @field_validator("region")
    @classmethod
    def _validate_region(cls, v: list[int] | None) -> list[int] | None:
        if v is None:
            return None
        if len(v) != 4:
            raise ValueError("region deve ter 4 inteiros: [x, y, largura, altura]")
        x, y, w, h = v
        if w <= 0 or h <= 0:
            raise ValueError("região com largura/altura <= 0 é inválida")
        if x < 0 or y < 0:
            raise ValueError("região com x/y negativos é inválida")
        return v


class RecordingStatusResponse(BaseModel):
    running: bool
    recording_id: int | None = None
    game_id: str | None = None
    fps_target: int = 0
    fps_real: float = 0.0
    frames_captured: int = 0
    started_at: datetime | None = None
    finished_at: datetime | None = None
    region: list[int] | None = None
    error: str | None = None


def _serialize_recorder_status() -> RecordingStatusResponse:
    s = _recorder.status()
    return RecordingStatusResponse(
        running=s.running,
        recording_id=s.recording_id,
        game_id=s.game_id,
        fps_target=s.fps_target,
        fps_real=s.fps_real,
        frames_captured=s.frames_captured,
        started_at=s.started_at,
        finished_at=s.finished_at,
        region=list(s.region) if s.region else None,
        error=s.error,
    )


@app.post("/recording/start", response_model=RecordingStatusResponse)
def recording_start(body: StartRecordingRequest) -> RecordingStatusResponse:
    # valida jogo no DB antes de mexer no recorder; recordings.game_id é FK.
    conn = get_connection()
    if games_repo.get(conn, body.game_id) is None:
        raise HTTPException(
            status_code=422,
            detail=f"jogo desconhecido: {body.game_id!r}",
        )
    region = _region_tuple(body.region) if body.region else None
    try:
        _recorder.start(game_id=body.game_id, fps=body.fps, region=region)
    except RecorderBusyError as e:
        raise HTTPException(status_code=409, detail=str(e)) from e
    except RecorderPermissionError as e:
        raise HTTPException(status_code=403, detail=str(e)) from e
    except RecorderError as e:
        log.exception("erro do recorder no /recording/start")
        raise HTTPException(status_code=500, detail=str(e)) from e

    log.info(
        "recording/start game=%s fps=%d region=%s",
        body.game_id,
        body.fps,
        body.region,
    )
    return _serialize_recorder_status()


@app.post("/recording/stop", response_model=RecordingStatusResponse)
def recording_stop() -> RecordingStatusResponse:
    _recorder.stop()
    log.info("recording/stop")
    return _serialize_recorder_status()


@app.get("/recording/status", response_model=RecordingStatusResponse)
def recording_status() -> RecordingStatusResponse:
    return _serialize_recorder_status()


def _recording_disk_size_bytes(recording_id: int) -> int:
    rec_dir = recordings_dir() / str(recording_id)
    if not rec_dir.exists():
        return 0
    total = 0
    for p in rec_dir.iterdir():
        try:
            total += p.stat().st_size
        except OSError:
            continue
    return total


class RecordingSummary(BaseModel):
    recording: Recording
    disk_size_bytes: int


@app.get("/recordings", response_model=list[RecordingSummary])
def recordings_list(
    game_id: str | None = Query(default=None),
) -> list[RecordingSummary]:
    conn = get_connection()
    recs = recordings_repo.list_all(conn, game_id=game_id)
    return [
        RecordingSummary(
            recording=r,
            disk_size_bytes=_recording_disk_size_bytes(r.id) if r.id else 0,
        )
        for r in recs
    ]


class RecordingDetail(BaseModel):
    recording: Recording
    frames_dir: str
    disk_size_bytes: int


@app.get("/recordings/{recording_id}", response_model=RecordingDetail)
def recordings_get(recording_id: int) -> RecordingDetail:
    conn = get_connection()
    rec = recordings_repo.get(conn, recording_id)
    if rec is None:
        raise HTTPException(
            status_code=404,
            detail=f"gravação {recording_id} não encontrada",
        )
    return RecordingDetail(
        recording=rec,
        frames_dir=str(recordings_dir() / str(recording_id)),
        disk_size_bytes=_recording_disk_size_bytes(recording_id),
    )


class DeleteRecordingRequest(BaseModel):
    confirm: bool = False


@app.delete("/recordings/{recording_id}", status_code=204)
def recordings_delete(
    recording_id: int, body: DeleteRecordingRequest | None = None
) -> None:
    if body is None or not body.confirm:
        raise HTTPException(
            status_code=400,
            detail=(
                'Envie {"confirm": true} no body para confirmar a remoção. '
                "Frames em disco são apagados junto."
            ),
        )
    conn = get_connection()
    rec = recordings_repo.get(conn, recording_id)
    if rec is None:
        raise HTTPException(
            status_code=404,
            detail=f"gravação {recording_id} não encontrada",
        )
    if recordings_repo.has_motor_models(conn, recording_id):
        raise HTTPException(
            status_code=409,
            detail=(
                f"a gravação {recording_id} tem motor_models treinados em cima dela; "
                f"apague-os primeiro pelo endpoint de motor models."
            ),
        )

    # Ordem: DB primeiro (atômico via CASCADE em recording_frames), disco depois
    # — orphan dir é detectável; orphan rows apontando pra disco apagado seria pior.
    recordings_repo.delete(conn, recording_id)
    rec_dir = recordings_dir() / str(recording_id)
    if rec_dir.exists():
        try:
            for p in rec_dir.iterdir():
                p.unlink(missing_ok=True)
            rec_dir.rmdir()
        except OSError:
            log.exception(
                "DB foi apagado mas falhou ao limpar disco %s", rec_dir
            )


# --- /motor-models (M6) -------------------------------------------------------


@app.get("/motor-models", response_model=list[MotorModel])
def motor_models_list(
    game_id: str | None = Query(default=None),
) -> list[MotorModel]:
    conn = get_connection()
    if game_id is None:
        return motor_models_repo.list_all(conn)
    return motor_models_repo.list_by_game(conn, game_id)


@app.get("/motor-models/{motor_id}", response_model=MotorModel)
def motor_models_get(motor_id: int) -> MotorModel:
    conn = get_connection()
    m = motor_models_repo.get(conn, motor_id)
    if m is None:
        raise HTTPException(
            status_code=404,
            detail=f"motor model {motor_id} não encontrado",
        )
    return m


@app.delete("/motor-models/{motor_id}", status_code=204)
def motor_models_delete(motor_id: int) -> None:
    conn = get_connection()
    m = motor_models_repo.get(conn, motor_id)
    if m is None:
        raise HTTPException(
            status_code=404,
            detail=f"motor model {motor_id} não encontrado",
        )
    # DB primeiro, disco depois — orphan file é recuperável; orphan row seria pior.
    onnx_path = Path(m.onnx_path) if m.onnx_path else None
    motor_models_repo.delete(conn, motor_id)
    if onnx_path is not None and onnx_path.exists():
        try:
            onnx_path.unlink(missing_ok=True)
        except OSError:
            log.exception("DB apagado mas falhou ao limpar ONNX %s", onnx_path)


@app.post("/session/start", response_model=SessionStateResponse)
async def session_start(body: StartSessionRequest) -> SessionStateResponse:
    region = _region_tuple(body.region) if body.region else None

    # Lookup do profile pra aplicar os gates de tempo/anti-cheat antes
    # de mexer no engine. O engine faz lookup de novo (defensivo); o
    # custo é desprezível e mantém a engine self-contained.
    conn = get_connection()
    profile = games_repo.get(conn, body.game)
    if profile is None:
        raise HTTPException(
            status_code=422,
            detail=f"jogo desconhecido: {body.game!r}",
        )

    if profile.tempo is not Tempo.TURN_BASED:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Este modo (M3 turn-based) só suporta jogos turn_based; "
                f"{profile.id!r} é {profile.tempo.value}. Jogos slow_realtime "
                f"e fast_realtime serão suportados a partir do M7 (loop hierárquico)."
            ),
        )

    if profile.anti_cheat is not AntiCheat.NONE:
        if body.acknowledge_ban_risk != ACK_BAN_RISK_TOKEN:
            raise HTTPException(
                status_code=403,
                detail=(
                    f"ATENÇÃO: este jogo usa {profile.anti_cheat.value}. "
                    f"Automação detectada = ban da conta (e possivelmente do HWID). "
                    f"Para prosseguir mesmo assim, envie acknowledge_ban_risk: "
                    f"'{ACK_BAN_RISK_TOKEN}' no body da requisição."
                ),
            )
        log.warning(
            "anti_cheat bypass aceito game=%s anti_cheat=%s",
            profile.id,
            profile.anti_cheat.value,
        )

    try:
        state = await _engine.start(
            game=body.game,
            region=region,
            max_actions=body.max_actions,
            max_duration_s=body.max_duration_s,
            step_delay_ms=body.step_delay_ms,
        )
    except SessionAlreadyRunningError as e:
        raise HTTPException(status_code=409, detail=str(e)) from e
    except ValueError as e:
        # jogo desconhecido (defesa em profundidade — endpoint já checou)
        raise HTTPException(status_code=422, detail=str(e)) from e

    log.info(
        "session/start game=%s region=%s max_actions=%d",
        body.game,
        body.region,
        body.max_actions,
    )
    return _serialize_state(state)


@app.post("/session/stop", response_model=SessionStateResponse)
async def session_stop() -> SessionStateResponse:
    state = await _engine.stop()
    log.info("session/stop status=%s", state.status)
    return _serialize_state(state)


@app.get("/session/status", response_model=SessionStateResponse)
def session_status() -> SessionStateResponse:
    return _serialize_state(_engine.status())


if __name__ == "__main__":
    log.info("starting sidecar on %s:%d", HOST, PORT)
    uvicorn.run(app, host=HOST, port=PORT, log_config=None)
