"""Recursive-descent parser: tokens -> Query AST.

Grammar (roughly):
    query      := SELECT select_list FROM table_ref join*
                  [WHERE expr] [GROUP BY expr_list]
                  [ORDER BY order_list] [LIMIT number]
    expr       := or_expr
    or_expr    := and_expr (OR and_expr)*
    and_expr   := not_expr (AND not_expr)*
    not_expr   := NOT not_expr | comparison
    comparison := additive (cmp_op additive)?
    additive   := multiplicative (('+'|'-') multiplicative)*
    multiplic. := unary (('*'|'/') unary)*
    unary      := '-' unary | primary
    primary    := NUMBER | STRING | TRUE|FALSE|NULL
                | func_call | column | '(' expr ')'
"""
from . import nodes
from .tokenizer import tokenize

_CMP_OPS = {"=", "!=", "<>", "<", "<=", ">", ">="}


class Parser:
    def __init__(self, sql: str):
        self.tokens = tokenize(sql)
        self.i = 0

    # -- token helpers ---------------------------------------------------
    def peek(self):
        return self.tokens[self.i]

    def next(self):
        tok = self.tokens[self.i]
        self.i += 1
        return tok

    def at(self, *types):
        return self.peek().type in types

    def at_op(self, value):
        t = self.peek()
        return t.type == "OP" and t.value == value

    def at_punct(self, value):
        t = self.peek()
        return t.type == "PUNCT" and t.value == value

    def eat(self, type_):
        tok = self.peek()
        if tok.type != type_:
            raise SyntaxError(
                f"Expected {type_} but got {tok.type} ({tok.value!r}) at {tok.pos}"
            )
        return self.next()

    def eat_punct(self, value):
        if not self.at_punct(value):
            tok = self.peek()
            raise SyntaxError(f"Expected {value!r} but got {tok.value!r} at {tok.pos}")
        return self.next()

    # -- entry -----------------------------------------------------------
    def parse(self) -> nodes.Query:
        q = self.query()
        self.eat("EOF")
        return q

    def query(self):
        self.eat("SELECT")
        select = self.select_list()
        self.eat("FROM")
        from_table = self.table_ref()

        joins = []
        while self.at("JOIN", "INNER"):
            if self.at("INNER"):
                self.next()
            self.eat("JOIN")
            tref = self.table_ref()
            self.eat("ON")
            joins.append(nodes.Join(tref, self.expr()))

        where = None
        if self.at("WHERE"):
            self.next()
            where = self.expr()

        group_by = []
        if self.at("GROUP"):
            self.next()
            self.eat("BY")
            group_by = self.expr_list()

        order_by = []
        if self.at("ORDER"):
            self.next()
            self.eat("BY")
            order_by = self.order_list()

        limit = None
        if self.at("LIMIT"):
            self.next()
            limit = int(self.eat("NUMBER").value)

        return nodes.Query(select, from_table, joins, where, group_by, order_by, limit)

    # -- clauses ---------------------------------------------------------
    def select_list(self):
        items = [self.select_item()]
        while self.at_punct(","):
            self.next()
            items.append(self.select_item())
        return items

    def select_item(self):
        if self.at_op("*"):
            self.next()
            return nodes.SelectItem(expr=None, star=True)
        e = self.expr()
        alias = self._optional_alias()
        return nodes.SelectItem(expr=e, alias=alias)

    def table_ref(self):
        name = self.eat("IDENT").value
        alias = self._optional_alias() or name
        return nodes.TableRef(name, alias)

    def _optional_alias(self):
        if self.at("AS"):
            self.next()
            return self.eat("IDENT").value
        if self.at("IDENT"):
            return self.next().value
        return None

    def expr_list(self):
        items = [self.expr()]
        while self.at_punct(","):
            self.next()
            items.append(self.expr())
        return items

    def order_list(self):
        items = []
        while True:
            e = self.expr()
            desc = False
            if self.at("ASC"):
                self.next()
            elif self.at("DESC"):
                self.next()
                desc = True
            items.append(nodes.OrderItem(e, desc))
            if self.at_punct(","):
                self.next()
                continue
            break
        return items

    # -- expressions -----------------------------------------------------
    def expr(self):
        return self.or_expr()

    def or_expr(self):
        left = self.and_expr()
        while self.at("OR"):
            self.next()
            left = nodes.BinaryOp("OR", left, self.and_expr())
        return left

    def and_expr(self):
        left = self.not_expr()
        while self.at("AND"):
            self.next()
            left = nodes.BinaryOp("AND", left, self.not_expr())
        return left

    def not_expr(self):
        if self.at("NOT"):
            self.next()
            return nodes.UnaryOp("NOT", self.not_expr())
        return self.comparison()

    def comparison(self):
        left = self.additive()
        t = self.peek()
        if t.type == "OP" and t.value in _CMP_OPS:
            op = self.next().value
            return nodes.BinaryOp(op, left, self.additive())
        return left

    def additive(self):
        left = self.multiplicative()
        while self.at_op("+") or self.at_op("-"):
            op = self.next().value
            left = nodes.BinaryOp(op, left, self.multiplicative())
        return left

    def multiplicative(self):
        left = self.unary()
        while self.at_op("*") or self.at_op("/"):
            op = self.next().value
            left = nodes.BinaryOp(op, left, self.unary())
        return left

    def unary(self):
        if self.at_op("-"):
            self.next()
            return nodes.UnaryOp("-", self.unary())
        return self.primary()

    def primary(self):
        tok = self.peek()
        if tok.type == "NUMBER":
            self.next()
            return nodes.Literal(float(tok.value) if "." in tok.value else int(tok.value))
        if tok.type == "STRING":
            self.next()
            return nodes.Literal(tok.value)
        if tok.type in ("TRUE", "FALSE"):
            self.next()
            return nodes.Literal(tok.type == "TRUE")
        if tok.type == "NULL":
            self.next()
            return nodes.Literal(None)
        if self.at_punct("("):
            self.next()
            e = self.or_expr()
            self.eat_punct(")")
            return e
        if tok.type == "IDENT":
            name = self.next().value
            # function call?
            if self.at_punct("("):
                self.next()
                if self.at_op("*"):
                    self.next()
                    self.eat_punct(")")
                    return nodes.FuncCall(name.lower(), None, star=True)
                arg = self.or_expr()
                self.eat_punct(")")
                return nodes.FuncCall(name.lower(), arg)
            # column, optionally qualified table.column
            table = None
            col = name
            if self.at_punct("."):
                self.next()
                table = name
                col = self.eat("IDENT").value
            return nodes.Column(col, table)
        raise SyntaxError(f"Unexpected token {tok.type} ({tok.value!r}) at {tok.pos}")


def parse_sql(sql: str) -> nodes.Query:
    return Parser(sql).parse()
