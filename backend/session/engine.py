"""Orquestra o loop captura → planner.decide() → executor.

Roda em uma ``asyncio.Task`` paralela ao FastAPI. ``stop()`` apenas seta um
``asyncio.Event``; o loop o checa no topo de cada iteração — então cada
``stop()`` mata a task em no máximo um ciclo de decisão.
"""

from __future__ import annotations

import asyncio
import base64
import dataclasses
import logging
from datetime import datetime
from time import monotonic

from capture.base import Region, ScreenCapture
from executor.base import InputExecutor
from executor.errors import ExecutorError
from memory.connection import get_connection
from memory.models import Game
from memory.repos import games_repo
from planner.actions import Action
from planner.base import Planner
from planner.errors import PlannerError, PlannerParseError
from vision.errors import VLMError

from .base import SessionState, StopReason

log = logging.getLogger("playia.session")

HISTORY_CAP = 20


class SessionAlreadyRunningError(RuntimeError):
    """``start()`` foi chamado mas já existe uma sessão ativa."""


class SessionEngine:
    """Singleton de loop de sessão (módulo-level no main.py)."""

    def __init__(
        self,
        capture: ScreenCapture,
        planner: Planner,
        executor: InputExecutor,
    ) -> None:
        self._capture = capture
        self._planner = planner
        self._executor = executor
        self._state = SessionState()
        self._task: asyncio.Task[None] | None = None
        self._stop = asyncio.Event()

    # ---- API pública (chamada pelos endpoints) ---------------------------

    def is_running(self) -> bool:
        return self._task is not None and not self._task.done()

    async def start(
        self,
        game: str,
        region: Region | None,
        max_actions: int,
        max_duration_s: int,
        step_delay_ms: int,
        initial_delay_ms: int = 3000,
    ) -> SessionState:
        if self.is_running():
            raise SessionAlreadyRunningError(
                "Já existe uma sessão em andamento. Pare a atual antes de iniciar outra."
            )
        profile = games_repo.get(get_connection(), game)
        if profile is None:
            raise ValueError(f"jogo desconhecido: {game!r}")

        self._state.reset()
        self._state.status = "running"
        self._state.game = profile.name
        self._state.region = region
        self._state.started_at = datetime.now()
        self._stop = asyncio.Event()

        self._task = asyncio.create_task(
            self._run(
                profile,
                region,
                max_actions,
                max_duration_s,
                step_delay_ms,
                initial_delay_ms,
            ),
            name=f"session-{profile.name}",
        )
        return self.status()

    async def stop(self) -> SessionState:
        if self.is_running():
            self._stop.set()
        return self.status()

    def status(self) -> SessionState:
        # Cópia rasa para a serialização HTTP não pegar mutação no meio.
        return dataclasses.replace(
            self._state,
            history=list(self._state.history),
        )

    # ---- Loop interno -----------------------------------------------------

    async def _run(
        self,
        profile: Game,
        region: Region | None,
        max_actions: int,
        max_duration_s: int,
        step_delay_ms: int,
        initial_delay_ms: int,
    ) -> None:
        stop_reason: StopReason | None = None
        log.info(
            "session start game=%s region=%s max_actions=%d max_duration_s=%d step_delay_ms=%d initial_delay_ms=%d",
            profile.name,
            region,
            max_actions,
            max_duration_s,
            step_delay_ms,
            initial_delay_ms,
        )

        # Janela de "foque o jogo agora": pyautogui dispara na janela em foco;
        # como o último clique foi em PlayIA, a tecla iria pro nosso próprio
        # app sem este delay inicial. Interrupível por stop.
        if initial_delay_ms > 0:
            try:
                await asyncio.wait_for(
                    self._stop.wait(), timeout=initial_delay_ms / 1000.0
                )
                self._state.status = "stopped"
                self._state.stop_reason = "user"
                self._state.finished_at = datetime.now()
                log.info("session abortada durante delay inicial")
                return
            except asyncio.TimeoutError:
                pass

        deadline = monotonic() + max_duration_s

        try:
            while True:
                if self._stop.is_set():
                    stop_reason = "user"
                    break
                if monotonic() > deadline:
                    stop_reason = "max_duration"
                    break
                if self._state.actions_taken >= max_actions:
                    stop_reason = "max_actions"
                    break

                # 1. captura (sync → thread)
                png = await asyncio.to_thread(self._capture.grab, region)
                self._state.last_screenshot_b64 = base64.b64encode(png).decode("ascii")

                # 2. decide (async)
                t0 = monotonic()
                action = await self._planner.decide(
                    png,
                    profile.goal,
                    list(self._state.history),
                    profile.allowed_keys,
                )
                latency_ms = int((monotonic() - t0) * 1000)
                log.info(
                    "decide kind=%s key=%s latency_ms=%d actions_taken=%d",
                    action.kind,
                    action.key,
                    latency_ms,
                    self._state.actions_taken,
                )

                # 3. registra
                self._state.last_action = action
                self._state.last_reason = action.reason
                self._state.history.append(action)
                if len(self._state.history) > HISTORY_CAP:
                    self._state.history.pop(0)

                # 4. stop pedido pela própria VLM?
                if action.kind == "stop":
                    stop_reason = "game_over"
                    break

                # 5. executa (sync → thread)
                await asyncio.to_thread(self._dispatch, action)
                self._state.actions_taken += 1

                # 6. respira (o delay soma à latência da decide, não substitui)
                if self._stop.is_set():
                    stop_reason = "user"
                    break
                try:
                    await asyncio.wait_for(
                        self._stop.wait(), timeout=step_delay_ms / 1000.0
                    )
                    # _stop foi setado durante o sleep
                    stop_reason = "user"
                    break
                except asyncio.TimeoutError:
                    pass

            self._state.status = "stopped"
            self._state.stop_reason = stop_reason or "user"
        except asyncio.CancelledError:
            self._state.status = "stopped"
            self._state.stop_reason = "user"
            raise
        except VLMError as e:
            log.exception("VLM error encerrou a sessão")
            self._state.status = "error"
            self._state.stop_reason = "vlm_unavailable"
            self._state.error = str(e)
        except PlannerParseError as e:
            log.exception("planner não conseguiu parsear resposta da VLM")
            self._state.status = "error"
            self._state.stop_reason = "error"
            self._state.error = f"planner: {e}"
        except (PlannerError, ExecutorError) as e:
            log.exception("erro tipado interrompeu a sessão")
            self._state.status = "error"
            self._state.stop_reason = "error"
            self._state.error = str(e)
        except Exception as e:  # noqa: BLE001 — última rede de proteção
            log.exception("erro inesperado encerrou a sessão")
            self._state.status = "error"
            self._state.stop_reason = "error"
            self._state.error = f"inesperado: {e}"
        finally:
            self._state.finished_at = datetime.now()
            log.info(
                "session end status=%s stop_reason=%s actions_taken=%d",
                self._state.status,
                self._state.stop_reason,
                self._state.actions_taken,
            )

    def _dispatch(self, action: Action) -> None:
        if action.kind == "key":
            assert action.key is not None  # validado pelo schema
            self._executor.key_tap(action.key)
        elif action.kind == "click":
            assert action.x is not None and action.y is not None
            self._executor.click(action.x, action.y)
        elif action.kind == "wait":
            assert action.duration_ms is not None
            self._executor.wait(action.duration_ms)
        # kind=="stop" não chega aqui (tratado no loop antes do dispatch).
