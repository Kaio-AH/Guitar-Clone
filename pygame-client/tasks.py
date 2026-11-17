"""Executa trabalho de rede/CPU sem travar o loop do PyGame."""
from __future__ import annotations

import threading
from typing import Any, Callable


class ThreadTask:
    def __init__(self, function: Callable[[], Any]) -> None:
        self.function = function
        self.result: Any = None
        self.error: BaseException | None = None
        self.done = False
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()

    def _run(self) -> None:
        try:
            self.result = self.function()
        except BaseException as exc:  # noqa: BLE001 - repassado para a UI
            self.error = exc
        finally:
            self.done = True
