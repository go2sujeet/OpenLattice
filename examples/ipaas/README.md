# iPaaS example: webhook-in -> transform -> Slack-out

The canonical "Zapier-style" integration pipeline: a third party POSTs data
to a webhook, the payload flows through a workflow that validates and
enriches it, and the last step calls out to a real third-party service
(Slack) via a `lattice_connector`. This proves the OpenLattice DSL
generalizes past CRUD backends to event-driven integration pipelines.

## The pipeline

1. `lattice_entity "lead"` — the shape of an inbound lead (`id`, `email`, `source`).
2. `lattice_api "receive_lead_webhook"` — `POST /webhooks/lead`, accepts a `Lead`
   body and `publishes = ["LeadReceived"]`.
3. `lattice_event "lead_received"` — the `LeadReceived` event contract, carrying
   the same fields as `Lead`.
4. `lattice_connector "slack_notify"` — an `http_webhook` connector that POSTs a
   Slack-formatted message to an incoming-webhook URL.
5. `lattice_workflow "process_lead"` — triggered by `LeadReceived`, runs three
   steps: `validate_lead` -> `enrich_lead` -> `slack_notify`. Because the last
   step's name (`slack_notify`) matches the snake-cased name of the
   `SlackNotify` connector, the generated workflow orchestrator calls the real
   connector client instead of leaving a stub.
6. `lattice_queue "lead_processing"` — durable queue for `LeadReceived` messages,
   5 retries, with a dead-letter queue enabled.

## Regenerating

```bash
uv run openlattice apply examples/ipaas/ipaas.lattice -o examples/ipaas/generated
```

This writes `schemas.py`, `models.py`, `routes.py`, `app.py`, `events.py`,
`connectors.py`, `workflows.py`, and `queues.py` into `examples/ipaas/generated/`,
and updates `examples/ipaas/generated/.lattice-state.json`.

Use `openlattice plan examples/ipaas/ipaas.lattice -o examples/ipaas/generated`
first to preview changes without writing anything.

## Using it for real

`slack_notify`'s `url` is a placeholder:

```hcl
resource "lattice_connector" "slack_notify" {
  name   = "SlackNotify"
  kind   = "http_webhook"
  url    = "https://hooks.slack.com/services/PLACEHOLDER"
  ...
}
```

To actually post to Slack, replace it with a real
[Slack incoming webhook URL](https://api.slack.com/messaging/webhooks) and
re-run `apply`. The generated `connectors.py` client (`slack_notify`) will POST
the rendered `body_template` (`{"text": "New lead: {{ email }}"}`) to that URL
whenever the workflow reaches its last step.
