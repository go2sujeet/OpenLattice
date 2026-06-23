"""State management for OpenLattice — analogous to Terraform's tfstate."""

import json
import hashlib
import re
import uuid as _uuid_mod
from dataclasses import dataclass, field
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
    to_add: list[str] = field(default_factory=list)
    to_change: list[str] = field(default_factory=list)
    to_destroy: list[str] = field(default_factory=list)


def compute_spec_hash(res_type: str, label: str, attributes: dict) -> str:
    canonical = json.dumps({"type": res_type, "label": label, "attributes": attributes},
                           sort_keys=True)
    digest = hashlib.sha256(canonical.encode()).hexdigest()
    return f"sha256:{digest}"


def _to_label(name: str) -> str:
    """PascalCase → snake_case for resource labels."""
    s = re.sub(r"([a-z])([A-Z])", r"\1_\2", name)
    return s.lower()


def _entity_attrs(e: EntityDef) -> dict:
    return {"name": e.name, "fields": {f.name: f.type for f in e.fields}}

def _api_attrs(a: ApiDef) -> dict:
    d = {"name": a.name, "method": a.method, "path": a.path}
    if a.input_entity:
        d["input"] = a.input_entity
    if a.output_entity:
        d["output"] = a.output_entity
    return d

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
        resources.append(("lattice_entity", _to_label(e.name), _entity_attrs(e)))
    for a in spec.apis:
        resources.append(("lattice_api", _to_label(a.name), _api_attrs(a)))
    for e in spec.events:
        resources.append(("lattice_event", _to_label(e.name), _event_attrs(e)))
    for w in spec.workflows:
        resources.append(("lattice_workflow", _to_label(w.name), _workflow_attrs(w)))
    for q in spec.queues:
        resources.append(("lattice_queue", _to_label(q.name), _queue_attrs(q)))
    return resources


def diff_spec_against_state(spec: LatticeSpec, state: StateFile) -> DiffResult:
    current = {(r.type, r.label): r for r in state.resources}
    desired_keys: set[tuple[str, str]] = set()
    result = DiffResult()

    for res_type, label, attrs in _spec_resources(spec):
        key = (res_type, label)
        desired_keys.add(key)
        ref = f"{res_type}.{label}"
        new_hash = compute_spec_hash(res_type, label, attrs)
        if key not in current:
            result.to_add.append(ref)
        elif current[key].spec_hash != new_hash:
            result.to_change.append(ref)

    for (res_type, label) in current:
        if (res_type, label) not in desired_keys:
            result.to_destroy.append(f"{res_type}.{label}")

    return result


def build_new_state(spec: LatticeSpec, existing: StateFile) -> StateFile:
    resources = []
    for res_type, label, attrs in _spec_resources(spec):
        resources.append(ResourceState(
            type=res_type, label=label, attributes=attrs,
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
            {"type": r.type, "label": r.label, "attributes": r.attributes, "spec_hash": r.spec_hash}
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
            ResourceState(type=r["type"], label=r["label"],
                          attributes=r["attributes"], spec_hash=r["spec_hash"])
            for r in data.get("resources", [])
        ],
    )
