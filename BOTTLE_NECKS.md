# UCF Framework Bottle Necks

Found by implementing **URL Shortener** product (Feb 2026).

## 🟢 FIXED

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
**Severity**: 🔴 High  
**Impact**: Can't handle transient failures or collisions

**Scenario**: URL Shortener slug collision
```yaml
steps:
  - id: generate-slug
    use: actions/generate-slug
  
  - id: check-exists
    use: actions/check-slug-exists
    # ❌ If exists, need to retry generate-slug
    # But no way to loop back!
```

**Workaround**: Create separate `retry-generate` action in alt flow (duplicates logic)

**Required**: `retry:` or `loop:` directive in steps

---

### #2: Alternative flows can't use framework actions
**Severity**: 🔴 High  
**Impact**: Can't reuse `render-cli-output`, `render-http-response` in errors

**Scenario**:
```yaml
alternative_flows:
  - name: invalid-url
    steps:
      - id: return-error
        use: actions/render-cli-output  # ❌ Generates action_return_error()
        # Should call framework render method!
```

**Problem**: Generator treats *all* actions as "to be implemented", even framework-provided ones

**Fix needed**: Mark certain actions as `framework: true` in metadata

---

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
**Severity**: 🟡 Medium  
**Impact**: Generated tests have syntax errors

**Generated**:
```python
action_acquire_click_lock(resource='short_urls', None, timeout=5000)
#                                                ^^^^ SyntaxError
```

**Fix needed**: Always generate keyword args when mixing with positional `None`

---

## Summary

| ID | Issue | Severity | Status |
|----|-------|----------|--------|
| #1 | No retry/loop | 🔴 High | Open |
| #2 | Alt flows can't use framework actions | 🔴 High | Open |
| #3 | No real test inputs | 🟡 Medium | Open |
| #4 | Alt triggers not verified | 🟡 Medium | Open |
| #5 | Nested field access | 🟢 Low | ✅ Fixed |
| #6 | `concurrency` ignored | 🟡 Medium | Open |
| #7 | No type checking | 🟡 Medium | Open |
| #8 | No for_each | 🟡 Medium | Open |
| #9 | No locking | 🔴 Critical | Partial (POC done) |
| #10 | Bad arg generation | 🟡 Medium | Open |

**Total**: 1 fixed, 9 open (3 critical/high, 6 medium)
