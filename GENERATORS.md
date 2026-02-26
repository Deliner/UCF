# Generator Engine

## Architecture: Interface + Orchestrator + Implementation

From one use case spec, the framework generates **three** artifacts:

| Artifact | Generated? | Editable? | Purpose |
|---|---|---|---|
| **Interface** (abstract class + dataclasses) | Yes, deterministic | DO NOT EDIT | Defines the contract |
| **Orchestrator** (test file) | Yes, deterministic | DO NOT EDIT | Calls interface methods in correct order |
| **Implementation** (concrete class) | No — written by AI or developer | Yes | Fills in real logic |

This separation solves LLM non-determinism: structure is always identical regardless of who generates it or when. Only the implementation varies, and it is constrained by the interface.

```
purchase-product.yaml
        │
        ▼
┌─────────────────────┐
│   ucf generate      │
├─────────────────────┤
│                     │
│  ┌───────────────┐  │    DO NOT EDIT
│  │  interface.py │──┼──▶ Abstract class + dataclasses
│  └───────────────┘  │
│                     │
│  ┌───────────────┐  │    DO NOT EDIT
│  │  test_orch.py │──┼──▶ Pytest orchestrator calling interface
│  └───────────────┘  │
│                     │
└─────────────────────┘
                          HUMAN / AI
   ┌───────────────┐
   │   impl.py     │────▶ Concrete class filling abstract methods
   └───────────────┘
```

## Generated Interface

The interface is a pure-Python abstract class with typed dataclasses. Every field in the spec maps to a method or a dataclass.

```python
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class AuthContext:
    user_id: str
    token: str


@dataclass(frozen=True)
class CartContext:
    cart_id: str
    item_ids: list[str]
    total: Decimal


@dataclass(frozen=True)
class CheckoutResult:
    order_id: str
    status: str


@dataclass(frozen=True)
class PaymentResult:
    transaction_id: str
    captured: bool
    amount: Decimal


class PurchaseProductInterface(ABC):

    # --- State Setup (from `requires`) ---

    @abstractmethod
    def setup_authenticated_user(self) -> AuthContext:
        ...

    @abstractmethod
    def setup_cart_with_items(self, auth: AuthContext) -> CartContext:
        ...

    # --- Actions (from `steps`) ---

    @abstractmethod
    def action_create_order(
        self, auth: AuthContext, cart: CartContext,
    ) -> CheckoutResult:
        ...

    @abstractmethod
    def action_process_payment(
        self, auth: AuthContext, checkout: CheckoutResult,
    ) -> PaymentResult:
        ...

    @abstractmethod
    def action_confirm_order(
        self, auth: AuthContext, checkout: CheckoutResult,
    ) -> None:
        ...

    # --- Verifications (from `postconditions` + `invariants`) ---

    @abstractmethod
    def verify_order_exists_with_status(
        self, auth: AuthContext, order_id: str, expected_status: str,
    ) -> None:
        ...

    @abstractmethod
    def verify_payment_captured(
        self, payment: PaymentResult,
    ) -> None:
        ...

    @abstractmethod
    def verify_stock_non_negative(self, item_ids: list[str]) -> None:
        ...

    @abstractmethod
    def verify_money_consistency(
        self, cart: CartContext, payment: PaymentResult,
    ) -> None:
        ...
```

Every method has a single responsibility. Naming follows a strict convention: `setup_*`, `action_*`, `verify_*`. The generator derives these names from the YAML spec fields `requires`, `steps`, `postconditions`, and `invariants`.

## Generated Orchestrator (Test)

The orchestrator is a pytest module that imports the interface and calls its methods in the order dictated by the spec. It contains zero business logic — only sequencing.

```python
from __future__ import annotations

import pytest

from .interface import PurchaseProductInterface


@pytest.fixture
def uc(purchase_product_impl: PurchaseProductInterface) -> PurchaseProductInterface:
    return purchase_product_impl


class TestHappyPath:

    def test_purchase_completes_successfully(
        self, uc: PurchaseProductInterface,
    ) -> None:
        auth = uc.setup_authenticated_user()
        cart = uc.setup_cart_with_items(auth=auth)

        checkout = uc.action_create_order(auth=auth, cart=cart)
        payment = uc.action_process_payment(auth=auth, checkout=checkout)
        uc.action_confirm_order(auth=auth, checkout=checkout)

        uc.verify_order_exists_with_status(
            auth=auth,
            order_id=checkout.order_id,
            expected_status="confirmed",
        )
        uc.verify_payment_captured(payment=payment)
        uc.verify_stock_non_negative(item_ids=cart.item_ids)
        uc.verify_money_consistency(cart=cart, payment=payment)


class TestPaymentDeclined:

    def test_order_cancelled_on_decline(
        self, uc: PurchaseProductInterface,
    ) -> None:
        auth = uc.setup_authenticated_user()
        cart = uc.setup_cart_with_items(auth=auth)

        checkout = uc.action_create_order(auth=auth, cart=cart)

        with pytest.raises(PaymentDeclinedError):
            uc.action_process_payment(auth=auth, checkout=checkout)

        uc.verify_order_exists_with_status(
            auth=auth,
            order_id=checkout.order_id,
            expected_status="cancelled",
        )
        uc.verify_stock_non_negative(item_ids=cart.item_ids)


class TestPaymentTimeout:

    def test_order_pending_on_timeout(
        self, uc: PurchaseProductInterface,
    ) -> None:
        auth = uc.setup_authenticated_user()
        cart = uc.setup_cart_with_items(auth=auth)

        checkout = uc.action_create_order(auth=auth, cart=cart)

        with pytest.raises(PaymentTimeoutError):
            uc.action_process_payment(auth=auth, checkout=checkout)

        uc.verify_order_exists_with_status(
            auth=auth,
            order_id=checkout.order_id,
            expected_status="pending_retry",
        )
```

The test file is entirely mechanical. Alternative flows map to additional test classes, each derived from the `alternative_flows` section of the spec.

## Implementation (AI-Written)

The implementation is the only file humans or AI write. It inherits the interface and fills each method body.

```python
from __future__ import annotations

import httpx

from .interface import (
    AuthContext,
    CartContext,
    CheckoutResult,
    PaymentResult,
    PurchaseProductInterface,
)

BASE_URL = "http://localhost:8000/api/v1"


class PurchaseProductImpl(PurchaseProductInterface):

    def __init__(self) -> None:
        self.client = httpx.Client(base_url=BASE_URL, timeout=10.0)

    def setup_authenticated_user(self) -> AuthContext:
        resp = self.client.post("/auth/register", json={"email": "test@e2e.local"})
        data = resp.json()
        return AuthContext(user_id=data["id"], token=data["token"])

    def setup_cart_with_items(self, auth: AuthContext) -> CartContext:
        headers = {"Authorization": f"Bearer {auth.token}"}
        resp = self.client.post(
            "/cart",
            json={"items": [{"sku": "WIDGET-1", "qty": 2}]},
            headers=headers,
        )
        data = resp.json()
        return CartContext(
            cart_id=data["cart_id"],
            item_ids=data["item_ids"],
            total=data["total"],
        )

    def action_create_order(
        self, auth: AuthContext, cart: CartContext,
    ) -> CheckoutResult:
        headers = {"Authorization": f"Bearer {auth.token}"}
        resp = self.client.post(
            f"/cart/{cart.cart_id}/checkout",
            headers=headers,
        )
        data = resp.json()
        return CheckoutResult(order_id=data["order_id"], status=data["status"])

    def action_process_payment(
        self, auth: AuthContext, checkout: CheckoutResult,
    ) -> PaymentResult:
        headers = {"Authorization": f"Bearer {auth.token}"}
        resp = self.client.post(
            f"/orders/{checkout.order_id}/pay",
            headers=headers,
        )
        data = resp.json()
        return PaymentResult(
            transaction_id=data["txn_id"],
            captured=data["captured"],
            amount=data["amount"],
        )

    def action_confirm_order(
        self, auth: AuthContext, checkout: CheckoutResult,
    ) -> None:
        headers = {"Authorization": f"Bearer {auth.token}"}
        self.client.post(
            f"/orders/{checkout.order_id}/confirm",
            headers=headers,
        )

    def verify_order_exists_with_status(
        self, auth: AuthContext, order_id: str, expected_status: str,
    ) -> None:
        headers = {"Authorization": f"Bearer {auth.token}"}
        resp = self.client.get(f"/orders/{order_id}", headers=headers)
        assert resp.json()["status"] == expected_status

    def verify_payment_captured(self, payment: PaymentResult) -> None:
        assert payment.captured is True

    def verify_stock_non_negative(self, item_ids: list[str]) -> None:
        for item_id in item_ids:
            resp = self.client.get(f"/inventory/{item_id}")
            assert resp.json()["quantity"] >= 0

    def verify_money_consistency(
        self, cart: CartContext, payment: PaymentResult,
    ) -> None:
        assert payment.amount == cart.total
```

Each method is small, focused, and independently reviewable. The AI fills only function bodies — it cannot change the method signatures, the call order, or the verification logic.

## Plugin Architecture

Generators are pluggable. Each plugin implements the `GeneratorPlugin` protocol:

```python
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable


@dataclass(frozen=True)
class GeneratedFile:
    path: str
    content: str
    overwrite: bool


@runtime_checkable
class GeneratorPlugin(Protocol):
    name: str
    platform: str
    language: str

    def generate_happy_path(self, spec: UseCaseSpec) -> GeneratedFile: ...
    def generate_alternative_flow(
        self, spec: UseCaseSpec, flow_name: str,
    ) -> GeneratedFile: ...
    def generate_invariant_test(
        self, spec: UseCaseSpec, invariant: InvariantSpec,
    ) -> GeneratedFile: ...
    def generate_conflict_test(
        self, spec: UseCaseSpec, conflict: ConflictSpec,
    ) -> GeneratedFile: ...
    def generate_mock(self, spec: UseCaseSpec) -> GeneratedFile: ...
```

The engine loads plugins, matches them to the spec's `platform` field, and delegates file generation.

## Built-in Plugins

| Plugin | Platform | Language | Generates |
|---|---|---|---|
| `pytest-http` | HTTP REST | Python | pytest tests with `httpx` |
| `jest-http` | HTTP REST | TypeScript | Jest tests with `fetch` |
| `playwright` | Web UI | TypeScript | Playwright E2E tests |
| `go-test-http` | HTTP REST | Go | `testing` + `net/http` tests |
| `mock-server` | HTTP REST | Python | WireMock / `responses` stubs |
| `mermaid` | — | — | Mermaid sequence diagrams |
| `openapi-sync` | HTTP REST | YAML | OpenAPI spec drift detection |

## Generated Artifacts

From a single spec file, the engine produces 5–7 files:

```
specs/purchase-product.yaml
    │
    ▼  ucf generate
    │
    ├── generated/purchase_product/interface.py
    ├── generated/purchase_product/test_happy_path.py
    ├── generated/purchase_product/test_alt_payment_declined.py
    ├── generated/purchase_product/test_alt_payment_timeout.py
    ├── generated/purchase_product/test_invariant_stock.py
    ├── generated/purchase_product/test_invariant_money.py
    └── generated/purchase_product/mock_server.py
```

All files except `impl.py` are re-generated on every `ucf generate` run. The implementation file is never overwritten.

## Developer Workflow

```
1. Human writes/edits YAML spec
2. ucf generate → framework generates interface.py + test_orchestrator.py
3. IDE highlights: "3 unimplemented abstract methods"
4. AI fills implementation.py
5. pytest test_orchestrator.py
6. Green? → Commit. Red? → AI fixes implementation.py
```

Step 3 is where the IDE becomes a feedback loop. Because the interface is a standard Python abstract class, any LSP-capable editor shows unimplemented methods as errors. The developer (or AI agent) sees exactly what needs to be written — no guessing, no prompt engineering.

The feedback cycle is tight:

```
spec change → generate → type error → implement → test → pass
     │                                                   │
     └───────────────────────────────────────────────────┘
```

## Spec Change Handling

When a spec changes, the generator re-runs and overwrites the interface and orchestrator. The implementation is **never touched**.

| What changed in spec | Effect on interface | Effect on orchestrator | Effect on implementation |
|---|---|---|---|
| New step added | New `action_*` method appears | New call inserted in test | IDE shows unimplemented method |
| Step removed | `action_*` method removed | Call removed from test | IDE shows unused import (safe) |
| New postcondition | New `verify_*` method appears | New assertion added | IDE shows unimplemented method |
| New invariant | New `verify_*` method appears | New test class generated | IDE shows unimplemented method |
| New alternative flow | No change | New test class generated | May need new error handling |
| Dataclass field added | Dataclass updated | Orchestrator passes new field | Existing code may break at type level |

The blast radius is minimal: only the implementation methods that correspond to changed spec fields need updating. Everything else remains stable.
