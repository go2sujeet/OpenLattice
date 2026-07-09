package main

import (
	"context"
	"flag"
	"log"

	"github.com/go2sujeet/OpenLattice/terraform-provider-openlattice/internal/provider"
	"github.com/hashicorp/terraform-plugin-framework/providerserver"
)

var (
	// version is set via -ldflags at build time (e.g. by goreleaser). It
	// defaults to "dev" for local builds.
	version string = "dev"
)

func main() {
	var debug bool

	flag.BoolVar(&debug, "debug", false, "set to true to run the provider with support for debuggers like delve")
	flag.Parse()

	opts := providerserver.ServeOpts{
		// This is a v0 / proof-of-concept provider — it is not published to
		// any registry. The address below is only used for local dev_overrides.
		Address: "registry.terraform.io/go2sujeet/openlattice",
		Debug:   debug,
	}

	err := providerserver.Serve(context.Background(), provider.New(version), opts)

	if err != nil {
		log.Fatal(err.Error())
	}
}
