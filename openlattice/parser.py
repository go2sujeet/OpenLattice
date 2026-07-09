"""TF-style parser for OpenLattice .lattice files."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, cast

from openlattice.ir import (
    AgentDef,
    ApiDef,
    ConnectorDef,
    EntityDef,
    EventDef,
    FieldDef,
    LatticeSpec,
    QueueDef,
    WorkflowDef,
    WorkflowStep,
)

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
    "lattice_connector",
    "lattice_agent",
}
_VALID_FIELD_TYPES = {"uuid", "int", "float", "string", "bool", "datetime", "json"}
_VALID_METHODS = {"GET", "POST", "PUT", "DELETE", "PATCH"}
_VALID_CONNECTOR_KINDS = {"http_webhook"}


def _infer_crud_operation(method: str, path: str) -> str | None:
    """Infer CRUD semantics from HTTP method + path shape (has a path param or not)."""
    has_path_param = "{" in path
    method = method.upper()
    if method == "GET":
        return "read" if has_path_param else "list"
    if method == "POST":
        return "create"
    if method in ("PUT", "PATCH"):
        return "update"
    if method == "DELETE":
        return "delete"
    return None


def _to_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.lower() == "true"
    return bool(value)


def _link_relationships(spec: LatticeSpec) -> None:
    """Derive EventDef.published_by / consumed_by from workflow/api/queue references.

    Publishers: workflow steps whose output is the event's name, and APIs that
    list the event in `publishes`.
    Consumers: workflows triggered by the event, and queues carrying it as
    their message_type.
    """
    for event in spec.events:
        for workflow in spec.workflows:
            if any(step.output == event.name for step in workflow.steps):
                if workflow.name not in event.published_by:
                    event.published_by.append(workflow.name)
            if workflow.trigger == event.name:
                if workflow.name not in event.consumed_by:
                    event.consumed_by.append(workflow.name)
        for api in spec.apis:
            if event.name in api.publishes and api.name not in event.published_by:
                event.published_by.append(api.name)
        for queue in spec.queues:
            if queue.message_type == event.name and queue.name not in event.consumed_by:
                event.consumed_by.append(queue.name)


class ParseError(Exception):
    def __init__(self, message: str, line: int = 0):
        self.message = message
        self.line = line
        super().__init__(f"Line {line}: {message}" if line else message)


def _validate_agents(spec: LatticeSpec) -> None:
    """Verify each AgentDef's tools/output_type reference known resources.

    `tools` entries must match the `.name` of a defined ApiDef or ConnectorDef.
    `output_type`, if set, must match the `.name` of a defined EntityDef.
    """
    known_tool_names = {a.name for a in spec.apis} | {c.name for c in spec.connectors}
    known_entity_names = {e.name for e in spec.entities}
    for agent in spec.agents:
        for tool in agent.tools:
            if tool not in known_tool_names:
                raise ParseError(
                    f"lattice_agent '{agent.name}' references unknown tool '{tool}' — "
                    f"no lattice_api or lattice_connector named '{tool}'"
                )
        if agent.output_type is not None and agent.output_type not in known_entity_names:
            raise ParseError(
                f"lattice_agent '{agent.name}' references unknown output_type "
                f"'{agent.output_type}' — no lattice_entity named '{agent.output_type}'"
            )


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
            if tok.kind == "STRING":
                key = self._consume_string()
            else:
                key = self._consume("IDENT").value
            self._consume("EQ")
            result[key] = self._parse_value()
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
        raw_publishes = attrs.get("publishes", [])
        if not isinstance(raw_publishes, list):
            raise ParseError(f"lattice_api '{label}' publishes must be a list", line)
        publishes = cast(list[str], raw_publishes)
        return ApiDef(
            name=name,
            method=method.upper(),
            path=path,
            input_entity=attrs.get("input") or None,
            output_entity=attrs.get("output") or None,
            publishes=publishes,
            crud_operation=_infer_crud_operation(method.upper(), path),
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
        raw_steps = attrs.get("steps", [])
        if not name:
            raise ParseError(f"lattice_workflow '{label}' missing 'name'", line)
        if not isinstance(raw_steps, list):
            raise ParseError(f"lattice_workflow '{label}' steps must be a list", line)
        steps: list[WorkflowStep] = []
        for raw_step in cast(list[Any], raw_steps):
            if isinstance(raw_step, str):
                steps.append(WorkflowStep(name=raw_step))
            elif isinstance(raw_step, dict):
                step_dict = cast(dict[str, str], raw_step)
                step_name = step_dict.get("name")
                if not step_name:
                    raise ParseError(f"lattice_workflow '{label}' step missing 'name'", line)
                steps.append(
                    WorkflowStep(
                        name=step_name,
                        input=step_dict.get("input") or None,
                        output=step_dict.get("output") or None,
                        on_error=step_dict.get("on_error") or None,
                    )
                )
            else:
                raise ParseError(
                    f"lattice_workflow '{label}' step must be a string or object", line
                )
        return WorkflowDef(name=name, steps=steps, trigger=attrs.get("trigger") or None)

    def _build_queue(self, label: str, attrs: dict[str, Any], line: int) -> QueueDef:
        name = attrs.get("name")
        if not name:
            raise ParseError(f"lattice_queue '{label}' missing 'name'", line)
        retries = attrs.get("retries", 3)
        return QueueDef(
            name=name,
            message_type=attrs.get("message_type") or None,
            retries=int(retries),
            dlq=_to_bool(attrs.get("dlq", False)),
        )

    def _build_connector(self, label: str, attrs: dict[str, Any], line: int) -> ConnectorDef:
        name = attrs.get("name")
        if not name:
            raise ParseError(f"lattice_connector '{label}' missing 'name'", line)
        kind = attrs.get("kind")
        if not kind:
            raise ParseError(f"lattice_connector '{label}' missing 'kind'", line)
        if kind not in _VALID_CONNECTOR_KINDS:
            raise ParseError(
                f"Unknown connector kind '{kind}' in connector '{name}'. "
                f"Valid: {', '.join(sorted(_VALID_CONNECTOR_KINDS))}",
                line,
            )
        url = attrs.get("url")
        if not url:
            raise ParseError(f"lattice_connector '{label}' missing 'url'", line)
        method = attrs.get("method", "POST")
        if method.upper() not in _VALID_METHODS:
            raise ParseError(
                f"Invalid method '{method}' in connector '{name}'. "
                f"Valid: {', '.join(_VALID_METHODS)}",
                line,
            )
        raw_headers = attrs.get("headers", {})
        if not isinstance(raw_headers, dict):
            raise ParseError(f"lattice_connector '{label}' headers must be a block", line)
        raw_body_template = attrs.get("body_template", {})
        if not isinstance(raw_body_template, dict):
            raise ParseError(f"lattice_connector '{label}' body_template must be a block", line)
        return ConnectorDef(
            name=name,
            kind=kind,
            url=url,
            method=method.upper(),
            headers=cast(dict[str, str], raw_headers),
            body_template=cast(dict[str, str], raw_body_template),
        )

    def _build_agent(self, label: str, attrs: dict[str, Any], line: int) -> AgentDef:
        name = attrs.get("name")
        if not name:
            raise ParseError(f"lattice_agent '{label}' missing 'name'", line)
        model = attrs.get("model")
        if not model:
            raise ParseError(f"lattice_agent '{label}' missing 'model'", line)
        system_prompt = attrs.get("system_prompt")
        if not system_prompt:
            raise ParseError(f"lattice_agent '{label}' missing 'system_prompt'", line)
        raw_tools = attrs.get("tools", [])
        if not isinstance(raw_tools, list):
            raise ParseError(f"lattice_agent '{label}' tools must be a list", line)
        tools = cast(list[str], raw_tools)
        return AgentDef(
            name=name,
            model=model,
            system_prompt=system_prompt,
            output_type=attrs.get("output_type") or None,
            tools=tools,
        )

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
            elif res_type == "lattice_connector":
                spec.connectors.append(self._build_connector(label, attrs, line))
            elif res_type == "lattice_agent":
                spec.agents.append(self._build_agent(label, attrs, line))
        _link_relationships(spec)
        _validate_agents(spec)
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
    print(f"Connectors: {[c.name for c in spec.connectors]}")
    print(f"Agents:    {[ag.name for ag in spec.agents]}")
