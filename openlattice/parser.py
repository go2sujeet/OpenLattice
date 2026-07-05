"""TF-style parser for OpenLattice .lattice files."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, cast

from openlattice.ir import ApiDef, EntityDef, EventDef, FieldDef, LatticeSpec, QueueDef, WorkflowDef

_KIND_LABELS = {
    "LBRACE": '"{{"',
    "RBRACE": '"}}"',
    "LBRACKET": '"["',
    "RBRACKET": '"]"',
    "EQ": '"="',
    "STRING": "string",
    "IDENT": "identifier",
    "NUMBER": "number",
}

_VALID_RESOURCE_TYPES = {
    "lattice_entity",
    "lattice_api",
    "lattice_event",
    "lattice_workflow",
    "lattice_queue",
}
_VALID_FIELD_TYPES = {"uuid", "int", "float", "string", "bool", "datetime", "json"}
_VALID_METHODS = {"GET", "POST", "PUT", "DELETE", "PATCH"}


class ParseError(Exception):
    def __init__(self, message: str, line: int = 0):
        self.message = message
        self.line = line
        super().__init__(f"Line {line}: {message}" if line else message)


@dataclass
class Token:
    kind: str
    value: str
    line: int


_TOKEN_RE = re.compile(
    r"(?P<COMMENT>#[^\n]*)"
    r'|(?P<STRING>"[^"]*")'
    r"|(?P<NUMBER>\d+(?:\.\d+)?)"
    r"|(?P<IDENT>[a-zA-Z_][a-zA-Z0-9_]*)"
    r"|(?P<LBRACE>\{)"
    r"|(?P<RBRACE>\})"
    r"|(?P<LBRACKET>\[)"
    r"|(?P<RBRACKET>\])"
    r"|(?P<EQ>=)"
    r"|(?P<COMMA>,)"
    r"|(?P<DOT>\.)"
    r"|(?P<WS>\s+)"
)


def _tokenize(src: str) -> list[Token]:
    tokens: list[Token] = []
    line = 1
    pos = 0
    while pos < len(src):
        m = _TOKEN_RE.match(src, pos)
        if not m:
            raise ParseError(f"Unexpected character: {src[pos]!r}", line)
        kind = m.lastgroup
        value = m.group()
        if kind == "WS":
            line += value.count("\n")
        elif kind != "COMMENT" and kind is not None:
            tokens.append(Token(kind, value, line))
        pos = m.end()
    return tokens


class _Parser:
    def __init__(self, tokens: list[Token]):
        self._tokens = tokens
        self._pos = 0
        self._label_to_name: dict[tuple[str, str], str] = {}

    def _peek(self) -> Token | None:
        if self._pos < len(self._tokens):
            return self._tokens[self._pos]
        return None

    def _consume(self, kind: str | None = None, value: str | None = None) -> Token:
        tok = self._peek()
        if tok is None:
            raise ParseError("Unexpected end of file")
        if kind and tok.kind != kind:
            expected = _KIND_LABELS.get(kind, kind)
            got = _KIND_LABELS.get(tok.kind, tok.kind)
            raise ParseError(f"Expected {expected}, got {got} ({tok.value!r})", tok.line)
        if value and tok.value != value:
            raise ParseError(f"Expected {value!r}, got {tok.value!r}", tok.line)
        self._pos += 1
        return tok

    def _consume_string(self) -> str:
        tok = self._consume("STRING")
        return tok.value[1:-1]

    def _parse_value(self) -> str | int | float | list[Any] | dict[str, Any]:
        tok = self._peek()
        if tok is None:
            raise ParseError("Expected value, got end of file")
        if tok.kind == "STRING":
            self._pos += 1
            return tok.value[1:-1]
        if tok.kind == "NUMBER":
            self._pos += 1
            return int(tok.value) if "." not in tok.value else float(tok.value)
        if tok.kind == "LBRACE":
            return self._parse_object()
        if tok.kind == "LBRACKET":
            return self._parse_array()
        if tok.kind == "IDENT":
            if (
                self._pos + 4 < len(self._tokens)
                and self._tokens[self._pos + 1].kind == "DOT"
                and self._tokens[self._pos + 2].kind == "IDENT"
                and self._tokens[self._pos + 3].kind == "DOT"
                and self._tokens[self._pos + 4].kind == "IDENT"
            ):
                res_type = self._tokens[self._pos].value
                label = self._tokens[self._pos + 2].value
                attr = self._tokens[self._pos + 4].value
                self._pos += 5
                key = (res_type, label)
                if key not in self._label_to_name:
                    raise ParseError(
                        f"Unresolved reference: {res_type}.{label}.{attr} — '{label}' not defined",
                        tok.line,
                    )
                if attr != "name":
                    raise ParseError(f"Only .name supported in references, got .{attr}", tok.line)
                return self._label_to_name[key]
            self._pos += 1
            return tok.value
        raise ParseError(f"Unexpected token {tok.kind} ({tok.value!r})", tok.line)

    def _parse_object(self) -> dict[str, Any]:
        self._consume("LBRACE")
        result: dict[str, Any] = {}
        while (tok := self._peek()) is not None and tok.kind != "RBRACE":
            key_tok = self._consume("IDENT")
            self._consume("EQ")
            result[key_tok.value] = self._parse_value()
        self._consume("RBRACE")
        return result

    def _parse_array(self) -> list[Any]:
        self._consume("LBRACKET")
        result: list[Any] = []
        while (tok := self._peek()) is not None and tok.kind != "RBRACKET":
            result.append(self._parse_value())
            if (tok2 := self._peek()) is not None and tok2.kind == "COMMA":
                self._pos += 1
        self._consume("RBRACKET")
        return result

    def _parse_attrs(self) -> dict[str, Any]:
        self._consume("LBRACE")
        attrs: dict[str, Any] = {}
        while (tok := self._peek()) is not None and tok.kind != "RBRACE":
            key_tok = self._consume("IDENT")
            self._consume("EQ")
            attrs[key_tok.value] = self._parse_value()
        self._consume("RBRACE")
        return attrs

    def _build_entity(self, label: str, attrs: dict[str, Any], line: int) -> EntityDef:
        name = attrs.get("name")
        if not name:
            raise ParseError(f"lattice_entity '{label}' missing 'name'", line)
        if "fields" not in attrs:
            raise ParseError(f"lattice_entity '{label}' missing 'fields' block", line)
        raw_fields = attrs["fields"]
        if not isinstance(raw_fields, dict):
            raise ParseError(f"lattice_entity '{label}' fields must be a block", line)
        fields_dict = cast(dict[str, str], raw_fields)
        fields: list[FieldDef] = []
        for fname, ftype in fields_dict.items():
            if ftype not in _VALID_FIELD_TYPES:
                raise ParseError(
                    f"Unknown field type '{ftype}' for field '{fname}' in entity '{name}'. "
                    f"Valid: {', '.join(sorted(_VALID_FIELD_TYPES))}",
                    line,
                )
            fields.append(FieldDef(name=fname, type=ftype))
        return EntityDef(name=name, fields=fields)

    def _build_api(self, label: str, attrs: dict[str, Any], line: int) -> ApiDef:
        name = attrs.get("name")
        method = attrs.get("method", "")
        path = attrs.get("path", "")
        if not name:
            raise ParseError(f"lattice_api '{label}' missing 'name'", line)
        if not method:
            raise ParseError(f"lattice_api '{label}' missing 'method'", line)
        if not path:
            raise ParseError(f"lattice_api '{label}' missing 'path'", line)
        if method.upper() not in _VALID_METHODS:
            raise ParseError(
                f"Invalid method '{method}' in api '{name}'. Valid: {', '.join(_VALID_METHODS)}",
                line,
            )
        return ApiDef(
            name=name,
            method=method.upper(),
            path=path,
            input_entity=attrs.get("input") or None,
            output_entity=attrs.get("output") or None,
        )

    def _build_event(self, label: str, attrs: dict[str, Any], line: int) -> EventDef:
        name = attrs.get("name")
        if not name:
            raise ParseError(f"lattice_event '{label}' missing 'name'", line)
        raw_payload = attrs.get("payload", {})
        if not isinstance(raw_payload, dict):
            raise ParseError(f"lattice_event '{label}' payload must be a block", line)
        payload_dict = cast(dict[str, str], raw_payload)
        payload: list[FieldDef] = []
        for fname, ftype in payload_dict.items():
            if ftype not in _VALID_FIELD_TYPES:
                raise ParseError(f"Unknown type '{ftype}' in event '{name}' payload", line)
            payload.append(FieldDef(name=fname, type=ftype))
        return EventDef(name=name, payload=payload)

    def _build_workflow(self, label: str, attrs: dict[str, Any], line: int) -> WorkflowDef:
        name = attrs.get("name")
        steps = attrs.get("steps", [])
        if not name:
            raise ParseError(f"lattice_workflow '{label}' missing 'name'", line)
        if not isinstance(steps, list):
            raise ParseError(f"lattice_workflow '{label}' steps must be a list", line)
        steps_list = cast(list[str], steps)
        return WorkflowDef(name=name, steps=steps_list)

    def _build_queue(self, label: str, attrs: dict[str, Any], line: int) -> QueueDef:
        name = attrs.get("name")
        if not name:
            raise ParseError(f"lattice_queue '{label}' missing 'name'", line)
        retries = attrs.get("retries", 3)
        return QueueDef(name=name, retries=int(retries))

    def _first_pass(self):
        """Collect (type, label) -> name for reference resolution."""
        saved = self._pos
        while (tok := self._peek()) is not None:
            if tok.kind == "IDENT" and tok.value == "resource":
                self._pos += 1
                res_type = self._consume_string()
                label = self._consume_string()
                self._consume("LBRACE")
                depth = 1
                name = label
                while (t := self._peek()) is not None and depth > 0:
                    if t.kind == "LBRACE":
                        depth += 1
                        self._pos += 1
                    elif t.kind == "RBRACE":
                        depth -= 1
                        self._pos += 1
                    elif t.kind == "IDENT" and t.value == "name" and depth == 1:
                        self._pos += 1
                        if (eq_tok := self._peek()) is not None and eq_tok.kind == "EQ":
                            self._pos += 1
                            if (str_tok := self._peek()) is not None and str_tok.kind == "STRING":
                                name = self._consume_string()
                    else:
                        self._pos += 1
                key = (res_type, label)
                if key in self._label_to_name:
                    raise ParseError(
                        f'Duplicate resource: {res_type} "{label}" is defined more than once', 0
                    )
                self._label_to_name[key] = name
            else:
                self._pos += 1
        self._pos = saved

    def parse(self) -> LatticeSpec:
        self._first_pass()
        spec = LatticeSpec()
        while (tok := self._peek()) is not None:
            if tok.kind != "IDENT" or tok.value != "resource":
                raise ParseError(f"Expected 'resource' block, got {tok.value!r}", tok.line)
            self._pos += 1
            res_type = self._consume_string()
            label = self._consume_string()
            peek_tok = self._peek()
            line = peek_tok.line if peek_tok is not None else 0
            if res_type not in _VALID_RESOURCE_TYPES:
                raise ParseError(
                    f"Unknown resource type '{res_type}'. "
                    f"Valid: {', '.join(sorted(_VALID_RESOURCE_TYPES))}",
                    line,
                )
            attrs = self._parse_attrs()
            if res_type == "lattice_entity":
                spec.entities.append(self._build_entity(label, attrs, line))
            elif res_type == "lattice_api":
                spec.apis.append(self._build_api(label, attrs, line))
            elif res_type == "lattice_event":
                spec.events.append(self._build_event(label, attrs, line))
            elif res_type == "lattice_workflow":
                spec.workflows.append(self._build_workflow(label, attrs, line))
            elif res_type == "lattice_queue":
                spec.queues.append(self._build_queue(label, attrs, line))
        return spec


def parse_string(src: str) -> LatticeSpec:
    """Parse a .lattice source string and return a LatticeSpec."""
    tokens = _tokenize(src)
    return _Parser(tokens).parse()


def parse_file(path: str) -> LatticeSpec:
    """Parse a .lattice file and return a LatticeSpec."""
    with open(path) as f:
        return parse_string(f.read())


if __name__ == "__main__":
    import sys

    spec = parse_file(sys.argv[1] if len(sys.argv) > 1 else "example.lattice")
    print(f"Entities:  {[e.name for e in spec.entities]}")
    print(f"APIs:      {[a.name for a in spec.apis]}")
    print(f"Events:    {[e.name for e in spec.events]}")
    print(f"Workflows: {[w.name for w in spec.workflows]}")
    print(f"Queues:    {[q.name for q in spec.queues]}")
