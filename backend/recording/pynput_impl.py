"""Gravação cross-platform via :mod:`pynput` + :mod:`capture`.

Arquitetura de threads:

- ``pynput.keyboard.Listener`` e ``pynput.mouse.Listener`` rodam cada um
  na sua thread interna, e seus callbacks atualizam um snapshot
  protegido por ``_snapshot_lock``.
- Uma thread dedicada (``recorder-<id>``) faz o loop de captura:
  ``capture.grab(region) → escreve PNG em disco → empilha
  :class:`RecordingFrame` no buffer``. A cada ``BATCH_SIZE`` frames
  faz um ``insert_many`` no DB (transação só, WAL pequeno).
- O endpoint que chamou ``start``/``stop`` roda em outra thread (do
  threadpool do uvicorn). Cada thread usa sua conexão SQLite (thread-
  local, via :func:`memory.connection.get_connection`).

Sobre permissões no macOS: ``pynput.Listener.start`` raramente levanta
quando falta Input Monitoring — ele inicia mas não recebe eventos.
Detectar isso de forma síncrona é caro; a documentação (README +
mensagem da UI) instrui o usuário e a UI já avisa quando o fps_real
fica em 0 com nenhuma tecla capturada.
"""

from __future__ import annotations

import dataclasses
import logging
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

from pynput import keyboard, mouse

from memory.connection import close_thread_connection, get_connection
from memory.models import RecordingFrame
from memory.paths import recordings_dir
from memory.repos import recording_frames_repo, recordings_repo

from .base import RecordingStatus
from .errors import RecorderBusyError, RecorderPermissionError

if TYPE_CHECKING:
    from capture.base import Region, ScreenCapture

log = logging.getLogger("playia.recording")

# Frames acumulados antes de bater o DB. A 30 fps isso é 1 flush/s.
BATCH_SIZE = 30

_KEY_MAP: dict["keyboard.Key", str] = {
    keyboard.Key.up: "ArrowUp",
    keyboard.Key.down: "ArrowDown",
    keyboard.Key.left: "ArrowLeft",
    keyboard.Key.right: "ArrowRight",
    keyboard.Key.space: "Space",
    keyboard.Key.enter: "Enter",
    keyboard.Key.tab: "Tab",
    keyboard.Key.shift_l: "LShift",
    keyboard.Key.shift_r: "RShift",
    keyboard.Key.ctrl_l: "LCtrl",
    keyboard.Key.ctrl_r: "RCtrl",
    keyboard.Key.alt_l: "LAlt",
    keyboard.Key.alt_r: "RAlt",
    keyboard.Key.cmd: "Cmd",
    keyboard.Key.cmd_l: "LCmd",
    keyboard.Key.cmd_r: "RCmd",
    keyboard.Key.esc: "Escape",
    keyboard.Key.backspace: "Backspace",
}

_BUTTON_MAP: dict["mouse.Button", str] = {
    mouse.Button.left: "MouseLeft",
    mouse.Button.right: "MouseRight",
    mouse.Button.middle: "MouseMiddle",
}


def _key_to_str(key: "keyboard.Key | keyboard.KeyCode | None") -> str | None:
    """Converte chave do pynput para a convenção do PlayIA (ex.: 'ArrowUp', 'W')."""
    if key is None:
        return None
    if isinstance(key, keyboard.Key):
        return _KEY_MAP.get(key, str(key).removeprefix("Key."))
    if isinstance(key, keyboard.KeyCode):
        ch = key.char
        if ch is None:
            return None
        return ch.upper() if ch.isalpha() else ch
    return None


class PynputRecorder:
    """Singleton de gravação. Mantido em ``main.py`` como variável de módulo."""

    def __init__(self, capture: "ScreenCapture") -> None:
        self._capture = capture
        self._status_lock = threading.Lock()
        self._snapshot_lock = threading.Lock()
        self._status = RecordingStatus()

        # snapshot de input do usuário, atualizado pelos listeners e lido
        # pelo capture loop em cada tick.
        self._keys_down: set[str] = set()
        self._mouse_x: int = 0
        self._mouse_y: int = 0
        self._mouse_buttons: set[str] = set()

        self._stop_event = threading.Event()
        self._capture_thread: threading.Thread | None = None
        self._kb_listener: keyboard.Listener | None = None
        self._mouse_listener: mouse.Listener | None = None

    # ---- API pública ----

    def status(self) -> RecordingStatus:
        with self._status_lock:
            return dataclasses.replace(self._status)

    def start(
        self,
        *,
        game_id: str,
        fps: int,
        region: "Region | None",
    ) -> RecordingStatus:
        with self._status_lock:
            if self._status.running:
                raise RecorderBusyError(
                    "Já existe gravação em andamento. Pare a atual antes de iniciar outra."
                )

        # cria recording no DB usando a conexão da thread atual (endpoint)
        rec = recordings_repo.create(get_connection(), game_id=game_id, fps=fps)
        rec_dir = recordings_dir() / str(rec.id)
        rec_dir.mkdir(parents=True, exist_ok=True)

        with self._snapshot_lock:
            self._keys_down.clear()
            self._mouse_buttons.clear()
            self._mouse_x = 0
            self._mouse_y = 0

        try:
            self._kb_listener = keyboard.Listener(
                on_press=self._on_key_press,
                on_release=self._on_key_release,
            )
            self._kb_listener.start()
            self._mouse_listener = mouse.Listener(
                on_move=self._on_mouse_move,
                on_click=self._on_mouse_click,
            )
            self._mouse_listener.start()
        except Exception as e:
            self._stop_listeners()
            recordings_repo.delete(get_connection(), rec.id)
            raise RecorderPermissionError(
                "Falha ao iniciar listener global do teclado/mouse. "
                "No macOS, abra System Settings → Privacy & Security → "
                "Input Monitoring e marque o app que rodou o sidecar "
                "(Terminal ou PlayIA.app). Depois reinicie e tente de novo."
            ) from e

        self._stop_event = threading.Event()
        with self._status_lock:
            self._status = RecordingStatus(
                running=True,
                recording_id=rec.id,
                game_id=game_id,
                fps_target=fps,
                fps_real=0.0,
                frames_captured=0,
                started_at=rec.started_at,
                region=region,
            )

        self._capture_thread = threading.Thread(
            target=self._capture_loop,
            args=(rec.id, region, fps, rec_dir),
            name=f"recorder-{rec.id}",
            daemon=True,
        )
        self._capture_thread.start()
        log.info(
            "gravação iniciada rec_id=%d game=%s fps=%d region=%s",
            rec.id,
            game_id,
            fps,
            region,
        )
        return self.status()

    def stop(self) -> RecordingStatus:
        with self._status_lock:
            if not self._status.running:
                return dataclasses.replace(self._status)

        self._stop_event.set()
        if self._capture_thread is not None:
            self._capture_thread.join(timeout=5.0)
            self._capture_thread = None
        self._stop_listeners()
        return self.status()

    # ---- listeners ----

    def _stop_listeners(self) -> None:
        if self._kb_listener is not None:
            try:
                self._kb_listener.stop()
            except Exception:  # noqa: BLE001 — listener pode estar em estado inválido
                log.exception("falha ao parar kb listener")
            self._kb_listener = None
        if self._mouse_listener is not None:
            try:
                self._mouse_listener.stop()
            except Exception:  # noqa: BLE001
                log.exception("falha ao parar mouse listener")
            self._mouse_listener = None

    def _on_key_press(self, key: "keyboard.Key | keyboard.KeyCode | None") -> None:
        s = _key_to_str(key)
        if s is None:
            return
        with self._snapshot_lock:
            self._keys_down.add(s)

    def _on_key_release(self, key: "keyboard.Key | keyboard.KeyCode | None") -> None:
        s = _key_to_str(key)
        if s is None:
            return
        with self._snapshot_lock:
            self._keys_down.discard(s)

    def _on_mouse_move(self, x: int, y: int) -> None:
        with self._snapshot_lock:
            self._mouse_x = int(x)
            self._mouse_y = int(y)

    def _on_mouse_click(
        self,
        x: int,
        y: int,
        button: "mouse.Button",
        pressed: bool,
    ) -> None:
        s = _BUTTON_MAP.get(button)
        if s is None:
            return
        with self._snapshot_lock:
            self._mouse_x = int(x)
            self._mouse_y = int(y)
            if pressed:
                self._mouse_buttons.add(s)
            else:
                self._mouse_buttons.discard(s)

    # ---- capture loop ----

    def _capture_loop(
        self,
        rec_id: int,
        region: "Region | None",
        fps: int,
        rec_dir: Path,
    ) -> None:
        period = 1.0 / fps
        t0 = time.monotonic()
        next_tick = t0
        frames_total = 0
        buffer: list[RecordingFrame] = []
        error: str | None = None

        try:
            while not self._stop_event.is_set():
                now = time.monotonic()
                ts_ms = int((now - t0) * 1000)
                try:
                    png = self._capture.grab(region)
                except Exception as e:  # noqa: BLE001
                    log.exception("falha ao capturar frame rec_id=%d", rec_id)
                    error = f"capture: {e}"
                    break

                with self._snapshot_lock:
                    keys = sorted(self._keys_down)
                    mx, my = self._mouse_x, self._mouse_y
                    btns = sorted(self._mouse_buttons)

                frame_path = rec_dir / f"{ts_ms}.png"
                try:
                    frame_path.write_bytes(png)
                except OSError as e:
                    log.exception("falha ao escrever PNG %s", frame_path)
                    error = f"io: {e}"
                    break

                buffer.append(
                    RecordingFrame(
                        recording_id=rec_id,
                        ts_ms=ts_ms,
                        frame_path=str(frame_path),
                        keys_down=keys,
                        mouse_x=mx,
                        mouse_y=my,
                        mouse_buttons=btns,
                    )
                )
                frames_total += 1

                if len(buffer) >= BATCH_SIZE:
                    try:
                        recording_frames_repo.insert_many(get_connection(), buffer)
                    except Exception as e:  # noqa: BLE001
                        log.exception("falha no batch insert rec_id=%d", rec_id)
                        error = f"db: {e}"
                        break
                    buffer.clear()

                with self._status_lock:
                    self._status.frames_captured = frames_total
                    self._status.fps_real = frames_total / max(time.monotonic() - t0, 1e-6)

                next_tick += period
                sleep_for = next_tick - time.monotonic()
                if sleep_for > 0:
                    if self._stop_event.wait(sleep_for):
                        break
                else:
                    # atrasado; alinha pro próximo ciclo agora.
                    next_tick = time.monotonic()
        finally:
            if buffer:
                try:
                    recording_frames_repo.insert_many(get_connection(), buffer)
                except Exception:  # noqa: BLE001
                    log.exception("falha no flush final do batch rec_id=%d", rec_id)
            try:
                recordings_repo.end(
                    get_connection(), rec_id, frame_count=frames_total
                )
            except Exception:  # noqa: BLE001
                log.exception("falha ao finalizar recording %d no DB", rec_id)

            duration = time.monotonic() - t0
            fps_final = frames_total / max(duration, 1e-6)
            with self._status_lock:
                self._status.running = False
                self._status.finished_at = datetime.now()
                self._status.frames_captured = frames_total
                self._status.fps_real = fps_final
                if error is not None:
                    self._status.error = error
            close_thread_connection()
            log.info(
                "gravação encerrada rec_id=%d frames=%d duration_s=%.1f fps_real=%.2f%s",
                rec_id,
                frames_total,
                duration,
                fps_final,
                f" error={error}" if error else "",
            )
