from pathlib import Path

from openlattice.ir import ApiDef, ConnectorDef, EntityDef, FieldDef, LatticeSpec
from openlattice.state import (
    ResourceState,
    StateFile,
    build_new_state,
    compute_spec_hash,
    diff_spec_against_state,
    load_state,
    save_state,
)


def _make_spec() -> LatticeSpec:
    return LatticeSpec(
        entities=[EntityDef("Order", [FieldDef("id", "uuid"), FieldDef("amount", "int")])],
        apis=[ApiDef("CreateOrder", "POST", "/orders", "Order", "Order")],
    )


def test_compute_spec_hash_deterministic():
    h1 = compute_spec_hash("lattice_entity", "order", {"name": "Order", "fields": {"id": "uuid"}})
    h2 = compute_spec_hash("lattice_entity", "order", {"name": "Order", "fields": {"id": "uuid"}})
    assert h1 == h2
    assert h1.startswith("sha256:")


def test_compute_spec_hash_changes_on_mutation():
    h1 = compute_spec_hash("lattice_entity", "order", {"name": "Order", "fields": {"id": "uuid"}})
    h2 = compute_spec_hash(
        "lattice_entity", "order", {"name": "Order", "fields": {"id": "uuid", "amount": "int"}}
    )
    assert h1 != h2


def test_diff_empty_state_all_new():
    spec = _make_spec()
    state = StateFile(resources=[])
    result = diff_spec_against_state(spec, state)
    assert "lattice_entity.order" in result.to_add
    assert "lattice_api.create_order" in result.to_add
    assert result.to_change == []
    assert result.to_destroy == []


def test_diff_empty_state_all_new_with_connector():
    spec = LatticeSpec(
        connectors=[
            ConnectorDef(
                name="SlackNotify",
                kind="http_webhook",
                url="https://hooks.slack.com/services/T000/B000/XXXX",
            )
        ]
    )
    state = StateFile(resources=[])
    result = diff_spec_against_state(spec, state)
    assert "lattice_connector.slack_notify" in result.to_add
    assert result.to_change == []
    assert result.to_destroy == []


def test_diff_unchanged_resource_not_in_diff():
    spec = _make_spec()
    h = compute_spec_hash(
        "lattice_entity", "order", {"name": "Order", "fields": {"id": "uuid", "amount": "int"}}
    )
    state = StateFile(
        resources=[
            ResourceState(
                type="lattice_entity",
                label="order",
                attributes={"name": "Order", "fields": {"id": "uuid", "amount": "int"}},
                spec_hash=h,
            )
        ]
    )
    result = diff_spec_against_state(spec, state)
    assert "lattice_entity.order" not in result.to_add
    assert "lattice_entity.order" not in result.to_change


def test_diff_changed_resource_in_change():
    spec = _make_spec()
    state = StateFile(
        resources=[
            ResourceState(
                type="lattice_entity",
                label="order",
                attributes={"name": "Order", "fields": {"id": "uuid"}},
                spec_hash="sha256:stale",
            )
        ]
    )
    result = diff_spec_against_state(spec, state)
    assert "lattice_entity.order" in result.to_change


def test_diff_removed_resource_in_destroy():
    spec = LatticeSpec()
    state = StateFile(
        resources=[
            ResourceState(
                type="lattice_entity",
                label="order",
                attributes={"name": "Order", "fields": {}},
                spec_hash="sha256:abc",
            )
        ]
    )
    result = diff_spec_against_state(spec, state)
    assert "lattice_entity.order" in result.to_destroy


def test_save_and_load_state(tmp_path: Path) -> None:
    state = StateFile(
        resources=[
            ResourceState(
                type="lattice_entity",
                label="order",
                attributes={"name": "Order", "fields": {"id": "uuid"}},
                spec_hash="sha256:abc123",
            )
        ]
    )
    path = str(tmp_path / ".lattice-state.json")
    save_state(state, path)
    loaded = load_state(path)
    assert len(loaded.resources) == 1
    assert loaded.resources[0].type == "lattice_entity"
    assert loaded.resources[0].label == "order"
    assert loaded.resources[0].spec_hash == "sha256:abc123"
    assert loaded.version == "1"


def test_load_state_missing_file_returns_empty(tmp_path: Path) -> None:
    state = load_state(str(tmp_path / "nonexistent.json"))
    assert state.resources == []


def test_build_new_state_increments_serial():
    spec = _make_spec()
    old_state = StateFile(resources=[], serial=3)
    new_state = build_new_state(spec, old_state)
    assert new_state.serial == 4
    assert len(new_state.resources) == 2  # 1 entity + 1 api


def test_build_new_state_preserves_lineage():
    spec = _make_spec()
    old_state = StateFile(resources=[], lineage="test-lineage-id")
    new_state = build_new_state(spec, old_state)
    assert new_state.lineage == "test-lineage-id"
