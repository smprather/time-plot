"""Custom expression parser for time-plot.

Grammar
-------
expr_def    := NAME '=' expr
expr        := add_expr
add_expr    := mul_expr ( ('+' | '-') mul_expr )*
mul_expr    := unary ( ('*' | '/') unary )*
unary       := '-' unary | primary
primary     := FUNC_NAME '(' arg_list ')' | '(' expr ')' | NUMBER | series_ref
arg_list    := expr ( ',' expr )*
series_ref  := pattern ( '|' pattern? )?  |  '|' pattern
pattern     := ( PATTERN_CHAR )+

PATTERN_CHAR includes alphanumerics, '_', '/', '.', '-', '*', '?', '[', ']'.

Series reference disambiguation
--------------------------------
'*' at the start of a `primary` = glob wildcard (part of a series ref pattern).
'*' between two expressions = multiplication operator.
'|' is always a series separator, never bitwise OR.

Return types
------------
ExprResult = np.ndarray | list[np.ndarray] | float

- np.ndarray   : single time-series
- list[ndarray]: array-of-series (from array-context aggregation or array arithmetic)
- float        : scalar (plotted as horizontal line)

Resolution callback
-------------------
Callers pass a ``resolve`` function:

    resolve(a_pat: str | None, b_pat: str, context: str) -> ExprResult

where ``context`` is ``'scalar'`` or ``'array'``. The callback is responsible for
pattern matching, uniqueness checking, and fetching the actual data.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto
from typing import Callable

import numpy as np


# ---------------------------------------------------------------------------
# Public types
# ---------------------------------------------------------------------------

ExprResult = np.ndarray | list[np.ndarray] | float
ResolveFn = Callable[[str | None, str, str], "EvalResult"]  # (a_pat, b_pat, context) -> EvalResult


# ---------------------------------------------------------------------------
# Tokenizer
# ---------------------------------------------------------------------------

class TokKind(Enum):
    NUMBER   = auto()
    NAME     = auto()   # identifier or function name
    PATTERN  = auto()   # series ref pattern (may contain /, ., *, ?, [], -)
    PIPE     = auto()   # |
    PLUS     = auto()   # +
    MINUS    = auto()   # -
    STAR     = auto()   # *  (role determined by parser context)
    SLASH    = auto()   # /
    LPAREN   = auto()   # (
    RPAREN   = auto()   # )
    COMMA    = auto()   # ,
    EOF      = auto()


# Characters valid inside a pattern (series ref component) but NOT plain identifiers
_PATTERN_EXTRA = frozenset("/*?[].-")
# Characters that terminate an ordinary name token (not a pattern)
_DELIMITERS = frozenset(" \t\n\r|+*/(),")
# Characters that terminate a pattern token (subset of _DELIMITERS: allows / * ? . [ ])
# '-' is included so binary minus still works as an operator outside patterns.
_PATTERN_STOP = frozenset(" \t\n\r|+-(,)")

# Known function names — these are parsed as function calls, not series refs
_FUNCTIONS = frozenset({"sum", "abs", "ddt", "rms", "average"})


@dataclass(slots=True)
class Token:
    kind: TokKind
    value: str
    pos: int


def tokenize(text: str) -> list[Token]:
    tokens: list[Token] = []
    i = 0
    n = len(text)
    while i < n:
        c = text[i]
        if c in " \t\n\r":
            i += 1
            continue
        if c == "|":
            tokens.append(Token(TokKind.PIPE, "|", i)); i += 1
        elif c == "+":
            tokens.append(Token(TokKind.PLUS, "+", i)); i += 1
        elif c == "-":
            tokens.append(Token(TokKind.MINUS, "-", i)); i += 1
        elif c == "/":
            tokens.append(Token(TokKind.SLASH, "/", i)); i += 1
        elif c == "(":
            tokens.append(Token(TokKind.LPAREN, "(", i)); i += 1
        elif c == ")":
            tokens.append(Token(TokKind.RPAREN, ")", i)); i += 1
        elif c == ",":
            tokens.append(Token(TokKind.COMMA, ",", i)); i += 1
        elif c == "*":
            tokens.append(Token(TokKind.STAR, "*", i)); i += 1
        elif c.isdigit() or (c == "." and i + 1 < n and text[i + 1].isdigit()):
            j = i
            while j < n and (text[j].isdigit() or text[j] in ".eE+-"):
                # Allow sign only after e/E
                if text[j] in "+-" and (j == i or text[j - 1] not in "eE"):
                    break
                j += 1
            tokens.append(Token(TokKind.NUMBER, text[i:j], i))
            i = j
        elif c.isalpha() or c == "_":
            # Could be a plain identifier/function name, or start of a pattern
            # with extra chars like slashes after the initial identifier part.
            j = i
            while j < n and (text[j].isalnum() or text[j] in "_"):
                j += 1
            word = text[i:j]
            # If followed immediately (no space) by a pattern-extra char, absorb it
            # as a PATTERN token.
            if j < n and text[j] in _PATTERN_EXTRA:
                # Continue reading as a pattern — allow /, *, ?, ., [, ] to continue
                while j < n and text[j] not in _PATTERN_STOP:
                    j += 1
                tokens.append(Token(TokKind.PATTERN, text[i:j], i))
            else:
                tokens.append(Token(TokKind.NAME, word, i))
            i = j
        else:
            raise SyntaxError(f"Unexpected character {c!r} at position {i} in expression")
    tokens.append(Token(TokKind.EOF, "", n))
    return tokens


# ---------------------------------------------------------------------------
# AST nodes
# ---------------------------------------------------------------------------

@dataclass(slots=True)
class NumNode:
    value: float

@dataclass(slots=True)
class SeriesRefNode:
    """a|b reference. Either part may be None (means match-all glob)."""
    a_pat: str | None   # file basename pattern; None means '*'
    b_pat: str          # series name pattern

@dataclass(slots=True)
class UnaryNode:
    op: str             # '-'
    operand: object     # ASTNode

@dataclass(slots=True)
class BinOpNode:
    op: str             # '+' '-' '*' '/'
    left: object        # ASTNode
    right: object       # ASTNode

@dataclass(slots=True)
class CallNode:
    func: str           # function name
    args: list          # list[ASTNode]


ASTNode = NumNode | SeriesRefNode | UnaryNode | BinOpNode | CallNode


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------

class _Parser:
    def __init__(self, tokens: list[Token]) -> None:
        self._tokens = tokens
        self._pos = 0

    def _peek(self) -> Token:
        return self._tokens[self._pos]

    def _consume(self, kind: TokKind | None = None) -> Token:
        tok = self._tokens[self._pos]
        if kind is not None and tok.kind != kind:
            raise SyntaxError(
                f"Expected {kind.name} but got {tok.kind.name} ({tok.value!r}) at pos {tok.pos}"
            )
        self._pos += 1
        return tok

    def parse_expr(self) -> ASTNode:
        node = self._parse_add()
        if self._peek().kind != TokKind.EOF:
            tok = self._peek()
            raise SyntaxError(f"Unexpected token {tok.value!r} at pos {tok.pos}")
        return node

    def _parse_add(self) -> ASTNode:
        left = self._parse_mul()
        while self._peek().kind in (TokKind.PLUS, TokKind.MINUS):
            op = self._consume().value
            right = self._parse_mul()
            left = BinOpNode(op=op, left=left, right=right)
        return left

    def _parse_mul(self) -> ASTNode:
        left = self._parse_unary()
        while self._peek().kind in (TokKind.STAR, TokKind.SLASH):
            # STAR here is multiplication (between two expressions)
            op = self._consume().value
            right = self._parse_unary()
            left = BinOpNode(op=op, left=left, right=right)
        return left

    def _parse_unary(self) -> ASTNode:
        if self._peek().kind == TokKind.MINUS:
            self._consume()
            operand = self._parse_unary()
            return UnaryNode(op="-", operand=operand)
        return self._parse_primary()

    def _parse_primary(self) -> ASTNode:
        tok = self._peek()

        # Parenthesised sub-expression
        if tok.kind == TokKind.LPAREN:
            self._consume(TokKind.LPAREN)
            node = self._parse_add()
            self._consume(TokKind.RPAREN)
            return node

        # Numeric literal
        if tok.kind == TokKind.NUMBER:
            self._consume()
            return NumNode(value=float(tok.value))

        # STAR at primary position = start of a glob pattern '*' or '*|...'
        if tok.kind == TokKind.STAR:
            self._consume(TokKind.STAR)
            return self._parse_series_ref_with_a("*")

        # PIPE at primary position = '|b' (any file, specific series)
        if tok.kind == TokKind.PIPE:
            self._consume(TokKind.PIPE)
            b = self._read_pattern_or_star()
            return SeriesRefNode(a_pat=None, b_pat=b)

        # NAME token: could be a function call or a series ref
        if tok.kind == TokKind.NAME:
            name = tok.value
            self._consume()
            if name in _FUNCTIONS and self._peek().kind == TokKind.LPAREN:
                # Function call
                self._consume(TokKind.LPAREN)
                args: list[ASTNode] = []
                if self._peek().kind != TokKind.RPAREN:
                    args.append(self._parse_add())
                    while self._peek().kind == TokKind.COMMA:
                        self._consume(TokKind.COMMA)
                        args.append(self._parse_add())
                self._consume(TokKind.RPAREN)
                return CallNode(func=name, args=args)
            # Series ref with a plain name as the left side
            return self._parse_series_ref_with_a(name)

        # PATTERN token (e.g. "rtr_0/foo"): always a series ref left side
        if tok.kind == TokKind.PATTERN:
            a = tok.value
            self._consume()
            return self._parse_series_ref_with_a(a)

        raise SyntaxError(
            f"Unexpected token {tok.kind.name} ({tok.value!r}) at pos {tok.pos}"
        )

    def _parse_series_ref_with_a(self, a: str) -> SeriesRefNode:
        """Given we've already consumed (or determined) the left-side pattern `a`,
        optionally consume '|' and the right-side pattern."""
        if self._peek().kind == TokKind.PIPE:
            self._consume(TokKind.PIPE)
            # Right side may be empty (meaning '*'), a STAR, a NAME, or a PATTERN
            nxt = self._peek()
            if nxt.kind in (TokKind.EOF, TokKind.PLUS, TokKind.MINUS,
                            TokKind.RPAREN, TokKind.COMMA):
                # Empty right side — treat as '*'
                b = "*"
            else:
                b = self._read_pattern_or_star()
            return SeriesRefNode(a_pat=a, b_pat=b)
        # No pipe — bare 'a' means '*|a' (any file, match series name)
        return SeriesRefNode(a_pat=None, b_pat=a)

    def _read_pattern_or_star(self) -> str:
        """Read the next token as a pattern string (NAME, PATTERN, or STAR)."""
        tok = self._peek()
        if tok.kind == TokKind.STAR:
            self._consume()
            return "*"
        if tok.kind in (TokKind.NAME, TokKind.PATTERN):
            self._consume()
            return tok.value
        # Empty — treat as '*'
        return "*"


def parse_expr(text: str) -> ASTNode:
    """Parse an expression string into an AST node."""
    tokens = tokenize(text)
    parser = _Parser(tokens)
    return parser.parse_expr()


def parse_expr_def(text: str) -> tuple[str, ASTNode]:
    """Parse 'name=expr' into (name, AST). Name must be a simple identifier."""
    eq = text.find("=")
    if eq == -1:
        raise SyntaxError(f"Expression definition must have the form 'name=expr', got: {text!r}")
    name = text[:eq].strip()
    if not name.isidentifier():
        raise SyntaxError(f"Expression name must be a simple identifier, got: {name!r}")
    expr_text = text[eq + 1:].strip()
    if not expr_text:
        raise SyntaxError(f"Empty expression body after '=' in: {text!r}")
    ast = parse_expr(expr_text)
    return name, ast


# ---------------------------------------------------------------------------
# Evaluator
# ---------------------------------------------------------------------------

@dataclass(slots=True)
class EvalResult:
    """Typed result from expression evaluation."""
    value: ExprResult
    y_unit: str
    y_unit_label: str
    y_label: str


def evaluate(
    node: ASTNode,
    resolve: ResolveFn,
    x_seconds: np.ndarray,
) -> EvalResult:
    """Recursively evaluate an AST node.

    ``resolve(a_pat, b_pat, context)`` is called for every SeriesRefNode.
    It should return an ExprResult (ndarray, list[ndarray], or float).
    """
    return _eval(node, resolve, x_seconds)


def _eval(node: ASTNode, resolve: ResolveFn, x: np.ndarray) -> EvalResult:
    if isinstance(node, NumNode):
        return EvalResult(value=float(node.value), y_unit="1", y_unit_label="1", y_label="")

    if isinstance(node, SeriesRefNode):
        a = node.a_pat  # None means '*'
        b = node.b_pat
        # resolve() returns a full EvalResult including unit info.
        return resolve(a, b, "scalar")

    if isinstance(node, UnaryNode):
        inner = _eval(node.operand, resolve, x)
        val = _negate(inner.value)
        return EvalResult(value=val, y_unit=inner.y_unit, y_unit_label=inner.y_unit_label, y_label=inner.y_label)

    if isinstance(node, BinOpNode):
        return _eval_binop(node, resolve, x)

    if isinstance(node, CallNode):
        return _eval_call(node, resolve, x)

    msg = f"Unknown AST node type: {type(node)}"
    raise TypeError(msg)


def _negate(val: ExprResult) -> ExprResult:
    if isinstance(val, float):
        return -val
    if isinstance(val, np.ndarray):
        return -val
    return [-v for v in val]  # list[ndarray]


def _eval_binop(node: BinOpNode, resolve: ResolveFn, x: np.ndarray) -> EvalResult:
    left = _eval(node.left, resolve, x)
    right = _eval(node.right, resolve, x)
    op = node.op

    lv, rv = left.value, right.value

    # Determine output type (series wins over scalar; array wins over series)
    if isinstance(lv, list) or isinstance(rv, list):
        # Array-of-series arithmetic
        lv_list = lv if isinstance(lv, list) else _broadcast_to_list(lv, _list_len(rv))
        rv_list = rv if isinstance(rv, list) else _broadcast_to_list(rv, _list_len(lv))
        if len(lv_list) != len(rv_list):
            raise ValueError(
                f"Cannot apply '{op}' to arrays of different lengths "
                f"({len(lv_list)} vs {len(rv_list)})"
            )
        if op == "+" and left.y_unit != right.y_unit and not _is_scalar_unit(left) and not _is_scalar_unit(right):
            raise ValueError(f"Cannot add series with different units: {left.y_unit} and {right.y_unit}")
        if op == "-" and left.y_unit != right.y_unit and not _is_scalar_unit(left) and not _is_scalar_unit(right):
            raise ValueError(f"Cannot subtract series with different units: {left.y_unit} and {right.y_unit}")
        result = [_apply_op(op, a, b) for a, b in zip(lv_list, rv_list)]
        y_unit = _result_unit(op, left.y_unit, right.y_unit)
        return EvalResult(value=result, y_unit=y_unit, y_unit_label=y_unit, y_label="")

    # Scalar or series arithmetic
    if op in ("+", "-"):
        if not _is_scalar_unit(left) and not _is_scalar_unit(right) and left.y_unit != right.y_unit:
            raise ValueError(
                f"Cannot {'+' if op == '+' else 'subtract'} series with different units: "
                f"{left.y_unit} and {right.y_unit}"
            )
    result_val = _apply_op(op, lv, rv)
    y_unit = _result_unit(op, left.y_unit, right.y_unit)
    # Determine best label/unit_label
    unit_label = left.y_unit_label if y_unit == left.y_unit else (
        right.y_unit_label if y_unit == right.y_unit else y_unit
    )
    y_label = left.y_label or right.y_label
    return EvalResult(value=result_val, y_unit=y_unit, y_unit_label=unit_label, y_label=y_label)


def _apply_op(op: str, a: ExprResult, b: ExprResult) -> ExprResult:
    if op == "+":
        return _arr(a) + _arr(b)  # type: ignore[operator]
    if op == "-":
        return _arr(a) - _arr(b)  # type: ignore[operator]
    if op == "*":
        return _arr(a) * _arr(b)  # type: ignore[operator]
    if op == "/":
        with np.errstate(divide="ignore", invalid="ignore"):
            return _arr(a) / _arr(b)  # type: ignore[operator]
    raise ValueError(f"Unknown operator: {op}")


def _arr(v: ExprResult) -> np.ndarray | float:
    if isinstance(v, list):
        raise TypeError("Cannot use array-of-series in scalar arithmetic")
    return v


def _broadcast_to_list(val: np.ndarray | float, n: int) -> list[np.ndarray | float]:
    return [val] * n


def _list_len(v: ExprResult) -> int:
    if isinstance(v, list):
        return len(v)
    return 1


def _is_scalar_unit(r: EvalResult) -> bool:
    return r.y_unit in ("1", "?", "")


def _result_unit(op: str, lu: str, ru: str) -> str:
    if op in ("+", "-"):
        return lu if lu not in ("1", "?", "") else ru
    if op == "*":
        if lu in ("1", "?", ""):
            return ru
        if ru in ("1", "?", ""):
            return lu
        return f"{lu}*{ru}"
    if op == "/":
        if ru in ("1", "?", ""):
            return lu
        if lu in ("1", "?", ""):
            return f"1/{ru}"
        return f"{lu}/{ru}"
    return "?"


def _eval_call(node: CallNode, resolve: ResolveFn, x: np.ndarray) -> EvalResult:
    fn = node.func

    if fn == "sum":
        if len(node.args) != 1:
            raise ValueError("sum() takes exactly one argument")
        arg_result = _eval_array_arg(node.args[0], resolve, x)
        series_list = _to_series_list(arg_result.value, x)
        if not series_list:
            result = np.zeros_like(x, dtype=np.float64)
        else:
            result = np.nansum(np.stack(series_list, axis=0), axis=0)
        return EvalResult(value=result, y_unit=arg_result.y_unit, y_unit_label=arg_result.y_unit_label, y_label="sum")

    if fn == "abs":
        if len(node.args) != 1:
            raise ValueError("abs() takes exactly one argument")
        inner = _eval(node.args[0], resolve, x)
        val = _apply_abs(inner.value)
        return EvalResult(value=val, y_unit=inner.y_unit, y_unit_label=inner.y_unit_label, y_label=inner.y_label)

    if fn == "ddt":
        if len(node.args) != 1:
            raise ValueError("ddt() takes exactly one argument")
        inner = _eval(node.args[0], resolve, x)
        if isinstance(inner.value, list):
            result_list = [_ddt_series(s, x) for s in inner.value]
            ddt_unit = _ddt_unit(inner.y_unit)
            return EvalResult(value=result_list, y_unit=ddt_unit, y_unit_label=ddt_unit, y_label=inner.y_label)
        if isinstance(inner.value, float):
            raise ValueError("ddt() cannot be applied to a scalar expression")
        ddt_val = _ddt_series(inner.value, x)
        ddt_unit = _ddt_unit(inner.y_unit)
        return EvalResult(value=ddt_val, y_unit=ddt_unit, y_unit_label=ddt_unit, y_label=inner.y_label)

    if fn == "rms":
        if len(node.args) != 1:
            raise ValueError("rms() takes exactly one argument")
        inner = _eval(node.args[0], resolve, x)
        if isinstance(inner.value, list):
            raise ValueError("rms() cannot be applied to an array-of-series; use a scalar ref or reduce first")
        if isinstance(inner.value, float):
            return EvalResult(value=abs(inner.value), y_unit=inner.y_unit, y_unit_label=inner.y_unit_label, y_label=inner.y_label)
        finite = inner.value[np.isfinite(inner.value)]
        rms_val = float(np.sqrt(np.mean(finite ** 2))) if finite.size else float("nan")
        return EvalResult(value=rms_val, y_unit=inner.y_unit, y_unit_label=inner.y_unit_label, y_label=inner.y_label)

    if fn == "average":
        if len(node.args) != 1:
            raise ValueError("average() takes exactly one argument")
        inner = _eval(node.args[0], resolve, x)
        if isinstance(inner.value, list):
            raise ValueError("average() cannot be applied to an array-of-series; use a scalar ref or reduce first")
        if isinstance(inner.value, float):
            return inner
        finite = inner.value[np.isfinite(inner.value)]
        avg_val = float(np.mean(finite)) if finite.size else float("nan")
        return EvalResult(value=avg_val, y_unit=inner.y_unit, y_unit_label=inner.y_unit_label, y_label=inner.y_label)

    raise ValueError(f"Unknown function: {fn}()")


def _eval_array_arg(node: ASTNode, resolve: ResolveFn, x: np.ndarray) -> EvalResult:
    """Evaluate a node in array context (for aggregate functions like sum())."""
    if isinstance(node, SeriesRefNode):
        er = resolve(node.a_pat, node.b_pat, "array")
        # Normalise to list[ndarray] so sum() always gets an array
        if isinstance(er.value, np.ndarray):
            return EvalResult(value=[er.value], y_unit=er.y_unit, y_unit_label=er.y_unit_label, y_label=er.y_label)
        if isinstance(er.value, float):
            return EvalResult(value=[np.full_like(x, er.value, dtype=np.float64)], y_unit=er.y_unit, y_unit_label=er.y_unit_label, y_label=er.y_label)
        return er  # already list[ndarray]
    # Non-ref arg — evaluate normally
    return _eval(node, resolve, x)


def _to_series_list(val: ExprResult, x: np.ndarray) -> list[np.ndarray]:
    if isinstance(val, list):
        result = []
        for v in val:
            if isinstance(v, float):
                result.append(np.full_like(x, v, dtype=np.float64))
            else:
                result.append(np.asarray(v, dtype=np.float64))
        return result
    if isinstance(val, float):
        return [np.full_like(x, val, dtype=np.float64)]
    return [np.asarray(val, dtype=np.float64)]


def _apply_abs(val: ExprResult) -> ExprResult:
    if isinstance(val, float):
        return abs(val)
    if isinstance(val, list):
        return [np.abs(v) for v in val]
    return np.abs(val)


def _ddt_series(arr: np.ndarray, x: np.ndarray) -> np.ndarray:
    out = np.full_like(arr, np.nan, dtype=np.float64)
    if arr.size < 2:
        return out
    dx = np.diff(x)
    finite = np.isfinite(arr)
    valid = finite[:-1] & finite[1:] & (dx > 0)
    deriv = np.full(arr.size - 1, np.nan, dtype=np.float64)
    deriv[valid] = (arr[1:][valid] - arr[:-1][valid]) / dx[valid]
    out[1:] = deriv
    if out.size > 1 and np.isfinite(out[1]):
        out[0] = out[1]
    return out


def _ddt_unit(unit: str) -> str:
    if unit in ("", "1", "?"):
        return "1/s"
    return f"{unit}/s"
