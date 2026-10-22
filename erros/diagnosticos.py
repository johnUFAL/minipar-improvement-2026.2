from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Diagnostic:
    """Erro ou aviso de uma fase do compilador."""
    phase: str
    message: str
    line: int | None = None
    column: int | None = None

    def __str__(self) -> str:
        location = ""
        if self.line is not None:
            location = f" Line {self.line}"
            if self.column is not None:
                location += f", column {self.column}"
        return f"[ERROR {self.phase.upper()}]{location}: {self.message}"


class DiagnosticBag:
    def __init__(self) -> None:
        self._diagnostics: list[Diagnostic] = []

    def report(self, diagnostic: Diagnostic) -> None:
        self._diagnostics.append(diagnostic)

    @property
    def diagnostics(self) -> tuple[Diagnostic, ...]:
        return tuple(self._diagnostics)

    @property
    def has_errors(self) -> bool:
        return bool(self._diagnostics)
