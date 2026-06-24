"use strict";

const vscode = require("vscode");
const { LanguageClient, TransportKind } = require("vscode-languageclient/node");

let client;

function activate(context) {
  const config = vscode.workspace.getConfiguration("openlattice");
  const lspPath = config.get("lspPath", "openlattice-lsp");

  const serverOptions = {
    command: lspPath,
    args: [],
    transport: TransportKind.stdio,
  };

  const clientOptions = {
    documentSelector: [{ scheme: "file", language: "lattice" }],
    synchronize: {
      fileEvents: vscode.workspace.createFileSystemWatcher("**/*.lattice"),
    },
  };

  client = new LanguageClient(
    "openlattice",
    "OpenLattice Language Server",
    serverOptions,
    clientOptions
  );

  client.start().catch((err) => {
    if (err && err.message && err.message.includes("ENOENT")) {
      vscode.window.showErrorMessage(
        `OpenLattice LSP: Could not start '${lspPath}'. ` +
          "Make sure openlattice is installed with LSP support: " +
          "`pip install openlattice[lsp]` and that 'openlattice-lsp' is on your PATH. " +
          "You can also set openlattice.lspPath to the full path of the binary."
      );
    } else {
      vscode.window.showErrorMessage(
        `OpenLattice LSP failed to start: ${err && err.message ? err.message : String(err)}`
      );
    }
  });

  context.subscriptions.push({
    dispose: () => {
      if (client) {
        client.stop();
      }
    },
  });
}

function deactivate() {
  if (!client) return undefined;
  return client.stop();
}

module.exports = { activate, deactivate };
