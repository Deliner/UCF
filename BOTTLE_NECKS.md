# UCF Framework Bottle Necks

Found by implementing **URL Shortener** product (Feb 2026).

## 🟢 FIXED

### #2: Alternative flows can't use framework actions
**Status**: ✅ PARTIALLY FIXED with `FrameworkActions` base class

**Problem**: Generator treated *all* actions as "to be implemented", even framework-provided ones like `render-cli-output`

**Solution**: 
1. Created `FrameworkActions` base class with framework methods:
   - `render_error_response()`
   - `render_cli_output()`
   - `render_http_response()`
2. Updated interface template to inherit from `FrameworkActions`
3. Impl classes can now call `self.render_cli_output()` directly

**Before**:
```python
# Generated orchestrator
def test_invalid_url(uc):
    uc.action_return_error(...)  # ❌ Not implemented!

# Impl needed manual stub
def action_return_error(self, data, format):
    pass  # Stub
```

**After**:
```python
# Manual orchestrator (generator not yet updated)
def test_invalid_url(uc):
    uc.render_cli_output(...)  # ✅ Framework method!

# No stub needed in impl
```

**Remaining work**: Update orchestrator generator to detect framework actions and call them directly

---

### #5: Nested field access in generator
**Status**: ✅ FIXED in `pytest_plugin.py`

**Problem**: Generator couldn't resolve nested fields like `$steps.lookup-url.url_record.original_url`

**Before**:
```python
# Generator produced:
redirect(lookup_url.url_record)  # Wrong! Whole object
```

**After**:
```python
# Generator now produces:
redirect(lookup_url.url_record.original_url)  # Correct! Nested field
```

**Fix**: Updated `_resolve_binding()` to iterate through all parts: `".".join(_to_snake(p) for p in parts[2:])`

---

## 🔴 OPEN

### #1: No retry/loop mechanism
**Status**: 🟡 PARTIAL (model added, generator not yet updated)

**Problem**: Can't handle transient failures or collisions without duplicating steps in alt flows

**Solution Design**: Added `retry` config to `StepDef`:
```yaml
steps:
  - id: generate-slug
    use: actions/generate-slug
    retry:
      max_attempts: 5
      on_error: SLUG_ALREADY_EXISTS
      backoff: exponential
      initial_delay_ms: 100
```

**Model Added**:
```python
class RetryConfig(BaseModel):
    max_attempts: int = Field(ge=1, le=100)
    on_error: str | list[str]  # Error code(s) that trigger retry
    backoff: Literal["constant", "linear", "exponential"] = "constant"
    initial_delay_ms: int = Field(default=1000, ge=0)
```

**Before** (workaround):
```yaml
alternative_flows:
  - name: slug-collision
    steps:
      - id: retry-generate
        use: actions/generate-slug  # ❌ Duplicates main flow logic
```

**After** (desired):
```python
# Generated orchestrator should wrap step in retry loop
for attempt in range(1, 6):  # max_attempts=5
    try:
        generate_slug = uc.action_generate_slug(length=8)
        break
    except SlugAlreadyExistsError:
        if attempt == 5:
            raise MaxRetriesExceededError()
        time.sleep(0.1 * (2 ** (attempt - 1)))  # exponential backoff
```

**Remaining Work**:
1. ✅ Model updated with `RetryConfig`
2. ✅ Validator accepts `retry` in YAML
3. ⏳ Tracer should show retry metadata
4. ⏳ Generator should wrap step in retry loop
5. ⏳ Completeness analyzer should verify error codes match


### #3: Generator doesn't generate real test inputs
**Severity**: 🟡 Medium  
**Impact**: Tests pass `None` for `$inputs.*`, requiring manual fixtures

**Generated**:
```python
def test_create_short_url(uc):
    validate = uc.action_validate_url(None)  # ❌ None instead of real URL
```

**Workaround**: Manual `conftest.py` with monkey-patching for every use case

**Fix needed**: Generator should extract sample inputs from spec `input:` sections or use faker

---

### #4: Alternative flow triggers not verified
**Severity**: 🟡 Medium  
**Impact**: Tests don't assert that validation/error handling actually occurred

**Generated**:
```python
def test_invalid_url(uc):
    action_return_error(data={...})  # ❌ No assertion that URL was validated!
```

**Fix needed**: Generator should add `assert uc._validation_called` or similar

---

### #6: `concurrency` section does nothing
**Severity**: 🟡 Medium  
**Impact**: Concurrent access patterns documented but not enforced

**Example**:
```yaml
concurrency:
  max_concurrent: 1000
  per_resource_key: true  # Multiple requests to same slug must serialize
```

**Current state**: Parsed but ignored by tracer, generator, completeness analyzer

---

### #7: No type checking for bindings
**Severity**: 🟡 Medium  
**Impact**: Type mismatches (array → string) not caught during validation

**Scenario**:
```yaml
- id: find-expired
  output:
    expired_slugs: expired_slugs  # array

- id: delete
  use: actions/delete-url  # expects single slug
  input:
    slug: $steps.find-expired.expired_slugs  # ❌ array → string
```

**Both `validate` and `trace` pass!** Type error only discovered at runtime.

**Fix needed**: Type inference system for outputs + validation of binding type compatibility

---

### #8: No for_each / batch operations
**Severity**: 🟡 Medium  
**Impact**: Can't iterate over arrays without creating duplicate batch actions

**Desired**:
```yaml
- id: delete-each
  use: actions/delete-url
  for_each: $steps.find-expired.expired_slugs
  input:
    slug: $item
```

**Workaround**: Create `delete-urls-batch` action (duplicates `delete-url` logic)

---

### #9: No transaction / resource locking
**Severity**: 🔴 CRITICAL  
**Impact**: Race conditions in concurrent writes to same resource

**Found by**: `ucf completeness` → Resource Conflict Coverage

**Scenario**:
```
Request A: increment_clicks("abc") → read count=5
Request B: increment_clicks("abc") → read count=5
Request A: write count=6
Request B: write count=6  ← LOST UPDATE! Should be 7
```

**Proof of concept**: Added `acquire-lock` / `release-lock` framework actions
```yaml
steps:
  - id: acquire-click-lock
    use: actions/acquire-lock
    input:
      resource: short_urls
      key: $inputs.slug
  
  - id: increment-clicks
    use: actions/increment-click-count
  
  - id: release-click-lock
    use: actions/release-lock
```

**Problem**: Manual locking is verbose and error-prone. Need automatic critical section detection.

**Fix needed**:
1. ✅ Framework actions for lock/unlock (done)
2. Analyzer to detect unguarded resource writes
3. Generator to auto-inject locks when `writes.mutation: increment`

---

### #10: Generator mixes positional & keyword args incorrectly
**Status**: ✅ FIXED in `pytest_plugin.py`

**Problem**: Generator mixed positional and keyword args, causing syntax errors

**Before**:
```python
action_acquire_click_lock(resource='short_urls', None, timeout=5000)
#                                                ^^^^ SyntaxError
```

**After**:
```python
action_acquire_click_lock(resource='short_urls', key=None, timeout=5000)
#                                                ^^^^^^^^ Correct!
```

**Fix**: Updated `_build_step_args()` to always generate keyword args:
```python
elif isinstance(binding, str) and binding.startswith("$"):
    args.append(f"{_to_snake(fname)}={_resolve_binding(binding)}")
```

---

## Summary

| ID | Issue | Severity | Status |
|----|-------|----------|--------|
| #1 | No retry/loop | 🔴 High | 🟡 Partial (model added) |
| #2 | Alt flows can't use framework actions | 🔴 High | 🟡 Partial (base class done) |
| #3 | No real test inputs | 🟡 Medium | Open |
| #4 | Alt triggers not verified | 🟡 Medium | Open |
| #5 | Nested field access | 🟢 Low | ✅ Fixed |
| #6 | `concurrency` ignored | 🟡 Medium | Open |
| #7 | No type checking | 🟡 Medium | Open |
| #8 | No for_each | 🟡 Medium | Open |
| #9 | No locking | 🔴 Critical | 🟡 Partial (POC done) |
| #10 | Bad arg generation | 🟡 Medium | ✅ Fixed |

**Total**: 2 fixed, 3 partial, 5 open (0 critical/high, 5 medium)
