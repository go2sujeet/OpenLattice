"""
openlattice/parser.py
---------------------
Manual tokenizer + recursive-descent parser for the .lattice DSL.

Public API
----------
    parse_file(path: str) -> LatticeSpec
    parse_string(src: str) -> LatticeSpec

Raises ParseError (with .message and .line) on any syntax or semantic error.
"""

from __future__ import annotations

import re
from typing import Iterator

from openlattice.ir import (
    ApiDef,
    EntityDef,
    EventDef,
    FieldDef,
    LatticeSpec,
    QueueDef,
    WorkflowDef,
)

# ---------------------------------------------------------------------------
# Error
# ---------------------------------------------------------------------------

class ParseError(Exception):
    """Raised when the DSL source is invalid."""

    def __init__(self, message: str, line: int) -> None:
        super().__init__(f"Line {line}: {message}")
        self.message = message
        self.line = line


# ---------------------------------------------------------------------------
# Token types
# ---------------------------------------------------------------------------

TK_IDENT   = "IDENT"    # bare word (entity, api, POST, uuid, …)
TK_STRING  = "STRING"   # "…"
TK_NUMBER  = "NUMBER"   # integer literal
TK_LBRACE  = "LBRACE"   # {
TK_RBRACE  = "RBRACE"   # }
TK_LBRACKET = "LBRACKET" # [
TK_RBRACKET = "RBRACKET" # ]
TK_EQ      = "EQ"       # =
TK_COMMA   = "COMMA"    # ,
TK_EOF     = "EOF"

_TOKEN_RE = re.compile(
    r'(?P<COMMENT>\#[^\n]*)'
    r'|(?P<STRING>"(?:[^"\\]|\\.)*")'
    r'|(?P<NUMBER>\d+)'
    r'|(?P<IDENT>[A-Za-z_][A-Za-z0-9_]*)'
    r'|(?P<LBRACE>\{)'
    r'|(?P<RBRACE>\})'
    r'|(?P<LBRACKET>\[)'
    r'|(?P<RBRACKET>\])'
    r'|(?P<EQ>=)'
    r'|(?P<COMMA>,)'
    r'|(?P<WS>[ \t\r\n]+)'
)

VALID_FIELD_TYPES = {"uuid", "int", "float", "string", "bool", "datetime", "json"}
VALID_BLOCK_TYPES = {"entity", "api", "event", "workflow", "queue"}
VALID_HTTP_METHODS = {"GET", "POST", "PUT", "DELETE", "PATCH"}


# ---------------------------------------------------------------------------
# Tokenizer
# ---------------------------------------------------------------------------

class Token:
    __slots__ = ("kind", "value", "line")

    def __init__(self, kind: str, value: str, line: int) -> None:
        self.kind = kind
        self.value = value
        self.line = line

    def __repr__(self) -> str:
        return f"Token({self.kind}, {self.value!r}, line={self.line})"


def _tokenize(src: str) -> list[Token]:
    """Return a flat list of tokens, skipping whitespace and comments."""
    tokens: list[Token] = []
    line = 1
    pos = 0
    length = len(src)

    while pos < length:
        m = _TOKEN_RE.match(src, pos)
        if m is None:
            ch = src[pos]
            raise ParseError(f"Unexpected character {ch!r}", line)

        kind = m.lastgroup
        value = m.group()
        span = m.end() - m.start()

        # Track newlines inside whitespace/strings
        newlines = value.count("\n")

        if kind == "WS":
            line += newlines
        elif kind == "COMMENT":
            pass  # discard; no newline inside (comment stops at \n)
        else:
            tokens.append(Token(kind, value, line))
            line += newlines  # for multi-line strings (edge case)

        pos = m.end()

    tokens.append(Token(TK_EOF, "", line))
    return tokens


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------

class _Parser:
    def __init__(self, tokens: list[Token]) -> None:
        self._tokens = tokens
        self._pos = 0

    # ------------------------------------------------------------------
    # Low-level helpers
    # ------------------------------------------------------------------

    def _peek(self) -> Token:
        return self._tokens[self._pos]

    def _advance(self) -> Token:
        tok = self._tokens[self._pos]
        if tok.kind != TK_EOF:
            self._pos += 1
        return tok

    def _expect(self, kind: str, hint: str = "") -> Token:
        tok = self._peek()
        if tok.kind != kind:
            msg = f"Expected {kind}"
            if hint:
                msg += f" ({hint})"
            msg += f", got {tok.kind} {tok.value!r}"
            raise ParseError(msg, tok.line)
        return self._advance()

    def _expect_ident(self, hint: str = "") -> Token:
        return self._expect(TK_IDENT, hint)

    def _expect_eq(self) -> None:
        self._expect(TK_EQ, "'='")

    def _at_end(self) -> bool:
        return self._peek().kind == TK_EOF

    # ------------------------------------------------------------------
    # Top-level
    # ------------------------------------------------------------------

    def parse(self) -> LatticeSpec:
        spec = LatticeSpec()

        while not self._at_end():
            tok = self._peek()

            if tok.kind != TK_IDENT:
                raise ParseError(
                    f"Expected block keyword, got {tok.kind} {tok.value!r}", tok.line
                )

            block_type = tok.value
            if block_type not in VALID_BLOCK_TYPES:
                raise ParseError(
                    f"Unknown block type {block_type!r}. "
                    f"Valid types: {sorted(VALID_BLOCK_TYPES)}", tok.line
                )

            self._advance()  # consume block keyword

            if block_type == "entity":
                spec.entities.append(self._parse_entity())
            elif block_type == "api":
                spec.apis.append(self._parse_api())
            elif block_type == "event":
                spec.events.append(self._parse_event())
            elif block_type == "workflow":
                spec.workflows.append(self._parse_workflow())
            elif block_type == "queue":
                spec.queues.append(self._parse_queue())

        return spec

    # ------------------------------------------------------------------
    # Block parsers
    # ------------------------------------------------------------------

    def _parse_block_name(self) -> str:
        """Parse the quoted name after a block keyword, e.g. "Order"."""
        tok = self._peek()
        if tok.kind == TK_STRING:
            self._advance()
            return tok.value[1:-1]  # strip quotes
        elif tok.kind == TK_IDENT:
            self._advance()
            return tok.value
        else:
            raise ParseError(
                f"Expected block name (quoted string or identifier), got {tok.kind} {tok.value!r}",
                tok.line,
            )

    def _parse_entity(self) -> EntityDef:
        name = self._parse_block_name()
        line = self._peek().line
        self._expect(TK_LBRACE, "opening '{' of entity block")

        fields: list[FieldDef] | None = None

        while self._peek().kind != TK_RBRACE:
            tok = self._peek()
            if tok.kind == TK_EOF:
                raise ParseError("Unterminated entity block", tok.line)

            attr = self._expect_ident("entity attribute name").value
            self._expect_eq()

            if attr == "fields":
                fields = self._parse_fields_block()
            else:
                raise ParseError(f"Unknown entity attribute {attr!r}", tok.line)

        self._expect(TK_RBRACE, "closing '}' of entity block")

        if fields is None:
            raise ParseError(f"Entity {name!r} is missing required 'fields' block", line)

        return EntityDef(name=name, fields=fields)

    def _parse_api(self) -> ApiDef:
        name = self._parse_block_name()
        line = self._peek().line
        self._expect(TK_LBRACE, "opening '{' of api block")

        method: str | None = None
        path: str | None = None
        input_entity: str | None = None
        output_entity: str | None = None

        while self._peek().kind != TK_RBRACE:
            tok = self._peek()
            if tok.kind == TK_EOF:
                raise ParseError("Unterminated api block", tok.line)

            attr = self._expect_ident("api attribute name").value
            self._expect_eq()

            if attr == "method":
                val_tok = self._expect_ident("HTTP method")
                if val_tok.value not in VALID_HTTP_METHODS:
                    raise ParseError(
                        f"Invalid HTTP method {val_tok.value!r}. "
                        f"Valid: {sorted(VALID_HTTP_METHODS)}",
                        val_tok.line,
                    )
                method = val_tok.value

            elif attr == "path":
                # Path is always a quoted string
                path_tok = self._peek()
                if path_tok.kind != TK_STRING:
                    raise ParseError(
                        f"Expected quoted string for 'path', got {path_tok.kind} {path_tok.value!r}",
                        path_tok.line,
                    )
                self._advance()
                path = path_tok.value[1:-1]  # strip quotes

            elif attr == "input":
                input_entity = self._expect_ident("input entity name").value

            elif attr == "output":
                output_entity = self._expect_ident("output entity name").value

            else:
                raise ParseError(f"Unknown api attribute {attr!r}", tok.line)

        self._expect(TK_RBRACE, "closing '}' of api block")

        if method is None:
            raise ParseError(f"Api {name!r} is missing required attribute 'method'", line)
        if path is None:
            raise ParseError(f"Api {name!r} is missing required attribute 'path'", line)

        return ApiDef(
            name=name,
            method=method,
            path=path,
            input_entity=input_entity,
            output_entity=output_entity,
        )

    def _parse_event(self) -> EventDef:
        name = self._parse_block_name()
        line = self._peek().line
        self._expect(TK_LBRACE, "opening '{' of event block")

        payload: list[FieldDef] | None = None

        while self._peek().kind != TK_RBRACE:
            tok = self._peek()
            if tok.kind == TK_EOF:
                raise ParseError("Unterminated event block", tok.line)

            attr = self._expect_ident("event attribute name").value
            self._expect_eq()

            if attr == "payload":
                payload = self._parse_fields_block()
            else:
                raise ParseError(f"Unknown event attribute {attr!r}", tok.line)

        self._expect(TK_RBRACE, "closing '}' of event block")

        if payload is None:
            raise ParseError(f"Event {name!r} is missing required 'payload' block", line)

        return EventDef(name=name, payload=payload)

    def _parse_workflow(self) -> WorkflowDef:
        name = self._parse_block_name()
        line = self._peek().line
        self._expect(TK_LBRACE, "opening '{' of workflow block")

        steps: list[str] | None = None

        while self._peek().kind != TK_RBRACE:
            tok = self._peek()
            if tok.kind == TK_EOF:
                raise ParseError("Unterminated workflow block", tok.line)

            attr = self._expect_ident("workflow attribute name").value
            self._expect_eq()

            if attr == "steps":
                steps = self._parse_steps_list()
            else:
                raise ParseError(f"Unknown workflow attribute {attr!r}", tok.line)

        self._expect(TK_RBRACE, "closing '}' of workflow block")

        if steps is None:
            raise ParseError(f"Workflow {name!r} is missing required 'steps' list", line)

        return WorkflowDef(name=name, steps=steps)

    def _parse_queue(self) -> QueueDef:
        name = self._parse_block_name()
        self._expect(TK_LBRACE, "opening '{' of queue block")

        retries = 3  # default

        while self._peek().kind != TK_RBRACE:
            tok = self._peek()
            if tok.kind == TK_EOF:
                raise ParseError("Unterminated queue block", tok.line)

            attr = self._expect_ident("queue attribute name").value
            self._expect_eq()

            if attr == "retries":
                num_tok = self._expect(TK_NUMBER, "integer value for 'retries'")
                retries = int(num_tok.value)
            else:
                raise ParseError(f"Unknown queue attribute {attr!r}", tok.line)

        self._expect(TK_RBRACE, "closing '}' of queue block")

        return QueueDef(name=name, retries=retries)

    # ------------------------------------------------------------------
    # Sub-structure parsers
    # ------------------------------------------------------------------

    def _parse_fields_block(self) -> list[FieldDef]:
        """Parse  { field_name = field_type  ... }"""
        self._expect(TK_LBRACE, "opening '{' of fields block")
        fields: list[FieldDef] = []

        while self._peek().kind != TK_RBRACE:
            tok = self._peek()
            if tok.kind == TK_EOF:
                raise ParseError("Unterminated fields block", tok.line)

            name_tok = self._expect_ident("field name")
            self._expect_eq()
            type_tok = self._expect_ident("field type")

            if type_tok.value not in VALID_FIELD_TYPES:
                raise ParseError(
                    f"Unknown field type {type_tok.value!r}. "
                    f"Valid types: {sorted(VALID_FIELD_TYPES)}",
                    type_tok.line,
                )

            fields.append(FieldDef(name=name_tok.value, type=type_tok.value))

        self._expect(TK_RBRACE, "closing '}' of fields block")
        return fields

    def _parse_steps_list(self) -> list[str]:
        """Parse  [ "step1", "step2", ... ]  — trailing comma OK."""
        self._expect(TK_LBRACKET, "opening '[' of steps list")
        steps: list[str] = []

        while self._peek().kind != TK_RBRACKET:
            tok = self._peek()
            if tok.kind == TK_EOF:
                raise ParseError("Unterminated steps list", tok.line)

            step_tok = self._expect(TK_STRING, "quoted step name")
            steps.append(step_tok.value[1:-1])  # strip quotes

            # Optional trailing comma
            if self._peek().kind == TK_COMMA:
                self._advance()

        self._expect(TK_RBRACKET, "closing ']' of steps list")
        return steps


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def parse_string(src: str) -> LatticeSpec:
    """Parse a .lattice DSL string and return a LatticeSpec."""
    tokens = _tokenize(src)
    return _Parser(tokens).parse()


def parse_file(path: str) -> LatticeSpec:
    """Read a .lattice file from *path* and return a LatticeSpec."""
    try:
        with open(path, "r", encoding="utf-8") as fh:
            src = fh.read()
    except OSError as exc:
        raise ParseError(f"Cannot read file {path!r}: {exc}", 0) from exc
    return parse_string(src)


# ---------------------------------------------------------------------------
# Self-test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    _SAMPLE = """
# OpenLattice spec example

entity "Order" {
  fields = {
    id     = uuid
    amount = int
    status = string
  }
}

entity "Product" {
  fields = {
    id    = uuid
    name  = string
    price = float
  }
}

api "CreateOrder" {
  method = POST
  path   = "/orders"
  input  = Order
  output = Order
}

api "GetOrder" {
  method = GET
  path   = "/orders/{id}"
  output = Order
}

api "ListOrders" {
  method = GET
  path   = "/orders"
  output = Order
}

event "OrderCreated" {
  payload = {
    order_id = uuid
    amount   = int
  }
}

workflow "Checkout" {
  steps = [
    "validate_order",
    "charge_customer",
    "publish_order_created"
  ]
}

queue "email_notifications" {
  retries = 3
}
"""

    import pprint

    spec = parse_string(_SAMPLE)

    print("=== LatticeSpec ===\n")

    print("Entities:")
    for e in spec.entities:
        print(f"  {e.name}: {[f'{f.name}:{f.type}' for f in e.fields]}")

    print("\nAPIs:")
    for a in spec.apis:
        print(f"  {a.name}: {a.method} {a.path!r}  in={a.input_entity} out={a.output_entity}")

    print("\nEvents:")
    for ev in spec.events:
        print(f"  {ev.name}: {[f'{f.name}:{f.type}' for f in ev.payload]}")

    print("\nWorkflows:")
    for wf in spec.workflows:
        print(f"  {wf.name}: {wf.steps}")

    print("\nQueues:")
    for q in spec.queues:
        print(f"  {q.name}: retries={q.retries}")

    print("\n--- Full repr ---")
    pprint.pprint(spec)
    print("\nAll tests passed.")
