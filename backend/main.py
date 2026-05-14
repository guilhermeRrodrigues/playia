"""PlayIA sidecar — FastAPI app que expõe captura de tela e VLM (M2)."""

from __future__ import annotations

import json
import logging
import sys
import time
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from pydantic import BaseModel, Field, field_validator

from capture.base import Region
from capture.factory import get_capture
from executor.factory import get_executor
from memory.connection import get_connection
from memory.migrations import apply_pending
from planner.actions import Action
from planner.factory import get_planner
from session.base import SessionState
from session.engine import SessionAlreadyRunningError, SessionEngine
from session.games import GAMES, GameProfile
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
    # Aplica migrations pendentes do SQLite no startup. Idempotente.
    conn = get_connection()
    applied = apply_pending(conn)
    if applied:
        log.info("schema atualizado: migrations aplicadas %s", applied)
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


class StartSessionRequest(BaseModel):
    game: str
    region: list[int] | None = Field(
        default=None,
        description="Recorte [x, y, largura, altura] do jogo na tela. None = tela inteira.",
    )
    max_actions: int = Field(default=200, ge=1, le=10_000)
    max_duration_s: int = Field(default=600, ge=1, le=86_400)
    step_delay_ms: int = Field(default=300, ge=0, le=60_000)

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


@app.get("/session/games", response_model=dict[str, GameProfile])
def session_games() -> dict[str, GameProfile]:
    return GAMES


@app.post("/session/start", response_model=SessionStateResponse)
async def session_start(body: StartSessionRequest) -> SessionStateResponse:
    region = _region_tuple(body.region) if body.region else None
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
        # jogo desconhecido
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
