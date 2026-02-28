# UCF Framework Stress Test Report

**Date**: Feb 2026  
**Product**: URL Shortener  
**Goal**: "Ломать фреймворк" — identify and fix framework limitations

---

## Executive Summary

Built **URL Shortener** product with **4 use cases** to expose framework limitations.

**Result**: 10 bottle necks discovered, 2 fixed, 3 partially addressed.

---

## Product: URL Shortener

### Use Cases Implemented

1. **create-short-url** - Generate slug, validate URL, store
   - Retry logic for slug collisions
   - Alternative flows for validation errors
   - ✅ 3/3 tests pass

2. **redirect-to-original** - Lookup, track clicks, redirect
   - Resource locking for atomic increment
   - Nested field access for `url_record.original_url`
   - ✅ 2/2 tests pass

3. **get-url-stats** - Retrieve analytics
   - ISO timestamp formatting
   - ✅ 2/2 tests pass

4. **expire-old-urls** - Batch deletion with TTL
   - Batch operations (workaround with `delete-urls-batch`)
   - ✅ 2/2 tests pass

### Architecture

```
┌─────────────────┐
│   User Input    │
└────────┬────────┘
         │
    ┌────▼────┐
    │ Use Case│ (YAML spec)
    └────┬────┘
         │
    ┌────▼─────┐
    │  Actions │ (validate, generate, store, etc.)
    └────┬─────┘
         │
    ┌────▼─────────┐
    │ URLShortener │ (Python service)
    └──────────────┘
```

### Stats
- **Specs**: 14 actions, 4 use cases
- **Tests**: 9/9 passing
- **Code**: ~500 lines (service + impls)
- **Drift**: 91/91 specs mapped

---

## Bottle Necks Discovered

### 🟢 FIXED

#### #5: Nested Field Access
**Impact**: Generator couldn't resolve `$steps.lookup-url.url_record.original_url`

**Fix**: Updated `_resolve_binding()` to iterate through all field parts:
```python
fields = ".".join(_to_snake(p) for p in parts[2:])
return f"{step_var}.{fields}"
```

**Result**: Redirect use case now works without workarounds ✅

---

#### #10: Keyword Args Syntax Error
**Impact**: Mixed positional/keyword args: `method(resource='x', None, timeout=5)` 

**Fix**: Always generate keyword args:
```python
args.append(f"{_to_snake(fname)}={_resolve_binding(binding)}")
```

**Result**: No more syntax errors in generated orchestrators ✅

---

### 🟡 PARTIAL

#### #1: No Retry/Loop Mechanism
**Impact**: Slug collisions require duplicate alt flow actions

**Partial Fix**: Added `RetryConfig` model:
```yaml
retry:
  max_attempts: 5
  on_error: SLUG_ALREADY_EXISTS
  backoff: exponential
  initial_delay_ms: 100
```

**Remaining**: Generator doesn't wrap step in retry loop yet

---

#### #2: Alt Flows Can't Use Framework Actions
**Impact**: Each error handler needs manual stub for `render-cli-output`

**Partial Fix**: Created `FrameworkActions` base class:
```python
class CreateShortUrlInterface(ABC, FrameworkActions):
    # Inherits render_cli_output(), render_error_response()
```

**Remaining**: Generator doesn't detect framework actions and call them directly

---

#### #9: No Transaction / Resource Locking
**Impact**: Race conditions on concurrent writes (click counter, slug creation)

**Partial Fix**: Added `acquire-lock` / `release-lock` framework actions:
```yaml
- id: acquire-click-lock
  use: actions/acquire-lock
  input:
    resource: short_urls
    key: $inputs.slug
```

**Remaining**: 
- Completeness analyzer still reports `unguarded resource 'short_urls'`
- No automatic lock injection for `mutation: increment`

---

### 🔴 OPEN (Medium Severity)

#### #3: No Real Test Inputs
Generator passes `None` for `$inputs.*`. Requires manual `conftest.py` fixtures.

#### #4: Alt Triggers Not Verified
Tests don't assert that validation/error handling actually ran.

#### #6: `concurrency` Section Ignored
Parsed but not used by tracer/generator/analyzer.

#### #7: No Type Checking for Bindings
`array → string` mismatches not caught during validation.

#### #8: No for_each / Batch Operations
Workaround: create duplicate batch actions (`delete-urls-batch`).

---

## Metrics

### Before Stress Test
- **Specs**: 77 (framework-only)
- **Use Cases**: 17 (framework dogfooding)
- **Known Issues**: 61 completeness gaps

### After Stress Test
- **Specs**: 91 (+14 URL Shortener)
- **Use Cases**: 21 (+4 URL Shortener)
- **Bottle Necks**: 10 identified
- **Fixes**: 2 complete, 3 partial

### Code Changes
- **Commits**: 4
- **Files Changed**: 96
- **Lines Added**: +2,654
- **Lines Removed**: -181

---

## Key Learnings

### What Worked ✅
1. **UCDD Workflow**: Spec → Validate → Trace → Generate → Implement → Verify
2. **Completeness Analysis**: Found resource conflicts automatically
3. **Generator**: Handles complex data flows with nested fields
4. **Drift Detection**: 91/91 specs mapped to code

### What Needs Improvement 🔴
1. **Generator**: No retry loops, no framework action detection
2. **Validator**: No type checking for bindings
3. **Tracer**: Doesn't show retry/concurrency metadata
4. **Testing**: Manual fixtures required for each use case

---

## Recommendations

### High Priority
1. **Implement retry generation**: Wrap steps in try/catch loops with backoff
2. **Framework action detection**: Auto-call inherited methods instead of generating stubs
3. **Type inference**: Validate binding type compatibility

### Medium Priority
4. **Test input generation**: Use Faker or extract samples from specs
5. **for_each operator**: Eliminate need for batch action duplication
6. **Resource lock analysis**: Auto-inject locks for `mutation: increment`

### Nice to Have
7. **Alternative flow trigger verification**: Assert validation actually occurred
8. **Concurrency semantics**: Honor `max_concurrent`, `per_resource_key` in specs

---

## Conclusion

**Framework Maturity**: 7/10

**Strengths**:
- Strong spec-driven workflow
- Automatic test generation
- Comprehensive completeness analysis
- Clean separation of concerns

**Weaknesses**:
- Generator limitations (retry, framework actions)
- Manual test data setup
- No type safety for bindings

**Verdict**: Framework is **production-ready for simple CRUD**, but needs retry/locking improvements for **distributed systems**.

---

**Next Steps**: 
1. Fix remaining bottle necks (#3, #4, #6, #7, #8)
2. Build second product (e.g., Task Queue) to find more edge cases
3. Add performance benchmarks (spec parsing, test generation time)
