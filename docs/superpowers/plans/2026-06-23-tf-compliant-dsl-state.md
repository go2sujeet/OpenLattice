# TF-Compliant DSL + State Management Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Evolve OpenLattice's `.lattice` DSL to use Terraform-style `resource` blocks with real state management — so `plan` shows actual diffs and `apply` is incremental, keeping Option B (OpenTofu provider) a zero-redesign migration.

**Architecture:** Parser rewritten to emit `resource "lattice_*" "label"` blocks identical in structure to HCL. A new `state.py` module reads/writes `.lattice-state.json` (TF state file analog) using SHA-256 content hashes per resource. CLI `plan` diffs current spec against state to show `+/-/~` per resource; `apply` writes only changed resources and updates state. IR and generators are untouched.

**Tech Stack:** Python 3.12, Click, Rich, hashlib (stdlib), existing FastAPI/SQLAlchemy generators.

---

## File Map

| File | Action | Responsibility |
|------|--------|---------------|
| `openlattice/parser.py` | **Rewrite** | Parse TF-style `resource` blocks → `LatticeSpec` |
| `openlattice/state.py` | **Create** | Read/write `.lattice-state.json`, compute diffs |
| `openlattice/cli.py` | **Modify** | `plan` = diff vs state, `apply` = incremental + state write |
| `example.lattice` | **Rewrite** | New TF-style syntax |
| `examples/ecommerce/ecommerce.lattice` | **Rewrite** | New TF-style syntax |
| `examples/blog/blog.lattice` | **Rewrite** | New TF-style syntax |
| `tests/test_parser.py` | **Create** | Parser unit tests |
| `tests/test_state.py` | **Create** | State diff unit tests |
| `openlattice/ir.py` | **Unchanged** | LatticeSpec dataclasses stay identical |
| `openlattice/generators/` | **Unchanged** | Generators consume LatticeSpec — no changes needed |

---

## New DSL Syntax (reference for all tasks)

```hcl
resource "lattice_entity" "order" {
  name = "Order"
  fields = {
    id     = "uuid"
    amount = "int"
    status = "string"
  }
}

resource "lattice_api" "create_order" {
  name   = "CreateOrder"
  method = "POST"
  path   = "/orders"
  input  = lattice_entity.order.name
  output = lattice_entity.order.name
}

resource "lattice_event" "order_created" {
  name = "OrderCreated"
  payload = {
    order_id = "uuid"
    amount   = "int"
  }
}

resource "lattice_workflow" "checkout" {
  name  = "Checkout"
  steps = ["validate_order", "charge_customer", "publish_order_created"]
}

resource "lattice_queue" "email_notifications" {
  name    = "email_notifications"
  retries = 3
}
```

Key changes from old syntax:
- `entity "Order" { ... }` → `resource "lattice_entity" "order" { ... }`
- Field types quoted: `id = uuid` → `id = "uuid"`
- References: `input = Order` → `input = lattice_entity.order.name` (resolved at parse time to `"Order"`)
- All resource types: `lattice_entity`, `lattice_api`, `lattice_event`, `lattice_workflow`, `lattice_queue`

---

## State File Format (`.lattice-state.json`)

```json
{
  "version": "1",
  "serial": 3,
  "lineage": "550e8400-e29b-41d4-a716-446655440000",
  "resources": [
    {
      "type": "lattice_entity",
      "label": "order",
      "attributes": {
        "name": "Order",
        "fields": { "id": "uuid", "amount": "int", "status": "string" }
      },
      "spec_hash": "sha256:a1b2c3..."
    }
  ]
}
```

`spec_hash` = `sha256(json.dumps(attributes, sort_keys=True))` — deterministic, reproducible.

---

## Plan Output Format

```
OpenLattice will perform the following actions:

  + resource "lattice_entity" "order"           # will be created
      name   = "Order"
      fields = {id: uuid, amount: int, ...}

  ~ resource "lattice_api" "create_order"       # will be updated
    ~ method = "GET" → "POST"

  - resource "lattice_entity" "product"         # will be destroyed

Plan: 2 to add, 1 to change, 1 to destroy.

Run `openlattice apply <file>` to perform these actions.
```

Colors: green `+`, yellow `~`, red `-`.

---

## Task 1: Rewrite Parser for TF-Style Blocks

**Files:**
- Rewrite: `openlattice/parser.py`
- Create: `tests/test_parser.py`

### Step 1.1: Write failing tests first

Create `tests/test_parser.py`:

```python
import pytest
from openlattice.parser import parse_string, ParseError
from openlattice.ir import LatticeSpec, EntityDef, FieldDef, ApiDef, EventDef, WorkflowDef, QueueDef

MINIMAL_SPEC = '''
resource "lattice_entity" "order" {
  name = "Order"
  fields = {
    id     = "uuid"
    amount = "int"
    status = "string"
  }
}

resource "lattice_api" "create_order" {
  name   = "CreateOrder"
  method = "POST"
  path   = "/orders"
  input  = lattice_entity.order.name
  output = lattice_entity.order.name
}
'''

def test_parse_entity():
    spec = parse_string(MINIMAL_SPEC)
    assert len(spec.entities) == 1
    e = spec.entities[0]
    assert e.name == "Order"
    assert len(e.fields) == 3
    assert e.fields[0].name == "id"
    assert e.fields[0].type == "uuid"
    assert e.fields[1].name == "amount"
    assert e.fields[1].type == "int"

def test_parse_api():
    spec = parse_string(MINIMAL_SPEC)
    assert len(spec.apis) == 1
    a = spec.apis[0]
    assert a.name == "CreateOrder"
    assert a.method == "POST"
    assert a.path == "/orders"
    assert a.input_entity == "Order"   # reference resolved
    assert a.output_entity == "Order"  # reference resolved

def test_parse_event():
    src = '''
resource "lattice_event" "order_created" {
  name = "OrderCreated"
  payload = {
    order_id = "uuid"
    amount   = "int"
  }
}
'''
    spec = parse_string(src)
    assert len(spec.events) == 1
    assert spec.events[0].name == "OrderCreated"
    assert spec.events[0].payload[0].name == "order_id"

def test_parse_workflow():
    src = '''
resource "lattice_workflow" "checkout" {
  name  = "Checkout"
  steps = ["validate_order", "charge_customer"]
}
'''
    spec = parse_string(src)
    assert len(spec.workflows) == 1
    assert spec.workflows[0].name == "Checkout"
    assert spec.workflows[0].steps == ["validate_order", "charge_customer"]

def test_parse_queue():
    src = '''
resource "lattice_queue" "emails" {
  name    = "emails"
  retries = 3
}
'''
    spec = parse_string(src)
    assert len(spec.queues) == 1
    assert spec.queues[0].name == "emails"
    assert spec.queues[0].retries == 3

def test_parse_comment():
    src = '''
# This is a comment
resource "lattice_entity" "task" {
  name = "Task"  # inline comment
  fields = {
    id = "uuid"  # primary key
  }
}
'''
    spec = parse_string(src)
    assert spec.entities[0].name == "Task"

def test_unknown_resource_type_raises():
    src = 'resource "lattice_unknown" "foo" { name = "Foo" }'
    with pytest.raises(ParseError) as exc:
        parse_string(src)
    assert "unknown resource type" in str(exc.value).lower()

def test_invalid_field_type_raises():
    src = '''
resource "lattice_entity" "bad" {
  name = "Bad"
  fields = { id = "badtype" }
}
'''
    with pytest.raises(ParseError) as exc:
        parse_string(src)
    assert "badtype" in str(exc.value)

def test_reference_resolution():
    src = '''
resource "lattice_entity" "product" {
  name = "Product"
  fields = { id = "uuid" }
}
resource "lattice_api" "get_product" {
  name   = "GetProduct"
  method = "GET"
  path   = "/products/{id}"
  output = lattice_entity.product.name
}
'''
    spec = parse_string(src)
    assert spec.apis[0].output_entity == "Product"

def test_unresolved_reference_raises():
    src = '''
resource "lattice_api" "bad" {
  name   = "Bad"
  method = "GET"
  path   = "/bad"
  output = lattice_entity.nonexistent.name
}
'''
    with pytest.raises(ParseError) as exc:
        parse_string(src)
    assert "nonexistent" in str(exc.value)
```

- [ ] **Step 1.2: Run tests to verify they fail**

```bash
uv run pytest tests/test_parser.py -v 2>&1 | head -30
```

Expected: All tests fail with `ImportError` or `ParseError` (old parser can't handle new syntax).

- [ ] **Step 1.3: Rewrite `openlattice/parser.py`**

Replace entire file with:

```python
"""TF-style parser for OpenLattice .lattice files.

Grammar (simplified):
  spec     = resource*
  resource = 'resource' STRING STRING '{' attr* '}'
  attr     = IDENT '=' value
  value    = STRING | NUMBER | IDENT | ref | object | array
  ref      = IDENT '.' IDENT '.' IDENT          (e.g. lattice_entity.order.name)
  object   = '{' (IDENT '=' value)* '}'
  array    = '[' (STRING (',' STRING)*)? ']'
"""

import re
import json
import hashlib
from dataclasses import dataclass
from openlattice.ir import (
    LatticeSpec, EntityDef, FieldDef, ApiDef, EventDef, WorkflowDef, QueueDef
)

_VALID_RESOURCE_TYPES = {
    "lattice_entity", "lattice_api", "lattice_event", "lattice_workflow", "lattice_queue"
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
    kind: str   # STRING | NUMBER | IDENT | LBRACE | RBRACE | LBRACKET | RBRACKET | EQ | COMMA | DOT
    value: str
    line: int


_TOKEN_RE = re.compile(
    r'(?P<COMMENT>#[^\n]*)'
    r'|(?P<STRING>"[^"]*")'
    r'|(?P<NUMBER>\d+(?:\.\d+)?)'
    r'|(?P<IDENT>[a-zA-Z_][a-zA-Z0-9_]*)'
    r'|(?P<LBRACE>\{)'
    r'|(?P<RBRACE>\})'
    r'|(?P<LBRACKET>\[)'
    r'|(?P<RBRACKET>\])'
    r'|(?P<EQ>=)'
    r'|(?P<COMMA>,)'
    r'|(?P<DOT>\.)'
    r'|(?P<WS>\s+)'
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
        elif kind != "COMMENT":
            tokens.append(Token(kind, value, line))
        pos = m.end()
    return tokens


class _Parser:
    def __init__(self, tokens: list[Token]):
        self._tokens = tokens
        self._pos = 0
        # First pass: collect all resource labels → name for reference resolution
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
            raise ParseError(f"Expected {kind}, got {tok.kind} ({tok.value!r})", tok.line)
        if value and tok.value != value:
            raise ParseError(f"Expected {value!r}, got {tok.value!r}", tok.line)
        self._pos += 1
        return tok

    def _consume_string(self) -> str:
        tok = self._consume("STRING")
        return tok.value[1:-1]  # strip quotes

    def _parse_value(self, attrs: dict) -> str | int | float | list | dict:
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
            # Could be a reference: type.label.attr (3 IDENTs separated by DOTs)
            # Peek ahead to detect
            if (self._pos + 4 < len(self._tokens)
                    and self._tokens[self._pos + 1].kind == "DOT"
                    and self._tokens[self._pos + 2].kind == "IDENT"
                    and self._tokens[self._pos + 3].kind == "DOT"
                    and self._tokens[self._pos + 4].kind == "IDENT"):
                res_type = self._tokens[self._pos].value
                label = self._tokens[self._pos + 2].value
                attr = self._tokens[self._pos + 4].value
                self._pos += 5
                key = (res_type, label)
                if key not in self._label_to_name:
                    raise ParseError(
                        f"Unresolved reference: {res_type}.{label}.{attr} — "
                        f"'{label}' not defined before this reference",
                        tok.line
                    )
                if attr != "name":
                    raise ParseError(
                        f"Only .name attribute supported in references, got .{attr}", tok.line
                    )
                return self._label_to_name[key]
            # Bare identifier — treat as unquoted string value (e.g. method = POST)
            self._pos += 1
            return tok.value

        raise ParseError(f"Unexpected token {tok.kind} ({tok.value!r})", tok.line)

    def _parse_object(self) -> dict:
        self._consume("LBRACE")
        result: dict = {}
        while self._peek() and self._peek().kind != "RBRACE":
            key_tok = self._consume("IDENT")
            self._consume("EQ")
            result[key_tok.value] = self._parse_value(result)
        self._consume("RBRACE")
        return result

    def _parse_array(self) -> list:
        self._consume("LBRACKET")
        result: list = []
        while self._peek() and self._peek().kind != "RBRACKET":
            result.append(self._parse_value({}))
            if self._peek() and self._peek().kind == "COMMA":
                self._pos += 1
        self._consume("RBRACKET")
        return result

    def _parse_attrs(self) -> dict:
        self._consume("LBRACE")
        attrs: dict = {}
        while self._peek() and self._peek().kind != "RBRACE":
            key_tok = self._consume("IDENT")
            self._consume("EQ")
            attrs[key_tok.value] = self._parse_value(attrs)
        self._consume("RBRACE")
        return attrs

    def _build_entity(self, label: str, attrs: dict, line: int) -> EntityDef:
        name = attrs.get("name")
        if not name:
            raise ParseError(f"lattice_entity '{label}' missing 'name'", line)
        raw_fields = attrs.get("fields", {})
        if not isinstance(raw_fields, dict):
            raise ParseError(f"lattice_entity '{label}' fields must be a block", line)
        fields = []
        for fname, ftype in raw_fields.items():
            if ftype not in _VALID_FIELD_TYPES:
                raise ParseError(
                    f"Unknown field type '{ftype}' for field '{fname}' in entity '{name}'. "
                    f"Valid types: {', '.join(sorted(_VALID_FIELD_TYPES))}", line
                )
            fields.append(FieldDef(name=fname, type=ftype))
        return EntityDef(name=name, fields=fields)

    def _build_api(self, label: str, attrs: dict, line: int) -> ApiDef:
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
                f"Invalid method '{method}' in api '{name}'. "
                f"Valid: {', '.join(_VALID_METHODS)}", line
            )
        return ApiDef(
            name=name,
            method=method.upper(),
            path=path,
            input_entity=attrs.get("input") or None,
            output_entity=attrs.get("output") or None,
        )

    def _build_event(self, label: str, attrs: dict, line: int) -> EventDef:
        name = attrs.get("name")
        if not name:
            raise ParseError(f"lattice_event '{label}' missing 'name'", line)
        raw_payload = attrs.get("payload", {})
        if not isinstance(raw_payload, dict):
            raise ParseError(f"lattice_event '{label}' payload must be a block", line)
        payload = []
        for fname, ftype in raw_payload.items():
            if ftype not in _VALID_FIELD_TYPES:
                raise ParseError(f"Unknown type '{ftype}' in event '{name}' payload", line)
            payload.append(FieldDef(name=fname, type=ftype))
        return EventDef(name=name, payload=payload)

    def _build_workflow(self, label: str, attrs: dict, line: int) -> WorkflowDef:
        name = attrs.get("name")
        steps = attrs.get("steps", [])
        if not name:
            raise ParseError(f"lattice_workflow '{label}' missing 'name'", line)
        if not isinstance(steps, list):
            raise ParseError(f"lattice_workflow '{label}' steps must be a list", line)
        return WorkflowDef(name=name, steps=steps)

    def _build_queue(self, label: str, attrs: dict, line: int) -> QueueDef:
        name = attrs.get("name")
        if not name:
            raise ParseError(f"lattice_queue '{label}' missing 'name'", line)
        retries = attrs.get("retries", 3)
        return QueueDef(name=name, retries=int(retries))

    def parse(self) -> LatticeSpec:
        # Two-pass: first collect all resource names for reference resolution,
        # then parse fully.
        self._first_pass()
        self._pos = 0
        return self._second_pass()

    def _first_pass(self):
        """Collect (type, label) → name mappings for reference resolution."""
        pos = self._pos
        while self._peek():
            tok = self._peek()
            if tok.kind == "IDENT" and tok.value == "resource":
                self._pos += 1
                res_type = self._consume_string()
                label = self._consume_string()
                # Skip into block looking for name = "..."
                self._consume("LBRACE")
                depth = 1
                name = label  # fallback: use label as name
                while self._peek() and depth > 0:
                    t = self._peek()
                    if t.kind == "LBRACE":
                        depth += 1
                        self._pos += 1
                    elif t.kind == "RBRACE":
                        depth -= 1
                        self._pos += 1
                    elif t.kind == "IDENT" and t.value == "name" and depth == 1:
                        self._pos += 1
                        if self._peek() and self._peek().kind == "EQ":
                            self._pos += 1
                            if self._peek() and self._peek().kind == "STRING":
                                name = self._consume_string()
                    else:
                        self._pos += 1
                self._label_to_name[(res_type, label)] = name
            else:
                self._pos += 1
        self._pos = pos

    def _second_pass(self) -> LatticeSpec:
        spec = LatticeSpec()
        while self._peek():
            tok = self._peek()
            if tok.kind != "IDENT" or tok.value != "resource":
                raise ParseError(f"Expected 'resource' block, got {tok.value!r}", tok.line)
            self._pos += 1
            res_type = self._consume_string()
            label = self._consume_string()
            line = self._peek().line if self._peek() else 0

            if res_type not in _VALID_RESOURCE_TYPES:
                raise ParseError(
                    f"Unknown resource type '{res_type}'. "
                    f"Valid types: {', '.join(sorted(_VALID_RESOURCE_TYPES))}", line
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
```

- [ ] **Step 1.4: Run tests to verify they pass**

```bash
uv run pytest tests/test_parser.py -v
```

Expected: All 9 tests pass.

- [ ] **Step 1.5: Commit**

```bash
git add openlattice/parser.py tests/test_parser.py
git commit -m "refactor: rewrite parser for TF-style resource blocks"
```

---

## Task 2: Add State Management

**Files:**
- Create: `openlattice/state.py`
- Create: `tests/test_state.py`

- [ ] **Step 2.1: Write failing tests**

Create `tests/test_state.py`:

```python
import json
import pytest
from openlattice.ir import LatticeSpec, EntityDef, FieldDef, ApiDef
from openlattice.state import (
    StateFile, ResourceState, compute_spec_hash,
    diff_spec_against_state, DiffResult,
    load_state, save_state,
)

def _make_spec() -> LatticeSpec:
    return LatticeSpec(
        entities=[EntityDef("Order", [FieldDef("id", "uuid"), FieldDef("amount", "int")])],
        apis=[ApiDef("CreateOrder", "POST", "/orders", "Order", "Order")],
    )

def test_compute_spec_hash_deterministic():
    spec = _make_spec()
    h1 = compute_spec_hash("lattice_entity", "order", {"name": "Order", "fields": {"id": "uuid"}})
    h2 = compute_spec_hash("lattice_entity", "order", {"name": "Order", "fields": {"id": "uuid"}})
    assert h1 == h2
    assert h1.startswith("sha256:")

def test_compute_spec_hash_changes_on_mutation():
    h1 = compute_spec_hash("lattice_entity", "order", {"name": "Order", "fields": {"id": "uuid"}})
    h2 = compute_spec_hash("lattice_entity", "order", {"name": "Order", "fields": {"id": "uuid", "amount": "int"}})
    assert h1 != h2

def test_diff_empty_state_all_new(tmp_path):
    spec = _make_spec()
    state = StateFile(resources=[])
    result = diff_spec_against_state(spec, state)
    assert result.to_add == ["lattice_entity.order", "lattice_api.create_order"]
    assert result.to_change == []
    assert result.to_destroy == []

def test_diff_unchanged_resource_not_in_diff(tmp_path):
    spec = _make_spec()
    # Pre-populate state with exact same entity
    h = compute_spec_hash(
        "lattice_entity", "order",
        {"name": "Order", "fields": {"id": "uuid", "amount": "int"}}
    )
    state = StateFile(resources=[
        ResourceState(type="lattice_entity", label="order",
                      attributes={"name": "Order", "fields": {"id": "uuid", "amount": "int"}},
                      spec_hash=h)
    ])
    result = diff_spec_against_state(spec, state)
    assert "lattice_entity.order" not in result.to_add
    assert "lattice_entity.order" not in result.to_change

def test_diff_changed_resource_in_change(tmp_path):
    spec = _make_spec()
    # State has wrong hash — simulates a field was added
    state = StateFile(resources=[
        ResourceState(type="lattice_entity", label="order",
                      attributes={"name": "Order", "fields": {"id": "uuid"}},
                      spec_hash="sha256:stale")
    ])
    result = diff_spec_against_state(spec, state)
    assert "lattice_entity.order" in result.to_change

def test_diff_removed_resource_in_destroy(tmp_path):
    spec = LatticeSpec()  # empty spec
    state = StateFile(resources=[
        ResourceState(type="lattice_entity", label="order",
                      attributes={"name": "Order", "fields": {}},
                      spec_hash="sha256:abc")
    ])
    result = diff_spec_against_state(spec, state)
    assert "lattice_entity.order" in result.to_destroy

def test_save_and_load_state(tmp_path):
    state = StateFile(resources=[
        ResourceState(
            type="lattice_entity",
            label="order",
            attributes={"name": "Order", "fields": {"id": "uuid"}},
            spec_hash="sha256:abc123"
        )
    ])
    path = tmp_path / ".lattice-state.json"
    save_state(state, str(path))
    loaded = load_state(str(path))
    assert len(loaded.resources) == 1
    assert loaded.resources[0].type == "lattice_entity"
    assert loaded.resources[0].label == "order"
    assert loaded.resources[0].spec_hash == "sha256:abc123"
    assert loaded.version == "1"

def test_load_state_missing_file_returns_empty(tmp_path):
    path = tmp_path / "nonexistent.json"
    state = load_state(str(path))
    assert state.resources == []
```

- [ ] **Step 2.2: Run tests to verify they fail**

```bash
uv run pytest tests/test_state.py -v 2>&1 | head -20
```

Expected: All fail with `ModuleNotFoundError: No module named 'openlattice.state'`.

- [ ] **Step 2.3: Implement `openlattice/state.py`**

```python
"""State management for OpenLattice — analogous to Terraform's tfstate."""

import json
import hashlib
import uuid as _uuid_mod
from dataclasses import dataclass, field, asdict
from openlattice.ir import LatticeSpec, EntityDef, ApiDef, EventDef, WorkflowDef, QueueDef


@dataclass
class ResourceState:
    type: str
    label: str
    attributes: dict
    spec_hash: str


@dataclass
class StateFile:
    resources: list[ResourceState] = field(default_factory=list)
    version: str = "1"
    serial: int = 0
    lineage: str = field(default_factory=lambda: str(_uuid_mod.uuid4()))


@dataclass
class DiffResult:
    to_add: list[str] = field(default_factory=list)      # "type.label"
    to_change: list[str] = field(default_factory=list)
    to_destroy: list[str] = field(default_factory=list)


def compute_spec_hash(res_type: str, label: str, attributes: dict) -> str:
    """Deterministic SHA-256 of a resource's attributes."""
    canonical = json.dumps({"type": res_type, "label": label, "attributes": attributes},
                           sort_keys=True)
    digest = hashlib.sha256(canonical.encode()).hexdigest()
    return f"sha256:{digest}"


def _entity_attrs(e: EntityDef) -> dict:
    return {"name": e.name, "fields": {f.name: f.type for f in e.fields}}

def _api_attrs(a: ApiDef) -> dict:
    return {k: v for k, v in {
        "name": a.name, "method": a.method, "path": a.path,
        "input": a.input_entity, "output": a.output_entity,
    }.items() if v is not None}

def _event_attrs(e: EventDef) -> dict:
    return {"name": e.name, "payload": {f.name: f.type for f in e.payload}}

def _workflow_attrs(w: WorkflowDef) -> dict:
    return {"name": w.name, "steps": w.steps}

def _queue_attrs(q: QueueDef) -> dict:
    return {"name": q.name, "retries": q.retries}


def _spec_resources(spec: LatticeSpec) -> list[tuple[str, str, dict]]:
    """Return (type, label, attributes) for every resource in the spec."""
    resources = []
    for e in spec.entities:
        label = e.name.lower()
        resources.append(("lattice_entity", label, _entity_attrs(e)))
    for a in spec.apis:
        # snake_case label from PascalCase name
        import re
        label = re.sub(r"([a-z])([A-Z])", r"\1_\2", a.name).lower()
        resources.append(("lattice_api", label, _api_attrs(a)))
    for e in spec.events:
        label = e.name.lower()
        resources.append(("lattice_event", label, _event_attrs(e)))
    for w in spec.workflows:
        label = w.name.lower()
        resources.append(("lattice_workflow", label, _workflow_attrs(w)))
    for q in spec.queues:
        resources.append(("lattice_queue", q.name.lower(), _queue_attrs(q)))
    return resources


def diff_spec_against_state(spec: LatticeSpec, state: StateFile) -> DiffResult:
    """Compute what needs to be added, changed, or destroyed."""
    current = {(r.type, r.label): r for r in state.resources}
    desired_keys = set()
    result = DiffResult()

    for res_type, label, attrs in _spec_resources(spec):
        key = (res_type, label)
        desired_keys.add(key)
        new_hash = compute_spec_hash(res_type, label, attrs)
        ref = f"{res_type}.{label}"
        if key not in current:
            result.to_add.append(ref)
        elif current[key].spec_hash != new_hash:
            result.to_change.append(ref)

    for (res_type, label), _ in current.items():
        if (res_type, label) not in desired_keys:
            result.to_destroy.append(f"{res_type}.{label}")

    return result


def build_new_state(spec: LatticeSpec, existing: StateFile) -> StateFile:
    """Build updated state from current spec (for use after apply)."""
    resources = []
    for res_type, label, attrs in _spec_resources(spec):
        resources.append(ResourceState(
            type=res_type,
            label=label,
            attributes=attrs,
            spec_hash=compute_spec_hash(res_type, label, attrs),
        ))
    return StateFile(
        resources=resources,
        version="1",
        serial=existing.serial + 1,
        lineage=existing.lineage,
    )


def save_state(state: StateFile, path: str = ".lattice-state.json") -> None:
    data = {
        "version": state.version,
        "serial": state.serial,
        "lineage": state.lineage,
        "resources": [
            {
                "type": r.type,
                "label": r.label,
                "attributes": r.attributes,
                "spec_hash": r.spec_hash,
            }
            for r in state.resources
        ],
    }
    with open(path, "w") as f:
        json.dump(data, f, indent=2)


def load_state(path: str = ".lattice-state.json") -> StateFile:
    try:
        with open(path) as f:
            data = json.load(f)
    except FileNotFoundError:
        return StateFile()
    return StateFile(
        version=data.get("version", "1"),
        serial=data.get("serial", 0),
        lineage=data.get("lineage", str(_uuid_mod.uuid4())),
        resources=[
            ResourceState(
                type=r["type"],
                label=r["label"],
                attributes=r["attributes"],
                spec_hash=r["spec_hash"],
            )
            for r in data.get("resources", [])
        ],
    )
```

- [ ] **Step 2.4: Run tests to verify they pass**

```bash
uv run pytest tests/test_state.py -v
```

Expected: All 8 tests pass.

- [ ] **Step 2.5: Commit**

```bash
git add openlattice/state.py tests/test_state.py
git commit -m "feat: add state management (diff, hash, load/save)"
```

---

## Task 3: Update CLI — Real Plan Diffs + Incremental Apply

**Files:**
- Modify: `openlattice/cli.py`

- [ ] **Step 3.1: Replace `openlattice/cli.py`**

```python
import click
from pathlib import Path
from rich.console import Console
from rich.panel import Panel
from rich.text import Text

from openlattice.parser import parse_file, ParseError
from openlattice.state import (
    load_state, save_state, diff_spec_against_state,
    build_new_state, _spec_resources, compute_spec_hash
)
from openlattice.generators.fastapi_gen import generate as gen_fastapi
from openlattice.generators.sqlalchemy_gen import generate as gen_sqlalchemy

console = Console()
STATE_FILE = ".lattice-state.json"


def _render_plan(diff, spec, state) -> Text:
    t = Text()
    current = {(r.type, r.label): r for r in state.resources}
    all_res = {(rt, lb): attrs for rt, lb, attrs in _spec_resources(spec)}

    adds = set(tuple(x.split(".", 1)) for x in diff.to_add)
    changes = set(tuple(x.split(".", 1)) for x in diff.to_change)
    destroys = set(tuple(x.split(".", 1)) for x in diff.to_destroy)

    for (rt, lb), attrs in all_res.items():
        key = (rt, lb)
        if key in adds:
            t.append(f"\n  + resource \"{rt}\" \"{lb}\"", style="green")
            t.append(f"  # will be created\n", style="dim")
            for k, v in attrs.items():
                if isinstance(v, dict):
                    fields_str = ", ".join(f"{fk}: {fv}" for fk, fv in v.items())
                    t.append(f"      {k} = {{{fields_str}}}\n", style="green")
                elif isinstance(v, list):
                    t.append(f"      {k} = {v}\n", style="green")
                else:
                    t.append(f"      {k} = \"{v}\"\n", style="green")
        elif key in changes:
            old = current[key].attributes
            t.append(f"\n  ~ resource \"{rt}\" \"{lb}\"", style="yellow")
            t.append(f"  # will be updated\n", style="dim")
            for k in set(list(old.keys()) + list(attrs.keys())):
                oval = old.get(k)
                nval = attrs.get(k)
                if oval != nval:
                    t.append(f"    ~ {k} = ", style="yellow")
                    t.append(f"\"{oval}\"", style="red")
                    t.append(" → ", style="dim")
                    t.append(f"\"{nval}\"\n", style="green")

    for ref in diff.to_destroy:
        rt, lb = ref.split(".", 1)
        t.append(f"\n  - resource \"{rt}\" \"{lb}\"", style="red")
        t.append(f"  # will be destroyed\n", style="dim")

    nadd = len(diff.to_add)
    nchange = len(diff.to_change)
    ndestroy = len(diff.to_destroy)
    t.append(f"\nPlan: {nadd} to add, {nchange} to change, {ndestroy} to destroy.\n", style="bold")

    if nadd + nchange + ndestroy == 0:
        t.append("\nNo changes. Infrastructure is up-to-date.\n", style="bold green")

    return t


@click.group()
def cli():
    """OpenLattice — declarative application specification compiler."""
    pass


@cli.command()
@click.argument("spec_file", type=click.Path(exists=True))
def plan(spec_file: str):
    """Show execution plan: what will be added, changed, or destroyed."""
    try:
        spec = parse_file(spec_file)
    except ParseError as e:
        console.print(f"[red]Parse error:[/red] {e}")
        raise SystemExit(1)

    state = load_state(STATE_FILE)
    diff = diff_spec_against_state(spec, state)

    content = Text()
    content.append(f"Spec: {spec_file}\n\n", style="dim")
    content.append(_render_plan(diff, spec, state))
    content.append("\n  Will generate:\n", style="dim")
    content.append("    → generated/main.py        FastAPI app + routes\n", style="cyan")
    content.append("    → generated/models.py      SQLAlchemy models\n", style="cyan")
    if diff.to_add or diff.to_change or diff.to_destroy:
        content.append(f"\n  Run `openlattice apply {spec_file}` to perform these actions.", style="dim")

    console.print(Panel(content, title="OpenLattice Plan", border_style="blue"))


@cli.command()
@click.argument("spec_file", type=click.Path(exists=True))
def apply(spec_file: str):
    """Apply spec: generate files and update state."""
    try:
        spec = parse_file(spec_file)
    except ParseError as e:
        console.print(f"[red]Parse error:[/red] {e}")
        raise SystemExit(1)

    state = load_state(STATE_FILE)
    diff = diff_spec_against_state(spec, state)

    if not (diff.to_add or diff.to_change or diff.to_destroy):
        console.print("[green]No changes.[/green] State is up-to-date.")
        return

    console.print(f"Applying OpenLattice spec: [bold]{spec_file}[/bold]\n")

    out_dir = Path("generated")
    out_dir.mkdir(exist_ok=True)

    files = {
        out_dir / "main.py": gen_fastapi(spec),
        out_dir / "models.py": gen_sqlalchemy(spec),
    }
    for path, content in files.items():
        path.write_text(content)
        console.print(f"  [green]✓[/green] {path}")

    new_state = build_new_state(spec, state)
    save_state(new_state, STATE_FILE)
    console.print(f"\nDone. [bold]{len(files)}[/bold] files written. State updated (serial={new_state.serial}).")


@cli.command()
def show():
    """Show current state."""
    state = load_state(STATE_FILE)
    if not state.resources:
        console.print("No state found. Run [bold]openlattice apply[/bold] first.")
        return
    console.print(f"[bold]State[/bold] (serial={state.serial}, lineage={state.lineage[:8]}…)\n")
    for r in state.resources:
        console.print(f"  [cyan]{r.type}.{r.label}[/cyan]  hash={r.spec_hash[:18]}…")
```

- [ ] **Step 3.2: Smoke-test plan with no state**

```bash
uv run openlattice plan example.lattice
```

Expected: All resources shown as `+` (green). Plan: N to add, 0 to change, 0 to destroy.

- [ ] **Step 3.3: Apply and verify state file created**

```bash
uv run openlattice apply example.lattice
cat .lattice-state.json | python3 -c "import json,sys; d=json.load(sys.stdin); print('resources:', len(d['resources']), 'serial:', d['serial'])"
```

Expected: state file exists, serial=1, resources count matches spec.

- [ ] **Step 3.4: Run plan again — expect "No changes"**

```bash
uv run openlattice plan example.lattice
```

Expected: "No changes. Infrastructure is up-to-date."

- [ ] **Step 3.5: Commit**

```bash
git add openlattice/cli.py
git commit -m "feat: cli — real plan diffs vs state, incremental apply, show command"
```

---

## Task 4: Update Example .lattice Files to TF Syntax

**Files:**
- Rewrite: `example.lattice`
- Rewrite: `examples/ecommerce/ecommerce.lattice`
- Rewrite: `examples/blog/blog.lattice`

- [ ] **Step 4.1: Rewrite `example.lattice`**

```hcl
# OpenLattice example spec — TF-style resource blocks

resource "lattice_entity" "order" {
  name = "Order"
  fields = {
    id     = "uuid"
    amount = "int"
    status = "string"
  }
}

resource "lattice_entity" "product" {
  name = "Product"
  fields = {
    id    = "uuid"
    name  = "string"
    price = "float"
  }
}

resource "lattice_api" "create_order" {
  name   = "CreateOrder"
  method = "POST"
  path   = "/orders"
  input  = lattice_entity.order.name
  output = lattice_entity.order.name
}

resource "lattice_api" "get_order" {
  name   = "GetOrder"
  method = "GET"
  path   = "/orders/{id}"
  output = lattice_entity.order.name
}

resource "lattice_api" "list_orders" {
  name   = "ListOrders"
  method = "GET"
  path   = "/orders"
  output = lattice_entity.order.name
}

resource "lattice_event" "order_created" {
  name = "OrderCreated"
  payload = {
    order_id = "uuid"
    amount   = "int"
  }
}

resource "lattice_workflow" "checkout" {
  name  = "Checkout"
  steps = ["validate_order", "charge_customer", "publish_order_created"]
}

resource "lattice_queue" "email_notifications" {
  name    = "email_notifications"
  retries = 3
}
```

- [ ] **Step 4.2: Rewrite `examples/ecommerce/ecommerce.lattice`**

```hcl
# E-Commerce platform spec

resource "lattice_entity" "user" {
  name = "User"
  fields = {
    id    = "uuid"
    email = "string"
    name  = "string"
  }
}

resource "lattice_entity" "product" {
  name = "Product"
  fields = {
    id    = "uuid"
    name  = "string"
    price = "float"
    stock = "int"
  }
}

resource "lattice_entity" "order" {
  name = "Order"
  fields = {
    id         = "uuid"
    user_id    = "uuid"
    total      = "float"
    status     = "string"
    created_at = "datetime"
  }
}

resource "lattice_api" "create_order" {
  name   = "CreateOrder"
  method = "POST"
  path   = "/orders"
  input  = lattice_entity.order.name
  output = lattice_entity.order.name
}

resource "lattice_api" "get_order" {
  name   = "GetOrder"
  method = "GET"
  path   = "/orders/{id}"
  output = lattice_entity.order.name
}

resource "lattice_api" "list_orders" {
  name   = "ListOrders"
  method = "GET"
  path   = "/orders"
  output = lattice_entity.order.name
}

resource "lattice_api" "create_product" {
  name   = "CreateProduct"
  method = "POST"
  path   = "/products"
  input  = lattice_entity.product.name
  output = lattice_entity.product.name
}

resource "lattice_api" "get_product" {
  name   = "GetProduct"
  method = "GET"
  path   = "/products/{id}"
  output = lattice_entity.product.name
}

resource "lattice_api" "get_user" {
  name   = "GetUser"
  method = "GET"
  path   = "/users/{id}"
  output = lattice_entity.user.name
}

resource "lattice_event" "order_created" {
  name = "OrderCreated"
  payload = {
    order_id = "uuid"
    user_id  = "uuid"
    total    = "float"
  }
}

resource "lattice_event" "order_shipped" {
  name = "OrderShipped"
  payload = {
    order_id   = "uuid"
    shipped_at = "datetime"
  }
}

resource "lattice_workflow" "checkout" {
  name  = "Checkout"
  steps = ["validate_cart", "reserve_inventory", "charge_payment", "create_order", "publish_order_created"]
}

resource "lattice_queue" "email_notifications" {
  name    = "email_notifications"
  retries = 5
}

resource "lattice_queue" "inventory_updates" {
  name    = "inventory_updates"
  retries = 3
}
```

- [ ] **Step 4.3: Rewrite `examples/blog/blog.lattice`**

```hcl
# Blog platform spec

resource "lattice_entity" "author" {
  name = "Author"
  fields = {
    id       = "uuid"
    username = "string"
    email    = "string"
    bio      = "string"
  }
}

resource "lattice_entity" "post" {
  name = "Post"
  fields = {
    id           = "uuid"
    author_id    = "uuid"
    title        = "string"
    content      = "string"
    status       = "string"
    published_at = "datetime"
  }
}

resource "lattice_entity" "comment" {
  name = "Comment"
  fields = {
    id         = "uuid"
    post_id    = "uuid"
    author_id  = "uuid"
    body       = "string"
    created_at = "datetime"
  }
}

resource "lattice_api" "create_post" {
  name   = "CreatePost"
  method = "POST"
  path   = "/posts"
  input  = lattice_entity.post.name
  output = lattice_entity.post.name
}

resource "lattice_api" "get_post" {
  name   = "GetPost"
  method = "GET"
  path   = "/posts/{id}"
  output = lattice_entity.post.name
}

resource "lattice_api" "list_posts" {
  name   = "ListPosts"
  method = "GET"
  path   = "/posts"
  output = lattice_entity.post.name
}

resource "lattice_api" "update_post" {
  name   = "UpdatePost"
  method = "PUT"
  path   = "/posts/{id}"
  input  = lattice_entity.post.name
  output = lattice_entity.post.name
}

resource "lattice_api" "delete_post" {
  name   = "DeletePost"
  method = "DELETE"
  path   = "/posts/{id}"
}

resource "lattice_api" "create_comment" {
  name   = "CreateComment"
  method = "POST"
  path   = "/posts/{id}/comments"
  input  = lattice_entity.comment.name
  output = lattice_entity.comment.name
}

resource "lattice_api" "get_author" {
  name   = "GetAuthor"
  method = "GET"
  path   = "/authors/{id}"
  output = lattice_entity.author.name
}

resource "lattice_event" "post_published" {
  name = "PostPublished"
  payload = {
    post_id   = "uuid"
    author_id = "uuid"
    title     = "string"
  }
}

resource "lattice_workflow" "publish_post" {
  name  = "PublishPost"
  steps = ["validate_content", "run_moderation", "set_published_status", "notify_subscribers"]
}

resource "lattice_queue" "subscriber_notifications" {
  name    = "subscriber_notifications"
  retries = 3
}
```

- [ ] **Step 4.4: Verify examples parse and apply**

```bash
uv run openlattice apply examples/ecommerce/ecommerce.lattice
cp generated/main.py examples/ecommerce/generated/main.py
cp generated/models.py examples/ecommerce/generated/models.py

uv run openlattice apply examples/blog/blog.lattice
cp generated/main.py examples/blog/generated/main.py
cp generated/models.py examples/blog/generated/models.py
```

Expected: No parse errors. Files regenerated.

- [ ] **Step 4.5: Commit**

```bash
git add example.lattice examples/ .lattice-state.json
git commit -m "refactor: update all .lattice files to TF-style resource syntax"
```

---

## Task 5: Full Integration Test + Drift Demo

**Goal:** Prove the state machine works end-to-end — apply, verify no-op plan, modify spec, verify diff shows change.

- [ ] **Step 5.1: Clean state and apply**

```bash
rm -f .lattice-state.json
uv run openlattice apply example.lattice
```

Expected: All resources `+`, state written, serial=1.

- [ ] **Step 5.2: Plan again — expect no changes**

```bash
uv run openlattice plan example.lattice
```

Expected: "No changes. Infrastructure is up-to-date."

- [ ] **Step 5.3: Add a field to `example.lattice` and plan**

Add `discount = "float"` to the `lattice_entity.order` fields block in `example.lattice`, then:

```bash
uv run openlattice plan example.lattice
```

Expected: `~ resource "lattice_entity" "order"` shown in yellow as changed. Plan: 0 to add, 1 to change, 0 to destroy.

- [ ] **Step 5.4: Apply the change**

```bash
uv run openlattice apply example.lattice
uv run openlattice show
```

Expected: Serial incremented to 2. State shows updated hash for `lattice_entity.order`.

- [ ] **Step 5.5: Run all tests**

```bash
uv run pytest tests/ -v
```

Expected: All tests pass.

- [ ] **Step 5.6: Final commit**

```bash
git add -A
git commit -m "test: integration test — state machine drift detection works end-to-end"
git push
```

---

## Option B Migration Notes (preserve throughout)

Every design decision above is made to minimize the delta to a TF provider:

| This plan | Option B equivalent |
|-----------|-------------------|
| `.lattice` resource blocks | `resource "lattice_entity" "order"` HCL — **identical syntax** |
| `state.py` + `.lattice-state.json` | Drop entirely — OpenTofu handles state |
| `cli.py plan/apply` | Thin wrapper over `tofu plan/apply` |
| `_spec_resources()` → resource list | TF provider `Read()` returning ResourceData |
| `gen_fastapi(spec)` | Called from Go provider via `subprocess` or rewritten in Go |

When migrating: the `.lattice` parser output (LatticeSpec) maps 1:1 to the TF provider schema. No IR redesign needed.
