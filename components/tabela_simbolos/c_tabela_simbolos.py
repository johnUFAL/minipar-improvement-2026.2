from __future__ import annotations

from dataclasses import dataclass, field, replace

from components.interfaces import ITabelaSimbolos


@dataclass(frozen=True)
class Symbol:
    name: str
    type: str
    params: tuple[str, ...] = field(default_factory=tuple)
    attributes: dict[str, str] = field(default_factory=dict)
    methods: dict[str, tuple[str, ...]] = field(default_factory=dict)
    category: str = "variable"
    scope: str = "global"
    line: int = 1
    signature: tuple[str, ...] | None = None
    parent_class: str | None = None

    def __post_init__(self) -> None:
        if self.signature is None and self.category in ("function", "method"):
            object.__setattr__(self, "signature", self.params)

    def to_dict(self) -> dict[str, object]:
        return {
            "name": self.name,
            "category": self.category,
            "type": self.type,
            "scope": self.scope,
            "line": self.line,
            "signature": list(self.signature) if self.signature is not None else None,
            "parent_class": self.parent_class,
            "params": list(self.params),
            "attributes": dict(self.attributes),
            "methods": {
                name: list(params) for name, params in self.methods.items()
            },
        }

    @property
    def nome(self) -> str:
        return self.name

    @property
    def categoria(self) -> str:
        return self.category

    @property
    def tipo(self) -> str:
        return self.type

    @property
    def escopo(self) -> str:
        return self.scope

    @property
    def linha(self) -> int:
        return self.line

    @property
    def assinatura(self) -> tuple[str, ...] | None:
        return self.signature

    @property
    def classe_pai(self) -> str | None:
        return self.parent_class


Simbolo = Symbol


@dataclass
class _Scope:
    name: str
    path: str
    parent: _Scope | None
    symbols: dict[str, Symbol] = field(default_factory=dict)
    children: dict[str, _Scope] = field(default_factory=dict)


class TabelaSimbolos(ITabelaSimbolos):
    def __init__(self) -> None:
        self._root = _Scope("global", "global", None)
        self._scopes: list[_Scope] = [self._root]
        self._all_scopes: dict[str, _Scope] = {"global": self._root}
        self._class_scopes: dict[str, str] = {}
        self._scope_counts: dict[tuple[str, str], int] = {}

    @property
    def current_scope_path(self) -> str:
        return self._scopes[-1].path

    def enter_scope(self, name: str | None = None, *, reuse: bool = False) -> None:
        parent = self._scopes[-1]
        scope_name = name or "block"
        if reuse and scope_name in parent.children:
            self._scopes.append(parent.children[scope_name])
            return

        count_key = (parent.path, scope_name)
        count = self._scope_counts.get(count_key, 0) + 1
        self._scope_counts[count_key] = count
        unique_name = scope_name if count == 1 else f"{scope_name}#{count}"
        path = f"{parent.path}/{unique_name}"
        scope = _Scope(unique_name, path, parent)
        parent.children[unique_name] = scope
        self._all_scopes[path] = scope
        self._scopes.append(scope)

    def exit_scope(self) -> None:
        if len(self._scopes) > 1:
            self._scopes.pop()

    def define(self, symbol: Symbol) -> bool:
        scope = self._scopes[-1]
        if symbol.name in scope.symbols:
            return False
        scope.symbols[symbol.name] = (
            symbol if symbol.scope == scope.path else replace(symbol, scope=scope.path)
        )
        return True

    def lookup(self, name: str) -> Symbol | None:
        for scope in reversed(self._scopes):
            symbol = scope.symbols.get(name)
            if symbol is not None:
                return symbol
        return None

    def lookup_local(self, name: str) -> Symbol | None:
        return self._scopes[-1].symbols.get(name)

    def register_class_scope(self, class_name: str, scope_path: str) -> None:
        if scope_path not in self._all_scopes:
            raise ValueError(f"Escopo desconhecido: {scope_path}")
        self._class_scopes[class_name] = scope_path

    def lookup_member(self, class_name: str, name: str) -> Symbol | None:
        visited: set[str] = set()
        current_class: str | None = class_name
        while current_class is not None and current_class not in visited:
            visited.add(current_class)
            scope_path = self._class_scopes.get(current_class)
            if scope_path is not None:
                symbol = self._all_scopes[scope_path].symbols.get(name)
                if symbol is not None:
                    return symbol
            class_symbol = self._root.symbols.get(current_class)
            current_class = (
                class_symbol.parent_class if class_symbol is not None else None
            )
        return None

    def lookup_method(self, class_name: str, name: str) -> Symbol | None:
        symbol = self.lookup_member(class_name, name)
        return symbol if symbol is not None and symbol.category == "method" else None

    def lookup_attribute(self, class_name: str, name: str) -> Symbol | None:
        symbol = self.lookup_member(class_name, name)
        return (
            symbol if symbol is not None and symbol.category == "attribute" else None
        )

    def export(self) -> dict[str, object]:
        scopes: list[dict[str, object]] = []
        for scope in self._all_scopes.values():
            scopes.append(
                {
                    "name": scope.name,
                    "path": scope.path,
                    "parent": scope.parent.path if scope.parent is not None else None,
                    "symbols": [
                        symbol.to_dict() for symbol in scope.symbols.values()
                    ],
                }
            )
        return {"scopes": scopes}

    def entrar_escopo(self, nome: str | None = None) -> None:
        self.enter_scope(nome)

    def sair_escopo(self) -> None:
        self.exit_scope()

    def declarar(self, simbolo: Symbol) -> bool:
        return self.define(simbolo)

    def buscar(self, nome: str) -> Symbol | None:
        return self.lookup(nome)

    def buscar_local(self, nome: str) -> Symbol | None:
        return self.lookup_local(nome)

    def exportar(self) -> dict[str, object]:
        return self.export()
