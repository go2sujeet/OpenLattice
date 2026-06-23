OpenLattice

Declarative Application Specifications for Modern Software Systems

⸻

Abstract

Infrastructure has largely become declarative through tools such as OpenTofu and Terraform. Engineers describe the desired state of infrastructure resources, and the platform computes dependencies and reconciles systems automatically.

Application development, however, remains largely imperative. Developers manually construct APIs, models, events, workflows, queues, and deployment artifacts — writing the same patterns across every project, for every entity, for every endpoint.

OpenLattice introduces a higher level of abstraction for application development. Instead of building applications from framework primitives, developers describe systems using application components and resource relationships. OpenLattice transforms these specifications into executable code, contracts, workflows, and infrastructure artifacts while preserving developer ownership and extensibility.

The result is less code, stronger consistency guarantees, and a standard way to express application architecture — from POC to production.

The philosophy is simple:

Describe the application. Generate the implementation.

⸻

1. Introduction

Infrastructure engineering has evolved from scripts to declarative resources.

Instead of writing:

aws s3api create-bucket ...

Engineers write:

resource "aws_s3_bucket" "uploads" {
  bucket = "my-uploads"
}

OpenTofu computes dependencies, creates execution plans, and converges infrastructure to the desired state.

Application development has not experienced the same transition.

Developers still manually implement:

* REST APIs
* Database models
* Event producers
* Message consumers
* Workflow orchestration
* Migrations
* SDKs
* Deployment manifests

Many of these artifacts are derived from the same underlying business concepts and are inherently repetitive. Every new entity means writing a model, a migration, an API endpoint, validation logic, serialization, and tests — across potentially multiple languages and frameworks.

OpenLattice is not a framework and does not introduce a runtime. It is a compiler that translates declarative application specifications into conventional code and infrastructure artifacts. It seeks to elevate application development from framework constructs to declarative components.

⸻

2. The Boilerplate Problem

Application development today is dominated by structural repetition.

A single entity in a typical stack requires:

* A database model with fields, types, constraints, and relationships
* A database migration defining the same schema in DDL
* API endpoints for CRUD operations with request and response schemas
* Serialization and deserialization logic
* Input validation rules
* An OpenAPI or GraphQL schema documenting the interface
* A client SDK or type definitions for consumers
* Event contracts if the entity is published or consumed
* Deployment manifests with environment configuration

These are often different representations of the same underlying specification. They are expressed in different formats, frameworks, and languages — maintained independently and therefore prone to drift.

The cost is not just the initial writing. It is the ongoing maintenance: every field change must be propagated across every layer. Every new framework means learning new conventions and rewriting existing patterns.

Low-code platforms solve this by constraining output, but introduce lock-in, proprietary runtimes, and version control challenges. Code generators solve single domains (one schema → one output type) but cannot validate cross-cutting concerns like whether an API handler matches a database migration.

OpenLattice takes a different approach: a single specification that describes the application at a higher level, and deterministic generators that produce every framework artifact from that spec.

⸻

3. Vision

Applications should be composed from resources rather than boilerplate.

Instead of writing:

@app.post("/orders")
async def create_order():
    ...
class Order(Base):
    ...
producer.send(...)

Developers describe:

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
}

OpenLattice generates:

* FastAPI endpoints
* SQLAlchemy models
* Alembic migrations
* OpenAPI specifications
* SDKs
* Event contracts
* Deployment artifacts

Generated artifacts remain consistent by construction. Every migration matches every model. Every endpoint matches every schema. Every SDK matches every contract.

A developer or team maintains a single specification file — not a dozen scattered framework files. Changes are made in one place and propagated automatically.

⸻

4. Core Principles

Resource-Oriented

Applications are composed of resources.

* Entities
* APIs
* Events
* Workflows
* Queues
* Services
* Policies

Resources form a dependency graph called the Application Lattice.

⸻

Specification as Source of Truth

The lattice specification is the authoritative description of the application architecture.

It is human-readable, diffable, and machine-processable.

Changes to the application begin as changes to the spec.

⸻

Code Ownership

Generated artifacts remain ordinary source code.

Developers retain full ownership of generated artifacts.

OpenLattice does not introduce a proprietary runtime. Generated code uses standard frameworks, libraries, and patterns.

⸻

Deterministic Generation

Given the same lattice specification, OpenLattice produces identical output.

This is critical for:

* Testability — generated code can be diffed and asserted against
* Reproducibility — builds produce the same results every time
* Auditing — changes to the lattice map directly to changes in generated code
* CI/CD — pipelines can reject unexpected code changes

⸻

Escape Hatches

Business logic remains imperative.

Example:

@step
def charge_customer(ctx):
    ...

**OpenLattice generates structure, not business logic.** Custom logic is injected through typed step handlers, hooks, and policies.

⸻

Incremental Adoption

OpenLattice can coexist with existing applications and frameworks.

Teams may adopt components independently, migrate existing applications resource by resource, or use OpenLattice for new features alongside a legacy codebase.

⸻

5. Architecture

Specification
      |
      v
Resource Graph
      |
      v
Generators
      |
+-----------------------------+
| FastAPI / SQLAlchemy        |
| Alembic / OpenAPI / AsyncAPI|
| TypeScript SDKs / Temporal  |
| Docker / Helm / OpenTofu    |
+-----------------------------+
      |
      v
Cloud Platforms

The specification is the only input developers write. The Resource Graph is the internal dependency graph. Generators consume the Resource Graph and produce all application artifacts — models, APIs, migrations, contracts, SDKs, workflows, and deployment manifests — in a single deterministic pass.

⸻

6. The Specification Language

The OpenLattice specification language is a small, typed DSL for describing application resources.

entity "Order" {
  fields = {
    id        = uuid
    created   = datetime
    amount    = int
    status    = string
  }
}

api "CreateOrder" {
  method = POST
  path   = "/orders"
  input  = Order
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

Built-in field types: `string`, `int`, `float`, `bool`, `uuid`, `datetime`, `json`, `enum`.

Resources reference each other by name. The grammar is parsed and validated before any code is generated — dangling references, mismatched types, and invalid relationships are caught at parse time, not runtime.

The spec file is the standard. It defines the contract between teams, between services, and between the developer and the platform.

⸻

7. Core Components

| Component | Example Spec | Generates |
|-----------|-------------|-----------|
| **Entity** | `entity "Order" { fields = { id = uuid, amount = int } }` | Models, validation schemas, database migrations |
| **CRUD** | `crud "Order"` | POST /orders, GET /orders/{id}, PUT /orders/{id}, DELETE /orders/{id} |
| **Event** | `event "OrderCreated" { payload = { order_id = uuid, amount = int } }` | Event contracts, producers, consumers, AsyncAPI specs |
| **Workflow** | `workflow "Checkout" { steps = ["validate", "charge"] }` | Orchestration shell (business steps user-defined) |
| **Queue** | `queue "emails" { retries = 5 }` | Queue infrastructure, consumer scaffolding |
| **Service** | `service "orders" { runtime = "container" }` | Deployment config, health checks, service mesh |

⸻

8. The Application Lattice

OpenLattice models applications as a graph of relationships.

Order Entity
      |
      v
CreateOrder API
      |
      v
Checkout Workflow
      |
      v
OrderCreated Event
      |
      v
Email Queue

The Application Lattice becomes the source of truth for the system. It captures every dependency: which APIs reference which entities, which workflows publish which events, which services subscribe to which queues.

Because these relationships are explicit, OpenLattice can verify the entire graph before generating a single file. A broken reference is caught at specification time, not at deployment time.

⸻

9. Development Workflow

Phase 1: Design

The developer defines or modifies the lattice specification — adding entities, APIs, events, workflows, and their relationships.

Phase 2: Plan

openlattice plan

The plan displays the full set of changes: entities, migrations, endpoints, SDK updates, event contracts, deployment changes.

+ Entity Order
+ CRUD endpoints
+ SQLAlchemy model
+ Database migration
+ OpenAPI schema
+ TypeScript SDK

Phase 3: Review

The plan is reviewed before any files are written. Because the plan is derived from structured specs, the review surface is small and high-signal — every change traces back to a resource definition.

Phase 4: Apply

openlattice apply

OpenLattice materializes the desired state into source code. Every artifact is consistent, typed, and matches every other artifact.

Phase 5: Extend

Generated unit tests and schema validations run automatically. The developer adds business logic in the designated escape-hatch files and confirms the system behaves as intended.

⸻

10. Planning and Reconciliation

Inspired by OpenTofu.

Plan

openlattice plan

Displays pending changes as a structured diff:

+ Entity Order
  + field id : uuid
  + field amount : int
  + field status : string
+ api CreateOrder (POST /orders)
  + input: Order
+ migration: create_orders_table
+ openapi: Order schema + CreateOrder endpoint

Apply

openlattice apply

Materializes the desired state into source code and infrastructure artifacts.

Reconciliation

OpenLattice tracks generated artifacts using content fingerprints and can surface differences during subsequent planning operations. The fingerprint is stored alongside the lattice specification — no runtime instrumentation is required. Developers choose to adopt, override, or re-generate.

⸻

11. Real-World Impact

Consider a typical feature: adding an Order entity with CRUD support and a checkout workflow.

Without OpenLattice, a developer writes across multiple files:

- FastAPI router with Order endpoints
- SQLAlchemy model with column definitions
- Alembic migration with matching DDL
- Pydantic schemas for request/response validation
- OpenAPI schema documentation (often manual or partially generated)
- Temporal workflow and activity definitions
- Event producer for OrderCreated
- Consumer for downstream processing
- Deployment manifest updates

Each file uses different conventions. Field names can drift. Types can mismatch. Migrations can fall out of sync. The developer must hold the entire system in their head to ensure consistency.

With OpenLattice, the developer writes one specification:

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
}
workflow "Checkout" {
  steps = [
    "validate_order",
    "charge_customer",
    "publish_order_created"
  ]
}
event "OrderCreated" {
  payload = {
    order_id = uuid
    amount   = int
  }
}

OpenLattice produces the models, migrations, endpoints, schemas, SDKs, contracts, and deployment artifacts — consistent by construction, not by convention.

Reduced boilerplate. Improved consistency. Faster iteration.

This is especially valuable for:
* **Prototyping** — stand up a full application stack from a single spec
* **Standardization** — every service follows the same patterns, conventions, and output structure
* **Multi-service coordination** — shared entities, events, and contracts are defined once and consumed across services
* **Onboarding** — new team members read the spec to understand the system, not scattered framework files

⸻

12. Generated Technologies

APIs

* FastAPI

Data

* SQLAlchemy
* Alembic

Contracts

* OpenAPI
* AsyncAPI

Workflows

* Temporal

Deployment

* OpenTofu
* Helm

Observability

* OpenTelemetry

⸻

13. Relationship with OpenTofu

OpenLattice does not replace OpenTofu.

OpenLattice operates at the application layer.

OpenLattice
      |
Application Graph
      |
Generators
      |
OpenTofu
      |
Cloud Infrastructure

OpenTofu manages infrastructure resources.

OpenLattice manages application resources.

Together, they form a complete declarative stack — from cloud infrastructure to application code.

⸻

14. Future Components

Future resource types may include:

* Aggregate
* Command
* Query
* Read Model
* Projection
* Policy
* Saga

Enabling:

* CQRS
* Event Sourcing
* Distributed Transactions
* Multi-language SDKs
* Multi-service orchestration

⸻

15. Status and Implementation

The ideas in this paper represent the current design phase of OpenLattice. The specification grammar, Application Lattice model, and generator architecture are being actively refined.

Areas under exploration include:

* Lattice diff and merge semantics for concurrent changes
* Incremental code generation that preserves hand-written business logic across re-generation cycles
* Pluggable generator backends for additional languages and frameworks
* Multi-service coordination across independently managed lattices
* Tooling integration (IDE plugins, hot-reload from spec, spec visualizers)

OpenLattice is envisioned as an open and extensible platform. Contributions, feedback, and collaborations are welcome.

⸻

16. Why OpenLattice?

A lattice represents interconnected structures where relationships matter as much as individual nodes.

Modern applications are not isolated components.

They are systems of APIs, entities, workflows, events, and services connected through dependencies.

OpenLattice captures these relationships and elevates them into first-class resources.

The result is a standard way to describe what an application is — independent of frameworks, languages, or deployment targets — with tooling that produces consistent, production-grade implementations from that description.

⸻

Conclusion

Infrastructure evolved from imperative scripts to declarative resources.

OpenLattice extends the same philosophy to application development.

Its goal is not to replace programming languages.

Its goal is to enable developers to operate at a higher level of abstraction — where intent is declared, structure is guaranteed, and boilerplate is eliminated.

Describe what the application is.

Let the platform determine how it is implemented.

⸻

*Version: Design Phase — June 2026*
