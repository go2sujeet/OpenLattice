# OpenLattice

**Declarative application specifications. Describe the system. Generate the implementation.**

[![PyPI](https://img.shields.io/pypi/v/openlattice.svg)](https://pypi.org/project/openlattice/)
[![CI](https://github.com/go2sujeet/OpenLattice/actions/workflows/ci.yml/badge.svg)](https://github.com/go2sujeet/OpenLattice/actions/workflows/ci.yml)
[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Open in GitHub Codespaces](https://github.com/codespaces/badge.svg)](https://codespaces.new/go2sujeet/OpenLattice)

---

## The Core Idea

Infrastructure is declarative. Terraform and OpenTofu let you describe cloud resources and converge reality to match. Application code is not — developers still hand-write every model, every endpoint, every migration, every event contract, by hand, every time.

OpenLattice is to applications what OpenTofu is to infrastructure. You describe the desired state of your application — entities, APIs, events, workflows, queues — and OpenLattice generates the implementation. Same mental model: declare intent, plan changes, apply to materialize.

It is not a framework. It is not a runtime. It is a compiler.

---

## How It Works

```
# Write this (order.lattice)                  # Get this (main.py)

entity "Order" {                    →         class Order(BaseModel):
  fields = {                        →             id: UUID
    id     = uuid                   →             amount: int
    amount = int                    →             status: str
    status = string                 →
  }                                 →         @router.post("/orders", response_model=Order)
}                                   →         async def create_order(body: Order) -> Order:
                                    →             raise NotImplementedError("Implement business logic here")
api "CreateOrder" {                 →
  method = POST                     →         # Get this (models.py)
  path   = "/orders"                →
  input  = Order                    →         class Order(Base):
  output = Order                    →             __tablename__ = "orders"
}                                   →             id = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
                                    →             amount = mapped_column(Integer, nullable=False)
                                    →             status = mapped_column(String, nullable=False)
```

One spec file. Two consistent, typed, production-shaped output files. No divergence between the API layer and the database layer.

---

## The OpenTofu Analogy

| OpenTofu | OpenLattice |
|---|---|
| Infrastructure resources | Application resources |
| `terraform plan` | `openlattice plan` |
| `terraform apply` | `openlattice apply` |
| HCL spec → cloud resources | `.lattice` spec → application code |
| State file | Content fingerprints |
| Providers | Generators |

OpenLattice does not replace OpenTofu. They are complementary layers of the same declarative stack — OpenTofu manages infrastructure, OpenLattice manages application code. Together: a fully declarative path from spec to cloud.

---

## Demo

```bash
# 1. Write a spec
cat order.lattice
```

```hcl
entity "Order" {
  fields = {
    id     = uuid
    amount = int
    status = string
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

event "OrderCreated" {
  payload = {
    order_id = uuid
    amount   = int
  }
}

workflow "Checkout" {
  steps = ["validate_order", "charge_customer", "publish_order_created"]
}

queue "email_notifications" {
  retries = 3
}
```

```bash
# 2. Preview changes
openlattice plan order.lattice
```

```
╭─ OpenLattice Plan ──────────────────────────────────────────╮
│                                                              │
│   Resources:                                                 │
│     + Entity:   Order                (3 fields)             │
│     + API:      CreateOrder          POST   /orders          │
│     + API:      GetOrder             GET    /orders/{id}     │
│     + Event:    OrderCreated                                 │
│     + Workflow: Checkout             (3 steps)              │
│     + Queue:    email_notifications  retries=3               │
│                                                              │
│   Will generate:                                             │
│     → generated/main.py        FastAPI app + routes          │
│     → generated/models.py      SQLAlchemy models             │
│                                                              │
│   Run `openlattice apply <file>` to materialize.             │
╰──────────────────────────────────────────────────────────────╯
```

```bash
# 3. Generate code
openlattice apply order.lattice
```

```
Applying OpenLattice spec: order.lattice

  ✓ generated/main.py
  ✓ generated/models.py

Done. 2 files written.
```

```bash
# 4. Run
uvicorn generated.main:app --reload
# → http://localhost:8000/docs
```

---

## Installation

```bash
# From PyPI (coming soon)
pip install openlattice

# From source (requires uv: pip install uv)
git clone https://github.com/go2sujeet/OpenLattice
cd OpenLattice
uv pip install -e .
# Or with plain pip:
pip install -e .
```

**Try instantly with no local install:** [![Open in GitHub Codespaces](https://github.com/codespaces/badge.svg)](https://codespaces.new/go2sujeet/OpenLattice)

---

## Quick Start

```bash
cat > myapp.lattice << 'EOF'
entity "Task" {
  fields = {
    id    = uuid
    title = string
    done  = bool
  }
}

api "CreateTask" { method = POST   path = "/tasks"      input = Task  output = Task }
api "GetTask"    { method = GET    path = "/tasks/{id}"               output = Task }
api "UpdateTask" { method = PUT    path = "/tasks/{id}" input = Task  output = Task }
api "DeleteTask" { method = DELETE path = "/tasks/{id}"                             }
EOF

openlattice plan myapp.lattice
openlattice apply myapp.lattice
uvicorn generated.main:app --reload
```

Open `http://localhost:8000/docs` — your API is live with full OpenAPI docs, typed request/response models, and SQLAlchemy ORM models ready for a database.

---

## The Lattice DSL

### Resource types

```hcl
entity "Name" {          # → Pydantic model + SQLAlchemy ORM model
  fields = {
    field_name = type    # types: uuid, int, float, string, bool, datetime, json
  }
}

api "Name" {             # → FastAPI route
  method = GET|POST|PUT|DELETE|PATCH
  path   = "/resource/{id}"
  input  = EntityName    # optional — request body
  output = EntityName    # optional — response model
}

event "Name" {           # → Event contract (AsyncAPI)
  payload = {
    field = type
  }
}

workflow "Name" {        # → Orchestration shell (Temporal)
  steps = ["step1", "step2", "step3"]
}

queue "name" {           # → Queue infrastructure
  retries = 3
}
```

### Field types

| Type | Python | SQLAlchemy | Use for |
|------|--------|------------|---------|
| `uuid` | `UUID` | `UUID(as_uuid=True)` | Primary keys, foreign keys |
| `string` | `str` | `String` | Names, emails, text |
| `int` | `int` | `Integer` | Counts, amounts |
| `float` | `float` | `Float` | Prices, scores |
| `bool` | `bool` | `Boolean` | Flags |
| `datetime` | `datetime` | `DateTime` | Timestamps |
| `json` | `dict` | `JSON` | Flexible payloads |

The parser validates DSL syntax and catches dangling references, unknown types, and missing required attributes at parse time — before any code is written.

---

## Examples

### [`examples/ecommerce/`](examples/ecommerce/)

Full e-commerce platform: `User`, `Product`, `Order` entities; six CRUD-style API endpoints; `OrderCreated` and `OrderShipped` event contracts; `Checkout` workflow with five steps; two queues with different retry policies. Generates `main.py` (FastAPI, Pydantic models, six route handlers) and `models.py` (SQLAlchemy ORM, three tables with typed mapped columns).

### [`examples/blog/`](examples/blog/)

Content platform: `Author`, `Post`, `Comment` entities; seven API endpoints including nested routes (`/posts/{id}/comments`); `PostPublished` event; `PublishPost` workflow with moderation and notification steps; subscriber notification queue.

Both examples include pre-generated output in `generated/` — read the spec, compare to the output, understand the full transformation.

---

## Generated Output

Generated files are plain Python. They import FastAPI, Pydantic, and SQLAlchemy directly — no OpenLattice runtime, no proprietary abstractions.

```python
# generated/main.py — your code to own and extend
@router.post("/orders", response_model=Order)
async def create_order(body: Order) -> Order:
    raise NotImplementedError("Implement business logic here")  # ← fill this in
```

```python
# generated/models.py — standard SQLAlchemy 2.x mapped columns
class Order(Base):
    __tablename__ = "orders"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    amount: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False)
```

The `NotImplementedError` stubs are intentional. OpenLattice generates structure — routing, typing, ORM mapping. Business logic stays imperative and yours. Add a database session, call your service layer, return the response. Re-running `apply` on an unchanged spec is idempotent; fingerprinting (in progress) will detect hand-edits and prompt before overwriting.

---

## Architecture

```
.lattice spec
     │
     ▼
┌─────────────────────┐
│   Parser            │  DSL → LatticeSpec (typed IR)
└────────┬────────────┘
         │
         ▼
┌─────────────────────┐
│   Resource Graph    │  Dependency resolution, validation
└────────┬────────────┘
         │
  ┌──────┴──────┐
  ▼             ▼
FastAPI      SQLAlchemy   ← Generators (pluggable)
Generator    Generator
  │             │
  ▼             ▼
main.py     models.py
```

**Parser** — Recursive-descent tokenizer and parser, zero third-party dependencies. Validates syntax, block types, HTTP methods, and field types at parse time. Returns a `LatticeSpec` typed dataclass tree.

**IR** — `openlattice/ir.py` defines `LatticeSpec`, `EntityDef`, `ApiDef`, `EventDef`, `WorkflowDef`, `QueueDef`, `FieldDef`. This is the contract between parser and generators. Generators read only from IR types; they never touch the DSL source.

**Generators** — Pure functions with signature `generate(spec: LatticeSpec) -> str`. `fastapi_gen` produces `main.py`; `sqlalchemy_gen` produces `models.py`. Adding a new target (TypeScript types, OpenAPI YAML, Alembic migrations) means adding a new generator module — no changes to parser or core.

**CLI** — Two commands: `plan` (dry-run preview, no files written) and `apply` (materialize to disk). Built with Click and Rich.

---

## Roadmap

| Feature | Status |
|---------|--------|
| DSL parser | Done |
| FastAPI generator | Done |
| SQLAlchemy generator | Done |
| CLI (`plan` + `apply`) | Done |
| Alembic migrations generator | Next |
| OpenAPI spec export | Next |
| TypeScript SDK generator | Planned |
| Temporal workflow generator | Planned |
| Pluggable generator API | Planned |
| State fingerprinting (safe re-apply) | Planned |
| IDE extension (VS Code) | Exploring |
| Multi-service coordination | Exploring |

---

## Contributing

Issues and PRs are welcome. Standard flow: fork the repo, create a branch, open a PR against `main`. CONTRIBUTING.md coming soon.

The most impactful contributions right now: new generators (Alembic, OpenAPI, TypeScript), improved error messages in the parser, and real-world spec examples.

---

## License

MIT
