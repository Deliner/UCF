package main

import (
	"crypto/sha256"
	"encoding/hex"
	"errors"
	"go/ast"
	"go/parser"
	"go/token"
	"reflect"
	"strconv"
	"strings"
)

const (
	goModuleDialectURI    = "urn:ucf:inventory-dialect:go-module:1.0.0"
	goExportedFunctionURI = "urn:ucf:inventory-interface:go-exported-function:1.0.0"
	goLiteralRouteURI     = "urn:ucf:inventory-interface:go-net-http-literal-route:1.0.0"
	goHTTPHandlerURI      = "urn:ucf:inventory-interface:go-net-http-handler:1.0.0"
	goRequestFieldURI     = "urn:ucf:inventory-interface:go-json-request-field:1.0.0"
	goResponseFieldURI    = "urn:ucf:inventory-interface:go-json-response-field:1.0.0"
	goResponseWriteURI    = "urn:ucf:inventory-interface:go-http-response-write:1.0.0"
	goNativeTestURI       = "urn:ucf:inventory-test:go-native-test-function:1.0.0"
)

const frozenGoModule = `module example.com/legacyquotes

go 1.26.0

toolchain go1.26.5
`

type inventorySourceSpan struct {
	startLine   int
	startColumn int
	endLine     int
	endColumn   int
}

type classifiedInventoryFact struct {
	kind       string
	path       string
	span       inventorySourceSpan
	attributes map[string]any
}

func (span inventorySourceSpan) logicalValue() map[string]any {
	return map[string]any{
		"kind":         "source_span",
		"start_line":   span.startLine,
		"start_column": span.startColumn,
		"end_line":     span.endLine,
		"end_column":   span.endColumn,
	}
}

func (fact classifiedInventoryFact) provenanceCoordinate() string {
	return strings.Join(
		[]string{
			fact.path,
			strconv.Itoa(fact.span.startLine),
			strconv.Itoa(fact.span.startColumn),
			strconv.Itoa(fact.span.endLine),
			strconv.Itoa(fact.span.endColumn),
		},
		":",
	)
}

func classifyFrozenGoFixture(
	entries []scannedInventoryEntry,
) ([]classifiedInventoryFact, error) {
	content := map[string][]byte{}
	for _, entry := range entries {
		if entry.kind == "file" {
			content[entry.path] = entry.content
		}
	}
	module := content["go.mod"]
	service := content["quote/service.go"]
	tests := content["quote/service_test.go"]
	if string(module) != frozenGoModule || service == nil || tests == nil {
		return nil, errors.New("supported Go inputs are unavailable")
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
	serviceFacts, err := classifyGoService(service)
	if err != nil {
		return nil, err
	}
	testFacts, err := classifyGoTests(tests)
	if err != nil {
		return nil, err
	}
	facts = append(facts, serviceFacts...)
	facts = append(facts, testFacts...)
	if len(facts) != 16 {
		return nil, errors.New("supported Go classification count differs")
	}
	return facts, nil
}

func classifyGoService(source []byte) ([]classifiedInventoryFact, error) {
	fileSet := token.NewFileSet()
	file, err := parser.ParseFile(
		fileSet,
		"quote/service.go",
		source,
		parser.SkipObjectResolution,
	)
	if err != nil || file.Name.Name != "quote" {
		return nil, errors.New("supported Go service cannot be parsed")
	}
	exported := make([]*ast.FuncDecl, 0, 5)
	byName := map[string]*ast.FuncDecl{}
	for _, declaration := range file.Decls {
		function, ok := declaration.(*ast.FuncDecl)
		if !ok || function.Recv != nil || !ast.IsExported(function.Name.Name) {
			continue
		}
		exported = append(exported, function)
		byName[function.Name.Name] = function
	}
	expectedExported := []string{
		"QuoteOrder",
		"FormatReceipt",
		"NormalizeCoupon",
		"LegacyDiscountHint",
		"Handler",
	}
	if len(exported) != len(expectedExported) {
		return nil, errors.New("supported exported function set differs")
	}
	for index, name := range expectedExported {
		if exported[index].Name.Name != name {
			return nil, errors.New("supported exported function order differs")
		}
	}

	facts := make([]classifiedInventoryFact, 0, 12)
	for _, name := range expectedExported[:4] {
		fact, err := publicInterfaceFact(
			fileSet,
			source,
			byName[name],
			goExportedFunctionURI,
			name,
			nil,
		)
		if err != nil {
			return nil, err
		}
		facts = append(facts, fact)
	}

	handlerDeclaration := byName["Handler"]
	routeCall, handler, err := exactLiteralRoute(handlerDeclaration)
	if err != nil {
		return nil, err
	}
	route, err := publicInterfaceFact(
		fileSet,
		source,
		routeCall,
		goLiteralRouteURI,
		"POST /quote-order",
		"Handler",
	)
	if err != nil {
		return nil, err
	}
	facts = append(facts, route)
	handlerFact, err := publicInterfaceFact(
		fileSet,
		source,
		handler,
		goHTTPHandlerURI,
		"quote.Handler.func1",
		"POST /quote-order",
	)
	if err != nil {
		return nil, err
	}
	facts = append(facts, handlerFact)

	inputs, err := exactRequestFields(fileSet, file, source)
	if err != nil {
		return nil, err
	}
	facts = append(facts, inputs...)
	outputs, err := exactResponseFields(fileSet, handler, source)
	if err != nil {
		return nil, err
	}
	facts = append(facts, outputs...)
	effect, err := publicInterfaceFact(
		fileSet,
		source,
		handler,
		goResponseWriteURI,
		"http-response-write",
		"POST /quote-order",
	)
	if err != nil {
		return nil, err
	}
	facts = append(facts, effect)
	if len(facts) != 12 {
		return nil, errors.New("supported Go interface count differs")
	}
	return facts, nil
}

func classifyGoTests(source []byte) ([]classifiedInventoryFact, error) {
	fileSet := token.NewFileSet()
	file, err := parser.ParseFile(
		fileSet,
		"quote/service_test.go",
		source,
		parser.SkipObjectResolution,
	)
	if err != nil || file.Name.Name != "quote" {
		return nil, errors.New("supported Go tests cannot be parsed")
	}
	expected := []string{
		"TestRealHTTPQuoteOrderReturnsLegacyResult",
		"TestRealHTTPQuoteOrderRejectsZeroQuantity",
		"TestLegacyBusinessFunctionsRetainStandaloneSemantics",
	}
	tests := make([]*ast.FuncDecl, 0, len(expected))
	for _, declaration := range file.Decls {
		function, ok := declaration.(*ast.FuncDecl)
		if ok && strings.HasPrefix(function.Name.Name, "Test") {
			tests = append(tests, function)
		}
	}
	if len(tests) != len(expected) {
		return nil, errors.New("supported native test set differs")
	}
	facts := make([]classifiedInventoryFact, 0, len(expected))
	for index, name := range expected {
		if tests[index].Name.Name != name {
			return nil, errors.New("supported native test order differs")
		}
		span, _, err := nodeCoordinates(fileSet, tests[index], source)
		if err != nil {
			return nil, err
		}
		facts = append(facts, classifiedInventoryFact{
			kind: "test_asset",
			path: "quote/service_test.go",
			span: span,
			attributes: map[string]any{
				"test_kind_uri": goNativeTestURI,
				"name":          name,
			},
		})
	}
	return facts, nil
}

func exactLiteralRoute(
	handlerDeclaration *ast.FuncDecl,
) (*ast.CallExpr, *ast.FuncLit, error) {
	if handlerDeclaration == nil || handlerDeclaration.Body == nil {
		return nil, nil, errors.New("supported Handler declaration is unavailable")
	}
	var route *ast.CallExpr
	var handler *ast.FuncLit
	routeReceiver := ""
	ast.Inspect(handlerDeclaration.Body, func(node ast.Node) bool {
		call, ok := node.(*ast.CallExpr)
		receiver, routeCall := selectorCallReceiver(call, "HandleFunc")
		if !ok || !routeCall {
			return true
		}
		if route != nil || len(call.Args) != 2 {
			route = nil
			handler = nil
			routeReceiver = ""
			return false
		}
		pattern, patternOK := stringLiteral(call.Args[0])
		function, functionOK := call.Args[1].(*ast.FuncLit)
		if !patternOK || pattern != "POST /quote-order" || !functionOK {
			route = nil
			handler = nil
			routeReceiver = ""
			return false
		}
		route = call
		handler = function
		routeReceiver = receiver
		return false
	})
	returnedReceiver, returnsReceiver := returnedIdentifier(handlerDeclaration)
	if route == nil || handler == nil || !returnsReceiver ||
		routeReceiver != returnedReceiver {
		return nil, nil, errors.New("supported literal route is unavailable")
	}
	return route, handler, nil
}

func exactRequestFields(
	fileSet *token.FileSet,
	file *ast.File,
	source []byte,
) ([]classifiedInventoryFact, error) {
	var structure *ast.StructType
	for _, declaration := range file.Decls {
		general, ok := declaration.(*ast.GenDecl)
		if !ok || general.Tok != token.TYPE {
			continue
		}
		for _, specification := range general.Specs {
			typeSpec, ok := specification.(*ast.TypeSpec)
			if ok && typeSpec.Name.Name == "quoteOrderBody" {
				structure, _ = typeSpec.Type.(*ast.StructType)
			}
		}
	}
	expected := []struct {
		goName   string
		jsonName string
	}{
		{goName: "UnitPriceCents", jsonName: "unit_price_cents"},
		{goName: "Quantity", jsonName: "quantity"},
	}
	if structure == nil || len(structure.Fields.List) != len(expected) {
		return nil, errors.New("supported request structure differs")
	}
	facts := make([]classifiedInventoryFact, 0, len(expected))
	for index, field := range structure.Fields.List {
		if len(field.Names) != 1 || field.Names[0].Name != expected[index].goName ||
			!pointerToIdentifier(field.Type, "int") || field.Tag == nil {
			return nil, errors.New("supported request field differs")
		}
		tag, err := strconv.Unquote(field.Tag.Value)
		if err != nil ||
			reflect.StructTag(tag).Get("json") != expected[index].jsonName {
			return nil, errors.New("supported request JSON tag differs")
		}
		fact, err := publicInterfaceFact(
			fileSet,
			source,
			field,
			goRequestFieldURI,
			expected[index].jsonName,
			"quoteOrderBody",
		)
		if err != nil {
			return nil, err
		}
		facts = append(facts, fact)
	}
	return facts, nil
}

func exactResponseFields(
	fileSet *token.FileSet,
	handler *ast.FuncLit,
	source []byte,
) ([]classifiedInventoryFact, error) {
	wantedStatus := map[string]string{
		"error":       "StatusBadRequest",
		"receipt":     "StatusOK",
		"total_cents": "StatusOK",
	}
	nodes := map[string]*ast.KeyValueExpr{}
	valid := true
	ast.Inspect(handler.Body, func(node ast.Node) bool {
		call, ok := node.(*ast.CallExpr)
		if !ok || !identifierCall(call, "writeJSON") {
			return true
		}
		if len(call.Args) != 3 {
			valid = false
			return false
		}
		status, statusOK := selectorName(call.Args[1], "http")
		literal, literalOK := call.Args[2].(*ast.CompositeLit)
		if !statusOK || !literalOK {
			valid = false
			return false
		}
		for _, element := range literal.Elts {
			pair, pairOK := element.(*ast.KeyValueExpr)
			if !pairOK {
				valid = false
				return false
			}
			name, nameOK := stringLiteral(pair.Key)
			expectedStatus, expected := wantedStatus[name]
			if !nameOK || !expected || status != expectedStatus {
				valid = false
				return false
			}
			if nodes[name] == nil {
				nodes[name] = pair
			}
		}
		return true
	})
	if !valid || len(nodes) != len(wantedStatus) {
		return nil, errors.New("supported response fields differ")
	}
	names := []string{"error", "receipt", "total_cents"}
	facts := make([]classifiedInventoryFact, 0, len(names))
	for _, name := range names {
		fact, err := publicInterfaceFact(
			fileSet,
			source,
			nodes[name],
			goResponseFieldURI,
			name,
			"POST /quote-order",
		)
		if err != nil {
			return nil, err
		}
		facts = append(facts, fact)
	}
	return facts, nil
}

func publicInterfaceFact(
	fileSet *token.FileSet,
	source []byte,
	node ast.Node,
	interfaceURI string,
	name string,
	container any,
) (classifiedInventoryFact, error) {
	return publicInterfaceFactAtPath(
		fileSet,
		source,
		"quote/service.go",
		node,
		interfaceURI,
		name,
		container,
	)
}

func publicInterfaceFactAtPath(
	fileSet *token.FileSet,
	source []byte,
	path string,
	node ast.Node,
	interfaceURI string,
	name string,
	container any,
) (classifiedInventoryFact, error) {
	span, declarationDigest, err := nodeCoordinates(fileSet, node, source)
	if err != nil {
		return classifiedInventoryFact{}, err
	}
	return classifiedInventoryFact{
		kind: "public_interface",
		path: path,
		span: span,
		attributes: map[string]any{
			"interface_kind_uri": interfaceURI,
			"name":               name,
			"container":          container,
			"declaration_digest": digestValue(declarationDigest),
		},
	}, nil
}

func nodeCoordinates(
	fileSet *token.FileSet,
	node ast.Node,
	source []byte,
) (inventorySourceSpan, string, error) {
	if node == nil {
		return inventorySourceSpan{}, "", errors.New("source node is unavailable")
	}
	start := fileSet.PositionFor(node.Pos(), false)
	end := fileSet.PositionFor(node.End(), false)
	if start.Offset < 0 || end.Offset <= start.Offset || end.Offset > len(source) {
		return inventorySourceSpan{}, "", errors.New("source node coordinates are invalid")
	}
	digest := sha256.Sum256(source[start.Offset:end.Offset])
	return inventorySourceSpan{
		startLine:   start.Line,
		startColumn: start.Column,
		endLine:     end.Line,
		endColumn:   end.Column,
	}, hex.EncodeToString(digest[:]), nil
}

func sourceSpanForOffsets(
	source []byte,
	startOffset int,
	endOffset int,
) inventorySourceSpan {
	startLine, startColumn := sourcePosition(source, startOffset)
	endLine, endColumn := sourcePosition(source, endOffset)
	return inventorySourceSpan{
		startLine:   startLine,
		startColumn: startColumn,
		endLine:     endLine,
		endColumn:   endColumn,
	}
}

func sourcePosition(source []byte, offset int) (int, int) {
	line := 1
	column := 1
	for _, value := range source[:offset] {
		if value == '\n' {
			line++
			column = 1
		} else {
			column++
		}
	}
	return line, column
}

func selectorCallReceiver(call *ast.CallExpr, name string) (string, bool) {
	if call == nil {
		return "", false
	}
	selector, ok := call.Fun.(*ast.SelectorExpr)
	if !ok || selector.Sel.Name != name {
		return "", false
	}
	receiver, ok := selector.X.(*ast.Ident)
	if !ok {
		return "", false
	}
	return receiver.Name, true
}

func returnedIdentifier(declaration *ast.FuncDecl) (string, bool) {
	if declaration == nil || declaration.Body == nil ||
		len(declaration.Body.List) == 0 {
		return "", false
	}
	statement, ok := declaration.Body.List[len(declaration.Body.List)-1].(*ast.ReturnStmt)
	if !ok || len(statement.Results) != 1 {
		return "", false
	}
	identifier, ok := statement.Results[0].(*ast.Ident)
	if !ok {
		return "", false
	}
	return identifier.Name, true
}

func identifierCall(call *ast.CallExpr, name string) bool {
	identifier, ok := call.Fun.(*ast.Ident)
	return ok && identifier.Name == name
}

func selectorName(expression ast.Expr, packageName string) (string, bool) {
	selector, ok := expression.(*ast.SelectorExpr)
	if !ok {
		return "", false
	}
	identifier, ok := selector.X.(*ast.Ident)
	if !ok || identifier.Name != packageName {
		return "", false
	}
	return selector.Sel.Name, true
}

func stringLiteral(expression ast.Expr) (string, bool) {
	literal, ok := expression.(*ast.BasicLit)
	if !ok || literal.Kind != token.STRING {
		return "", false
	}
	value, err := strconv.Unquote(literal.Value)
	return value, err == nil
}

func pointerToIdentifier(expression ast.Expr, name string) bool {
	pointer, ok := expression.(*ast.StarExpr)
	if !ok {
		return false
	}
	identifier, ok := pointer.X.(*ast.Ident)
	return ok && identifier.Name == name
}
