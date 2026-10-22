"""Shared diagnostic models and collection for compiler phases."""
from __future__ import annotations

import json
from collections.abc import Iterator
from dataclasses import dataclass
from enum import Enum
from typing import Any


class Phase(str, Enum):
    LEXICAL = "lexical"
    SYNTAX = "syntax"
    SEMANTIC = "semantic"
    GENERATION = "generation"
    EXECUTION = "execution"


class Severity(str, Enum):
    ERROR = "error"
    WARNING = "warning"


@dataclass(frozen=True, init=False)
class Diagnostic:
    """Immutable diagnostic data; source text belongs to the collector."""

    phase: str | Phase
    message: str
    line: int | None = None
    column: int | None = None
    length: int = 1
    severity: str | Severity = Severity.ERROR

    def __init__(
        self,
        phase: str | Phase | None = None,
        message: str = "",
        line: int | None = None,
        column: int | None = None,
        length: int = 1,
        severity: str | Severity = Severity.ERROR,
        *,
        fase: str | Phase | None = None,
        mensagem: str | None = None,
        linha: int | None = None,
        coluna: int | None = None,
        comprimento: int | None = None,
        severidade: str | Severidade | None = None,
    ) -> None:
        object.__setattr__(self, "phase", fase if fase is not None else phase)
        object.__setattr__(self, "message", mensagem if mensagem is not None else message)
        object.__setattr__(self, "line", linha if linha is not None else line)
        object.__setattr__(self, "column", coluna if coluna is not None else column)
        object.__setattr__(self, "length", comprimento if comprimento is not None else length)
        object.__setattr__(
            self, "severity", severidade if severidade is not None else severity
        )

    @property
    def header(self) -> str:
        phase = self.phase.value if isinstance(self.phase, Enum) else self.phase
        severity = (
            self.severity.value if isinstance(self.severity, Enum) else self.severity
        )
        location = ""
        if self.line is not None:
            location = (
                f" [{self.line}:{self.column}]"
                if self.column is not None
                else f" [{self.line}]"
            )
        return f"{severity} {phase}{location}: {self.message}"

    def __str__(self) -> str:
        phase = self.phase.value if isinstance(self.phase, Enum) else self.phase
        location = ""
        if self.line is not None:
            location = f" Line {self.line}"
            if self.column is not None:
                location += f", column {self.column}"
        return f"[ERROR {phase.upper()}]{location}: {self.message}"

    @property
    def fase(self) -> str | Phase:
        return self.phase

    @property
    def mensagem(self) -> str:
        return self.message

    @property
    def linha(self) -> int | None:
        return self.line

    @property
    def coluna(self) -> int | None:
        return self.column

    @property
    def comprimento(self) -> int:
        return self.length

    @property
    def severidade(self) -> str | Severity | Severidade:
        return self.severity


class DiagnosticBag:
    """Collects diagnostics and formats them with source context."""

    def __init__(self, source: str | None = None) -> None:
        self._lines = source.splitlines() if source is not None else []
        self._diagnostics: list[Diagnostic] = []

    def report(self, diagnostic: Diagnostic) -> None:
        self._diagnostics.append(diagnostic)

    def error(
        self,
        phase: str | Phase,
        message: str,
        line: int | None = None,
        column: int | None = None,
        length: int = 1,
    ) -> None:
        self.report(Diagnostic(phase, message, line, column, length))

    @property
    def diagnostics(self) -> tuple[Diagnostic, ...]:
        return tuple(self._diagnostics)

    @property
    def has_errors(self) -> bool:
        return any(self._severity(diagnostic) == "erro" for diagnostic in self._diagnostics)

    def __len__(self) -> int:
        return len(self._diagnostics)

    def __iter__(self) -> Iterator[Diagnostic]:
        return iter(self._diagnostics)

    @staticmethod
    def _phase(diagnostic: Diagnostic) -> str:
        phase = diagnostic.phase.value if isinstance(diagnostic.phase, Enum) else diagnostic.phase
        return {
            "lexical": "léxico",
            "syntax": "sintático",
            "semantic": "semântico",
            "generation": "geração",
            "execution": "execução",
        }.get(phase, phase)

    @staticmethod
    def _severity(diagnostic: Diagnostic) -> str:
        severity = (
            diagnostic.severity.value
            if isinstance(diagnostic.severity, Enum)
            else diagnostic.severity
        )
        return {"error": "erro", "warning": "aviso"}.get(severity, severity)

    def source_line(self, diagnostic: Diagnostic) -> str | None:
        if diagnostic.line is None or not 1 <= diagnostic.line <= len(self._lines):
            return None
        return self._lines[diagnostic.line - 1]

    def format(self, diagnostic: Diagnostic) -> str:
        source_line = self.source_line(diagnostic)
        phase = self._phase(diagnostic)
        severity = self._severity(diagnostic)
        location = ""
        if diagnostic.line is not None:
            location = (
                f" [{diagnostic.line}:{diagnostic.column}]"
                if diagnostic.column is not None
                else f" [{diagnostic.line}]"
            )
        header = f"{severity} {phase}{location}: {diagnostic.message}"
        if source_line is None:
            return header

        line_number = str(diagnostic.line)
        column = diagnostic.column or 1
        prefix = source_line[: max(0, column - 1)]
        caret_indent = "".join("\t" if char == "\t" else " " for char in prefix)
        caret_indent += " " * max(0, column - 1 - len(source_line))
        marker = "^" + "~" * max(0, diagnostic.length - 1)
        return (
            f"{header}\n"
            f"  {line_number} | {source_line}\n"
            f"  {' ' * len(line_number)} | {caret_indent}{marker}"
        )

    def format_text(self) -> str:
        if not self._diagnostics:
            return ""
        blocks = [self.format(diagnostic) for diagnostic in self._diagnostics]
        errors = sum(
            self._severity(diagnostic) == "erro"
            for diagnostic in self._diagnostics
        )
        warnings = len(self._diagnostics) - errors
        blocks.append(f"{errors} erro(s), {warnings} aviso(s)")
        return "\n\n".join(blocks)

    def to_dict(self) -> dict[str, Any]:
        return {
            "has_errors": self.has_errors,
            "diagnostics": [
                {
                    "phase": (
                        diagnostic.phase.value
                        if isinstance(diagnostic.phase, Enum)
                        else diagnostic.phase
                    ),
                    "severity": (
                        diagnostic.severity.value
                        if isinstance(diagnostic.severity, Enum)
                        else diagnostic.severity
                    ),
                    "line": diagnostic.line,
                    "column": diagnostic.column,
                    "length": diagnostic.length,
                    "message": diagnostic.message,
                    "source_line": self.source_line(diagnostic),
                }
                for diagnostic in self._diagnostics
            ],
        }

    def to_json(self, indent: int | None = None) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=indent)

    # Portuguese aliases remain available for the issue's initial API.
    def adicionar(self, diagnostico: Diagnostic) -> None:
        self.report(diagnostico)

    def erro(
        self,
        fase: str | Phase,
        mensagem: str,
        linha: int | None = None,
        coluna: int | None = None,
        comprimento: int = 1,
    ) -> None:
        self.error(fase, mensagem, linha, coluna, comprimento)

    def listar(self) -> tuple[Diagnostic, ...]:
        return self.diagnostics

    def tem_erros(self) -> bool:
        return self.has_errors

    def trecho(self, diagnostico: Diagnostic) -> str | None:
        return self.source_line(diagnostico)

    def formatar(self, diagnostico: Diagnostic) -> str:
        return self.format(diagnostico)

    def formatar_texto(self) -> str:
        return self.format_text()

    def para_dict(self) -> dict[str, Any]:
        result = self.to_dict()
        return {
            "tem_erros": result["has_errors"],
            "diagnosticos": [
                {
                    "fase": self._phase(diagnostic),
                    "severidade": self._severity(diagnostic),
                    "linha": diagnostic.line,
                    "coluna": diagnostic.column,
                    "comprimento": diagnostic.length,
                    "mensagem": diagnostic.message,
                    "trecho": self.source_line(diagnostic),
                }
                for diagnostic in self._diagnostics
            ],
        }

    def para_json(self, indent: int | None = None) -> str:
        return json.dumps(self.para_dict(), ensure_ascii=False, indent=indent)


class Fase(str, Enum):
    LEXICO = "léxico"
    SINTATICO = "sintático"
    SEMANTICO = "semântico"
    GERACAO = "geração"
    EXECUCAO = "execução"


class Severidade(str, Enum):
    ERRO = "erro"
    AVISO = "aviso"


ColetorDiagnosticos = DiagnosticBag
Diagnostico = Diagnostic
