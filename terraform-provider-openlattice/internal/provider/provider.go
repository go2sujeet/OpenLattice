// Package provider implements a minimal (v0 / proof-of-concept) Terraform
// and OpenTofu provider that wraps the `openlattice` CLI. It does not
// provision any real infrastructure — it shells out to `openlattice apply`
// / `openlattice plan` to generate application code from a .lattice spec
// file, treating "code generation" as the provisioned resource.
package provider

import (
	"context"

	"github.com/hashicorp/terraform-plugin-framework/datasource"
	"github.com/hashicorp/terraform-plugin-framework/provider"
	"github.com/hashicorp/terraform-plugin-framework/provider/schema"
	"github.com/hashicorp/terraform-plugin-framework/resource"
)

// Ensure OpenLatticeProvider satisfies the provider.Provider interface.
var _ provider.Provider = &OpenLatticeProvider{}

// OpenLatticeProvider is the provider implementation.
type OpenLatticeProvider struct {
	// version is set by goreleaser (or "dev" for local builds).
	version string
}

// OpenLatticeProviderModel describes the provider-level configuration. v0
// has no provider-level configuration; the `openlattice` CLI is expected to
// already be on PATH.
type OpenLatticeProviderModel struct{}

func (p *OpenLatticeProvider) Metadata(_ context.Context, _ provider.MetadataRequest, resp *provider.MetadataResponse) {
	resp.TypeName = "openlattice"
	resp.Version = p.version
}

func (p *OpenLatticeProvider) Schema(_ context.Context, _ provider.SchemaRequest, resp *provider.SchemaResponse) {
	resp.Schema = schema.Schema{
		Description: "OpenLattice is a v0 / proof-of-concept provider that shells out to the " +
			"`openlattice` CLI (https://github.com/go2sujeet/OpenLattice) to generate application " +
			"code from a .lattice spec file. It does not provision real infrastructure and has no " +
			"provider-level configuration: the `openlattice` CLI must already be installed and on " +
			"PATH (e.g. via `pip install openlattice` or `uv tool install openlattice`).",
	}
}

func (p *OpenLatticeProvider) Configure(_ context.Context, _ provider.ConfigureRequest, _ *provider.ConfigureResponse) {
	// No provider-level configuration in v0.
}

func (p *OpenLatticeProvider) Resources(_ context.Context) []func() resource.Resource {
	return []func() resource.Resource{
		NewPipelineResource,
	}
}

func (p *OpenLatticeProvider) DataSources(_ context.Context) []func() datasource.DataSource {
	return []func() datasource.DataSource{}
}

// New returns a function that constructs a fresh OpenLatticeProvider,
// suitable for passing to providerserver.Serve / providerserver.NewProtocol6.
func New(version string) func() provider.Provider {
	return func() provider.Provider {
		return &OpenLatticeProvider{
			version: version,
		}
	}
}
