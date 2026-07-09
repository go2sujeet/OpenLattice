from dataclasses import dataclass, field


@dataclass
class FieldDef:
    name: str
    type: str  # "uuid" | "int" | "float" | "string" | "bool" | "datetime" | "json"


@dataclass
class EntityDef:
    name: str
    fields: list[FieldDef]


@dataclass
class ApiDef:
    name: str
    method: str  # "GET" | "POST" | "PUT" | "DELETE" | "PATCH"
    path: str
    input_entity: str | None = None
    output_entity: str | None = None
    publishes: list[str] = field(default_factory=list)
    crud_operation: str | None = None  # "create" | "read" | "list" | "update" | "delete" | None


@dataclass
class EventDef:
    name: str
    payload: list[FieldDef]
    published_by: list[str] = field(default_factory=list)
    consumed_by: list[str] = field(default_factory=list)


@dataclass
class WorkflowStep:
    name: str
    input: str | None = None
    output: str | None = None
    on_error: str | None = None


@dataclass
class WorkflowDef:
    name: str
    steps: list[WorkflowStep]
    trigger: str | None = None


@dataclass
class QueueDef:
    name: str
    message_type: str | None = None
    retries: int = 3
    dlq: bool = False


@dataclass
class ConnectorDef:
    name: str
    kind: str  # "http_webhook" (only valid value for now)
    url: str
    method: str = "POST"
    headers: dict[str, str] = field(default_factory=dict)
    body_template: dict[str, str] = field(default_factory=dict)


@dataclass
class LatticeSpec:
    entities: list[EntityDef] = field(default_factory=list)
    apis: list[ApiDef] = field(default_factory=list)
    events: list[EventDef] = field(default_factory=list)
    workflows: list[WorkflowDef] = field(default_factory=list)
    queues: list[QueueDef] = field(default_factory=list)
    connectors: list[ConnectorDef] = field(default_factory=list)
