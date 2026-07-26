"""AST node definitions produced by the parser."""
from dataclasses import dataclass, field
from typing import Any, List, Optional


# ---- expressions -------------------------------------------------------

@dataclass
class Column:
    name: str
    table: Optional[str] = None


@dataclass
class Literal:
    value: Any


@dataclass
class BinaryOp:
    op: str
    left: Any
    right: Any


@dataclass
class UnaryOp:
    op: str
    operand: Any


@dataclass
class FuncCall:
    name: str            # lower-cased function name, e.g. "count"
    arg: Any             # expression, or None for COUNT(*)
    star: bool = False


# ---- clauses -----------------------------------------------------------

@dataclass
class SelectItem:
    expr: Any
    alias: Optional[str] = None
    star: bool = False   # True for a bare "*"


@dataclass
class TableRef:
    name: str
    alias: str


@dataclass
class Join:
    table: TableRef
    condition: Any


@dataclass
class OrderItem:
    expr: Any
    desc: bool = False


@dataclass
class Query:
    select: List[SelectItem]
    from_table: TableRef
    joins: List[Join] = field(default_factory=list)
    where: Any = None
    group_by: List[Any] = field(default_factory=list)
    order_by: List[OrderItem] = field(default_factory=list)
    limit: Optional[int] = None
