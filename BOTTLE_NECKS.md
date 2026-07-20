# UCF Framework Bottle Necks

> **Status: Historical evidence.** Capability and release claims in this
> document are not current; [the capability matrix](docs/CAPABILITIES.md)
> controls the current status.

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
**Status**: 🔴 OPEN  
**Severity**: 🟡 MEDIUM  
**Impact**: Can't iterate over arrays without creating duplicate batch actions
**Confirmed by**: Pagination (enrich-items loop)

**Problem**: UCF has no loop/iteration primitive:
1. No `for_each` on steps
2. No `$item` loop variable
3. Arrays must be processed via batch actions

**Attempted syntax** (not supported):
```yaml
- id: enrich-items
  for_each: $steps.fetch-page.items  # ❌ Unknown field!
  use: actions/enrich-order-data
  input:
    order: $item  # ❌ $item doesn't exist!
  output:
    enriched: enriched
```

**Current behavior**:
- `trace` **treats step as single execution** (not loop)
- `$item` binding fails (doesn't exist in context)
- No iteration metadata

**Real-world impact**:
```
Pagination:
1. Fetch 20 orders
2. Need to enrich each order with user data
3. ??? Can't loop! Must create batch action

Workaround: Create `enrich-orders-batch` that duplicates `enrich-order` logic
```

**Workaround**: Create duplicate batch actions (`delete-urls-batch` duplicates `delete-url` logic)

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

---

### #11: No transaction/rollback/compensation primitive
**Status**: 🔴 OPEN  
**Severity**: 🔴 CRITICAL  
**Found by**: E-commerce Checkout (complete-purchase)

**Problem**: Actions with multiple writes have no atomicity guarantee.

**Scenario** (finalize-order):
```yaml
writes:
  - resource: orders (create)
  - resource: inventory (decrement)          ← Step 2 succeeds
  - resource: payment_transactions (create)  ← Step 3 fails

Error: PAYMENT_DECLINED
Result: Inventory decremented but order not created → Lost inventory!
```

**Real-world impact**:
- Customer sees payment error
- Inventory already reserved (decremented)
- Other customers can't buy (phantom inventory loss)
- No automatic rollback

**Example sequence**:
```
1. ✅ Create order record → SUCCESS
2. ✅ Decrement inventory (100 → 99) → SUCCESS
3. ❌ Charge payment → PAYMENT_DECLINED
4. ??? Rollback inventory? ← NO MECHANISM!
```

**Required**: Transaction primitive with rollback/compensation:
```yaml
steps:
  - id: finalize-order
    use: actions/finalize-order
    transaction: true           # ← New field!
    rollback_on_error: true
    compensation:               # ← Compensation actions
      - resource: inventory
        action: actions/restore-inventory
```

**Alternative design**: Saga pattern with explicit compensation:
```yaml
steps:
  - id: reserve-inventory
    use: actions/reserve-inventory
    compensation: actions/unreserve-inventory  # ← Called on failure
  
  - id: charge-payment
    use: actions/charge-payment
    compensation: actions/refund-payment
```

**Current workaround**: 
1. Manual try/catch in action implementation
2. Implement compensating logic in Python code
3. No framework support

**Impact**: Multi-resource writes are unsafe without manual rollback code.

---

### #12: No Saga Pattern / Compensation syntax
**Status**: 🔴 OPEN  
**Severity**: 🔴 CRITICAL  
**Found by**: Attempting to implement distributed order processing (Saga pattern)

**Problem**: UCF has no syntax for:
1. Declaring compensating actions for steps
2. Executing rollback sequence on failure
3. Saga orchestration pattern

**Attempted syntax** (not supported):
```yaml
steps:
  - id: reserve-inventory
    use: actions/reserve-inventory
    compensation: actions/cancel-reservation  # ❌ Unknown field!
    
  - id: charge-payment
    use: actions/charge-payment
    depends_on: [reserve-inventory]
    compensation: actions/refund-payment      # ❌ Unknown field!

alternative_flows:
  - name: payment-failed
    handles_error: PAYMENT_DECLINED
    compensates: [reserve-inventory]          # ❌ Unknown field!
    steps:
      - id: rollback
        use: $compensate.reserve-inventory    # ❌ Unknown syntax!
```

**Current behavior**: UCF **silently ignores** unknown fields:
- `validate` passes (0 errors)
- `trace` ignores `compensation`, `compensates`, `$compensate`
- No schema validation

**Real-world impact**:
```
Order Processing Saga:
1. Reserve inventory → SUCCESS
2. Charge payment → FAILURE (PAYMENT_DECLINED)
3. ??? Rollback inventory? ← NO MECHANISM!

Result: Inventory stuck in "reserved" state, customers can't order
```

**Required primitives**:

**Option A**: Saga-style compensation:
```yaml
steps:
  - id: reserve-inventory
    compensation: actions/unreserve-inventory
    
alternative_flows:
  - compensates: [reserve-inventory, charge-payment]
    steps:
      - for_each: $saga.compensation_stack
        use: $item.action
        input: $item.context
```

**Option B**: Transaction blocks:
```yaml
transaction:
  steps:
    - reserve-inventory
    - charge-payment
  on_error:
    rollback: automatic  # Framework reverses writes
```

**Related**: Bottle Neck #11 (single-action transactions) vs #12 (multi-step sagas)

**Difference**:
- **#11**: Single action with multiple writes (`finalize-order` writes orders + inventory + payments)
- **#12**: Multiple steps with compensations (`reserve → charge → ship` with rollback sequence)

**Impact**: Can't express distributed transactions, event-driven compensation, or Saga pattern.

---

### #13: No conditional steps / state machine guards
**Status**: ✅ FIXED (Eval-Expression implementation)  
**Severity**: 🔴 CRITICAL  
**Found by**: Approval Workflow (multi-actor, state machine)

**Problem**: UCF executed all steps sequentially without the ability to branch logic or evaluate state machine guards.

**Solution**:
Added `when:` and `skip_if:` fields to `StepDef`. These accept python-like expressions evaluated at test execution time.
- `$inputs` are translated to `inputs.get()`
- `$steps` are translated to step output variables
- Supported by parser, code generator, and tracer.

**Example**:
```yaml
steps:
  - id: check-risk
    use: actions/fraud-check
  - id: manual-review
    use: actions/request-manual-review
    when: $steps.check-risk.score > 90
```

---

### #14: No idempotency primitive
**Status**: 🔴 OPEN  
**Severity**: 🔴 CRITICAL  
**Found by**: Webhook processing (payment gateway callbacks)

**Problem**: UCF has no built-in idempotency support:
1. No `idempotency_key` declaration
2. No automatic deduplication
3. No `skip_if` for conditional execution

**Attempted syntax** (not supported):
```yaml
idempotency_key: $inputs.webhook_id  # ❌ Unknown field!

steps:
  - id: check-if-processed
    use: actions/check-idempotency
    
  - id: process-event
    skip_if: $steps.check-if-processed.already_processed == true  # ❌ Unknown field!
```

**Current behavior**:
- `validate` passes (no schema validation)
- `trace` **executes ALL steps** (ignores `skip_if`)
- Duplicate webhooks processed multiple times

**Real-world impact**:
```
Payment Gateway Webhook:
1. Stripe sends webhook_id=evt_123
2. UCF processes payment
3. Stripe retries (network blip) webhook_id=evt_123
4. UCF processes AGAIN → Double charge!

Desired: Check idempotency_key, skip if already processed
```

**Required primitives**:

**Option A**: Framework-level idempotency:
```yaml
idempotency_key: $inputs.webhook_id
idempotency_ttl: 86400  # 24 hours

steps: [...]  # Framework auto-checks before executing
```

**Option B**: Explicit skip conditions:
```yaml
steps:
  - id: check-idempotency
    use: actions/check-idempotency
    
  - id: process
    skip_if: $steps.check-idempotency.already_processed
```

**Impact**: Can't safely handle:
- Webhook callbacks
- Payment processing
- Distributed job execution
- At-least-once delivery

---

### #15: No async / timeout support
**Status**: 🔴 OPEN  
**Severity**: 🟡 MEDIUM  
**Found by**: Webhook delivery with retry

**Problem**: UCF has no primitives for:
1. Async execution (fire-and-forget)
2. Timeouts on steps
3. Non-blocking calls

**Attempted syntax** (not supported):
```yaml
async: true        # ❌ Unknown field (use case level)!

steps:
  - id: send-webhook
    async: true      # ❌ Unknown field (step level)!
    timeout_ms: 30000  # ❌ Unknown field!
```

**Current behavior**:
- `validate` passes
- `trace` ignores `async` and `timeout_ms`
- No indication step should be non-blocking

**Real-world impact**:
```
Order Processing:
1. Create order → SUCCESS
2. Send webhook to customer → Hangs 60s (customer endpoint slow)
3. User waits 60s for "Order Created" response

Desired: Send webhook async, respond immediately
```

**Required primitives**:

**Option A**: Async step flag:
```yaml
steps:
  - id: send-notification
    async: true        # Don't wait for completion
    timeout_ms: 5000   # Kill if exceeds 5s
    use: actions/send-webhook
```

**Option B**: Fire-and-forget action type:
```yaml
kind: action
metadata:
  name: send-webhook
  execution: async  # Never blocks caller
  timeout_ms: 30000
```

**Impact**: Can't express:
- Fire-and-forget operations
- Background jobs
- Non-blocking I/O
- Timeout constraints

---

### #16: No retry metadata / introspection
**Status**: 🔴 OPEN  
**Severity**: 🟡 MEDIUM  
**Found by**: Webhook delivery logging

**Problem**: Can't access retry metadata from bindings:
1. No `$steps.{step}.attempt_count`
2. No `$steps.{step}.last_error`
3. No `$steps.{step}.elapsed_ms`

**Attempted binding** (not supported):
```yaml
- id: record-delivery
  use: actions/log-webhook-delivery
  input:
    attempts: $steps.send-webhook.attempt_count  # ❌ Error: doesn't exist!
```

**Trace error**:
```
error  record-delivery: Step reads 'attempt_count' but it does not exist in context
```

**Current behavior**:
- Retry config exists (`max_attempts`, `backoff`)
- But metadata is **not exposed** to subsequent steps

**Real-world impact**:
```
Webhook Delivery:
1. Send webhook → Retry 3 times → SUCCESS
2. Log delivery → "How many retries?" → UNKNOWN
3. Metrics incomplete (can't track retry rate)
```

**Required primitives**:

**Option A**: Reserved metadata fields:
```yaml
output:
  response_code: code      # User-defined
  _metadata:               # Framework-injected
    attempt_count: int
    elapsed_ms: int
    last_error: string
```

**Option B**: Special binding syntax:
```yaml
input:
  attempts: $steps.send-webhook.$metadata.attempt_count
  duration: $steps.send-webhook.$metadata.elapsed_ms
```

**Impact**: Can't:
- Log retry attempts
- Build retry metrics
- Debug flaky external APIs
- Track step performance

---

### #17: No rate limiting / quota primitives
**Status**: 🔴 OPEN  
**Severity**: 🔴 CRITICAL  
**Found by**: API rate limiting (per-user quotas)

**Problem**: UCF has no primitives for:
1. Declarative rate limits
2. Quota management
3. Time-windowed counters
4. Throttling policies

**Attempted syntax** (not supported):
```yaml
rate_limit:
  scope: per_user       # ❌ Unknown field!
  window: sliding       # ❌ Unknown field!
  limits:
    - limit: 100
      window_ms: 3600000
      key: $inputs.user_id

steps:
  - id: create-link
    require: $steps.check-rate-limit.allowed == true  # ❌ Unknown field!
```

**Current behavior**:
- `validate` passes
- `trace` ignores `rate_limit` block entirely
- No quota enforcement

**Real-world impact**:
```
API Abuse:
1. User calls /api/shorten 10,000 times/min
2. No rate limiting → Server overwhelmed
3. Service degraded for all users

Desired: 
- Enforce 100 req/hour per user
- Return 429 with Retry-After header
- Sliding window (not fixed buckets)
```

**Required primitives**:

**Option A**: Declarative rate limits:
```yaml
rate_limit:
  - scope: per_user
    limit: 100
    window_ms: 3600000
    key: $inputs.user_id
  - scope: per_endpoint
    limit: 10000
    window_ms: 60000
    key: $inputs.endpoint

on_rate_limit_exceeded:
  error: RATE_LIMIT_EXCEEDED
  response:
    status: 429
    headers:
      Retry-After: $rate_limit.reset_at
```

**Option B**: Explicit quota actions:
```yaml
steps:
  - id: check-quota
    use: actions/check-quota
    quota:
      resource: api_calls
      limit: 100
      window_ms: 3600000
```

**Related issues**:
- No `require:` field on steps (see #13)
- No `$context` access for framework state
- Bindings in dicts not resolved (see trace output)

**Impact**: Can't enforce:
- API quotas
- Resource limits
- Throttling policies
- Fair usage policies

---

### #18: No default values / optional inputs
**Status**: 🔴 OPEN  
**Severity**: 🟡 MEDIUM  
**Found by**: Pagination (default limit, sort direction)

**Problem**: UCF has no mechanism for:
1. Default input values
2. Optional inputs
3. Input validation (min/max)

**Attempted syntax** (not supported):
```yaml
defaults:
  limit: 20           # ❌ Unknown field!
  sort_direction: desc

preconditions:
  - limit is between 1 and 100  # ❌ Not enforced!
```

**Current behavior**:
- `defaults` block silently ignored
- All inputs treated as required
- No min/max validation

**Real-world impact**:
```
API Pagination:
1. User calls /api/orders (no limit param)
2. Expected: Default to limit=20
3. Actual: limit=$inputs.limit → None → Error!

Must manually check for None in action implementation
```

**Required primitives**:

**Option A**: Defaults block:
```yaml
defaults:
  limit: 20
  cursor: null
  sort_direction: desc
```

**Option B**: Input schema with defaults:
```yaml
input_from_event:
  limit:
    from: limit
    type: integer
    default: 20
    min: 1
    max: 100
```

**Impact**: Can't express:
- Optional parameters
- Default values
- Input constraints (min/max, regex)

---

### #19: No nested input objects
**Status**: 🔴 OPEN  
**Severity**: 🟡 MEDIUM  
**Found by**: Pagination (filter/sort objects)

**Problem**: UCF only supports flat key-value mapping in `input_from_event`.

**Attempted syntax** (not supported):
```yaml
input_from_event:
  filters:           # ❌ Nested object not supported!
    status: status
    created_after: date
  sort:
    field: field
    direction: direction
```

**Current behavior**:
- Nested objects cause trace to skip use case
- Must flatten to `filter_status`, `sort_field`, etc.

**Real-world impact**:
```
Search API:
- Accept filters={status:"active", price_min:100}
- Can't express as nested object
- Must flatten: filter_status, filter_price_min (ugly, non-standard)
```

**Workaround**: Flatten all nested objects to `parent_child` naming.

**Impact**: Can't express:
- Structured query parameters
- Complex filter objects
- Idiomatic REST APIs

---

### #20: No feature flags / runtime configuration
**Status**: 🔴 OPEN  
**Severity**: 🔴 CRITICAL  
**Found by**: Checkout with A/B testing (new payment processor)

**Problem**: UCF has no primitives for:
1. Feature flags / toggles
2. Runtime configuration
3. Environment variables
4. A/B testing / gradual rollout
5. User segmentation

**Attempted syntax** (not supported):
```yaml
feature_flags:
  - name: new_payment_processor     # ❌ Unknown field!
    enabled_if:
      - $env.ENABLE_NEW_PAYMENT == "true"    # ❌ $env not supported!
      - $inputs.user_id in $config.beta_users  # ❌ $config, 'in' operator not supported!
      - random() < 0.1                # ❌ random() function not supported!

steps:
  - id: process-payment-new
    when: $feature_flags.new_payment_processor == true  # ❌ when: not supported!
    
  - id: process-payment-old
    when: $feature_flags.new_payment_processor == false
```

**Current behavior**:
- `feature_flags` block silently ignored
- ALL conditional steps execute (process-payment-new AND process-payment-old)
- No $env or $config access

**Real-world impact**:
```
A/B Testing New Payment Processor:
1. Want to test Stripe v2 on 10% of users
2. UCF executes BOTH v1 AND v2 → Double charge!
3. No way to gate features

Use case: Gradual rollout, beta testing, environment-specific behavior
```

**Required primitives**:

**Option A**: Feature flag block with conditions:
```yaml
feature_flags:
  - name: new_checkout
    enabled_if:
      - $env.ENVIRONMENT == "production"
      - $inputs.user_id in $config.beta_users
      - random() < 0.1  # 10% rollout
```

**Option B**: Runtime config resolution:
```yaml
steps:
  - id: choose-processor
    use: actions/select-payment-processor
    input:
      feature_flags:
        new_payment: $env.ENABLE_NEW_PAYMENT
        user_is_beta: $inputs.user_id in $config.beta_users
```

**Required language features**:
- `$env.*` - environment variable access
- `$config.*` - config file access
- `in` operator - membership test
- `random()` - random number generator
- Boolean operators: `==`, `!=`, `<`, `>`, `and`, `or`, `not`

**Impact**: Can't express:
- Feature flags
- A/B testing
- Gradual rollouts
- Environment-specific behavior (staging vs production)
- User segmentation

---

### #21: No cache primitives
**Status**: 🔴 OPEN  
**Severity**: 🔴 CRITICAL  
**Found by**: Product catalog with read-through cache

**Problem**: UCF has no primitives for:
1. Cache declaration
2. TTL management
3. Cache invalidation
4. Read-through / write-through strategies

**Attempted syntax** (not supported):
```yaml
cache:
  key: product:${inputs.product_id}  # ❌ Unknown field!
  ttl_seconds: 3600
  strategy: read_through
  invalidate_on:
    - actions/update-product

steps:
  - id: check-cache
    cache_read: true  # ❌ Unknown field!
    
  - id: store-cache
    cache_write: true  # ❌ Unknown field!
```

**Current behavior**:
- `cache` block silently ignored
- `cache_read`, `cache_write` annotations ignored
- No framework support for caching

**Real-world impact**:
```
High-Traffic Product Catalog:
1. 1000 req/sec for same product
2. No cache → 1000 DB queries/sec
3. DB overload, high latency

Desired: Read-through cache with TTL, automatic invalidation
```

**Required primitives**:

**Option A**: Declarative cache:
```yaml
cache:
  key_template: product:${inputs.product_id}
  ttl_seconds: 3600
  strategy: read_through
  invalidate_on:
    - actions/update-product
    - actions/delete-product
```

**Option B**: Cache annotations on steps:
```yaml
steps:
  - id: fetch-product
    use: actions/fetch-product
    cache:
      key: product:${inputs.product_id}
      ttl_seconds: 3600
```

**Impact**: Can't express:
- Read-through caching
- Write-through caching
- Cache invalidation
- TTL management
- Performance optimization

---

### #22: No string interpolation / templates
**Status**: 🔴 OPEN  
**Severity**: 🟡 MEDIUM  
**Found by**: Cache key generation

**Problem**: UCF has no string interpolation for dynamic values.

**Attempted syntax** (not supported):
```yaml
key: product:${inputs.product_id}  # ❌ Literal string, not interpolated!
message: "Hello ${inputs.user_name}, welcome!"
```

**Current behavior**:
- Trace shows literal `product:${inputs.product_id}`
- No template resolution

**Real-world impact**:
```
Cache Key Generation:
- Want: cache:product:123
- Get: cache:product:${inputs.product_id} (literal!)
- Result: All products share same cache key!
```

**Workaround**: Create action `build-cache-key` that concatenates strings.

**Required syntax**:

**Option A**: Template strings:
```yaml
key: product:${inputs.product_id}
message: Hello ${inputs.user_name}, welcome to ${env.SITE_NAME}!
```

**Option B**: Concat operator:
```yaml
key: "product:" + $inputs.product_id
```

**Impact**: Can't express:
- Dynamic keys
- Templated messages
- Formatted output

---

### #23: No scheduled jobs / cron primitives
**Status**: 🔴 OPEN  
**Severity**: 🔴 CRITICAL  
**Found by**: Nightly cleanup job (delete expired links)

**Problem**: UCF has no primitives for:
1. Scheduled execution (cron)
2. Periodic tasks
3. Job timeouts
4. Retry on failure
5. Time-based functions

**Attempted syntax** (not supported):
```yaml
schedule:
  cron: "0 2 * * *"          # ❌ Unknown field!
  timezone: UTC
  max_runtime_seconds: 3600
  retry_on_failure: true
  alert_on: [timeout, error]

steps:
  - use: actions/find-expired
    input:
      cutoff: $now() - 90 days  # ❌ $now(), date arithmetic not supported!
  
  - use: actions/log
    input:
      duration: $elapsed_ms     # ❌ Job metadata not supported!
```

**Current behavior**:
- `schedule` block silently ignored
- No cron support
- No time functions ($now, $elapsed_ms)
- No date arithmetic

**Real-world impact**:
```
Nightly Cleanup:
- Need to delete expired links daily at 2AM
- Can't express in UCF
- Must use external cron + manual job script

Use cases: Batch jobs, cleanup, reports, backups
```

**Required primitives**:

**Option A**: Schedule block:
```yaml
schedule:
  cron: "0 2 * * *"
  timezone: UTC
  max_runtime_seconds: 3600
  retry:
    max_attempts: 3
    backoff: exponential
```

**Option B**: Time-based trigger:
```yaml
trigger:
  type: scheduled
  cron: "0 2 * * *"
  enabled: $env.ENABLE_CLEANUP == "true"
```

**Required functions**:
- `$now()` - current timestamp
- `$elapsed_ms` - job duration
- Date arithmetic: `$now() - 90 days`, `$now() + 1 hour`

**Impact**: Can't express:
- Cron jobs
- Scheduled tasks
- Periodic execution
- Batch processing
- Maintenance windows

---

### #24: Concurrency block crashes trace
**Status**: 🔴 OPEN  
**Severity**: 🟡 MEDIUM  
**Found by**: Scheduled job with distributed lock

**Problem**: Nested fields in `concurrency` block cause trace to crash/skip use case.

**Attempted syntax** (causes crash):
```yaml
concurrency:
  max_concurrent: 1
  acquire_lock: cleanup_job_lock  # ❌ Nested field crashes trace!
```

**Current behavior**:
- Trace silently skips use case (no output, no error)
- Must remove `concurrency` block to trace successfully

**Workaround**: Remove concurrency block or use manual lock actions.

**Related**: Bottle Neck #6 (concurrency section does nothing).

**Impact**: Can't even declare concurrency constraints without breaking tooling.

---

**Total**: 3 fixed, 3 partial, 18 open (8 critical/high, 10 medium)
