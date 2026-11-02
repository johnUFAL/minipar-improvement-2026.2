from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Sequence, cast

from components.codegen.c_gerador_cpp import CppCodeGenerator
from components.codegen.driver_gcc import DriverGCC
from components.controle.c_controle import CControle
from components.interfaces import (
    IGeradorCpp,
    IGeradorTAC,
    ILexico,
    ISemantico,
    ISintatico,
)
from components.lexico.c_lexico import Lexer
from components.lexico.token import TokenType
from components.semantico.c_semantico import SemanticAnalyzer
from components.sintatico.c_sintatico import Parser
from components.tac.c_gerador_tac import TACGenerator
from erros.diagnosticos import DiagnosticBag, Phase


_COMMANDS = ("compilar", "tokens", "ast", "tac", "cpp", "build", "run")
_PHASE_EXIT_CODES = {
    "lexical": 2,
    "syntax": 3,
    "semantic": 4,
    "generation": 5,
    "build": 6,
    "execution": 7,
}


def _optimization_level(value: str) -> str:
    level = value.upper().removeprefix("-")
    if not level.startswith("O"):
        level = f"O{level}"
    if level not in {"O0", "O1", "O2", "O3"}:
        raise argparse.ArgumentTypeError("use um nível de otimização entre O0 e O3")
    return level


def _add_build_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "-O", dest="optimization", type=_optimization_level, default="O2",
        metavar="N",
        help="nível de otimização GCC: -O0, -O1, -O2 ou -O3 (padrão: -O2)",
    )
    parser.add_argument(
        "-o", "--output", type=Path,
        help="caminho do executável de saída",
    )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="minipar",
        description="Compilador MiniPar — inspeção das fases e compilação",
    )
    commands = parser.add_subparsers(dest="command", required=True)

    compile_parser = commands.add_parser(
        "compilar", help="compila um programa MiniPar"
    )
    compile_parser.add_argument("source", type=Path, help="arquivo fonte .mp")
    stages = compile_parser.add_mutually_exclusive_group()
    stages.add_argument("--tokens", action="store_const", const="tokens", dest="stage")
    stages.add_argument("--ast", action="store_const", const="ast", dest="stage")
    stages.add_argument("--tac", action="store_const", const="tac", dest="stage")
    stages.add_argument(
        "--emit-cpp", action="store_const", const="cpp", dest="stage"
    )
    compile_parser.set_defaults(stage="build", execute=False)
    compile_parser.add_argument(
        "--executar", dest="execute", action="store_true",
        help="executa o binário depois de compilar",
    )
    _add_build_options(compile_parser)

    for name in ("tokens", "ast", "tac", "cpp", "build", "run"):
        command_parser = commands.add_parser(
            name, help=f"executa a fase {name} diretamente"
        )
        command_parser.add_argument("source", type=Path, help="arquivo fonte .mp")
        command_parser.set_defaults(stage=name, execute=name == "run")
        _add_build_options(command_parser)

    return parser


def _exit_code(diagnostics: DiagnosticBag, fallback: int) -> int:
    phases = {
        diagnostic.phase.value
        if isinstance(diagnostic.phase, Phase)
        else diagnostic.phase
        for diagnostic in diagnostics
    }
    for phase in ("lexical", "syntax", "semantic", "generation"):
        if phase in phases:
            return _PHASE_EXIT_CODES[phase]
    return fallback


def _report_diagnostics(diagnostics: DiagnosticBag) -> int:
    print(diagnostics.format_text(), file=sys.stderr)
    return _exit_code(diagnostics, 1)


def _read_source(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8")
    except OSError as error:
        print(f"[ERRO] Não foi possível ler '{path}': {error}", file=sys.stderr)
        return None


def _collect_tokens(source: str, diagnostics: DiagnosticBag):
    lexer = Lexer(source, diagnostics)
    tokens = []
    while True:
        token = lexer.next_token()
        tokens.append(token)
        if token.type is TokenType.END_OF_FILE:
            break
    return tokens


def _output_base(source: Path, output: Path | None) -> Path:
    if output is not None:
        return output
    return Path("output") / source.stem


def _compile(args: argparse.Namespace) -> int:
    source_code = _read_source(args.source)
    if source_code is None:
        return 1

    diagnostics = DiagnosticBag(source_code)
    if args.stage == "tokens":
        tokens = _collect_tokens(source_code, diagnostics)
        if diagnostics.has_errors:
            return _report_diagnostics(diagnostics)
        for token in tokens:
            print(
                f"{token.line}:{token.column} "
                f"{token.type.name} {token.lexeme!r}"
            )
        return 0

    controller = CControle(
        cast(ILexico, Lexer()),
        cast(ISintatico, Parser()),
        cast(ISemantico, SemanticAnalyzer()),
        cast(IGeradorTAC, TACGenerator()),
        cast(IGeradorCpp, CppCodeGenerator()),
    )
    program = controller.analyze(
        source_code,
        analyze_semantics=args.stage != "ast",
        diagnostics=diagnostics,
    )
    diagnostics = controller.diagnostics
    if program is None:
        return _report_diagnostics(diagnostics)
    if args.stage == "ast":
        print(json.dumps(program.para_dict(), ensure_ascii=False, indent=2))
        return 0

    if args.stage in {"tac", "cpp", "build", "run"}:
        if not SemanticAnalyzer(diagnostics).analyze(program):
            return _report_diagnostics(diagnostics)
    if diagnostics.has_errors:
        return _report_diagnostics(diagnostics)

    output_base = _output_base(args.source, args.output)
    tac_path = output_base.with_suffix(".tac")
    cpp_path = output_base.with_suffix(".cpp")
    try:
        tac = TACGenerator().generate_text(program)
    except (NotImplementedError, ValueError) as error:
        diagnostics.error(Phase.GENERATION, str(error))
        return _report_diagnostics(diagnostics)

    if args.stage == "tac":
        try:
            tac_path.parent.mkdir(parents=True, exist_ok=True)
            tac_path.write_text(tac, encoding="utf-8")
        except OSError as error:
            diagnostics.error(Phase.GENERATION, f"não foi possível gravar TAC: {error}")
            return _report_diagnostics(diagnostics)
        print(tac, end="" if tac.endswith("\n") else "\n")
        return 0

    try:
        cpp = CppCodeGenerator().generate_source(tac)
        cpp_path.parent.mkdir(parents=True, exist_ok=True)
        cpp_path.write_text(cpp, encoding="utf-8")
    except (NotImplementedError, ValueError, OSError) as error:
        diagnostics.error(Phase.GENERATION, f"falha ao gerar C++: {error}")
        return _report_diagnostics(diagnostics)

    if args.stage == "cpp":
        print(f"[SUCESSO] C++ gerado: {cpp_path}")
        return 0

    try:
        if not DriverGCC().compile(
            cpp_path, args.output or output_base, args.optimization
        ):
            return _PHASE_EXIT_CODES["build"]
    except (OSError, ValueError) as error:
        print(f"[ERRO] Falha na compilação C++: {error}", file=sys.stderr)
        return _PHASE_EXIT_CODES["build"]

    if not args.execute:
        return 0

    try:
        result = DriverGCC().executar(args.output or output_base)
    except OSError as error:
        diagnostics.error(Phase.EXECUTION, f"não foi possível iniciar o programa: {error}")
        print(diagnostics.format_text(), file=sys.stderr)
        return _PHASE_EXIT_CODES["execution"]
    if result.stdout:
        print(result.stdout, end="")
    if result.stderr:
        print(result.stderr, end="", file=sys.stderr)
    return 0 if result.returncode == 0 else _PHASE_EXIT_CODES["execution"]


def run(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    return _compile(args)


def main() -> int:
    return run()


if __name__ == "__main__":
    sys.exit(main())
