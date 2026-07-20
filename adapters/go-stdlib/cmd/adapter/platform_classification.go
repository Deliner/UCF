package main

import (
	"errors"
	"go/ast"
	"go/parser"
	"go/token"
	"strings"
)

const (
	goCLICommandURI            = "urn:ucf:inventory-interface:go-cli-subcommand:1.0.0"
	goFileSpoolEventCommandURI = "urn:ucf:inventory-interface:go-file-spool-event-command:1.0.0"
)

const frozenGoPlatformModule = `module example.com/legacyplatforms

go 1.26.0

toolchain go1.26.5
`

func classifyFrozenGoPlatformFixture(
	entries []scannedInventoryEntry,
) ([]classifiedInventoryFact, error) {
	content := map[string][]byte{}
	for _, entry := range entries {
		if entry.kind == "file" {
			content[entry.path] = entry.content
		}
	}
	module := content["go.mod"]
	if string(module) != frozenGoPlatformModule {
		return nil, errors.New("supported Go platform module is unavailable")
	}
	facts := []classifiedInventoryFact{
		{
			kind: "build_manifest",
			path: "go.mod",
			span: sourceSpanForOffsets(module, 0, len(module)-1),
			attributes: map[string]any{
				"dialect_uri": goModuleDialectURI,
			},
		},
	}
	classifiers := []func(map[string][]byte) ([]classifiedInventoryFact, error){
		classifyPlatformQuoteService,
		classifyPlatformSpool,
		classifyPlatformCommands,
		classifyPlatformTests,
	}
	for _, classifier := range classifiers {
		classified, err := classifier(content)
		if err != nil {
			return nil, err
		}
		facts = append(facts, classified...)
	}
	if len(facts) != 17 {
		return nil, errors.New("supported Go platform classification count differs")
	}
	return facts, nil
}

func classifyPlatformQuoteService(
	content map[string][]byte,
) ([]classifiedInventoryFact, error) {
	const path = "quote/service.go"
	source := content[path]
	fileSet, functions, err := exactTopLevelFunctions(
		path,
		source,
		"quote",
		[]string{"QuoteOrder", "FormatReceipt"},
	)
	if err != nil {
		return nil, err
	}
	return interfaceFactsForFunctions(
		fileSet,
		source,
		path,
		functions,
		[]platformInterfaceSpec{
			{
				function: "QuoteOrder",
				uri:      goExportedFunctionURI,
				name:     "QuoteOrder",
			},
			{
				function: "FormatReceipt",
				uri:      goExportedFunctionURI,
				name:     "FormatReceipt",
			},
		},
	)
}

func classifyPlatformSpool(
	content map[string][]byte,
) ([]classifiedInventoryFact, error) {
	const path = "spool/spool.go"
	source := content[path]
	fileSet, functions, err := exactTopLevelFunctions(
		path,
		source,
		"spool",
		[]string{
			"Enqueue",
			"DispatchOne",
			"Observe",
			"validateRequest",
			"validEventID",
			"prepareLayout",
			"writeExclusive",
			"readEnvelope",
		},
	)
	if err != nil {
		return nil, err
	}
	return interfaceFactsForFunctions(
		fileSet,
		source,
		path,
		functions,
		[]platformInterfaceSpec{
			{
				function:  "Enqueue",
				uri:       goExportedFunctionURI,
				name:      "Enqueue",
				container: "file-spool",
			},
			{
				function:  "DispatchOne",
				uri:       goExportedFunctionURI,
				name:      "DispatchOne",
				container: "file-spool",
			},
			{
				function:  "Observe",
				uri:       goExportedFunctionURI,
				name:      "Observe",
				container: "file-spool",
			},
		},
	)
}

func classifyPlatformCommands(
	content map[string][]byte,
) ([]classifiedInventoryFact, error) {
	const path = "cmd/platform/main.go"
	source := content[path]
	fileSet, functions, err := exactTopLevelFunctions(
		path,
		source,
		"main",
		[]string{
			"main",
			"run",
			"runQuote",
			"runEvent",
			"runEnqueue",
			"runDispatch",
			"runObserve",
			"eventErrorExit",
		},
	)
	if err != nil {
		return nil, err
	}
	return interfaceFactsForFunctions(
		fileSet,
		source,
		path,
		functions,
		[]platformInterfaceSpec{
			{
				function:  "runQuote",
				uri:       goCLICommandURI,
				name:      "quote",
				container: "legacy-platforms",
			},
			{
				function:  "runEnqueue",
				uri:       goFileSpoolEventCommandURI,
				name:      "event enqueue",
				container: "legacy-platforms",
			},
			{
				function:  "runDispatch",
				uri:       goFileSpoolEventCommandURI,
				name:      "event dispatch-once",
				container: "legacy-platforms",
			},
			{
				function:  "runObserve",
				uri:       goFileSpoolEventCommandURI,
				name:      "event observe",
				container: "legacy-platforms",
			},
		},
	)
}

func classifyPlatformTests(
	content map[string][]byte,
) ([]classifiedInventoryFact, error) {
	specifications := []struct {
		path        string
		packageName string
		functions   []string
		tests       []string
	}{
		{
			path:        "cmd/platform/main_test.go",
			packageName: "main",
			functions: []string{
				"TestPlatformHelperProcess",
				"TestCommandProcessesExposeCLIAndTemporallyDecoupledEvent",
				"TestCommandProcessesRejectInvalidAndDuplicateInput",
				"runProcess",
				"normalizeTestStderr",
			},
			tests: []string{
				"TestPlatformHelperProcess",
				"TestCommandProcessesExposeCLIAndTemporallyDecoupledEvent",
				"TestCommandProcessesRejectInvalidAndDuplicateInput",
			},
		},
		{
			path:        "quote/service_test.go",
			packageName: "quote",
			functions: []string{
				"TestQuoteOrderReturnsTheLegacyTotal",
				"TestQuoteOrderRejectsInvalidValues",
			},
			tests: []string{
				"TestQuoteOrderReturnsTheLegacyTotal",
				"TestQuoteOrderRejectsInvalidValues",
			},
		},
		{
			path:        "spool/spool_test.go",
			packageName: "spool",
			functions: []string{
				"TestEventRemainsUnobservedUntilIndependentDispatch",
				"TestEventSpoolRejectsDuplicatesInvalidIDsAndSymlinks",
			},
			tests: []string{
				"TestEventRemainsUnobservedUntilIndependentDispatch",
				"TestEventSpoolRejectsDuplicatesInvalidIDsAndSymlinks",
			},
		},
	}
	facts := make([]classifiedInventoryFact, 0, 7)
	for _, specification := range specifications {
		source := content[specification.path]
		fileSet, functions, err := exactTopLevelFunctions(
			specification.path,
			source,
			specification.packageName,
			specification.functions,
		)
		if err != nil {
			return nil, err
		}
		for _, name := range specification.tests {
			span, _, err := nodeCoordinates(
				fileSet,
				functions[name],
				source,
			)
			if err != nil {
				return nil, err
			}
			facts = append(facts, classifiedInventoryFact{
				kind: "test_asset",
				path: specification.path,
				span: span,
				attributes: map[string]any{
					"test_kind_uri": goNativeTestURI,
					"name":          name,
				},
			})
		}
	}
	return facts, nil
}

type platformInterfaceSpec struct {
	function  string
	uri       string
	name      string
	container any
}

func interfaceFactsForFunctions(
	fileSet *token.FileSet,
	source []byte,
	path string,
	functions map[string]*ast.FuncDecl,
	specifications []platformInterfaceSpec,
) ([]classifiedInventoryFact, error) {
	facts := make([]classifiedInventoryFact, 0, len(specifications))
	for _, specification := range specifications {
		fact, err := publicInterfaceFactAtPath(
			fileSet,
			source,
			path,
			functions[specification.function],
			specification.uri,
			specification.name,
			specification.container,
		)
		if err != nil {
			return nil, err
		}
		facts = append(facts, fact)
	}
	return facts, nil
}

func exactTopLevelFunctions(
	path string,
	source []byte,
	packageName string,
	expected []string,
) (*token.FileSet, map[string]*ast.FuncDecl, error) {
	if source == nil {
		return nil, nil, errors.New("supported Go platform source is unavailable")
	}
	fileSet := token.NewFileSet()
	file, err := parser.ParseFile(
		fileSet,
		path,
		source,
		parser.SkipObjectResolution,
	)
	if err != nil || file.Name.Name != packageName {
		return nil, nil, errors.New("supported Go platform source cannot be parsed")
	}
	actual := make([]string, 0, len(expected))
	functions := map[string]*ast.FuncDecl{}
	for _, declaration := range file.Decls {
		function, ok := declaration.(*ast.FuncDecl)
		if !ok || function.Recv != nil {
			continue
		}
		actual = append(actual, function.Name.Name)
		functions[function.Name.Name] = function
	}
	if strings.Join(actual, "\x00") != strings.Join(expected, "\x00") {
		return nil, nil, errors.New("supported Go platform function set differs")
	}
	return fileSet, functions, nil
}
