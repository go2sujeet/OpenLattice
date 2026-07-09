package provider

import (
	"reflect"
	"testing"
)

func TestBuildApplyArgs(t *testing.T) {
	tests := []struct {
		name      string
		specFile  string
		outputDir string
		stateFile string
		want      []string
	}{
		{
			name:      "without state file",
			specFile:  "ipaas.lattice",
			outputDir: "generated",
			stateFile: "",
			want:      []string{"apply", "ipaas.lattice", "--output-dir", "generated"},
		},
		{
			name:      "with state file",
			specFile:  "ipaas.lattice",
			outputDir: "generated",
			stateFile: "generated/.lattice-state.json",
			want: []string{
				"apply", "ipaas.lattice", "--output-dir", "generated",
				"--state-file", "generated/.lattice-state.json",
			},
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			got := buildApplyArgs(tt.specFile, tt.outputDir, tt.stateFile)
			if !reflect.DeepEqual(got, tt.want) {
				t.Errorf("buildApplyArgs(%q, %q, %q) = %#v, want %#v",
					tt.specFile, tt.outputDir, tt.stateFile, got, tt.want)
			}
		})
	}
}

func TestBuildPlanArgs(t *testing.T) {
	tests := []struct {
		name      string
		specFile  string
		outputDir string
		stateFile string
		want      []string
	}{
		{
			name:      "without state file",
			specFile:  "ipaas.lattice",
			outputDir: "generated",
			stateFile: "",
			want:      []string{"plan", "ipaas.lattice", "--output-dir", "generated"},
		},
		{
			name:      "with state file",
			specFile:  "ipaas.lattice",
			outputDir: "generated",
			stateFile: "custom-state.json",
			want: []string{
				"plan", "ipaas.lattice", "--output-dir", "generated",
				"--state-file", "custom-state.json",
			},
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			got := buildPlanArgs(tt.specFile, tt.outputDir, tt.stateFile)
			if !reflect.DeepEqual(got, tt.want) {
				t.Errorf("buildPlanArgs(%q, %q, %q) = %#v, want %#v",
					tt.specFile, tt.outputDir, tt.stateFile, got, tt.want)
			}
		})
	}
}
