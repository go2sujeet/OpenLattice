"""Tests for enriched IR: workflow step I/O, queue message types, event
pub/sub links, and API publishes/crud attributes."""

import pytest

from openlattice.ir import WorkflowStep
from openlattice.parser import parse_string


ENRICHED_SPEC = """
resource "lattice_entity" "cart" {
  name = "Cart"
  fields = {
    id = "uuid"
  }
}

resource "lattice_entity" "order" {
  name = "Order"
  fields = {
    id      = "uuid"
    user_id = "uuid"
    total   = "float"
  }
}

resource "lattice_api" "create_order" {
  name   = "CreateOrder"
  method = "POST"
  path   = "/orders"
  input  = lattice_entity.order.name
  output = lattice_entity.order.name
  publishes = ["OrderCreated"]
  crud      = "create"
}

resource "lattice_event" "order_created" {
  name = "OrderCreated"
  payload = {
    order_id = "uuid"
    total    = "float"
  }
  published_by = ["CreateOrder"]
  consumed_by  = ["email_notifications", "Checkout"]
}

resource "lattice_workflow" "checkout" {
  name    = "Checkout"
  trigger = "OrderCreated"
  steps = [
    { name = "validate_cart",  input = "Cart",  output = "Cart" },
    { name = "charge_payment", input = "Cart",  output = "Payment", on_error = "refund" },
    { name = "create_order",   input = "Payment", output = "Order" },
  ]
}

resource "lattice_queue" "email_notifications" {
  name         = "email_notifications"
  retries      = 5
  message_type = "OrderCreated"
  dlq          = true
}
"""


def test_parses_enriched_spec() -> None:
    spec = parse_string(ENRICHED_SPEC)
    assert len(spec.entities) == 2
    assert len(spec.apis) == 1
    assert len(spec.events) == 1
    assert len(spec.workflows) == 1
    assert len(spec.queues) == 1


def test_api_publishes() -> None:
    spec = parse_string(ENRICHED_SPEC)
    api = spec.apis[0]
    assert api.publishes == ["OrderCreated"]
    assert api.crud_operation == "create"


def test_event_pub_sub_links() -> None:
    spec = parse_string(ENRICHED_SPEC)
    event = spec.events[0]
    assert event.published_by == ["CreateOrder"]
    assert event.consumed_by == ["email_notifications", "Checkout"]


def test_workflow_step_io() -> None:
    spec = parse_string(ENRICHED_SPEC)
    wf = spec.workflows[0]
    assert wf.trigger == "OrderCreated"
    assert len(wf.steps) == 3

    assert wf.steps[0].name == "validate_cart"
    assert wf.steps[0].input == "Cart"
    assert wf.steps[0].output == "Cart"
    assert wf.steps[0].on_error is None

    assert wf.steps[1].name == "charge_payment"
    assert wf.steps[1].input == "Cart"
    assert wf.steps[1].output == "Payment"
    assert wf.steps[1].on_error == "refund"

    assert wf.steps[2].name == "create_order"
    assert wf.steps[2].input == "Payment"
    assert wf.steps[2].output == "Order"


def test_queue_message_type_and_dlq() -> None:
    spec = parse_string(ENRICHED_SPEC)
    q = spec.queues[0]
    assert q.message_type == "OrderCreated"
    assert q.dlq is True
    assert q.retries == 5


def test_backward_compat_string_steps() -> None:
    """Old-style string steps still parse as WorkflowStep with no I/O."""
    src = """
resource "lattice_workflow" "checkout" {
  name  = "Checkout"
  steps = ["validate_order", "charge_customer"]
}
"""
    spec = parse_string(src)
    wf = spec.workflows[0]
    assert wf.steps == [WorkflowStep(name="validate_order"), WorkflowStep(name="charge_customer")]
    assert wf.trigger is None


def test_backward_compat_queue_without_message_type() -> None:
    """Old-style queue without message_type/dlq still parses."""
    src = """
resource "lattice_queue" "emails" {
  name    = "emails"
  retries = 3
}
"""
    spec = parse_string(src)
    q = spec.queues[0]
    assert q.name == "emails"
    assert q.retries == 3
    assert q.message_type is None
    assert q.dlq is False


def test_backward_compat_api_without_publishes() -> None:
    """Old-style API without publishes/crud still parses."""
    src = """
resource "lattice_entity" "order" {
  name = "Order"
  fields = {
    id = "uuid"
  }
}

resource "lattice_api" "get_order" {
  name   = "GetOrder"
  method = "GET"
  path   = "/orders/{id}"
  output = lattice_entity.order.name
}
"""
    spec = parse_string(src)
    api = spec.apis[0]
    assert api.publishes == []
    assert api.crud_operation is None


def test_backward_compat_event_without_pub_sub() -> None:
    """Old-style event without published_by/consumed_by still parses."""
    src = """
resource "lattice_event" "order_created" {
  name = "OrderCreated"
  payload = {
    order_id = "uuid"
  }
}
"""
    spec = parse_string(src)
    event = spec.events[0]
    assert event.published_by == []
    assert event.consumed_by == []


def test_backward_compat_workflow_without_trigger() -> None:
    """Old-style workflow without trigger still parses."""
    src = """
resource "lattice_workflow" "checkout" {
  name  = "Checkout"
  steps = ["validate_cart"]
}
"""
    spec = parse_string(src)
    wf = spec.workflows[0]
    assert wf.trigger is None