"""PlayIA sidecar — FastAPI app que expõe captura de tela e (futuramente) IA."""

from __future__ import annotations

import json
import logging
import sys
from typing import Any

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response

from capture.factory import get_capture

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

app = FastAPI(title="PlayIA Backend", version="0.1.0")

# UI roda em http://localhost:1420 (Tauri dev) ou tauri://localhost (produção).
# Em M1 liberamos qualquer origem local — restringir no M7 quando tivermos Settings.
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"^(https?|tauri)://(localhost|127\.0\.0\.1)(:\d+)?$",
    allow_methods=["*"],
    allow_headers=["*"],
)

_capture = get_capture()


@app.get("/health")
def health() -> dict[str, bool]:
    return {"ok": True}


@app.post("/capture")
def capture() -> Response:
    try:
        png = _capture.grab()
    except Exception as e:
        log.exception("falha ao capturar tela")
        raise HTTPException(status_code=500, detail=str(e)) from e
    return Response(content=png, media_type="image/png")


if __name__ == "__main__":
    log.info("starting sidecar on %s:%d", HOST, PORT)
    uvicorn.run(app, host=HOST, port=PORT, log_config=None)
