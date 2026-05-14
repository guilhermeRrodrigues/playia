"""Coordenador do loop hierárquico.

Cria duas ``asyncio.Task`` por chamada de :meth:`start`:

- ``hsession-motor``: captura → ``motor.predict`` → diff keys vs estado
  segurado → emit press/release. Cadência ``target_fps`` (default 30).
- ``hsession-strategist``: captura → ``VLMStrategist.decide`` → publica
  ``Intention``. Cadência ditada pela latência do VLM mais ``ttl_s``.

Stop:
- ``stop()`` seta ``asyncio.Event``; ambas as tasks checam no topo do
  loop e saem no próximo tick.
- O ``motor`` libera **todas** as teclas que estava segurando no
  cleanup do ``finally`` — evita deixar tecla "presa" se a stack
  travar.
- ``pyautogui.FAILSAFE`` continua ativo no executor: mover mouse pro
  canto superior esquerdo aborta com exceção tipada.
"""

from __future__ import annotations

import asyncio
import base64
import dataclasses
import logging
import time
from datetime import datetime
from typing import TYPE_CHECKING

from motor.errors import MotorInferenceError, MotorNotFoundError

from .base import HierarchicalState, Intention
from .errors import (
    HSessionAlreadyRunningError,
    MotorNotTrainedError,
    StrategistError,
)

if TYPE_CHECKING:
    from capture.base import Region, ScreenCapture
    from executor.base import InputExecutor
    from motor.base import Motor

    from .vlm_strategist import VLMStrategist

log = logging.getLogger("playia.strategist")

DEFAULT_MOTOR_FPS = 30
INTENTION_HISTORY_CAP = 50


class HierarchicalEngine:
    """Singleton do loop hierárquico. ``main.py`` segura uma instância."""

    def __init__(
        self,
        capture: "ScreenCapture",
        motor: "Motor",
        executor: "InputExecutor",
        strategist: "VLMStrategist",
    ) -> None:
        self._capture = capture
        self._motor = motor
        self._executor = executor
        self._strategist = strategist
        self._state = HierarchicalState()
        self._stop_event = asyncio.Event()
        self._motor_task: asyncio.Task[None] | None = None
        self._strategist_task: asyncio.Task[None] | None = None
        self._held_keys: set[str] = set()

    # ---- API pública ----

    def is_running(self) -> bool:
        return self._state.status == "running"

    def status(self) -> HierarchicalState:
        return dataclasses.replace(
            self._state,
            intentions_history=list(self._state.intentions_history),
        )

    async def start(
        self,
        *,
        game_id: str,
        goal: str,
        region: "Region | None",
        max_duration_s: int,
        target_fps: int = DEFAULT_MOTOR_FPS,
        initial_delay_ms: int = 3000,
    ) -> HierarchicalState:
        if self.is_running():
            raise HSessionAlreadyRunningError(
                "Já existe sessão hierárquica em andamento. Pare-a antes."
            )

        # Carrega o motor model — se não houver, levantamos MotorNotTrainedError
        # que o endpoint converte em HTTP 412 com instrução pra treinar.
        try:
            meta = self._motor.load_for_game(game_id)
        except MotorNotFoundError as e:
            raise MotorNotTrainedError(str(e)) from e
        except MotorInferenceError as e:
            raise StrategistError(str(e)) from e

        self._state = HierarchicalState(
            status="running",
            game=game_id,
            region=region,
            motor_model_id=meta.motor_model_id,
            motor_accuracy=meta.accuracy,
            started_at=datetime.now(),
        )
        self._held_keys = set()
        self._stop_event = asyncio.Event()

        self._motor_task = asyncio.create_task(
            self._loop_motor(region, max_duration_s, target_fps, initial_delay_ms),
            name=f"hsession-motor-{game_id}",
        )
        self._strategist_task = asyncio.create_task(
            self._loop_strategist(region, goal, initial_delay_ms),
            name=f"hsession-strategist-{game_id}",
        )
        log.info(
            "hsession iniciada game=%s motor_id=%d target_fps=%d max_duration_s=%d",
            game_id, meta.motor_model_id, target_fps, max_duration_s,
        )
        return self.status()

    async def stop(self) -> HierarchicalState:
        if not self.is_running():
            return self.status()
        self._stop_event.set()
        tasks = [t for t in (self._motor_task, self._strategist_task) if t is not None]
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        return self.status()

    # ---- loops ----

    async def _loop_motor(
        self,
        region: "Region | None",
        max_duration_s: int,
        target_fps: int,
        initial_delay_ms: int,
    ) -> None:
        # Janela pro usuário focar o jogo após clicar Iniciar; sem isso o
        # primeiro key_press vai pra janela do PlayIA, que ficou em foco
        # depois do clique do botão.
        if initial_delay_ms > 0:
            try:
                await asyncio.wait_for(
                    self._stop_event.wait(), timeout=initial_delay_ms / 1000.0
                )
                return  # user cancelou no delay
            except asyncio.TimeoutError:
                pass

        period = 1.0 / max(target_fps, 1)
        t0 = time.monotonic()
        next_tick = t0
        n_actions = 0
        try:
            while not self._stop_event.is_set():
                now = time.monotonic()
                if now - t0 >= max_duration_s:
                    self._state.stop_reason = "max_duration"
                    break

                try:
                    png = await asyncio.to_thread(self._capture.grab, region)
                    # v0.1: motor.predict() recebe SÓ o frame; a intenção
                    # atual fica em state.current_intention (publicada pelo
                    # strategist em paralelo) mas não entra como input do
                    # modelo. Para jogos simples como Chrome Dino o frame
                    # carrega contexto suficiente. Quando o motor ganhar
                    # condicionamento por texto (M+), basta plugar a
                    # intention aqui — o schema dele já tem o slot.
                    action = await asyncio.to_thread(self._motor.predict, png)
                except Exception as e:  # noqa: BLE001
                    log.exception("motor tick erro")
                    self._state.error = f"motor: {e}"
                    self._state.stop_reason = "error"
                    self._state.status = "error"
                    break

                # log alinhando intenção atual e ação predita pra debug do
                # acoplamento estrategista/motor durante teste manual.
                if n_actions % 30 == 0:
                    intention_text = (
                        self._state.current_intention.text
                        if self._state.current_intention is not None
                        else "(sem intenção ainda)"
                    )
                    log.info(
                        "motor tick=%d keys=%s click_l=%s click_r=%s "
                        "intention=%r lat=%.1fms",
                        n_actions,
                        action.keys_down,
                        action.click_left,
                        action.click_right,
                        intention_text,
                        action.latency_ms,
                    )

                new_keys = set(action.keys_down)
                released = self._held_keys - new_keys
                pressed = new_keys - self._held_keys
                for k in released:
                    try:
                        await asyncio.to_thread(self._executor.key_release, k)
                    except Exception:  # noqa: BLE001
                        log.exception("key_release(%s) falhou", k)
                for k in pressed:
                    try:
                        await asyncio.to_thread(self._executor.key_press, k)
                    except Exception:  # noqa: BLE001
                        log.exception("key_press(%s) falhou", k)
                self._held_keys = new_keys

                n_actions += 1
                self._state.last_frame_b64 = base64.b64encode(png).decode("ascii")
                self._state.total_actions = n_actions
                elapsed = time.monotonic() - t0
                self._state.actions_per_second = n_actions / max(elapsed, 1e-6)

                next_tick += period
                sleep_for = next_tick - time.monotonic()
                if sleep_for > 0:
                    try:
                        await asyncio.wait_for(
                            self._stop_event.wait(), timeout=sleep_for
                        )
                        break
                    except asyncio.TimeoutError:
                        pass
                else:
                    next_tick = time.monotonic()
            else:
                if self._state.stop_reason is None:
                    self._state.stop_reason = "user"
        except asyncio.CancelledError:
            self._state.stop_reason = "user"
            raise
        finally:
            # cleanup CRÍTICO: solta toda tecla que ficou segurada.
            for k in list(self._held_keys):
                try:
                    await asyncio.to_thread(self._executor.key_release, k)
                except Exception:  # noqa: BLE001
                    log.exception("cleanup key_release(%s) falhou", k)
            self._held_keys.clear()

            if self._state.status == "running":
                self._state.status = "stopped"
            self._state.finished_at = datetime.now()
            # garante que o strategist também pare
            self._stop_event.set()
            log.info(
                "hsession encerrada stop_reason=%s actions=%d aps=%.1f",
                self._state.stop_reason,
                self._state.total_actions,
                self._state.actions_per_second,
            )

    async def _loop_strategist(
        self, region: "Region | None", goal: str, initial_delay_ms: int
    ) -> None:
        if initial_delay_ms > 0:
            try:
                await asyncio.wait_for(
                    self._stop_event.wait(), timeout=initial_delay_ms / 1000.0
                )
                return
            except asyncio.TimeoutError:
                pass
        try:
            while not self._stop_event.is_set():
                try:
                    png = await asyncio.to_thread(self._capture.grab, region)
                except Exception:  # noqa: BLE001
                    log.exception("strategist capture erro")
                    await asyncio.sleep(2.0)
                    continue

                try:
                    history = list(self._state.intentions_history[-5:])
                    intention = await self._strategist.decide(png, goal, history)
                except Exception as e:  # noqa: BLE001
                    log.warning("strategist VLM erro: %s", e)
                    intention = Intention(
                        text=f"(erro VLM: {e})",
                        ttl_s=5.0,
                    )

                self._state.current_intention = intention
                self._state.intentions_history.append(intention)
                if len(self._state.intentions_history) > INTENTION_HISTORY_CAP:
                    del self._state.intentions_history[0]

                try:
                    await asyncio.wait_for(
                        self._stop_event.wait(), timeout=intention.ttl_s
                    )
                    break
                except asyncio.TimeoutError:
                    pass
        except asyncio.CancelledError:
            raise
