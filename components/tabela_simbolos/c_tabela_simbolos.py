from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Symbol:
    name: str
    type: str
    params: tuple[str, ...] = field(default_factory=tuple)
    attributes: dict[str, str] = field(default_factory=dict)
    methods: dict[str, tuple[str, ...]] = field(default_factory=dict)


class TabelaSimbolos:
    def __init__(self) -> None:
        self._scopes: list[dict[str, Symbol]] = [{}]

    def enter_scope(self) -> None:
        self._scopes.append({})

    def exit_scope(self) -> None:
        if len(self._scopes) > 1:
            self._scopes.pop()

    def define(self, symbol: Symbol) -> bool:
        scope = self._scopes[-1]
        if symbol.name in scope:
            return False
        scope[symbol.name] = symbol
        return True

    def lookup(self, name: str) -> Symbol | None:
        for scope in reversed(self._scopes):
            if name in scope:
                return scope[name]
        return None
