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
    assert [s.name for s in spec.workflows[0].steps] == ["validate_order", "charge_customer"]
    assert spec.workflows[0].steps[0].input is None
    assert spec.workflows[0].trigger is None


def test_parse_workflow_steps_with_io():
    src = """
resource "lattice_workflow" "checkout" {
  name    = "Checkout"
  trigger = "OrderCreated"
  steps = [
    { name = "validate_cart" input = "Cart" output = "Cart" }
    { name = "charge_payment" input = "Cart" output = "Payment" on_error = "refund" }
  ]
}
"""
    spec = parse_string(src)
    w = spec.workflows[0]
    assert w.trigger == "OrderCreated"
    assert w.steps[0].name == "validate_cart"
    assert w.steps[0].input == "Cart"
    assert w.steps[0].output == "Cart"
    assert w.steps[0].on_error is None
    assert w.steps[1].on_error == "refund"


def test_parse_workflow_step_missing_name_raises():
    src = """
resource "lattice_workflow" "checkout" {
  name  = "Checkout"
  steps = [{ input = "Cart" }]
}
"""
    with pytest.raises(ParseError) as exc:
        parse_string(src)
    assert "name" in str(exc.value).lower()


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
    assert spec.queues[0].message_type is None
    assert spec.queues[0].dlq is False


def test_parse_queue_message_type_and_dlq():
    src = """
resource "lattice_queue" "emails" {
  name         = "emails"
  message_type = "OrderCreated"
  retries      = 5
  dlq          = true
}
"""
    spec = parse_string(src)
    q = spec.queues[0]
    assert q.message_type == "OrderCreated"
    assert q.retries == 5
    assert q.dlq is True


def test_parse_api_publishes_and_crud_operation():
    src = """
resource "lattice_entity" "order" {
  name = "Order"
  fields = { id = "uuid" }
}
resource "lattice_api" "create_order" {
  name      = "CreateOrder"
  method    = "POST"
  path      = "/orders"
  input     = lattice_entity.order.name
  output    = lattice_entity.order.name
  publishes = ["OrderCreated"]
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
"""
    spec = parse_string(src)
    create, get, list_ = spec.apis
    assert create.publishes == ["OrderCreated"]
    assert create.crud_operation == "create"
    assert get.crud_operation == "read"
    assert list_.crud_operation == "list"


def test_event_published_by_and_consumed_by_linked():
    src = """
resource "lattice_event" "order_created" {
  name = "OrderCreated"
  payload = { order_id = "uuid" }
}
resource "lattice_workflow" "checkout" {
  name  = "Checkout"
  steps = [{ name = "create_order" output = "OrderCreated" }]
}
resource "lattice_workflow" "send_receipt" {
  name    = "SendReceipt"
  trigger = "OrderCreated"
  steps   = ["send_email"]
}
resource "lattice_queue" "notifications" {
  name         = "notifications"
  message_type = "OrderCreated"
}
"""
    spec = parse_string(src)
    event = spec.events[0]
    assert event.published_by == ["Checkout"]
    assert event.consumed_by == ["SendReceipt", "notifications"]


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


def test_parse_connector():
    src = """
resource "lattice_connector" "slack_notify" {
  name    = "SlackNotify"
  kind    = "http_webhook"
  url     = "https://hooks.slack.com/services/T000/B000/XXXX"
  method  = "POST"
  headers = { "Content-Type" = "application/json" }
  body_template = {
    text = "{{ order_id }} shipped"
  }
}
"""
    spec = parse_string(src)
    assert len(spec.connectors) == 1
    c = spec.connectors[0]
    assert c.name == "SlackNotify"
    assert c.kind == "http_webhook"
    assert c.url == "https://hooks.slack.com/services/T000/B000/XXXX"
    assert c.method == "POST"
    assert c.headers == {"Content-Type": "application/json"}
    assert c.body_template == {"text": "{{ order_id }} shipped"}


def test_parse_connector_defaults():
    src = """
resource "lattice_connector" "slack_notify" {
  name = "SlackNotify"
  kind = "http_webhook"
  url  = "https://hooks.slack.com/services/T000/B000/XXXX"
}
"""
    spec = parse_string(src)
    c = spec.connectors[0]
    assert c.method == "POST"
    assert c.headers == {}
    assert c.body_template == {}


def test_connector_invalid_kind_raises():
    src = """
resource "lattice_connector" "bad" {
  name = "Bad"
  kind = "something_else"
  url  = "https://example.com"
}
"""
    with pytest.raises(ParseError) as exc:
        parse_string(src)
    assert "something_else" in str(exc.value)


def test_connector_missing_name_raises():
    src = """
resource "lattice_connector" "bad" {
  kind = "http_webhook"
  url  = "https://example.com"
}
"""
    with pytest.raises(ParseError) as exc:
        parse_string(src)
    assert "name" in str(exc.value).lower()


def test_connector_missing_url_raises():
    src = """
resource "lattice_connector" "bad" {
  name = "Bad"
  kind = "http_webhook"
}
"""
    with pytest.raises(ParseError) as exc:
        parse_string(src)
    assert "url" in str(exc.value).lower()


def test_object_quoted_string_key():
    src = """
resource "lattice_connector" "slack_notify" {
  name    = "SlackNotify"
  kind    = "http_webhook"
  url     = "https://example.com"
  headers = { "Content-Type" = "application/json" }
}
"""
    spec = parse_string(src)
    assert spec.connectors[0].headers == {"Content-Type": "application/json"}


def test_object_bare_ident_key_still_works():
    src = """
resource "lattice_entity" "order" {
  name = "Order"
  fields = { id = "uuid" }
}
"""
    spec = parse_string(src)
    assert spec.entities[0].fields[0].name == "id"
    assert spec.entities[0].fields[0].type == "uuid"


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
