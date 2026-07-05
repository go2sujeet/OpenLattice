import pytest

from openlattice.parser import ParseError, parse_string

MINIMAL_SPEC = """
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
"""


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
    assert a.input_entity == "Order"
    assert a.output_entity == "Order"


def test_parse_event():
    src = """
resource "lattice_event" "order_created" {
  name = "OrderCreated"
  payload = {
    order_id = "uuid"
    amount   = "int"
  }
}
"""
    spec = parse_string(src)
    assert len(spec.events) == 1
    assert spec.events[0].name == "OrderCreated"
    assert spec.events[0].payload[0].name == "order_id"


def test_parse_workflow():
    src = """
resource "lattice_workflow" "checkout" {
  name  = "Checkout"
  steps = ["validate_order", "charge_customer"]
}
"""
    spec = parse_string(src)
    assert len(spec.workflows) == 1
    assert spec.workflows[0].name == "Checkout"
    assert spec.workflows[0].steps == ["validate_order", "charge_customer"]


def test_parse_queue():
    src = """
resource "lattice_queue" "emails" {
  name    = "emails"
  retries = 3
}
"""
    spec = parse_string(src)
    assert len(spec.queues) == 1
    assert spec.queues[0].name == "emails"
    assert spec.queues[0].retries == 3


def test_parse_comment():
    src = """
# This is a comment
resource "lattice_entity" "task" {
  name = "Task"
  fields = {
    id = "uuid"
  }
}
"""
    spec = parse_string(src)
    assert spec.entities[0].name == "Task"


def test_unknown_resource_type_raises():
    src = 'resource "lattice_unknown" "foo" { name = "Foo" }'
    with pytest.raises(ParseError) as exc:
        parse_string(src)
    assert "unknown resource type" in str(exc.value).lower()


def test_invalid_field_type_raises():
    src = """
resource "lattice_entity" "bad" {
  name = "Bad"
  fields = { id = "badtype" }
}
"""
    with pytest.raises(ParseError) as exc:
        parse_string(src)
    assert "badtype" in str(exc.value)


def test_reference_resolution():
    src = """
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
"""
    spec = parse_string(src)
    assert spec.apis[0].output_entity == "Product"


def test_unresolved_reference_raises():
    src = """
resource "lattice_api" "bad" {
  name   = "Bad"
  method = "GET"
  path   = "/bad"
  output = lattice_entity.nonexistent.name
}
"""
    with pytest.raises(ParseError) as exc:
        parse_string(src)
    assert "nonexistent" in str(exc.value)


def test_duplicate_label_raises():
    src = """
resource "lattice_entity" "order" {
  name = "Order"
  fields = { id = "uuid" }
}
resource "lattice_entity" "order" {
  name = "OrderDuplicate"
  fields = { id = "uuid" }
}
"""
    with pytest.raises(ParseError) as exc:
        parse_string(src)
    assert "duplicate" in str(exc.value).lower()


def test_entity_missing_fields_raises():
    src = """
resource "lattice_entity" "bad" {
  name = "Bad"
}
"""
    with pytest.raises(ParseError) as exc:
        parse_string(src)
    assert "fields" in str(exc.value).lower()


def test_empty_spec():
    spec = parse_string("")
    assert spec.entities == []
    assert spec.apis == []


def test_unsupported_reference_attr_raises():
    src = """
resource "lattice_entity" "order" {
  name = "Order"
  fields = { id = "uuid" }
}
resource "lattice_api" "bad" {
  name   = "Bad"
  method = "GET"
  path   = "/bad"
  output = lattice_entity.order.id
}
"""
    with pytest.raises(ParseError) as exc:
        parse_string(src)
    assert ".id" in str(exc.value) or "name" in str(exc.value).lower()
