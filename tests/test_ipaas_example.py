"""Regression test for examples/ipaas/ipaas.lattice.

Guards against the example silently rotting out of sync with the parser:
if the DSL grammar changes in a way that breaks this spec, or the spec
stops asserting the facts the README/generated output rely on, this test
should fail loudly.
"""

from pathlib import Path

from openlattice.generators.connectors_gen import generate as gen_connectors
from openlattice.generators.workflow_gen import generate as gen_workflows
from openlattice.parser import parse_file

REPO_ROOT = Path(__file__).resolve().parent.parent
SPEC_FILE = REPO_ROOT / "examples" / "ipaas" / "ipaas.lattice"


def test_ipaas_spec_parses_cleanly():
    spec = parse_file(str(SPEC_FILE))

    assert [e.name for e in spec.entities] == ["Lead"]

    assert len(spec.apis) == 1
    api = spec.apis[0]
    assert api.name == "ReceiveLeadWebhook"
    assert api.method == "POST"
    assert api.path == "/webhooks/lead"
    assert api.input_entity == "Lead"
    assert api.publishes == ["LeadReceived"]

    assert len(spec.events) == 1
    event = spec.events[0]
    assert event.name == "LeadReceived"
    assert {f.name for f in event.payload} == {"id", "email", "source"}
    # The api publishes it, so it should show up as a publisher.
    assert "ReceiveLeadWebhook" in event.published_by

    assert len(spec.connectors) == 1
    connector = spec.connectors[0]
    assert connector.name == "SlackNotify"
    assert connector.kind == "http_webhook"
    assert connector.method == "POST"
    assert connector.headers.get("Content-Type") == "application/json"
    assert "email" in connector.body_template["text"]

    assert len(spec.workflows) == 1
    workflow = spec.workflows[0]
    assert workflow.name == "ProcessLead"
    assert workflow.trigger == "LeadReceived"
    step_names = [s.name for s in workflow.steps]
    assert step_names == ["validate_lead", "enrich_lead", "slack_notify"]

    assert len(spec.queues) == 1
    queue = spec.queues[0]
    assert queue.name == "lead_processing"
    assert queue.message_type == "LeadReceived"
    assert queue.retries == 5
    assert queue.dlq is True


def test_ipaas_workflow_step_wires_to_connector():
    """The `slack_notify` step must resolve to the real connector, not a stub."""
    spec = parse_file(str(SPEC_FILE))

    workflows_src = gen_workflows(spec)
    assert "from .connectors import slack_notify" in workflows_src
    assert 'async def slack_notify(' not in workflows_src  # no stub generated

    connectors_src = gen_connectors(spec)
    assert "async def slack_notify(" in connectors_src
    assert "hooks.slack.com" in connectors_src
