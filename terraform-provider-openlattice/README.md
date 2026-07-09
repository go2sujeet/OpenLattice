# terraform-provider-openlattice

A Terraform / OpenTofu provider that wraps the [`openlattice`](https://github.com/go2sujeet/OpenLattice)
CLI as a provisioning resource. `terraform apply` shells out to `openlattice apply` to
generate application code (FastAPI routes, SQLAlchemy models, event/workflow/queue
handlers, ...) from a `.lattice` spec file.

> **v0 / proof-of-concept — not production-ready.**
>
> - **This provider is not published to any Terraform/OpenTofu registry.** It's meant to
>   be built locally and exercised via a `dev_override` (see below).
> - **`Delete` is a no-op.** Removing an `openlattice_pipeline` resource from state does
>   **not** delete the generated files on disk. "Provisioning" here means generating
>   code, not creating real infrastructure — there's nothing sensible to "destroy". If
>   you want the generated files gone, remove them yourself.
> - **No real infrastructure is provisioned.** This does not create Lambdas, ECS
>   services, API gateways, or anything else — it only runs the `openlattice` CLI
>   against a spec file. Provisioning actual compute/runtime infra is a possible future
>   resource, not something this provider does today.
> - **Drift detection is minimal.** `Read` is a no-op (the CLI's own state file is the
>   source of truth). `ModifyPlan` makes a best-effort call to `openlattice plan` on
>   updates and surfaces its raw output as a Terraform warning, purely as a preview —
>   it does not parse the output or drive `RequiresReplace`.

## Prerequisites

This provider does not vendor or reimplement any OpenLattice logic — it is a thin
shell-out wrapper. You need the `openlattice` CLI installed and on `PATH` wherever
Terraform/OpenTofu runs:

```bash
pip install openlattice
# or
uv tool install openlattice
```

Verify it's reachable:

```bash
openlattice --help
```

## Building

```bash
cd terraform-provider-openlattice
go build ./...
```

This produces a `terraform-provider-openlattice` binary in the current directory.

Run the tests and vet with:

```bash
go vet ./...
go test ./...
```

## Local development install (dev_override)

Terraform/OpenTofu supports pointing directly at a locally built provider binary via a
`dev_overrides` block, without needing to publish anything to a registry.

1. Build the provider binary into a stable directory, e.g.:

   ```bash
   cd terraform-provider-openlattice
   go build -o ~/go/bin/terraform-provider-openlattice .
   ```

2. Create (or edit) your CLI config file — `~/.terraformrc` for Terraform, or
   `~/.tofurc` for OpenTofu:

   ```hcl
   provider_installation {
     dev_overrides {
       "go2sujeet/openlattice" = "/Users/you/go/bin"
     }

     # For all other providers, install them as normal.
     direct {}
   }
   ```

   (Point the path at whatever directory contains the binary you built in step 1.)

3. Skip `terraform init` — with a `dev_override` in effect, Terraform/OpenTofu uses the
   local binary directly and warns that overrides are active. Just run `terraform plan`
   / `terraform apply` in a directory containing the example config below.

## Example usage

```hcl
terraform {
  required_providers {
    openlattice = {
      source = "go2sujeet/openlattice"
    }
  }
}

resource "openlattice_pipeline" "leads" {
  spec_file  = "${path.module}/ipaas.lattice"
  output_dir = "${path.module}/generated"
  # state_file is optional; defaults to <output_dir>/.lattice-state.json
}
```

```bash
terraform plan
terraform apply
```

`apply` runs (roughly):

```bash
openlattice apply <spec_file> --output-dir <output_dir> [--state-file <state_file>]
```

If the CLI exits non-zero, the provider fails the operation and surfaces the captured
stdout/stderr as a Terraform diagnostic.

## Resource: `openlattice_pipeline`

| Attribute    | Type   | Required | Description                                                                 |
|--------------|--------|----------|-------------------------------------------------------------------------------|
| `spec_file`  | string | yes      | Path to the `.lattice` spec file to compile.                                 |
| `output_dir` | string | yes      | Directory generated files are written to.                                    |
| `state_file` | string | no       | Path to the OpenLattice state file (defaults to `<output_dir>/.lattice-state.json`). |

## Project layout

```
terraform-provider-openlattice/
├── main.go                              # provider entrypoint (providerserver.Serve)
├── internal/provider/
│   ├── provider.go                      # OpenLatticeProvider (provider-level schema, no config)
│   ├── pipeline_resource.go             # openlattice_pipeline resource + CLI shell-out helpers
│   └── pipeline_resource_test.go        # unit tests for shell-out argument construction
├── go.mod / go.sum
└── README.md
```
