from __future__ import annotations

from collections.abc import Sequence
from typing import Literal, Protocol, overload

from erros.diagnosticos import Diagnostic, DiagnosticBag, Phase

from ..lexico.token import Token, TokenType
from .ast import (
    Assignment,
    ASTNode,
    AttributeDecl,
    BinaryExpr,
    BoolExpr,
    BreakStmt,
    ChannelDecl,
    ClassDecl,
    ContinueStmt,
    ForStmt,
    FuncCallExpr,
    FuncDecl,
    IdentifierExpr,
    IfStmt,
    IndexAssign,
    IndexExpr,
    InputExpr,
    ListLiteral,
    MethodCall,
    MethodDecl,
    NewExpr,
    NumberExpr,
    Parameter,
    ParBlock,
    PrintStmt,
    Program,
    PropertyAccess,
    PropertyAssign,
    ReturnStmt,
    SeqBlock,
    StringExpr,
    ThisExpr,
    UnaryExpr,
    VarDecl,
    WhileStmt,
    ForkStmt,
    JoinStmt,
)


class _TokenSource(Protocol):
    def next_token(self) -> Token: ...


class _ParseError(Exception):
    pass


class Parser:
    def __init__(
        self,
        tokens: Sequence[Token] | _TokenSource | None = None,
        diagnostics: DiagnosticBag | None = None,
    ) -> None:
        self._lexer: _TokenSource | None = None
        self._tokens: list[Token] = []
        if isinstance(tokens, Sequence):
            self._tokens.extend(tokens)
        elif tokens is not None:
            self._lexer = tokens
        self._pos = 0
        self._diagnostics = diagnostics if diagnostics is not None else DiagnosticBag()
        self._previous = Token(TokenType.END_OF_FILE, "", 1, 1)

    @property
    def diagnostics(self) -> tuple[Diagnostic, ...]:
        return self._diagnostics.diagnostics

    def set_diagnostic_collector(self, diagnostics: DiagnosticBag) -> None:
        self._diagnostics = diagnostics

    def _fill(self, index: int) -> None:
        while self._lexer is not None and len(self._tokens) <= index:
            token = self._lexer.next_token()
            self._tokens.append(token)
            if token.type is TokenType.END_OF_FILE:
                self._lexer = None

    def _peek(self) -> Token:
        self._fill(self._pos)
        if self._pos >= len(self._tokens):
            return self._tokens[-1] if self._tokens else self._previous
        return self._tokens[self._pos]

    def _advance(self) -> Token:
        token = self._peek()
        if token.type is not TokenType.END_OF_FILE:
            self._pos += 1
            self._previous = token
        return token

    def _match(self, *types: TokenType) -> bool:
        if self._peek().type in types:
            self._advance()
            return True
        return False

    def _consume(self, type_: TokenType, message: str) -> Token:
        if self._peek().type is type_:
            return self._advance()
        token = self._peek()
        self._diagnostics.error(
            Phase.SYNTAX,
            message,
            token.line,
            token.column,
            max(1, len(token.lexeme)),
        )
        raise _ParseError

    def _synchronize(self) -> None:
        while self._peek().type not in (
            TokenType.END_OF_FILE,
            TokenType.NEWLINE,
            TokenType.DEDENT,
        ):
            self._advance()
        self._match(TokenType.NEWLINE)

    def _statement_recovering(self) -> ASTNode | None:
        try:
            return self._statement()
        except _ParseError:
            self._synchronize()
            return None

    def _skip_newlines(self) -> None:
        while self._match(TokenType.NEWLINE):
            pass

    def _suite(self, require_colon: bool = True) -> tuple[ASTNode, ...]:
        if require_colon:
            self._consume(TokenType.COLON, "Esperado ':' antes do bloco")
        self._consume(TokenType.NEWLINE, "Esperada quebra de linha após ':'")
        self._consume(TokenType.INDENT, "Esperado bloco indentado")
        statements: list[ASTNode] = []
        while self._peek().type not in (TokenType.DEDENT, TokenType.END_OF_FILE):
            if self._match(TokenType.NEWLINE):
                continue
            statement = self._statement_recovering()
            if statement is not None:
                statements.append(statement)
        self._consume(TokenType.DEDENT, "Esperado fim do bloco indentado")
        if not statements:
            self._diagnostics.error(
                Phase.SYNTAX, "blocos não podem ser vazios", self._previous.line
            )
        return tuple(statements)

    def _block(self, parallel: bool) -> ASTNode:
        token = self._previous
        statements = self._suite(require_colon=False)
        if parallel:
            return ParBlock(
                statements=statements, line=token.line, column=token.column
            )
        return SeqBlock(statements=statements, line=token.line, column=token.column)

    def _parse_channel(self) -> ChannelDecl:
        keyword = self._previous
        name = self._consume(TokenType.IDENTIFIER, "Esperado nome do canal")
        first_host = self._consume(TokenType.IDENTIFIER, "Esperado primeiro host")
        second_host = self._consume(TokenType.IDENTIFIER, "Esperado segundo host")
        self._consume(TokenType.NEWLINE, "Esperada quebra de linha após declaração")
        return ChannelDecl(
            name=name.lexeme,
            first_host=first_host.lexeme,
            second_host=second_host.lexeme,
            line=keyword.line,
            column=keyword.column,
        )

    def _type_name(self) -> str:
        if self._peek().type is TokenType.TYPE:
            return self._advance().lexeme
        return self._consume(TokenType.IDENTIFIER, "Esperado nome de tipo").lexeme

    @overload
    def _parse_function(self, *, method: Literal[True]) -> MethodDecl: ...

    @overload
    def _parse_function(self, *, method: Literal[False] = False) -> FuncDecl: ...

    def _parse_function(self, *, method: bool = False) -> FuncDecl:
        keyword = self._previous
        name = self._consume(TokenType.IDENTIFIER, "Esperado nome da função")
        self._consume(TokenType.LPAREN, "Esperado '(' após nome da função")
        params: list[Parameter] = []
        if self._peek().type is not TokenType.RPAREN:
            while True:
                param = self._consume(TokenType.IDENTIFIER, "Esperado nome de parâmetro")
                param_type = "var"
                default_value: ASTNode | None = None
                if self._match(TokenType.COLON):
                    param_type = self._type_name()
                if self._match(TokenType.ASSIGN):
                    default_value = self._literal()
                params.append(
                    Parameter(
                        name=param.lexeme,
                        type=param_type,
                        default_value=default_value,
                        line=param.line,
                        column=param.column,
                    )
                )
                if not self._match(TokenType.COMMA):
                    break
        self._consume(TokenType.RPAREN, "Esperado ')' após parâmetros")
        return_type = None
        if self._match(TokenType.ARROW):
            return_type = self._type_name()
        body = SeqBlock(
            statements=self._suite(), line=keyword.line, column=keyword.column
        )
        if method:
            return MethodDecl(
                name=name.lexeme,
                params=tuple(params),
                body=body,
                return_type=return_type,
                line=keyword.line,
                column=keyword.column,
            )
        return FuncDecl(
            name=name.lexeme,
            params=tuple(params),
            body=body,
            return_type=return_type,
            line=keyword.line,
            column=keyword.column,
        )

    def _literal(self) -> ASTNode:
        if self._match(TokenType.MINUS):
            sign = self._previous
            number = self._peek()
            if number.type not in (TokenType.INT_LITERAL, TokenType.FLOAT_LITERAL):
                self._consume(
                    TokenType.INT_LITERAL, "Esperado literal numérico"
                )
            else:
                self._advance()
            return UnaryExpr(
                op="-",
                operand=NumberExpr(
                    value=number.lexeme,
                    line=number.line,
                    column=number.column,
                ),
                line=sign.line,
                column=sign.column,
            )
        token = self._peek()
        if self._match(TokenType.INT_LITERAL, TokenType.FLOAT_LITERAL):
            return NumberExpr(
                value=token.lexeme, line=token.line, column=token.column
            )
        if self._match(TokenType.STRING_LITERAL):
            return StringExpr(
                value=str(token.value), line=token.line, column=token.column
            )
        if self._match(TokenType.BOOL_LITERAL):
            return BoolExpr(value=bool(token.value), line=token.line, column=token.column)
        self._consume(TokenType.INT_LITERAL, "Esperado literal")
        raise _ParseError

    def _parse_class(self) -> ClassDecl:
        keyword = self._previous
        name = self._consume(TokenType.IDENTIFIER, "Esperado nome da classe")
        superclass = None
        if self._match(TokenType.EXTENDS):
            superclass = self._consume(
                TokenType.IDENTIFIER, "Esperado nome da superclasse"
            ).lexeme
        self._consume(TokenType.COLON, "Esperado ':' após nome da classe")
        self._consume(TokenType.NEWLINE, "Esperada quebra de linha")
        self._consume(TokenType.INDENT, "Esperado bloco indentado")
        attributes: list[AttributeDecl] = []
        methods: list[MethodDecl] = []
        while self._peek().type not in (TokenType.DEDENT, TokenType.END_OF_FILE):
            if self._match(TokenType.NEWLINE):
                continue
            if self._match(TokenType.DEF):
                methods.append(self._parse_function(method=True))
                continue
            member = self._consume(TokenType.IDENTIFIER, "Esperado atributo ou método")
            type_name = "var"
            if self._match(TokenType.COLON):
                type_name = self._type_name()
            self._consume(TokenType.ASSIGN, "Esperado '=' após atributo")
            value = self._expression()
            self._consume(TokenType.NEWLINE, "Esperada quebra de linha após atributo")
            attributes.append(
                AttributeDecl(
                    name=member.lexeme,
                    init_value=value,
                    type=type_name,
                    line=member.line,
                    column=member.column,
                )
            )
        self._consume(TokenType.DEDENT, "Esperado fim da classe")
        if not attributes and not methods:
            self._diagnostics.error(
                Phase.SYNTAX, "classes não podem ser vazias", keyword.line
            )
        return ClassDecl(
            name=name.lexeme,
            superclass=superclass,
            attributes=tuple(attributes),
            methods=tuple(methods),
            line=keyword.line,
            column=keyword.column,
        )

    def _statement(self) -> ASTNode:
        if self._match(TokenType.SEQ):
            return self._block(False)
        if self._match(TokenType.PAR):
            return self._block(True)
        if self._match(TokenType.FORK):
            keyword = self._previous
            task = self._consume(TokenType.IDENTIFIER, "Esperado nome da tarefa")
            target_kind = None
            target: ASTNode | None = None
            if self._match(TokenType.EM):
                if self._match(TokenType.CORE):
                    target_kind = "core"
                    self._consume(TokenType.LPAREN, "Esperado '(' após core")
                    target = self._expression()
                    self._consume(TokenType.RPAREN, "Esperado ')' após core")
                elif self._match(TokenType.HOST):
                    target_kind = "host"
                    self._consume(TokenType.LPAREN, "Esperado '(' após host")
                    token = self._peek()
                    if not self._match(TokenType.STRING_LITERAL, TokenType.IDENTIFIER):
                        self._consume(TokenType.STRING_LITERAL, "Esperado host")
                    target = (
                        StringExpr(
                            value=str(token.value),
                            line=token.line,
                            column=token.column,
                        )
                        if token.type is TokenType.STRING_LITERAL
                        else IdentifierExpr(
                            name=token.lexeme,
                            line=token.line,
                            column=token.column,
                        )
                    )
                    self._consume(TokenType.RPAREN, "Esperado ')' após host")
                else:
                    self._consume(TokenType.CORE, "Esperado core ou host")
            body = SeqBlock(
                statements=self._suite(),
                line=keyword.line,
                column=keyword.column,
            )
            return ForkStmt(
                task_name=task.lexeme,
                target_kind=target_kind,
                target=target,
                body=body,
                line=keyword.line,
                column=keyword.column,
            )
        if self._match(TokenType.JOIN):
            keyword = self._previous
            tasks = [self._consume(TokenType.IDENTIFIER, "Esperado nome da tarefa").lexeme]
            while self._match(TokenType.COMMA):
                tasks.append(
                    self._consume(TokenType.IDENTIFIER, "Esperado nome da tarefa").lexeme
                )
            self._consume(TokenType.NEWLINE, "Esperada quebra de linha após join")
            return JoinStmt(
                task_names=tuple(tasks), line=keyword.line, column=keyword.column
            )
        if self._match(TokenType.IF):
            keyword = self._previous
            condition = self._expression()
            then_branch = SeqBlock(
                statements=self._suite(),
                line=keyword.line,
                column=keyword.column,
            )
            else_branch: ASTNode | None = None
            elif_branches: list[tuple[Token, ASTNode, SeqBlock]] = []
            while self._match(TokenType.ELIF):
                elif_keyword = self._previous
                elif_condition = self._expression()
                elif_body = SeqBlock(
                    statements=self._suite(),
                    line=elif_keyword.line,
                    column=elif_keyword.column,
                )
                elif_branches.append((elif_keyword, elif_condition, elif_body))
            if self._match(TokenType.ELSE):
                else_branch = SeqBlock(
                    statements=self._suite(),
                    line=self._previous.line,
                    column=self._previous.column,
                )
            elif_chain: ASTNode | None = else_branch
            for elif_keyword, elif_condition, elif_body in reversed(elif_branches):
                elif_chain = IfStmt(
                    condition=elif_condition,
                    then_branch=elif_body,
                    else_branch=elif_chain,
                    line=elif_keyword.line,
                    column=elif_keyword.column,
                )
            return IfStmt(
                condition=condition,
                then_branch=then_branch,
                else_branch=elif_chain,
                line=keyword.line,
                column=keyword.column,
            )
        if self._match(TokenType.WHILE):
            keyword = self._previous
            condition = self._expression()
            body = SeqBlock(
                statements=self._suite(),
                line=keyword.line,
                column=keyword.column,
            )
            return WhileStmt(
                condition=condition,
                body=body,
                line=keyword.line,
                column=keyword.column,
            )
        if self._match(TokenType.FOR):
            keyword = self._previous
            name = self._consume(TokenType.IDENTIFIER, "Esperado variável do for")
            self._consume(TokenType.IN, "Esperado 'in' no for")
            iterable = self._expression()
            body = SeqBlock(
                statements=self._suite(),
                line=keyword.line,
                column=keyword.column,
            )
            return ForStmt(
                iterator_name=name.lexeme,
                iterable=iterable,
                body=body,
                line=keyword.line,
                column=keyword.column,
            )
        if self._match(TokenType.RETURN):
            keyword = self._previous
            value = None if self._peek().type is TokenType.NEWLINE else self._expression()
            self._consume(TokenType.NEWLINE, "Esperada quebra de linha após return")
            return ReturnStmt(
                value=value, line=keyword.line, column=keyword.column
            )
        if self._match(TokenType.BREAK):
            keyword = self._previous
            self._consume(TokenType.NEWLINE, "Esperada quebra de linha após break")
            return BreakStmt(line=keyword.line, column=keyword.column)
        if self._match(TokenType.CONTINUE):
            keyword = self._previous
            self._consume(TokenType.NEWLINE, "Esperada quebra de linha após continue")
            return ContinueStmt(line=keyword.line, column=keyword.column)
        if self._match(TokenType.PRINT):
            keyword = self._previous
            arguments = self._arguments_in_parens()
            self._consume(TokenType.NEWLINE, "Esperada quebra de linha após print")
            return PrintStmt(
                arguments=arguments, line=keyword.line, column=keyword.column
            )
        return self._simple_statement()

    def _simple_statement(self) -> ASTNode:
        expression = self._expression()
        if self._match(TokenType.COLON):
            if not isinstance(expression, IdentifierExpr):
                self._diagnostics.error(
                    Phase.SYNTAX, "declaração tipada exige um identificador",
                    expression.line,
                )
                raise _ParseError
            type_name = self._type_name()
            self._consume(TokenType.ASSIGN, "Esperado '=' após tipo")
            value = self._expression()
            self._consume(TokenType.NEWLINE, "Esperada quebra de linha")
            return VarDecl(
                name=expression.name, init_value=value, type=type_name,
                line=expression.line,
                column=expression.column,
            )
        operator = self._peek()
        if self._match(
            TokenType.ASSIGN, TokenType.PLUS_ASSIGN, TokenType.MINUS_ASSIGN,
            TokenType.STAR_ASSIGN, TokenType.SLASH_ASSIGN,
        ):
            value = self._expression()
            self._consume(TokenType.NEWLINE, "Esperada quebra de linha após atribuição")
            if operator.type is not TokenType.ASSIGN:
                value = BinaryExpr(
                    op=operator.lexeme,
                    left=expression,
                    right=value,
                    line=operator.line,
                    column=operator.column,
                )
            if isinstance(expression, IdentifierExpr):
                return Assignment(
                    name=expression.name,
                    value=value,
                    line=expression.line,
                    column=expression.column,
                )
            if isinstance(expression, PropertyAccess):
                return PropertyAssign(
                    object=expression.object,
                    property_name=expression.property_name,
                    value=value,
                    line=expression.line,
                    column=expression.column,
                )
            if isinstance(expression, IndexExpr):
                return IndexAssign(
                    target=expression,
                    value=value,
                    line=expression.line,
                    column=expression.column,
                )
            self._diagnostics.error(
                Phase.SYNTAX, "alvo inválido para atribuição", expression.line
            )
            raise _ParseError
        self._consume(TokenType.NEWLINE, "Esperada quebra de linha após expressão")
        if isinstance(expression, (FuncCallExpr, MethodCall)):
            return expression
        self._diagnostics.error(
            Phase.SYNTAX, "expressão isolada não é uma instrução", expression.line
        )
        raise _ParseError

    def _arguments_in_parens(self) -> tuple[ASTNode, ...]:
        self._consume(TokenType.LPAREN, "Esperado '('")
        args: list[ASTNode] = []
        if self._peek().type is not TokenType.RPAREN:
            args.append(self._expression())
            while self._match(TokenType.COMMA):
                args.append(self._expression())
        self._consume(TokenType.RPAREN, "Esperado ')'")
        return tuple(args)

    def _expression(self) -> ASTNode:
        return self._parse_or()

    def _binary(self, parse_operand, operators: tuple[TokenType, ...]) -> ASTNode:
        expression = parse_operand()
        while self._peek().type in operators:
            operator = self._advance()
            right = parse_operand()
            expression = BinaryExpr(
                op=operator.lexeme,
                left=expression,
                right=right,
                line=operator.line,
                column=operator.column,
            )
        return expression

    def _parse_or(self) -> ASTNode:
        return self._binary(self._parse_and, (TokenType.OR,))

    def _parse_and(self) -> ASTNode:
        return self._binary(self._parse_not, (TokenType.AND,))

    def _parse_not(self) -> ASTNode:
        if self._match(TokenType.NOT):
            operator = self._previous
            return UnaryExpr(
                op=operator.lexeme,
                operand=self._parse_not(),
                line=operator.line,
                column=operator.column,
            )
        return self._parse_comparison()

    def _parse_comparison(self) -> ASTNode:
        expression = self._parse_sum()
        if self._match(
            TokenType.EQ, TokenType.NEQ, TokenType.LT, TokenType.GT,
            TokenType.LTE, TokenType.GTE,
        ):
            operator = self._previous
            expression = BinaryExpr(
                op=operator.lexeme,
                left=expression,
                right=self._parse_sum(),
                line=operator.line,
                column=operator.column,
            )
            if self._peek().type in (
                TokenType.EQ, TokenType.NEQ, TokenType.LT, TokenType.GT,
                TokenType.LTE, TokenType.GTE,
            ):
                self._diagnostics.error(
                    Phase.SYNTAX, "comparações encadeadas não são permitidas",
                    self._peek().line, self._peek().column,
                )
                raise _ParseError
        return expression

    def _parse_sum(self) -> ASTNode:
        return self._binary(self._parse_product, (TokenType.PLUS, TokenType.MINUS))

    def _parse_product(self) -> ASTNode:
        return self._binary(
            self._parse_unary,
            (TokenType.STAR, TokenType.SLASH, TokenType.MOD),
        )

    def _parse_unary(self) -> ASTNode:
        if self._match(TokenType.MINUS, TokenType.PLUS):
            operator = self._previous
            return UnaryExpr(
                op=operator.lexeme,
                operand=self._parse_unary(),
                line=operator.line,
                column=operator.column,
            )
        return self._parse_postfix()

    def _parse_postfix(self) -> ASTNode:
        expression = self._primary()
        while True:
            if self._match(TokenType.DOT):
                prop = self._consume(TokenType.IDENTIFIER, "Esperado nome após '.'")
                if self._match(TokenType.LPAREN):
                    args: list[ASTNode] = []
                    if self._peek().type is not TokenType.RPAREN:
                        args.append(self._expression())
                        while self._match(TokenType.COMMA):
                            args.append(self._expression())
                    self._consume(TokenType.RPAREN, "Esperado ')' após argumentos")
                    expression = MethodCall(
                        object=expression,
                        method_name=prop.lexeme,
                        arguments=tuple(args),
                        line=prop.line,
                        column=prop.column,
                    )
                else:
                    expression = PropertyAccess(
                        object=expression,
                        property_name=prop.lexeme,
                        line=prop.line,
                        column=prop.column,
                    )
            elif self._match(TokenType.LBRACKET):
                index = self._expression()
                self._consume(TokenType.RBRACKET, "Esperado ']'")
                expression = IndexExpr(
                    object=expression,
                    index=index,
                    line=expression.line,
                    column=expression.column,
                )
            else:
                return expression

    def _primary(self) -> ASTNode:
        token = self._peek()
        if self._match(TokenType.INT_LITERAL, TokenType.FLOAT_LITERAL):
            return NumberExpr(
                value=token.lexeme, line=token.line, column=token.column
            )
        if self._match(TokenType.STRING_LITERAL):
            return StringExpr(
                value=str(token.value), line=token.line, column=token.column
            )
        if self._match(TokenType.BOOL_LITERAL):
            return BoolExpr(
                value=bool(token.value), line=token.line, column=token.column
            )
        if self._match(TokenType.SELF):
            return ThisExpr(line=token.line, column=token.column)
        if self._match(TokenType.INPUT):
            input_args = self._arguments_in_parens()
            return InputExpr(
                prompt=input_args[0] if input_args else None,
                line=token.line,
                column=token.column,
            )
        if self._match(TokenType.NEW):
            name = self._consume(TokenType.IDENTIFIER, "Esperado nome da classe")
            return NewExpr(
                class_name=name.lexeme,
                arguments=self._arguments_in_parens(),
                line=token.line,
                column=token.column,
            )
        if self._match(TokenType.IDENTIFIER):
            if self._match(TokenType.LPAREN):
                call_args: list[ASTNode] = []
                if self._peek().type is not TokenType.RPAREN:
                    call_args.append(self._expression())
                    while self._match(TokenType.COMMA):
                        call_args.append(self._expression())
                self._consume(TokenType.RPAREN, "Esperado ')' após argumentos")
                return FuncCallExpr(
                    name=token.lexeme,
                    arguments=tuple(call_args),
                    line=token.line,
                    column=token.column,
                )
            return IdentifierExpr(
                name=token.lexeme, line=token.line, column=token.column
            )
        if self._match(TokenType.LBRACKET):
            list_elements: list[ASTNode] = []
            if self._peek().type is not TokenType.RBRACKET:
                list_elements.append(self._expression())
                while self._match(TokenType.COMMA):
                    list_elements.append(self._expression())
            self._consume(TokenType.RBRACKET, "Esperado ']'")
            return ListLiteral(
                elements=tuple(list_elements),
                line=token.line,
                column=token.column,
            )
        if self._match(TokenType.LPAREN):
            expression = self._expression()
            self._consume(TokenType.RPAREN, "Esperado ')'")
            return expression
        self._diagnostics.error(
            Phase.SYNTAX,
            f"Esperada expressão; encontrado {token.lexeme!r}",
            token.line,
            token.column,
            max(1, len(token.lexeme)),
        )
        raise _ParseError

    def parse(
        self,
        lexer: _TokenSource | None = None,
        semantic_analyzer: object | None = None,
    ) -> Program:
        if lexer is not None:
            self._lexer = lexer
            self._tokens.clear()
            self._pos = 0
        statements: list[ASTNode] = []
        self._skip_newlines()
        while self._peek().type not in (TokenType.SEQ, TokenType.PAR, TokenType.END_OF_FILE):
            try:
                if self._match(TokenType.C_CHANNEL):
                    statements.append(self._parse_channel())
                elif self._match(TokenType.DEF):
                    statements.append(self._parse_function())
                elif self._match(TokenType.CLASS):
                    statements.append(self._parse_class())
                else:
                    self._consume(
                        TokenType.SEQ,
                        "Esperada declaração ou bloco raiz SEQ/PAR",
                    )
                self._skip_newlines()
            except _ParseError:
                self._synchronize()
        if self._match(TokenType.SEQ):
            statements.append(self._block(False))
        elif self._match(TokenType.PAR):
            statements.append(self._block(True))
        else:
            self._diagnostics.error(
                Phase.SYNTAX, "Esperado bloco raiz SEQ ou PAR",
                self._peek().line, self._peek().column,
            )
        while self._match(TokenType.NEWLINE):
            pass
        self._consume(TokenType.END_OF_FILE, "Conteúdo após o bloco raiz")
        return Program(statements=tuple(statements))
