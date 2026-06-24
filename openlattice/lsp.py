"""LSP server for .lattice files using pygls."""

from __future__ import annotations

import re
from typing import Optional

from pygls.server import LanguageServer
from lsprotocol import types

from openlattice.parser import parse_string, ParseError

server = LanguageServer("openlattice-lsp", "v0.1.0")

_RESOURCE_TYPES = [
    "lattice_entity",
    "lattice_api",
    "lattice_event",
    "lattice_workflow",
    "lattice_queue",
]

_FIELD_TYPES = ["uuid", "string", "int", "float", "bool", "datetime", "json"]

_HTTP_METHODS = ["GET", "POST", "PUT", "DELETE", "PATCH"]

_RESOURCE_DOCS = {
    "lattice_entity": "Defines a data entity (model) with typed fields — maps to a database table and Pydantic model.",
    "lattice_api": "Defines an HTTP API endpoint with method, path, and optional input/output entity bindings.",
    "lattice_event": "Defines a domain event with a typed payload for event-driven patterns.",
    "lattice_workflow": "Defines a named multi-step workflow with an ordered list of step names.",
    "lattice_queue": "Defines a message queue with a retry policy.",
}


def _extract_entity_labels(text: str) -> list[str]:
    """Best-effort extraction of lattice_entity labels from document text."""
    labels: list[str] = []
    pattern = re.compile(r'resource\s+"lattice_entity"\s+"([^"]+)"')
    for m in pattern.finditer(text):
        labels.append(m.group(1))
    return labels


def _publish_diagnostics(ls: LanguageServer, uri: str, text: str) -> None:
    diagnostics: list[types.Diagnostic] = []
    try:
        parse_string(text)
    except ParseError as e:
        # line is 1-based; LSP positions are 0-based
        line_idx = max(0, (e.line or 1) - 1)
        diagnostics.append(
            types.Diagnostic(
                range=types.Range(
                    start=types.Position(line=line_idx, character=0),
                    end=types.Position(line=line_idx, character=1000),
                ),
                message=e.message,
                severity=types.DiagnosticSeverity.Error,
                source="openlattice-lsp",
            )
        )
    ls.publish_diagnostics(uri, diagnostics)


@server.feature(types.TEXT_DOCUMENT_DID_OPEN)
def did_open(ls: LanguageServer, params: types.DidOpenTextDocumentParams) -> None:
    _publish_diagnostics(ls, params.text_document.uri, params.text_document.text)


@server.feature(types.TEXT_DOCUMENT_DID_CHANGE)
def did_change(ls: LanguageServer, params: types.DidChangeTextDocumentParams) -> None:
    for change in params.content_changes:
        _publish_diagnostics(ls, params.text_document.uri, change.text)


def _get_line_text(text: str, line_idx: int) -> str:
    lines = text.splitlines()
    if line_idx < len(lines):
        return lines[line_idx]
    return ""


def _get_document_text(ls: LanguageServer, uri: str) -> Optional[str]:
    doc = ls.workspace.get_text_document(uri)
    return doc.source if doc else None


def _detect_context(line_text: str, char: int) -> str:
    """
    Return a context string describing what completions to offer.

    Contexts:
      "resource_type"  — cursor is inside resource "..." after the keyword
      "method"         — cursor is on a method = ... line
      "field_type"     — cursor is inside fields = {} or payload = {} value position
      "input_output"   — cursor is on input = ... or output = ... line
      "none"           — no specific completions
    """
    prefix = line_text[:char].lstrip()

    # After: resource "
    if re.search(r'\bresource\s+"[^"]*$', line_text[:char]):
        return "resource_type"

    # method = (with optional partial quote)
    if re.search(r'\bmethod\s*=\s*"?[^"]*$', line_text[:char]):
        return "method"

    # input = or output =
    if re.search(r'\b(?:input|output)\s*=\s*', line_text[:char]):
        return "input_output"

    # Inside a fields/payload block value: looks like `  key = "`
    # We detect: identifier followed by = followed by optional partial string
    if re.search(r'^\s*\w+\s*=\s*"[^"]*$', line_text[:char]):
        return "field_type"

    return "none"


def _make_snippet(label: str, resource_type: str) -> str:
    snippets = {
        "lattice_entity": (
            'lattice_entity" "${2:label}" {\n'
            '  name   = "${3:EntityName}"\n'
            '  fields = {\n'
            '    id = "uuid"\n'
            '  }\n'
            '}'
        ),
        "lattice_api": (
            'lattice_api" "${2:label}" {\n'
            '  name   = "${3:ApiName}"\n'
            '  method = "${4:POST}"\n'
            '  path   = "${5:/path}"\n'
            '}'
        ),
        "lattice_event": (
            'lattice_event" "${2:label}" {\n'
            '  name    = "${3:EventName}"\n'
            '  payload = {\n'
            '    id = "uuid"\n'
            '  }\n'
            '}'
        ),
        "lattice_workflow": (
            'lattice_workflow" "${2:label}" {\n'
            '  name  = "${3:WorkflowName}"\n'
            '  steps = ["${4:step_one}"]\n'
            '}'
        ),
        "lattice_queue": (
            'lattice_queue" "${2:label}" {\n'
            '  name    = "${3:queue_name}"\n'
            '  retries = ${4:3}\n'
            '}'
        ),
    }
    return snippets.get(resource_type, resource_type)


@server.feature(
    types.TEXT_DOCUMENT_COMPLETION,
    types.CompletionOptions(trigger_characters=['"', "=", " ", "."]),
)
def completion(
    ls: LanguageServer, params: types.CompletionParams
) -> Optional[types.CompletionList]:
    text = _get_document_text(ls, params.text_document.uri)
    if text is None:
        return None

    line_idx = params.position.line
    char = params.position.character
    line_text = _get_line_text(text, line_idx)
    context = _detect_context(line_text, char)

    items: list[types.CompletionItem] = []

    if context == "resource_type":
        for rt in _RESOURCE_TYPES:
            # Insert the resource type string content (without opening quote — editor already has it)
            items.append(
                types.CompletionItem(
                    label=rt,
                    kind=types.CompletionItemKind.EnumMember,
                    detail=_RESOURCE_DOCS.get(rt, ""),
                    insert_text_format=types.InsertTextFormat.Snippet,
                    insert_text=_make_snippet("", rt),
                )
            )

    elif context == "method":
        for method in _HTTP_METHODS:
            items.append(
                types.CompletionItem(
                    label=method,
                    kind=types.CompletionItemKind.EnumMember,
                    insert_text=f'"{method}"',
                    insert_text_format=types.InsertTextFormat.PlainText,
                )
            )

    elif context == "field_type":
        for ft in _FIELD_TYPES:
            items.append(
                types.CompletionItem(
                    label=ft,
                    kind=types.CompletionItemKind.TypeParameter,
                    insert_text=ft,
                    insert_text_format=types.InsertTextFormat.PlainText,
                )
            )

    elif context == "input_output":
        entity_labels = _extract_entity_labels(text)
        for label in entity_labels:
            ref = f"lattice_entity.{label}.name"
            items.append(
                types.CompletionItem(
                    label=ref,
                    kind=types.CompletionItemKind.Reference,
                    detail=f"Reference to entity '{label}'",
                    insert_text=ref,
                    insert_text_format=types.InsertTextFormat.PlainText,
                )
            )

    if not items:
        return None

    return types.CompletionList(is_incomplete=False, items=items)


@server.feature(types.TEXT_DOCUMENT_HOVER)
def hover(
    ls: LanguageServer, params: types.HoverParams
) -> Optional[types.Hover]:
    text = _get_document_text(ls, params.text_document.uri)
    if text is None:
        return None

    line_idx = params.position.line
    char = params.position.character
    line_text = _get_line_text(text, line_idx)

    # Check if the cursor is over a resource type keyword
    for rt in _RESOURCE_TYPES:
        idx = line_text.find(rt)
        if idx != -1 and idx <= char < idx + len(rt):
            return types.Hover(
                contents=types.MarkupContent(
                    kind=types.MarkupKind.Markdown,
                    value=f"**`{rt}`** — {_RESOURCE_DOCS[rt]}",
                ),
                range=types.Range(
                    start=types.Position(line=line_idx, character=idx),
                    end=types.Position(line=line_idx, character=idx + len(rt)),
                ),
            )

    return None


def main() -> None:
    server.start_io()


if __name__ == "__main__":
    main()
