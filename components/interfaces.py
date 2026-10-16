from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import Any, Protocol


class ILexico(Protocol):
    def tokenize(self) -> Sequence[Any]: ...


class ISintatico(Protocol):
    def parse(self) -> Any: ...


class ISemantico(Protocol):
    def analyze(self, program: Any) -> bool: ...


class ITabelaSimbolos(Protocol):
    def enter_scope(self) -> None: ...
    def exit_scope(self) -> None: ...
    def define(self, symbol: Any) -> bool: ...
    def lookup(self, name: str) -> Any | None: ...


class IGeradorTAC(Protocol):
    def generate(self, program: Any, output_name: str) -> str: ...


class IGeradorCpp(Protocol):
    def generate(self, program: Any, output_name: str) -> bool: ...


class IControle(Protocol):
    def compile_file(self, source_path: str | Path, output_name: str) -> bool: ...
