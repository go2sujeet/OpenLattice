"""State management for OpenLattice — analogous to Terraform's tfstate."""

import hashlib
import json
import re
import uuid as _uuid_mod
from dataclasses import dataclass, field
from typing import Any

from openlattice.ir import (
    AgentDef,
    ApiDef,
    ConnectorDef,
    EntityDef,
    EventDef,
    LatticeSpec,
    QueueDef,
    WorkflowDef,
)


@dataclass
class ResourceState:
    type: str
    label: str
    attributes: dict[str, Any]
    spec_hash: str


@dataclass
class StateFile:
    resources: list[ResourceState] = field(default_factory=list)
    version: str = "1"
    serial: int = 0
    lineage: str = field(default_factory=lambda: str(_uuid_mod.uuid4()))


@dataclass
class DiffResult:
    to_add: list[str] = field(default_factory=list)
    to_change: list[str] = field(default_factory=list)
    to_destroy: list[str] = field(default_factory=list)


def compute_spec_hash(res_type: str, label: str, attributes: dict[str, Any]) -> str:
    canonical = json.dumps(
        {"type": res_type, "label": label, "attributes": attributes}, sort_keys=True
    )
    digest = hashlib.sha256(canonical.encode()).hexdigest()
    return f"sha256:{digest}"


def _to_label(name: str) -> str:
    """PascalCase → snake_case for resource labels."""
    s = re.sub(r"([a-z])([A-Z])", r"\1_\2", name)
    return s.lower()


def _entity_attrs(e: EntityDef) -> dict[str, Any]:
    return {"name": e.name, "fields": {f.name: f.type for f in e.fields}}


def _api_attrs(a: ApiDef) -> dict[str, Any]:
    d: dict[str, Any] = {"name": a.name, "method": a.method, "path": a.path}
    if a.input_entity:
        d["input"] = a.input_entity
    if a.output_entity:
        d["output"] = a.output_entity
    if a.publishes:
        d["publishes"] = a.publishes
    return d


def _event_attrs(e: EventDef) -> dict[str, Any]:
    return {"name": e.name, "payload": {f.name: f.type for f in e.payload}}


def _workflow_attrs(w: WorkflowDef) -> dict[str, Any]:
    d: dict[str, Any] = {
        "name": w.name,
        "steps": [
            {"name": s.name, "input": s.input, "output": s.output, "on_error": s.on_error}
            for s in w.steps
        ],
    }
    if w.trigger:
        d["trigger"] = w.trigger
    return d


def _queue_attrs(q: QueueDef) -> dict[str, Any]:
    d: dict[str, Any] = {"name": q.name, "retries": q.retries}
    if q.message_type:
        d["message_type"] = q.message_type
    if q.dlq:
        d["dlq"] = q.dlq
    return d


def _connector_attrs(c: ConnectorDef) -> dict[str, Any]:
    d: dict[str, Any] = {"name": c.name, "kind": c.kind, "url": c.url, "method": c.method}
    if c.headers:
        d["headers"] = c.headers
    if c.body_template:
        d["body_template"] = c.body_template
    return d


def _agent_attrs(a: AgentDef) -> dict[str, Any]:
    d: dict[str, Any] = {
        "name": a.name,
        "model": a.model,
        "system_prompt": a.system_prompt,
    }
    if a.output_type:
        d["output_type"] = a.output_type
    if a.tools:
        d["tools"] = a.tools
    return d


def spec_resources(spec: LatticeSpec) -> list[tuple[str, str, dict[str, Any]]]:
    """Return (type, label, attributes) for every resource in the spec."""
    resources: list[tuple[str, str, dict[str, Any]]] = []
    for e in spec.entities:
        resources.append(("lattice_entity", _to_label(e.name), _entity_attrs(e)))
    for a in spec.apis:
        resources.append(("lattice_api", _to_label(a.name), _api_attrs(a)))
    for ev in spec.events:
        resources.append(("lattice_event", _to_label(ev.name), _event_attrs(ev)))
    for w in spec.workflows:
        resources.append(("lattice_workflow", _to_label(w.name), _workflow_attrs(w)))
    for q in spec.queues:
        resources.append(("lattice_queue", _to_label(q.name), _queue_attrs(q)))
    for c in spec.connectors:
        resources.append(("lattice_connector", _to_label(c.name), _connector_attrs(c)))
    for ag in spec.agents:
        resources.append(("lattice_agent", _to_label(ag.name), _agent_attrs(ag)))
    return resources


def diff_spec_against_state(spec: LatticeSpec, state: StateFile) -> DiffResult:
    current = {(r.type, r.label): r for r in state.resources}
    desired_keys: set[tuple[str, str]] = set()
    result = DiffResult()

    for res_type, label, attrs in spec_resources(spec):
        key = (res_type, label)
        desired_keys.add(key)
        ref = f"{res_type}.{label}"
        new_hash = compute_spec_hash(res_type, label, attrs)
        if key not in current:
            result.to_add.append(ref)
        elif current[key].spec_hash != new_hash:
            result.to_change.append(ref)

    for res_type, label in current:
        if (res_type, label) not in desired_keys:
            result.to_destroy.append(f"{res_type}.{label}")

    return result


def build_new_state(spec: LatticeSpec, existing: StateFile) -> StateFile:
    resources: list[ResourceState] = []
    for res_type, label, attrs in spec_resources(spec):
        resources.append(
            ResourceState(
                type=res_type,
                label=label,
                attributes=attrs,
                spec_hash=compute_spec_hash(res_type, label, attrs),
            )
        )
    return StateFile(
        resources=resources,
        version="1",
        serial=existing.serial + 1,
        lineage=existing.lineage,
    )


def save_state(state: StateFile, path: str = ".lattice-state.json") -> None:
    data: dict[str, Any] = {
        "version": state.version,
        "serial": state.serial,
        "lineage": state.lineage,
        "resources": [
            {"type": r.type, "label": r.label, "attributes": r.attributes, "spec_hash": r.spec_hash}
            for r in state.resources
        ],
    }
    with open(path, "w") as f:
        json.dump(data, f, indent=2)


def load_state(path: str = ".lattice-state.json") -> StateFile:
    try:
        with open(path) as f:
            data: dict[str, Any] = json.load(f)
    except FileNotFoundError:
        return StateFile()
    return StateFile(
        version=str(data.get("version", "1")),
        serial=int(data.get("serial", 0)),
        lineage=str(data.get("lineage", str(_uuid_mod.uuid4()))),
        resources=[
            ResourceState(
                type=r["type"],
                label=r["label"],
                attributes=r["attributes"],
                spec_hash=r["spec_hash"],
            )
            for r in list(data.get("resources", []))
        ],
    )
