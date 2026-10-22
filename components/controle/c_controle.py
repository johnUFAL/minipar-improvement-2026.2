from __future__ import annotations

import sys
from pathlib import Path

from ..codegen.c_gerador_cpp import CppCodeGenerator
from ..lexico.c_lexico import Lexer
from ..semantico.c_semantico import SemanticAnalyzer
from ..sintatico.c_sintatico import Parser
from ..tac.c_gerador_tac import TACGenerator
from ..interfaces import (
    IControle,
    IGeradorCpp,
    IGeradorTAC,
    ILexico,
    ISemantico,
    ISintatico,
)
from erros.diagnosticos import DiagnosticBag, Phase


class CControle(IControle):
    """Componente Controle: sabe a ORDEM das fases, não como cada uma funciona."""

    def __init__(
        self,
        lexer: ILexico,
        parser: ISintatico,
        semantic_analyzer: ISemantico,
        tac_generator: IGeradorTAC,
        cpp_generator: IGeradorCpp,
    ) -> None:
        self._lexer = lexer
        self._parser = parser
        self._semantic_analyzer = semantic_analyzer
        self._tac_generator = tac_generator
        self._cpp_generator = cpp_generator
        self.diagnostics = DiagnosticBag()

    def compile(self, source: str, output_name: str) -> bool:
        self.diagnostics = DiagnosticBag(source)
        for component in (self._lexer, self._parser, self._semantic_analyzer):
            set_collector = getattr(component, "set_diagnostic_collector", None)
            if callable(set_collector):
                set_collector(self.diagnostics)

        self._lexer.initialize(source)
        program = self._parser.parse(self._lexer, self._semantic_analyzer)
        for component in (self._lexer, self._parser, self._semantic_analyzer):
            component_diagnostics = getattr(component, "diagnostics", ())
            for diagnostic in component_diagnostics:
                if diagnostic not in self.diagnostics.diagnostics:
                    self.diagnostics.report(diagnostic)

        if self.diagnostics.has_errors:
            print(self.diagnostics.format_text(), file=sys.stderr)
            return False
        self._tac_generator.generate(program, output_name)
        success = self._cpp_generator.generate(program, output_name)
        if not success:
            self.diagnostics.error(Phase.GENERATION, "C++ code generation failed")
            print(self.diagnostics.format_text(), file=sys.stderr)
        return success


class Controle:
    def compile_file(self, source_path: str | Path, output_name: str) -> bool:
        return compile_file(source_path, output_name)


def compile_file(
    source_path: str | Path,
    output_name: str,
    diagnostics: DiagnosticBag | None = None,
) -> bool:
    """Executa as fases léxica, sintática, semântica, TAC e geração C++."""
    source = Path(source_path)
    print(f"\n=== Compilando: {source_path} ===")
    try:
        source_code = source.read_text(encoding="utf-8")
    except FileNotFoundError:
        print(f"[ERRO] Arquivo nao encontrado: {source_path}", file=sys.stderr)
        return False

    print("[Fase 1] Analise Lexica e Sintatica...")
    collector = diagnostics if diagnostics is not None else DiagnosticBag(source_code)
    tokens = Lexer(source_code, collector).tokenize()
    program = Parser(tokens, collector).parse()

    print("[Fase 2] Analise Semantica e Tabela de Simbolos...")
    SemanticAnalyzer(collector).analyze(program)
    if collector.has_errors:
        print(collector.format_text(), file=sys.stderr)
        return False

    print("[Fase 3] Geracao de Codigo Intermediario (TAC - 3 enderecos)...")
    tac_path = TACGenerator().generate(program, output_name)
    print(f"[TAC] Arquivo gerado: {tac_path}")

    print("[Fase 4] Transpilacao e Chamada do GCC (-O3)...")
    success = CppCodeGenerator().generate(program, output_name)
    if not success:
        collector.error(Phase.GENERATION, "C++ code generation failed")
        print(collector.format_text(), file=sys.stderr)
    return success
