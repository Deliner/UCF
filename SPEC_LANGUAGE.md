# UCF Spec Language: 6 Primitives

> **Current status — source declarations, not an execution IR.** See
> [docs/CAPABILITIES.md](docs/CAPABILITIES.md) for the canonical implemented,
> experimental, and planned support matrix. Parser acceptance records declared
> intent and does not prove transport execution, invariant checking, or formal
> verification.

The current UCF source model has six YAML document kinds with `kind`,
`metadata`, and kind-specific fields. The generated JSON Schema and parser are
the authority for accepted input. The shapes and examples below are
illustrative declarations; fields without an executable consumer named in the
capability matrix remain declaration-only.

---

## 1. Action

An **action** declares a logical operation and may record intended HTTP, gRPC,
GraphQL, UI, CLI, or Kafka bindings. The current core can retain selected
binding shapes, but it does not execute those transports.

### Illustrative source shape

```yaml
kind: action
metadata:
  name: <kebab-case identifier>
  version: <semver>
  owner: <team or person>

platform:
  http:
    method: POST | GET | PUT | PATCH | DELETE
    path: /resource/{param}
  grpc:
    service: ServiceName
    method: MethodName
    proto: path/to/file.proto
  graphql:
    operation: mutation | query
    name: operationName
  ui:
    steps:
      - click: <selector or label>
      - fill: <selector or label>
        value: <value expression>
      - assert: <condition>
  cli:
    command: <shell command template>
    exit_code: 0
  kafka:
    topic: <topic name>

input:
  field_name:
    type: string | integer | number | boolean | array | object
    required: true | false
    format: uuid | email | iso8601 | uri
    min: <number>
    max: <number>
    enum: [value1, value2]

output:
  field_name:
    type: string | integer | number | boolean | array | object

errors:
  - status: <http status or error code>
    code: <application error code>
    condition: <when this error occurs>

reads:
  - resource: <entity name>
    fields: [field1, field2]

writes:
  - resource: <entity name>
    mutation: create | set | increment | decrement | append | delete
    by: <value expression>

preconditions:
  - <condition expression>

postconditions:
  - <condition expression>

emits:
  - event: <event name>
```

### Example: `add-to-cart` — HTTP declaration only

```yaml
kind: action
metadata:
  name: add-to-cart
  version: 1.0.0
  owner: commerce-team

platform:
  http:
    method: POST
    path: /carts/{cart_id}/items

input:
  cart_id:
    type: string
    required: true
    format: uuid
  product_id:
    type: string
    required: true
    format: uuid
  quantity:
    type: integer
    required: true
    min: 1
    max: 99

output:
  cart_id:
    type: string
  item_id:
    type: string
  product_id:
    type: string
  quantity:
    type: integer
  unit_price:
    type: number
  total_items:
    type: integer

errors:
  - status: 404
    code: PRODUCT_NOT_FOUND
    condition: product with given product_id does not exist
  - status: 409
    code: OUT_OF_STOCK
    condition: available inventory for product_id is less than requested quantity
  - status: 422
    code: CART_LIMIT_EXCEEDED
    condition: total_items would exceed 50

reads:
  - resource: product
    fields: [id, price, inventory_count]
  - resource: cart
    fields: [id, items, total_items]

writes:
  - resource: cart_item
    mutation: create
    by: product_id
  - resource: cart
    mutation: increment
    by: quantity

preconditions:
  - product.inventory_count >= quantity
  - cart.total_items + quantity <= 50

postconditions:
  - cart.total_items == $old.cart.total_items + quantity
  - cart_item exists with product_id and quantity

emits:
  - event: item-added-to-cart
```

### Example: `add-to-cart` — gRPC declaration only

```yaml
kind: action
metadata:
  name: add-to-cart
  version: 1.0.0
  owner: commerce-team

platform:
  grpc:
    service: CartService
    method: AddItem
    proto: proto/cart/v1/cart_service.proto

input:
  cart_id:
    type: string
    required: true
    format: uuid
  product_id:
    type: string
    required: true
    format: uuid
  quantity:
    type: integer
    required: true
    min: 1
    max: 99

output:
  cart_id:
    type: string
  item_id:
    type: string
  product_id:
    type: string
  quantity:
    type: integer
  unit_price:
    type: number
  total_items:
    type: integer

errors:
  - status: NOT_FOUND
    code: PRODUCT_NOT_FOUND
    condition: product with given product_id does not exist
  - status: FAILED_PRECONDITION
    code: OUT_OF_STOCK
    condition: available inventory for product_id is less than requested quantity

reads:
  - resource: product
    fields: [id, price, inventory_count]
  - resource: cart
    fields: [id, items, total_items]

writes:
  - resource: cart_item
    mutation: create
    by: product_id
  - resource: cart
    mutation: increment
    by: quantity

preconditions:
  - product.inventory_count >= quantity
  - cart.total_items + quantity <= 50

postconditions:
  - cart.total_items == $old.cart.total_items + quantity
  - cart_item exists with product_id and quantity

emits:
  - event: item-added-to-cart
```

### Example: `add-to-cart` — UI declaration only

```yaml
kind: action
metadata:
  name: add-to-cart
  version: 1.0.0
  owner: commerce-team

platform:
  ui:
    steps:
      - click: "[data-testid='product-{product_id}']"
      - fill: "[data-testid='quantity-input']"
        value: $inputs.quantity
      - click: "[data-testid='add-to-cart-button']"
      - assert: "[data-testid='cart-count']" contains $steps.add-to-cart.total_items

input:
  product_id:
    type: string
    required: true
    format: uuid
  quantity:
    type: integer
    required: true
    min: 1
    max: 99

output:
  total_items:
    type: integer
  confirmation_visible:
    type: boolean

errors:
  - status: ui_error
    code: OUT_OF_STOCK_BANNER
    condition: banner with text "Out of stock" is displayed

reads:
  - resource: product
    fields: [id, price, inventory_count]

writes:
  - resource: cart_item
    mutation: create
    by: product_id
  - resource: cart
    mutation: increment
    by: quantity

preconditions:
  - product page for product_id is loaded

postconditions:
  - confirmation_visible == true
  - cart badge shows updated total_items

emits:
  - event: item-added-to-cart
```

---

## 2. Event

An **event** declares an asynchronous fact and its intended delivery metadata.
The current source model does not deliver events or activate event-driven use
cases at runtime.

### Illustrative source shape

```yaml
kind: event
metadata:
  name: <kebab-case identifier>
  version: <semver>
  owner: <team or person>

trigger:
  after: <action name that produces this event>

payload:
  field_name:
    type: string | integer | number | boolean | array | object
    format: uuid | email | iso8601

delivery:
  - channel: websocket | push-notification | internal | email | sms
    condition: <when to deliver via this channel>
```

### Example: `message-created` — declaration only

```yaml
kind: event
metadata:
  name: message-created
  version: 1.0.0
  owner: messaging-team

trigger:
  after: send-message

payload:
  message_id:
    type: string
    format: uuid
  conversation_id:
    type: string
    format: uuid
  sender_id:
    type: string
    format: uuid
  recipient_id:
    type: string
    format: uuid
  body:
    type: string
  sent_at:
    type: string
    format: iso8601

delivery:
  - channel: websocket
    condition: recipient is currently connected
  - channel: push-notification
    condition: recipient is not connected and has push enabled
  - channel: internal
    condition: always
```

---

## 3. Component

A **component** is a reusable block of steps — the analog of a function.
Use cases declare which components they require, and components inject data into the use case context.

### Illustrative source shape

```yaml
kind: component
metadata:
  name: <kebab-case identifier>
  version: <semver>
  owner: <team or person>

parameters:
  param_name:
    type: string | integer | boolean
    required: true | false
    default: <default value>
    enum: [value1, value2]

provides:
  field_name:
    type: string | integer | object
    description: <what this field represents>

steps:
  - id: <step identifier>
    use: <action reference>
    input:
      field: <value or $ expression>
    output:
      field: <binding name>
    when: <condition for conditional execution>
```

### Example: `authenticated-user` — declaration only

```yaml
kind: component
metadata:
  name: authenticated-user
  version: 1.0.0
  owner: platform-team

parameters:
  role:
    type: string
    required: true
    enum: [buyer, seller, admin]
  require_mfa:
    type: boolean
    required: false
    default: false

provides:
  user_id:
    type: string
    description: authenticated user identifier
  user_email:
    type: string
    description: verified email of the user
  user_role:
    type: string
    description: role assigned to the user
  session_token:
    type: string
    description: active session token

steps:
  - id: validate-session
    use: actions/validate-session-token
    input:
      token: $context.authorization_header
    output:
      user_id: user_id
      email: user_email
      role: user_role
      session: session_token

  - id: check-role
    use: actions/authorize-role
    input:
      user_id: $steps.validate-session.user_id
      required_role: $parameters.role
    output:
      authorized: authorized

  - id: verify-mfa
    use: actions/verify-mfa-code
    when: $parameters.require_mfa == true
    input:
      user_id: $steps.validate-session.user_id
      mfa_code: $context.mfa_header
    output:
      mfa_verified: mfa_verified
```

---

## 4. Protocol

A **protocol** declares an abstract interface and possible concrete
implementations—the source-level analog of an interface or trait. The current
runtime does not select or execute an implementation.

### Illustrative source shape

```yaml
kind: protocol
metadata:
  name: <kebab-case identifier>
  version: <semver>
  owner: <team or person>

input:
  field_name:
    type: string | integer | number | boolean
    required: true | false

output:
  field_name:
    type: string | integer | number | boolean

writes:
  - resource: <entity name>
    mutation: create | set

guarantees:
  - <behavioral promise the implementation must uphold>

implementations:
  - $ref: components/<implementation-name>
```

### Example: `payment` — declaration only

```yaml
kind: protocol
metadata:
  name: payment
  version: 1.0.0
  owner: payments-team

input:
  order_id:
    type: string
    required: true
    format: uuid
  amount_cents:
    type: integer
    required: true
    min: 1
  currency:
    type: string
    required: true
    enum: [usd, eur, gbp]
  method:
    type: string
    required: true
    enum: [stripe, paypal, crypto]

output:
  transaction_id:
    type: string
  status:
    type: string
    enum: [succeeded, declined, pending]
  charged_amount_cents:
    type: integer
  provider_reference:
    type: string

writes:
  - resource: payment_transaction
    mutation: create
  - resource: order
    mutation: set
    by: status

guarantees:
  - exactly one charge attempt per invocation
  - idempotent when called with the same order_id
  - charged_amount_cents equals input amount_cents on success
  - transaction is recorded regardless of outcome

implementations:
  - $ref: components/payment-stripe
  - $ref: components/payment-paypal
  - $ref: components/payment-crypto
```

---

## 5. Use Case

A **use case** declares the intended shape of a user scenario and references
actions, components, protocols, events, and invariants. Loading or graphing
that declaration is not evidence that the end-to-end scenario ran.

### Illustrative source shape

```yaml
kind: usecase
metadata:
  name: <kebab-case identifier>
  version: <semver>
  owner: <team or person>
  actor: <who initiates this use case>
  tags: [tag1, tag2]

trigger: event/<event-name>        # for event-triggered use cases
input_from_event:                   # maps event payload to use case input
  field: $event.payload_field

requires:
  - $ref: components/<component-name>
    as: <namespace alias>
    params:
      param_name: value

preconditions:
  - <condition expression>

steps:
  - id: <step identifier>
    use: actions/<action-name> | protocols/<protocol-name>
    input:
      field: <value or $ expression>
    output:
      field: <binding name>
    postcondition: <condition after this step>
    depends_on: [step_id_1, step_id_2]
    when: <conditional execution>

alternative_flows:
  - name: <flow name>
    trigger: <condition that activates this flow>
    steps:
      - id: <step identifier>
        use: actions/<action-name>
        input:
          field: <value or $ expression>

postconditions:
  - <condition expression>

invariants:
  - $ref: invariants/<invariant-name>

concurrency:
  - conflict: <what can conflict>
    strategy: optimistic-lock | pessimistic-lock | retry | last-write-wins
    description: <human-readable explanation>
```

### Example: `purchase-product` (actor-initiated, declaration only)

```yaml
kind: usecase
metadata:
  name: purchase-product
  version: 1.0.0
  owner: commerce-team
  actor: buyer
  tags: [commerce, checkout, critical-path]

requires:
  - $ref: components/authenticated-user
    as: auth
    params:
      role: buyer
      require_mfa: false

preconditions:
  - cart is not empty
  - all items in cart are in stock

steps:
  - id: load-cart
    use: actions/get-cart
    input:
      user_id: $auth.user_id
    output:
      cart_id: cart_id
      items: items
      total_cents: total_cents

  - id: reserve-inventory
    use: actions/reserve-inventory
    depends_on: [load-cart]
    input:
      items: $steps.load-cart.items
    output:
      reservation_id: reservation_id
      reserved_until: reserved_until
    postcondition: all items are reserved for 15 minutes

  - id: create-order
    use: actions/create-order
    depends_on: [reserve-inventory]
    input:
      user_id: $auth.user_id
      cart_id: $steps.load-cart.cart_id
      items: $steps.load-cart.items
      total_cents: $steps.load-cart.total_cents
      reservation_id: $steps.reserve-inventory.reservation_id
    output:
      order_id: order_id
      order_status: order_status
    postcondition: order exists with status pending

  - id: charge-payment
    use: protocols/payment
    depends_on: [create-order]
    input:
      order_id: $steps.create-order.order_id
      amount_cents: $steps.load-cart.total_cents
      currency: usd
      method: $inputs.payment_method
    output:
      transaction_id: transaction_id
      payment_status: status

  - id: confirm-order
    use: actions/confirm-order
    depends_on: [charge-payment]
    when: $steps.charge-payment.payment_status == "succeeded"
    input:
      order_id: $steps.create-order.order_id
      transaction_id: $steps.charge-payment.transaction_id
    output:
      confirmed_at: confirmed_at
    postcondition: order status is confirmed

  - id: clear-cart
    use: actions/clear-cart
    depends_on: [confirm-order]
    input:
      cart_id: $steps.load-cart.cart_id

alternative_flows:
  - name: payment_declined
    trigger: $steps.charge-payment.payment_status == "declined"
    steps:
      - id: release-inventory-declined
        use: actions/release-inventory
        input:
          reservation_id: $steps.reserve-inventory.reservation_id

      - id: mark-order-failed
        use: actions/update-order-status
        depends_on: [release-inventory-declined]
        input:
          order_id: $steps.create-order.order_id
          status: payment_declined

      - id: notify-buyer-declined
        use: actions/send-notification
        depends_on: [mark-order-failed]
        input:
          user_id: $auth.user_id
          template: payment_declined
          order_id: $steps.create-order.order_id

  - name: payment_timeout
    trigger: $steps.charge-payment timed out after 30s
    steps:
      - id: release-inventory-timeout
        use: actions/release-inventory
        input:
          reservation_id: $steps.reserve-inventory.reservation_id

      - id: mark-order-timeout
        use: actions/update-order-status
        depends_on: [release-inventory-timeout]
        input:
          order_id: $steps.create-order.order_id
          status: payment_timeout

      - id: enqueue-retry
        use: actions/enqueue-payment-retry
        depends_on: [mark-order-timeout]
        input:
          order_id: $steps.create-order.order_id
          retry_after_seconds: 300

postconditions:
  - order exists with status confirmed or failed
  - inventory is either committed or released
  - payment transaction is recorded

invariants:
  - $ref: invariants/inventory-never-negative
  - $ref: invariants/order-total-matches-items

concurrency:
  - conflict: two buyers purchasing the last unit of the same product
    strategy: optimistic-lock
    description: inventory reservation uses version-based optimistic locking; second buyer receives OUT_OF_STOCK
```

### Example: `receive-new-message` (event-triggered declaration only)

```yaml
kind: usecase
metadata:
  name: receive-new-message
  version: 1.0.0
  owner: messaging-team
  actor: system
  tags: [messaging, real-time, notifications]

trigger: event/message-created

input_from_event:
  message_id: $event.message_id
  conversation_id: $event.conversation_id
  sender_id: $event.sender_id
  recipient_id: $event.recipient_id
  body: $event.body
  sent_at: $event.sent_at

steps:
  - id: load-recipient-preferences
    use: actions/get-user-preferences
    input:
      user_id: $inputs.recipient_id
    output:
      push_enabled: push_enabled
      sound_enabled: sound_enabled
      is_online: is_online

  - id: increment-unread-count
    use: actions/increment-unread-counter
    input:
      user_id: $inputs.recipient_id
      conversation_id: $inputs.conversation_id
    output:
      unread_count: unread_count

  - id: deliver-via-websocket
    use: actions/push-websocket-message
    depends_on: [load-recipient-preferences, increment-unread-count]
    when: $steps.load-recipient-preferences.is_online == true
    input:
      recipient_id: $inputs.recipient_id
      payload:
        type: new_message
        message_id: $inputs.message_id
        conversation_id: $inputs.conversation_id
        sender_id: $inputs.sender_id
        body: $inputs.body
        sent_at: $inputs.sent_at
        unread_count: $steps.increment-unread-count.unread_count

  - id: send-push-notification
    use: actions/send-push-notification
    depends_on: [load-recipient-preferences]
    when: $steps.load-recipient-preferences.is_online == false and $steps.load-recipient-preferences.push_enabled == true
    input:
      recipient_id: $inputs.recipient_id
      title: New message
      body: $inputs.body
      data:
        conversation_id: $inputs.conversation_id
        message_id: $inputs.message_id

  - id: update-conversation-timestamp
    use: actions/update-conversation-last-activity
    input:
      conversation_id: $inputs.conversation_id
      timestamp: $inputs.sent_at

postconditions:
  - unread counter for recipient and conversation is incremented
  - recipient is notified via websocket or push notification
  - conversation last_activity timestamp is updated
```

### Example: `return-product` (dependency declaration only)

```yaml
kind: usecase
metadata:
  name: return-product
  version: 1.0.0
  owner: commerce-team
  actor: buyer
  tags: [commerce, returns]

requires:
  - $ref: components/authenticated-user
    as: auth
    params:
      role: buyer
  - $ref: use-cases/purchase-product
    as: original_purchase

preconditions:
  - original purchase exists and is in status confirmed
  - return window has not expired (within 30 days of confirmed_at)

steps:
  - id: load-order
    use: actions/get-order
    input:
      order_id: $inputs.order_id
      user_id: $auth.user_id
    output:
      order_id: order_id
      items: items
      total_cents: total_cents
      confirmed_at: confirmed_at
      transaction_id: transaction_id

  - id: validate-return-window
    use: actions/validate-return-eligibility
    depends_on: [load-order]
    input:
      confirmed_at: $steps.load-order.confirmed_at
      max_return_days: 30
    output:
      eligible: eligible

  - id: create-return-request
    use: actions/create-return-request
    depends_on: [validate-return-window]
    when: $steps.validate-return-window.eligible == true
    input:
      order_id: $steps.load-order.order_id
      user_id: $auth.user_id
      items: $inputs.return_items
      reason: $inputs.reason
    output:
      return_id: return_id
      return_status: status

  - id: initiate-refund
    use: protocols/payment
    depends_on: [create-return-request]
    input:
      order_id: $steps.load-order.order_id
      amount_cents: $steps.load-order.total_cents
      currency: usd
      method: $inputs.refund_method
    output:
      refund_transaction_id: transaction_id
      refund_status: status

  - id: release-inventory-back
    use: actions/restore-inventory
    depends_on: [initiate-refund]
    when: $steps.initiate-refund.refund_status == "succeeded"
    input:
      items: $inputs.return_items
    output:
      restored: restored

  - id: notify-buyer-return
    use: actions/send-notification
    depends_on: [release-inventory-back]
    input:
      user_id: $auth.user_id
      template: return_confirmed
      return_id: $steps.create-return-request.return_id

postconditions:
  - return request exists with status approved or rejected
  - refund transaction is recorded if approved
  - inventory is restored for returned items

invariants:
  - $ref: invariants/inventory-never-negative
  - $ref: invariants/refund-never-exceeds-original
```

---

## 6. Invariant

An **invariant** declares a business rule intended to hold across relevant use
cases. The current package retains selected invariant declarations but does not
automatically check them or formally verify them.

The target verification design and illustrative enforcement patterns are in
[INVARIANTS.md](INVARIANTS.md); they are not current support unless the
capability matrix names executable evidence.

### Illustrative source shape

```yaml
kind: invariant
metadata:
  name: <kebab-case identifier>
  severity: critical | high | medium

type: data | relationship | aggregate | state-machine | temporal | uniqueness

rule: <formal expression>

applies_to:
  - <resource or use case this invariant guards>
```

### Example: `data` invariant — declaration only

```yaml
kind: invariant
metadata:
  name: price-always-positive
  severity: critical

type: data

rule: product.price_cents > 0

applies_to:
  - resource: product
  - action: actions/update-product-price
  - action: actions/create-product
```

### Example: `relationship` invariant — declaration only

```yaml
kind: invariant
metadata:
  name: order-belongs-to-existing-user
  severity: critical

type: relationship

rule: order.user_id must reference an existing user

applies_to:
  - resource: order
  - action: actions/create-order
```

### Example: `aggregate` invariant — declaration only

```yaml
kind: invariant
metadata:
  name: inventory-never-negative
  severity: critical

type: aggregate

rule: sum(inventory.quantity) for any product_id >= 0

applies_to:
  - resource: inventory
  - action: actions/reserve-inventory
  - action: actions/restore-inventory
  - usecase: use-cases/purchase-product
```

### Example: `state-machine` invariant — declaration only

```yaml
kind: invariant
metadata:
  name: order-valid-transitions
  severity: critical

type: state-machine

rule: |
  order.status transitions:
    pending -> confirmed | payment_declined | payment_timeout
    confirmed -> shipped | return_requested
    shipped -> delivered
    return_requested -> returned | return_rejected
    delivered -> return_requested

applies_to:
  - resource: order
  - action: actions/confirm-order
  - action: actions/update-order-status
```

### Example: `temporal` invariant — declaration only

```yaml
kind: invariant
metadata:
  name: return-within-30-days
  severity: high

type: temporal

rule: return_request.created_at <= order.confirmed_at + 30 days

applies_to:
  - resource: return_request
  - usecase: use-cases/return-product
```

### Example: `uniqueness` invariant — declaration only

```yaml
kind: invariant
metadata:
  name: one-active-cart-per-user
  severity: medium

type: uniqueness

rule: count(cart where user_id = X and status = active) <= 1

applies_to:
  - resource: cart
  - action: actions/create-cart
```

---

## Expression Syntax

UCF source documents use `$` expressions to declare data mappings. Consumer
coverage varies: retaining or tracing an expression does not mean UCF evaluates
it at runtime.

| Expression | Resolves to |
|---|---|
| `$inputs.field` | A field from the use case input |
| `$steps.step_id.field` | Output field from a completed step |
| `$component_alias.field` | Data provided by a required component |
| `$event.field` | Payload field from the trigger event |
| `$old.entity.field` | Previous value before mutation (for postconditions) |
| `$parameters.field` | Parameter passed to a component |
| `$generated.uuid` | Auto-generated UUID value |
| `$context.field` | Contextual data (headers, environment flags) |

### Usage examples

```yaml
# Use case input
input:
  user_id: $inputs.user_id

# Output from a previous step
input:
  order_id: $steps.create-order.order_id

# Data from a required component
input:
  user_id: $auth.user_id

# Event payload in event-triggered use cases
input_from_event:
  message_id: $event.message_id

# Previous value in postconditions
postconditions:
  - cart.total_items == $old.cart.total_items + quantity

# Component parameters inside component definitions
when: $parameters.require_mfa == true

# Declared generated value (consumer-dependent)
input:
  id: $generated.uuid

# Contextual data
input:
  token: $context.authorization_header
```

---

## Project Structure

This is an illustrative source layout, not proof that every declaration shown
above has an executable consumer.

```
specs/
├── actions/
│   ├── add-to-cart.yaml
│   ├── get-cart.yaml
│   ├── reserve-inventory.yaml
│   ├── release-inventory.yaml
│   ├── restore-inventory.yaml
│   ├── create-order.yaml
│   ├── confirm-order.yaml
│   ├── update-order-status.yaml
│   ├── clear-cart.yaml
│   ├── send-notification.yaml
│   ├── send-push-notification.yaml
│   ├── push-websocket-message.yaml
│   ├── validate-session-token.yaml
│   ├── authorize-role.yaml
│   └── verify-mfa-code.yaml
├── events/
│   └── message-created.yaml
├── components/
│   ├── authenticated-user.yaml
│   ├── payment-stripe.yaml
│   ├── payment-paypal.yaml
│   └── payment-crypto.yaml
├── protocols/
│   └── payment.yaml
├── use-cases/
│   ├── purchase-product.yaml
│   ├── return-product.yaml
│   └── receive-new-message.yaml
└── invariants/
    ├── inventory-never-negative.yaml
    ├── order-total-matches-items.yaml
    ├── order-valid-transitions.yaml
    ├── price-always-positive.yaml
    ├── order-belongs-to-existing-user.yaml
    ├── return-within-30-days.yaml
    ├── one-active-cart-per-user.yaml
    └── refund-never-exceeds-original.yaml
```
