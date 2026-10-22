from __future__ import annotations

from typing import cast

from erros.diagnosticos import Diagnostic, DiagnosticBag, Phase

from ..lexico.token import Token, TokenType
from .ast import (
    Assignment,
    ASTNode,
    BinaryExpr,
    BoolExpr,
    BreakStmt,
    CChannelExpr,
    ClassDecl,
    ContinueStmt,
    DoWhileStmt,
    ForStmt,
    FuncCallExpr,
    FuncDecl,
    IdentifierExpr,
    IfStmt,
    IndexAssign,
    IndexExpr,
    InputExpr,
    ListLiteral,
    MatrixCreateExpr,
    MethodCall,
    NewExpr,
    NumberExpr,
    ParBlock,
    PrintStmt,
    Program,
    PropertyAccess,
    PropertyAssign,
    ReceiveExpr,
    ReturnStmt,
    SendStmt,
    SeqBlock,
    StringExpr,
    ThisExpr,
    UnaryExpr,
    VarDecl,
    WhileStmt,
)


class _ParseError(Exception):
    pass


class Parser:
    def __init__(
        self, tokens: list[Token], diagnostics: DiagnosticBag | None = None
    ) -> None:
        self._tokens = tokens
        self._pos = 0
        self._diagnostics = diagnostics if diagnostics is not None else DiagnosticBag()

    @property
    def diagnostics(self) -> tuple[Diagnostic, ...]:
        return self._diagnostics.diagnostics

    def set_diagnostic_collector(self, diagnostics: DiagnosticBag) -> None:
        self._diagnostics = diagnostics

    def _peek(self) -> Token:
        if self._pos >= len(self._tokens):
            return self._tokens[-1]
        return self._tokens[self._pos]

    def _advance(self) -> Token:
        token = self._tokens[self._pos]
        if self._pos < len(self._tokens):
            self._pos += 1
        return token

    def _match(self, token_type: TokenType) -> bool:
        if self._peek().type == token_type:
            self._advance()
            return True
        return False

    def _consume(self, token_type: TokenType, err_msg: str) -> Token:
        if self._peek().type == token_type:
            return self._advance()
        tok = self._peek()
        self._syntax_error(
            tok, f"{err_msg} (encontrado {tok.lexeme!r})"
        )
        raise _ParseError

    def _syntax_error(self, token: Token, message: str) -> None:
        if self._diagnostics is not None:
            self._diagnostics.error(
                Phase.SYNTAX,
                message,
                token.line,
                token.column,
                max(1, len(token.lexeme)),
            )

    def _synchronize(self) -> None:
        if self._peek().type in (TokenType.END_OF_FILE, TokenType.RBRACE):
            return
        statement_starters = {
            TokenType.CLASS, TokenType.FUNC, TokenType.RETURN, TokenType.BREAK,
            TokenType.CONTINUE, TokenType.VAR, TokenType.TYPE, TokenType.SEQ,
            TokenType.PAR, TokenType.PRINT, TokenType.SEND, TokenType.IF,
            TokenType.WHILE, TokenType.DO, TokenType.FOR,
        }
        if self._peek().type in statement_starters:
            return
        while self._peek().type not in (
            TokenType.END_OF_FILE, TokenType.RBRACE, TokenType.SEMICOLON,
        ):
            if self._peek().type in statement_starters:
                return
            self._advance()
        if self._peek().type == TokenType.SEMICOLON:
            self._advance()

    def _parse_statement_recovering(self) -> ASTNode | None:
        try:
            return self._parse_statement()
        except _ParseError:
            self._synchronize()
            return None

    def _parse_var_decl(
        self,
        declared_type: str = "var",
        require_semicolon: bool = True
    ) -> ASTNode:
        line = self._peek().line
        name = self._consume(
            TokenType.IDENTIFIER, "Esperado nome da variavel"
        ).lexeme
        init_value = self._parse_expression() if self._match(TokenType.ASSIGN) else None
        if require_semicolon:
            self._consume(
                TokenType.SEMICOLON, "Esperado ';' apos declaracao de variavel"
            )
        return VarDecl(
            name=name,
            init_value=init_value,
            type=declared_type,
            line=line,
        )

    def _parse_assignment_tail(self, target: ASTNode, require_semicolon: bool = True) -> ASTNode:
        val = self._parse_expression()
        if require_semicolon:
            self._consume(TokenType.SEMICOLON, "Esperado ';'")
        if isinstance(target, IdentifierExpr):
            return Assignment(name=target.name, value=val, line=target.line)
        if isinstance(target, PropertyAccess):
            return PropertyAssign(
                object=target.object,
                property_name=target.property_name,
                value=val,
                line=target.line
            )
        if isinstance(target, IndexExpr):
            return IndexAssign(target=target, value=val, line=target.line)
        token = self._tokens[max(0, self._pos - 1)]
        self._syntax_error(token, "invalid assignment target")
        raise _ParseError

    def _parse_print_stmt(self) -> ASTNode:
        line = self._peek().line
        arguments: list[ASTNode] = []
        self._consume(TokenType.LPAREN, "Esperado '(' apos print")
        if self._peek().type != TokenType.RPAREN:
            arguments.append(self._parse_expression())
            while self._match(TokenType.COMMA):
                arguments.append(self._parse_expression())
        self._consume(TokenType.RPAREN, "Esperado ')' apos argumentos do print")
        self._consume(TokenType.SEMICOLON, "Esperado ';' apos print")
        return PrintStmt(arguments=tuple(arguments), line=line)

    def _parse_send_stmt(self) -> ASTNode:
        line = self._tokens[self._pos - 1].line
        self._consume(TokenType.LPAREN, "Esperado '(' apos send")
        channel = self._parse_expression()
        self._consume(TokenType.COMMA, "Esperado ',' entre canal e mensagem")
        message = self._parse_expression()
        self._consume(TokenType.RPAREN, "Esperado ')'")
        self._consume(TokenType.SEMICOLON, "Esperado ';'")
        return SendStmt(channel=channel, message=message, line=line)

    def _parse_seq_block(self) -> ASTNode:
        statements: list[ASTNode] = []
        self._consume(TokenType.LBRACE, "Esperado '{' para iniciar bloco")
        while self._peek().type not in (TokenType.RBRACE, TokenType.END_OF_FILE):
            statement = self._parse_statement_recovering()
            if statement is not None:
                statements.append(statement)
        self._consume(TokenType.RBRACE, "Esperado '}' para fechar bloco")
        return SeqBlock(statements=tuple(statements))

    def _parse_par_block(self) -> ASTNode:
        statements: list[ASTNode] = []
        self._consume(TokenType.LBRACE, "Esperado '{' para iniciar bloco PAR")
        while self._peek().type not in (TokenType.RBRACE, TokenType.END_OF_FILE):
            statement = self._parse_statement_recovering()
            if statement is not None:
                statements.append(statement)
        self._consume(TokenType.RBRACE, "Esperado '}' para fechar bloco PAR")
        return ParBlock(statements=tuple(statements))

    def _parse_if_stmt(self) -> ASTNode:
        line = self._tokens[self._pos - 1].line
        self._consume(TokenType.LPAREN, "Esperado '(' apos 'if'")
        condition = self._parse_expression()
        self._consume(TokenType.RPAREN, "Esperado ')' apos condicao do 'if'")
        then_branch = self._parse_statement()
        else_branch = self._parse_statement() if self._match(TokenType.ELSE) else None
        return IfStmt(
            condition=condition,
            then_branch=then_branch,
            else_branch=else_branch,
            line=line
        )

    def _parse_while_stmt(self) -> ASTNode:
        line = self._tokens[self._pos - 1].line
        self._consume(TokenType.LPAREN, "Esperado '(' apos 'while'")
        condition = self._parse_expression()
        self._consume(TokenType.RPAREN, "Esperado ')' apos condicao")
        body = self._parse_statement()
        return WhileStmt(condition=condition, body=body, line=line)

    def _parse_do_while_stmt(self) -> ASTNode:
        line = self._tokens[self._pos - 1].line
        body = self._parse_statement()
        self._consume(TokenType.WHILE, "Esperado 'while' apos bloco do")
        self._consume(TokenType.LPAREN, "Esperado '(' apos 'while'")
        condition = self._parse_expression()
        self._consume(TokenType.RPAREN, "Esperado ')' apos condicao")
        self._match(TokenType.SEMICOLON)
        return DoWhileStmt(body=body, condition=condition, line=line)

    def _parse_for_stmt(self) -> ASTNode:
        line = self._tokens[self._pos - 1].line
        self._consume(TokenType.LPAREN, "Esperado '(' apos 'for'")

        initializer: ASTNode | None = None
        condition: ASTNode | None = None
        increment: ASTNode | None = None
        iterator_name: str | None = None
        iterable: ASTNode | None = None

        if self._match(TokenType.VAR):
            name_tok = self._consume(TokenType.IDENTIFIER, "Esperado variavel do for")
            if self._match(TokenType.IN):
                iterator_name = name_tok.lexeme
                iterable = self._parse_expression()
                self._consume(TokenType.RPAREN, "Esperado ')' apos iteravel")
                body = self._parse_statement()
                return ForStmt(
                    body=body,
                    iterator_name=iterator_name,
                    iterable=iterable,
                    line=line,
                )
            init_value = (
                self._parse_expression() if self._match(TokenType.ASSIGN) else None
            )
            initializer = VarDecl(
                name=name_tok.lexeme,
                init_value=init_value,
                type="var",
                line=name_tok.line,
            )
            self._consume(TokenType.SEMICOLON, "Esperado ';' apos inicializador do for")
        elif self._peek().type == TokenType.TYPE:
            type_tok = self._advance()
            initializer = self._parse_var_decl(type_tok.lexeme, require_semicolon=False)
            self._consume(TokenType.SEMICOLON, "Esperado ';' apos inicializador do for")
        elif not self._match(TokenType.SEMICOLON):
            target = self._parse_expression()
            if self._match(TokenType.ASSIGN):
                initializer = self._parse_assignment_tail(
                    target,
                    require_semicolon=False
                )
            else:
                initializer = target
            self._consume(TokenType.SEMICOLON, "Esperado ';' apos inicializador do for")

        if not self._match(TokenType.SEMICOLON):
            condition = self._parse_expression()
            self._consume(TokenType.SEMICOLON, "Esperado ';' apos condicao do for")

        if self._peek().type != TokenType.RPAREN:
            target = self._parse_expression()
            if self._match(TokenType.ASSIGN):
                increment = self._parse_assignment_tail(target, require_semicolon=False)
            else:
                increment = target
        self._consume(TokenType.RPAREN, "Esperado ')' apos for")
        body = self._parse_statement()
        return ForStmt(
            initializer=initializer,
            condition=condition,
            increment=increment,
            body=body,
            line=line,
        )

    def _parse_class_decl(self) -> ASTNode:
        line = self._tokens[self._pos - 1].line
        name = self._consume(TokenType.IDENTIFIER, "Esperado nome da classe").lexeme
        superclass = self._consume(
            TokenType.IDENTIFIER, "Esperado nome da superclasse").lexeme if self._match(
                TokenType.EXTENDS
            ) else None
        self._consume(TokenType.LBRACE, "Esperado '{' na classe")

        attrs: list[VarDecl] = []
        methods: list[FuncDecl] = []

        while self._peek().type not in (TokenType.RBRACE, TokenType.END_OF_FILE):
            if self._match(TokenType.VAR):
                try:
                    attrs.append(cast(VarDecl, self._parse_var_decl()))
                except _ParseError:
                    self._synchronize()
            elif self._match(TokenType.FUNC):
                try:
                    methods.append(cast(FuncDecl, self._parse_func_decl()))
                except _ParseError:
                    self._synchronize()
            else:
                self._syntax_error(
                    self._peek(), "expected 'var' or 'func' in class definition"
                )
                raise _ParseError
        self._consume(TokenType.RBRACE, "Esperado '}' no fim da classe")

        return ClassDecl(
            name=name,
            superclass=superclass,
            attributes=tuple(attrs),
            methods=tuple(methods),
            line=line
        )

    def _parse_func_decl(self) -> ASTNode:
        line = self._tokens[self._pos - 1].line
        name = self._consume(TokenType.IDENTIFIER, "Esperado nome da funcao").lexeme
        self._consume(TokenType.LPAREN, "Esperado '('")
        params: list[str] = []
        if self._peek().type != TokenType.RPAREN:
            if self._peek().type == TokenType.TYPE:
                self._advance()
            params.append(
                self._consume(TokenType.IDENTIFIER, "Esperado parametro").lexeme
            )
            while self._match(TokenType.COMMA):
                if self._peek().type == TokenType.TYPE:
                    self._advance()
                params.append(
                    self._consume(TokenType.IDENTIFIER, "Esperado parametro").lexeme
                )
        self._consume(TokenType.RPAREN, "Esperado ')'")
        body = self._parse_seq_block()
        return FuncDecl(name=name, params=tuple(params), body=body, line=line)

    def _parse_return_stmt(self) -> ASTNode:
        line = self._tokens[self._pos - 1].line
        value = None if self._peek().type == TokenType.SEMICOLON else self._parse_expression()
        self._match(TokenType.SEMICOLON)
        return ReturnStmt(value=value, line=line)

    def _parse_statement(self) -> ASTNode:
        if self._match(TokenType.CLASS):
            return self._parse_class_decl()
        if self._match(TokenType.FUNC):
            return self._parse_func_decl()
        if self._match(TokenType.RETURN):
            return self._parse_return_stmt()
        if self._match(TokenType.BREAK):
            line = self._tokens[self._pos - 1].line
            self._match(TokenType.SEMICOLON)
            return BreakStmt(line=line)
        if self._match(TokenType.CONTINUE):
            line = self._tokens[self._pos - 1].line
            self._match(TokenType.SEMICOLON)
            return ContinueStmt(line=line)
        if self._match(TokenType.VAR):
            return self._parse_var_decl()
        if self._peek().type == TokenType.TYPE:
            type_tok = self._advance()
            return self._parse_var_decl(type_tok.lexeme)
        if self._match(TokenType.SEQ) or self._peek().type == TokenType.LBRACE:
            if self._peek().type == TokenType.SEQ:
                self._advance()
            return self._parse_seq_block()
        if self._match(TokenType.PAR):
            return self._parse_par_block()
        if self._match(TokenType.PRINT):
            return self._parse_print_stmt()
        if self._match(TokenType.SEND):
            return self._parse_send_stmt()
        if self._match(TokenType.IF):
            return self._parse_if_stmt()
        if self._match(TokenType.WHILE):
            return self._parse_while_stmt()
        if self._match(TokenType.DO):
            return self._parse_do_while_stmt()
        if self._match(TokenType.FOR):
            return self._parse_for_stmt()

        if self._peek().type in (TokenType.IDENTIFIER, TokenType.THIS, TokenType.NEW, TokenType.RECEIVE, TokenType.INPUT, TokenType.C_CHANNEL, TokenType.MATRIX, TokenType.LBRACKET):
            expr = self._parse_expression()
            if self._match(TokenType.ASSIGN):
                return self._parse_assignment_tail(expr)
            elif isinstance(expr, (MethodCall, FuncCallExpr)):
                self._consume(TokenType.SEMICOLON, "Esperado ';'")
                return expr
            token = self._tokens[max(0, self._pos - 1)]
            self._syntax_error(token, "invalid standalone expression")
            raise _ParseError

        tok = self._peek()
        self._syntax_error(tok, f"unrecognized statement {tok.lexeme!r}")
        raise _ParseError

    def _parse_expression(self) -> ASTNode:
        return self._parse_or()

    def _parse_or(self) -> ASTNode:
        expr = self._parse_and()
        while self._match(TokenType.OR):
            op_tok = self._tokens[self._pos - 1]
            expr = BinaryExpr(
                op=op_tok.lexeme,
                left=expr,
                right=self._parse_and(),
                line=op_tok.line
            )
        return expr

    def _parse_and(self) -> ASTNode:
        expr = self._parse_comparison()
        while self._match(TokenType.AND):
            op_tok = self._tokens[self._pos - 1]
            expr = BinaryExpr(
                op=op_tok.lexeme,
                left=expr,
                right=self._parse_comparison(),
                line=op_tok.line
            )
        return expr

    def _parse_comparison(self) -> ASTNode:
        expr = self._parse_term()
        while self._peek().type in (
                TokenType.EQ,
                TokenType.NEQ,
                TokenType.LT,
                TokenType.GT,
                TokenType.LTE,
                TokenType.GTE
        ):
            op_tok = self._advance()
            expr = BinaryExpr(
                op=op_tok.lexeme,
                left=expr,
                right=self._parse_term(),
                line=op_tok.line,
            )
        return expr

    def _parse_term(self) -> ASTNode:
        expr = self._parse_factor()
        while self._peek().type in (TokenType.PLUS, TokenType.MINUS):
            op_tok = self._advance()
            expr = BinaryExpr(
                op=op_tok.lexeme,
                left=expr,
                right=self._parse_factor(),
                line=op_tok.line,
            )
        return expr

    def _parse_factor(self) -> ASTNode:
        expr = self._parse_unary()
        while self._peek().type in (TokenType.STAR, TokenType.SLASH, TokenType.MOD):
            op_tok = self._advance()
            expr = BinaryExpr(
                op=op_tok.lexeme,
                left=expr,
                right=self._parse_unary(),
                line=op_tok.line,
            )
        return expr

    def _parse_unary(self) -> ASTNode:
        if self._peek().type in (TokenType.MINUS, TokenType.PLUS, TokenType.NOT):
            op_tok = self._advance()
            return UnaryExpr(
                op=op_tok.lexeme,
                operand=self._parse_unary(),
                line=op_tok.line,
            )
        return self._parse_primary()

    def _parse_primary(self) -> ASTNode:
        tok = self._peek()
        node: ASTNode | None = None

        if self._match(TokenType.MATRIX):
            line = tok.line
            self._consume(TokenType.LPAREN, "Esperado '(' apos matrix")
            rows = self._parse_expression()
            self._consume(TokenType.COMMA, "Esperado ','")
            cols = self._parse_expression()
            self._consume(TokenType.COMMA, "Esperado ','")
            init_val = self._parse_expression()
            self._consume(TokenType.RPAREN, "Esperado ')'")
            node = MatrixCreateExpr(
                rows=rows,
                cols=cols,
                init_value=init_val,
                line=line
            )
        elif self._match(TokenType.LBRACKET):
            line = tok.line
            elements = []
            if self._peek().type != TokenType.RBRACKET:
                elements.append(self._parse_expression())
                while self._match(TokenType.COMMA):
                    elements.append(self._parse_expression())
            self._consume(TokenType.RBRACKET, "Esperado ']'")
            node = ListLiteral(elements=tuple(elements), line=line)
        elif self._match(TokenType.C_CHANNEL):
            line = tok.line
            self._consume(TokenType.LPAREN, "Esperado '(' apos c_channel")
            ip = self._parse_expression()
            self._consume(TokenType.COMMA, "Esperado ',' entre ip e porta")
            port = self._parse_expression()
            self._consume(TokenType.RPAREN, "Esperado ')'")
            node = CChannelExpr(ip=ip, port=port, line=line)
        elif self._match(TokenType.RECEIVE):
            line = tok.line
            self._consume(TokenType.LPAREN, "Esperado '(' apos receive")
            channel = self._parse_expression()
            self._consume(TokenType.RPAREN, "Esperado ')'")
            node = ReceiveExpr(channel=channel, line=line)
        elif self._match(TokenType.INPUT):
            line = tok.line
            self._consume(TokenType.LPAREN, "Esperado '(' apos input")
            prompt = None if self._peek().type == TokenType.RPAREN else self._parse_expression()
            self._consume(TokenType.RPAREN, "Esperado ')' apos input")
            node = InputExpr(prompt=prompt, line=line)
        elif self._match(TokenType.NEW):
            line = tok.line
            class_name = self._consume(
                TokenType.IDENTIFIER, "Esperado nome da classe"
            ).lexeme
            self._consume(TokenType.LPAREN, "Esperado '('")
            args = []
            if self._peek().type != TokenType.RPAREN:
                args.append(self._parse_expression())
                while self._match(TokenType.COMMA):
                    args.append(self._parse_expression())
            self._consume(TokenType.RPAREN, "Esperado ')'")
            node = NewExpr(
                class_name=class_name,
                arguments=tuple(args),
                line=line,
            )
        elif self._match(TokenType.THIS):
            node = ThisExpr(line=tok.line)
        elif self._match(TokenType.NUMBER):
            node = NumberExpr(value=tok.lexeme, line=tok.line)
        elif self._match(TokenType.STRING_LITERAL):
            node = StringExpr(value=tok.lexeme, line=tok.line)
        elif self._match(TokenType.BOOL_LITERAL):
            node = BoolExpr(value=(tok.lexeme == "true"), line=tok.line)
        elif self._match(TokenType.IDENTIFIER):
            name = tok.lexeme
            if self._match(TokenType.LPAREN):
                args = []
                if self._peek().type != TokenType.RPAREN:
                    args.append(self._parse_expression())
                    while self._match(TokenType.COMMA):
                        args.append(self._parse_expression())
                self._consume(TokenType.RPAREN, "Esperado ')'")
                node = FuncCallExpr(
                    name=name,
                    arguments=tuple(args),
                    line=tok.line,
                )
            else:
                node = IdentifierExpr(name=name, line=tok.line)
        elif self._match(TokenType.LPAREN):
            node = self._parse_expression()
            self._consume(TokenType.RPAREN, "Esperado ')'")
        else:
            self._syntax_error(tok, "expected expression")
            raise _ParseError

        if node is None:
            self._syntax_error(tok, "failed to parse primary expression")
            raise _ParseError

        while True:
            if self._match(TokenType.DOT):
                prop_tok = self._consume(
                    TokenType.IDENTIFIER, "Esperado identificador apos '.'"
                )
                if self._match(TokenType.LPAREN):
                    args = []
                    if self._peek().type != TokenType.RPAREN:
                        args.append(self._parse_expression())
                        while self._match(TokenType.COMMA):
                            args.append(self._parse_expression())
                    self._consume(TokenType.RPAREN, "Esperado ')'")
                    node = MethodCall(
                        object=node,
                        method_name=prop_tok.lexeme,
                        arguments=tuple(args),
                        line=prop_tok.line
                    )
                else:
                    node = PropertyAccess(
                        object=node,
                        property_name=prop_tok.lexeme,
                        line=prop_tok.line
                    )
            elif self._match(TokenType.LBRACKET):
                idx_tok = self._tokens[self._pos - 1]
                idx = self._parse_expression()
                self._consume(TokenType.RBRACKET, "Esperado ']'")
                node = IndexExpr(object=node, index=idx, line=idx_tok.line)
            else:
                break

        return node

    def parse(self) -> Program:
        statements: list[ASTNode] = []
        while self._peek().type != TokenType.END_OF_FILE:
            if self._peek().type == TokenType.RBRACE:
                token = self._advance()
                self._syntax_error(token, "unexpected '}'")
                continue
            stmt = self._parse_statement_recovering()
            if stmt is not None:
                statements.append(stmt)
        return Program(statements=tuple(statements))
