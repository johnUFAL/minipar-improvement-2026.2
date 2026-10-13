from __future__ import annotations

import sys
from pathlib import Path

from ..codegen.c_gerador_cpp import CppCodeGenerator
from ..lexico.c_lexico import Lexer
from ..semantico.c_semantico import SemanticAnalyzer
from ..sintatico.c_sintatico import Parser
from ..tac.c_gerador_tac import TACGenerator


class Controle:
    def compile_file(self, source_path: str | Path, output_name: str) -> bool:
        return compile_file(source_path, output_name)


def compile_file(source_path: str | Path, output_name: str) -> bool:
    """Executa as fases léxica, sintática, semântica, TAC e geração C++."""
    source = Path(source_path)
    print(f"\n=== Compilando: {source_path} ===")
    try:
        source_code = source.read_text(encoding="utf-8")
    except FileNotFoundError:
        print(f"[ERRO] Arquivo nao encontrado: {source_path}", file=sys.stderr)
        return False

    print("[Fase 1] Analise Lexica e Sintatica...")
    tokens = Lexer(source_code).tokenize()
    program = Parser(tokens).parse()

    print("[Fase 2] Analise Semantica e Tabela de Simbolos...")
    if not SemanticAnalyzer().analyze(program):
        print("[ERRO] Falha na Analise Semantica. Compilacao abortada.", file=sys.stderr)
        return False

    print("[Fase 3] Geracao de Codigo Intermediario (TAC - 3 enderecos)...")
    tac_path = TACGenerator().generate(program, output_name)
    print(f"[TAC] Arquivo gerado: {tac_path}")

    print("[Fase 4] Transpilacao e Chamada do GCC (-O3)...")
    return CppCodeGenerator().generate(program, output_name)
