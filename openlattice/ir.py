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


@dataclass
class EventDef:
    name: str
    payload: list[FieldDef]


@dataclass
class WorkflowDef:
    name: str
    steps: list[str]


@dataclass
class QueueDef:
    name: str
    retries: int = 3


@dataclass
class LatticeSpec:
    entities: list[EntityDef] = field(default_factory=list)
    apis: list[ApiDef] = field(default_factory=list)
    events: list[EventDef] = field(default_factory=list)
    workflows: list[WorkflowDef] = field(default_factory=list)
    queues: list[QueueDef] = field(default_factory=list)
