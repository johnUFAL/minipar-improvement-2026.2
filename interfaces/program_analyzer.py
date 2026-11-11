"""
Análise estática de programas MiniPar — detecta requisitos de entrada
e execução multi-terminal diretamente do código-fonte.
"""
from __future__ import annotations

import os
import re
from typing import Any


def _read_source(path: str) -> str:
    with open(path, encoding="utf-8") as f:
        return f.read()


def _extract_title(source: str, filename: str) -> str:
    for line in source.splitlines():
        line = line.strip()
        if line.startswith("#") and len(line) > 2:
            return line.lstrip("#").strip()
    return os.path.splitext(filename)[0]


def _strip_comments(source: str) -> str:
    """Remove comentários de linha sem afetar o conteúdo de strings."""
    linhas: list[str] = []
    for linha in source.splitlines():
        resultado: list[str] = []
        em_string = False
        escape = False
        for caractere in linha:
            if em_string:
                resultado.append(caractere)
                if escape:
                    escape = False
                elif caractere == "\\":
                    escape = True
                elif caractere == '"':
                    em_string = False
            elif caractere == '"':
                em_string = True
                resultado.append(caractere)
            elif caractere == "#":
                break
            else:
                resultado.append(caractere)
        linhas.append("".join(resultado))
    return "\n".join(linhas)


def _find_inputs(source: str) -> list[dict[str, str]]:
    """Detecta chamadas input() no código MiniPar."""
    inputs: list[dict[str, str]] = []

    # input("prompt") — cada prompt vira uma entrada identificada
    for match in re.finditer(r'input\s*\(\s*"((?:\\.|[^"\\])*)"\s*\)', source):
        prompt = match.group(1).replace("\\n", "\n").replace('\\"', '"')
        if prompt == "":
            continue  # input("") é tratado abaixo (geralmente dentro de loop)
        desc = prompt.strip() if prompt.strip() else "Entrada do teclado"
        inputs.append({"prompt": prompt, "descricao": desc})

    # input() ou input("") sem prompt: expande pelo limite do while (ex.: i < 16)
    bare_count = len(re.findall(r'input\s*\(\s*\)', source))
    empty_quoted = len(re.findall(r'input\s*\(\s*""\s*\)', source))
    empty_total = bare_count + empty_quoted

    if empty_total:
        loop_match = re.search(r'while\s*\(\s*\w+\s*<\s*(\d+)\s*\)', source)
        count = int(loop_match.group(1)) if loop_match else empty_total
        for i in range(count):
            inputs.append({"prompt": "", "descricao": f"Entrada {i + 1}"})

    return inputs


_CHANNEL_DECLARATION = re.compile(
    r"(?m)^\s*c_channel\s+([A-Za-z_]\w*)\s+([A-Za-z_]\w*)\s+([A-Za-z_]\w*)\b"
)
_CHANNEL_FUNCTION = re.compile(r"\bc_channel\s*\(")
_CHANNEL_FUNCTION_DETAIL = re.compile(
    r'c_channel\s*\(\s*"((?:\\.|[^"\\])*)"\s*,\s*(\d+)\s*\)'
)


def _extract_channels(source: str) -> list[dict[str, Any]]:
    """Extrai canais declarativos e chamadas c_channel(host, porta)."""
    channels: list[dict[str, Any]] = []
    for match in _CHANNEL_DECLARATION.finditer(source):
        channels.append({
            "tipo": "declaracao",
            "nome": match.group(1),
            "conecta": match.group(2),
            "escuta": match.group(3),
        })

    for match in _CHANNEL_FUNCTION.finditer(source):
        detail = _CHANNEL_FUNCTION_DETAIL.match(source, match.start())
        channel: dict[str, Any] = {
            "tipo": "funcao",
            "nome": None,
            "conecta": None,
            "escuta": None,
            "host": None,
            "porta": None,
        }
        if detail:
            channel["host"] = detail.group(1)
            channel["porta"] = int(detail.group(2))
        channels.append(channel)

    return channels


def _summarize_roles(channels: list[dict[str, Any]]) -> tuple[list[str], dict[str, str]]:
    roles: list[str] = []
    role_modes: dict[str, str] = {}
    for channel in channels:
        if channel.get("tipo") != "declaracao":
            continue
        for papel, modo in (
            (channel.get("conecta"), "conecta"),
            (channel.get("escuta"), "escuta"),
        ):
            if not isinstance(papel, str):
                continue
            if papel not in roles:
                roles.append(papel)
            if papel not in role_modes:
                role_modes[papel] = modo
            elif role_modes[papel] != modo:
                role_modes[papel] = "indefinido"
    return roles, role_modes


def analyze_program(source_path: str) -> dict[str, Any]:
    """Analisa um arquivo MiniPar e retorna requisitos de execução."""
    filename = os.path.basename(source_path)
    raw_source = _read_source(source_path)
    source = _strip_comments(raw_source)
    titulo = _extract_title(raw_source, filename)
    inputs = _find_inputs(source)

    has_send = bool(re.search(r'\bsend\s*\(', source))
    has_receive = bool(re.search(r'\breceive\s*\(', source))
    has_par = bool(re.search(r'\bpar\s*\{', source))
    channels = _extract_channels(source)
    channel_count = len(channels)
    roles, role_modes = _summarize_roles(channels)
    declarations = [c for c in channels if c.get("tipo") == "declaracao"]
    function_channels = [c for c in channels if c.get("tipo") == "funcao"]
    auto_execution = len(declarations) == 1 and not function_channels

    multi_computer: dict[str, Any] | None = None
    # c_channel + send/receive indica comunicação entre terminais distintos
    if channel_count > 0 and (has_send or has_receive):
        count = max(len(roles), 2)
        if auto_execution:
            instrucoes = (
                "Este programa declara o canal "
                f"'{declarations[0]['nome']}'. Escolha um dos papéis, defina a porta "
                "no lado que escuta e inicie a execução automática."
            )
        elif function_channels and not declarations:
            instrucoes = (
                "Este programa usa c_channel(host, porta) com endereço fixo. "
                "A execução automática entre máquinas exige um par com canal "
                "declarativo (ex.: t01_multiterminal)."
            )
        else:
            instrucoes = (
                "Este programa declara múltiplos canais. A execução automática "
                "aceita um canal declarativo por programa nesta versão."
            )
        multi_computer = {
            "required": True,
            "count": count,
            "roles": roles,
            "role_modes": role_modes,
            "channels": channels,
            "auto_execution": auto_execution,
            "instrucoes": instrucoes,
        }

    return {
        "titulo": titulo,
        "descricao": f"Arquivo: {filename}",
        "filename": filename,
        "inputs": inputs,
        "requires_input": len(inputs) > 0,
        "input_count": len(inputs),
        "multi_computer": multi_computer,
        "has_par": has_par,
        "channel_count": channel_count,
    }


def get_program_spec(source_path: str) -> dict[str, Any]:
    """Retorna spec do programa; analisa o arquivo se existir."""
    if os.path.isfile(source_path):
        return analyze_program(source_path)
    filename = os.path.basename(source_path)
    return {
        "titulo": os.path.splitext(filename)[0],
        "descricao": "",
        "filename": filename,
        "inputs": [],
        "requires_input": False,
        "input_count": 0,
        "multi_computer": None,
        "has_par": False,
        "channel_count": 0,
    }
