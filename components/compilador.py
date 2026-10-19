from __future__ import annotations

from pathlib import Path

from components.interfaces import IControle


class CompiladorMiniPar:
    """Equivalente ao InterpretadorMiniPar: ponto de entrada do sistema.

    Só conhece IControle; E/S de arquivo fica aqui para o Controle ser puro.
    """

    def __init__(self, controller: IControle) -> None:
        self._controller = controller

    def compile_file(self, source_path: str | Path, output_name: str) -> bool:
        return self._controller.compile(
            Path(source_path).read_text(encoding="utf-8"),
            output_name
        )

    def compile_text(self, source: str, output_name: str) -> bool:
        return self._controller.compile(source, output_name)
