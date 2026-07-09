package provider

import (
	"bytes"
	"context"
	"fmt"
	"os/exec"

	"github.com/hashicorp/terraform-plugin-framework/diag"
	"github.com/hashicorp/terraform-plugin-framework/resource"
	"github.com/hashicorp/terraform-plugin-framework/resource/schema"
	"github.com/hashicorp/terraform-plugin-framework/types"
)

// openLatticeBinary is the name of the CLI this provider shells out to. It
// must already be installed and on PATH (e.g. via `pip install openlattice`
// or `uv tool install openlattice`) — this provider does not vendor or
// reimplement any of its logic.
const openLatticeBinary = "openlattice"

// Ensure PipelineResource satisfies the expected interfaces.
var (
	_ resource.Resource               = &PipelineResource{}
	_ resource.ResourceWithModifyPlan = &PipelineResource{}
)

// PipelineResource implements the openlattice_pipeline resource.
type PipelineResource struct{}

// NewPipelineResource is the constructor registered with the provider.
func NewPipelineResource() resource.Resource {
	return &PipelineResource{}
}

// PipelineResourceModel maps the openlattice_pipeline schema to Go types.
type PipelineResourceModel struct {
	SpecFile  types.String `tfsdk:"spec_file"`
	OutputDir types.String `tfsdk:"output_dir"`
	StateFile types.String `tfsdk:"state_file"`
}

func (r *PipelineResource) Metadata(_ context.Context, req resource.MetadataRequest, resp *resource.MetadataResponse) {
	resp.TypeName = req.ProviderTypeName + "_pipeline"
}

func (r *PipelineResource) Schema(_ context.Context, _ resource.SchemaRequest, resp *resource.SchemaResponse) {
	resp.Schema = schema.Schema{
		Description: "Provisions the generated application code for a single OpenLattice .lattice " +
			"spec by shelling out to the `openlattice` CLI. This is a v0 / proof-of-concept resource: " +
			"it does not provision any real infrastructure, and `Delete` is a no-op — destroying this " +
			"resource in Terraform/OpenTofu state does NOT delete the generated files on disk. Remove " +
			"them manually if that's what you want.",
		Attributes: map[string]schema.Attribute{
			"spec_file": schema.StringAttribute{
				Required:    true,
				Description: "Path to the .lattice spec file to compile, passed as the positional argument to `openlattice apply`/`openlattice plan`.",
			},
			"output_dir": schema.StringAttribute{
				Required:    true,
				Description: "Directory generated files are written to, passed as `--output-dir` to `openlattice apply`/`openlattice plan`.",
			},
			"state_file": schema.StringAttribute{
				Optional:    true,
				Description: "Path to the OpenLattice state file, passed as `--state-file`. If omitted, `openlattice` uses its own default (colocated with output_dir).",
			},
		},
	}
}

func (r *PipelineResource) Create(ctx context.Context, req resource.CreateRequest, resp *resource.CreateResponse) {
	var data PipelineResourceModel
	resp.Diagnostics.Append(req.Plan.Get(ctx, &data)...)
	if resp.Diagnostics.HasError() {
		return
	}

	if diags := r.applyPipeline(ctx, data); diags.HasError() {
		resp.Diagnostics.Append(diags...)
		return
	}

	resp.Diagnostics.Append(resp.State.Set(ctx, &data)...)
}

func (r *PipelineResource) Read(_ context.Context, _ resource.ReadRequest, _ *resource.ReadResponse) {
	// v0: no-op. The "state" tracked here is simply "did the last apply
	// succeed" — there is no drift detection against the generated files.
	// A future version could shell out to `openlattice plan` here and
	// surface differences, but that's explicitly out of scope for v0.
}

func (r *PipelineResource) Update(ctx context.Context, req resource.UpdateRequest, resp *resource.UpdateResponse) {
	var data PipelineResourceModel
	resp.Diagnostics.Append(req.Plan.Get(ctx, &data)...)
	if resp.Diagnostics.HasError() {
		return
	}

	if diags := r.applyPipeline(ctx, data); diags.HasError() {
		resp.Diagnostics.Append(diags...)
		return
	}

	resp.Diagnostics.Append(resp.State.Set(ctx, &data)...)
}

func (r *PipelineResource) Delete(_ context.Context, _ resource.DeleteRequest, _ *resource.DeleteResponse) {
	// v0: no-op. Generated code files are not deleted from disk — removing
	// this resource from Terraform/OpenTofu state does not "destroy"
	// anything in the traditional infrastructure sense. The framework
	// automatically removes the resource from state after Delete returns
	// without diagnostics.
}

// ModifyPlan is a lightweight bonus (not required for v0): when an existing
// openlattice_pipeline is being updated, it shells out to `openlattice plan`
// and surfaces the raw plan output as a warning so `terraform plan` gives
// the practitioner a preview of what OpenLattice itself thinks will change.
// It intentionally does not parse the output or set RequiresReplace — that
// would be real drift detection, which is explicitly out of scope for v0.
func (r *PipelineResource) ModifyPlan(ctx context.Context, req resource.ModifyPlanRequest, resp *resource.ModifyPlanResponse) {
	// Nothing to preview on create (no prior state) or destroy (no planned state).
	if req.State.Raw.IsNull() || req.Plan.Raw.IsNull() {
		return
	}

	var data PipelineResourceModel
	resp.Diagnostics.Append(req.Plan.Get(ctx, &data)...)
	if resp.Diagnostics.HasError() {
		return
	}

	args := buildPlanArgs(data.SpecFile.ValueString(), data.OutputDir.ValueString(), data.StateFile.ValueString())
	stdout, stderr, err := runOpenLattice(ctx, args)
	if err != nil {
		resp.Diagnostics.AddWarning(
			fmt.Sprintf("openlattice plan preview failed for %q", data.SpecFile.ValueString()),
			fmt.Sprintf("command: %s %s\nerror: %s\nstdout:\n%s\nstderr:\n%s",
				openLatticeBinary, joinArgs(args), err, stdout, stderr),
		)
		return
	}

	if stdout != "" {
		resp.Diagnostics.AddWarning(
			fmt.Sprintf("OpenLattice plan preview for %q", data.SpecFile.ValueString()),
			stdout,
		)
	}
}

// applyPipeline shells out to `openlattice apply` for the given resource
// model and returns diagnostics describing any failure.
func (r *PipelineResource) applyPipeline(ctx context.Context, data PipelineResourceModel) diag.Diagnostics {
	var diags diag.Diagnostics

	args := buildApplyArgs(data.SpecFile.ValueString(), data.OutputDir.ValueString(), data.StateFile.ValueString())

	stdout, stderr, err := runOpenLattice(ctx, args)
	if err != nil {
		diags.AddError(
			fmt.Sprintf("openlattice apply failed for %q", data.SpecFile.ValueString()),
			fmt.Sprintf("command: %s %s\nerror: %s\nstdout:\n%s\nstderr:\n%s",
				openLatticeBinary, joinArgs(args), err, stdout, stderr),
		)
	}

	return diags
}

// buildApplyArgs constructs the argument list for `openlattice apply`.
// It's a standalone function (rather than inline in applyPipeline) so it
// can be unit tested without invoking a real subprocess.
func buildApplyArgs(specFile, outputDir, stateFile string) []string {
	args := []string{"apply", specFile, "--output-dir", outputDir}
	if stateFile != "" {
		args = append(args, "--state-file", stateFile)
	}
	return args
}

// buildPlanArgs constructs the argument list for `openlattice plan`.
func buildPlanArgs(specFile, outputDir, stateFile string) []string {
	args := []string{"plan", specFile, "--output-dir", outputDir}
	if stateFile != "" {
		args = append(args, "--state-file", stateFile)
	}
	return args
}

// runOpenLattice executes the `openlattice` CLI with the given args and
// returns its captured stdout/stderr.
func runOpenLattice(ctx context.Context, args []string) (stdout string, stderr string, err error) {
	cmd := exec.CommandContext(ctx, openLatticeBinary, args...)

	var outBuf, errBuf bytes.Buffer
	cmd.Stdout = &outBuf
	cmd.Stderr = &errBuf

	err = cmd.Run()
	return outBuf.String(), errBuf.String(), err
}

func joinArgs(args []string) string {
	out := ""
	for i, a := range args {
		if i > 0 {
			out += " "
		}
		out += a
	}
	return out
}
