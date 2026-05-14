# TODO(windows-only): implementar com `pydirectinput` para jogos AAA com
# DirectInput. Por enquanto, o factory escolhe `PyAutoGuiExecutor` mesmo
# no Windows. Avaliação real fica para M8 (validação em Windows nativo).
"""DirectInput stub — placeholder até o M+ (Windows AAA games)."""

from __future__ import annotations


class DirectInputExecutor:
    def __init__(self) -> None:
        raise NotImplementedError(
            "DirectInputExecutor ainda não foi implementado. "
            "Use PyAutoGuiExecutor (default) — pydirectinput entra em M+."
        )
