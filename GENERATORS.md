# Generator Engine

> **Current status — experimental Python contract skeleton.** The canonical
> support and evidence boundary is
> [docs/CAPABILITIES.md](docs/CAPABILITIES.md). UCF does not currently ship
> JavaScript, Go, UI, mock-server, or transport-specific generators, and
> generated verification methods are user-owned obligations rather than formal
> verification. The separate exact external-adapter generation path is
> documented in [docs/GENERATION.md](docs/GENERATION.md); it does not change
> the legacy in-process generator described below.

## Current Ownership Boundary

For a supported use-case subset, the current Python generator emits three
files:

| File | Write policy | Ownership | Current purpose |
|---|---|---|---|
| `interface.py` | Regenerated | Generated-owned | Python abstract contract for selected declarations |
| `test_orchestrator.py` | Regenerated | Generated-owned | Pytest sequencing for selected declarations |
| `impl.py` | Created only when absent | User-owned | Stub whose methods and fixtures the user completes |

This boundary protects an existing `impl.py` from regeneration. It does not by
itself make the output executable: the user must implement the methods and
provide any required inputs or fixtures. CAP-211 proves a different,
generated-only transaction for one external Python/pytest action-function
profile; it does not make this legacy multi-file writer transactional.

```text
purchase-product.yaml
        │
        ▼  ucf generate
generated/purchase_product/
        ├── interface.py          generated-owned
        ├── test_orchestrator.py  generated-owned
        └── impl.py               user-owned after first creation
```

## Generated Interface

The current plugin derives a Python abstract class and selected dataclasses
from the supported portion of a resolved use case. It does not map every source
field, execute platform bindings, or enforce declared business rules.

The following code is an illustrative contract shape, not a golden output
fixture:

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

For shapes the plugin currently consumes, generated method names use
`setup_*`, `action_*`, and `verify_*` conventions. A `verify_*` signature says
that user-owned code must perform a check; its presence is not verification
evidence.

## Generated Orchestrator (Test)

The current orchestrator is a pytest module that calls generated interface
methods for the supported subset. Business behavior and assertions live in the
user-owned implementation. Conditional and alternative-flow source fields are
only supported where executable tests name that behavior.

The following is an illustrative target-shaped test, not a promise that every
shown declaration is currently translated:

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

Supported alternative-flow shapes can produce additional test classes. Retry
semantics are rejected before generation, and other declarations without an
encoded consumer remain intent only.

## User-Owned Implementation

The generator creates `impl.py` only when it is absent, then leaves it
untouched. A developer may fill its method bodies directly or with an AI
assistant. The HTTP implementation below is illustrative user code; UCF does
not generate it and it is not evidence of an HTTP executor.

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

The generated interface constrains the expected method signatures, but the
repository does not prevent a user from editing files. Regeneration overwrites
generated-owned files; assertions and integration behavior remain the user's
responsibility in `impl.py`.

## Internal Generator Seam

The Python package contains an in-process `GeneratorPlugin` protocol. This is
an internal extension seam, not the planned stable out-of-process adapter
protocol, and the CLI currently instantiates only `PytestPlugin`.

```python
class GeneratorPlugin(Protocol):
    name: str
    language: str

    def generate_interface(
        self, spec: UseCaseSpec, registry: SpecRegistry
    ) -> GeneratedFile: ...

    def generate_orchestrator(
        self, spec: UseCaseSpec, registry: SpecRegistry
    ) -> GeneratedFile: ...

    def generate_impl_stub(
        self, spec: UseCaseSpec, registry: SpecRegistry
    ) -> GeneratedFile: ...
```

Plugins may additionally implement `validate_spec(...)` for support preflight.
There is currently no CLI plugin discovery, platform-based selection, or
cross-language conformance contract.

## Current Generator

| CLI-selected implementation | Language | Status | Output |
|---|---|---|---|
| `PytestPlugin` | Python | Experimental | Interface, pytest orchestrator, non-overwriting implementation stub |

Other language, platform, mock, documentation, and synchronization generators
are not shipped. Their delivery dependencies are tracked in
[docs/CAPABILITIES.md](docs/CAPABILITIES.md).

## Generated Artifacts

For one accepted use case, the current engine creates this package shape:

```text
specs/purchase-product.yaml
    │
    ▼  ucf generate
    │
    ├── generated/purchase_product/__init__.py
    ├── generated/purchase_product/interface.py
    ├── generated/purchase_product/test_orchestrator.py
    └── generated/purchase_product/impl.py
```

`interface.py` and `test_orchestrator.py` are regenerated. `__init__.py` and
`impl.py` are created only when absent. The current engine is not a
project-wide transactional generator across multiple use cases.

## Developer Workflow

```text
1. Write and validate source declarations.
2. Run: ucf generate specs --output tests/generated
3. Implement the generated-once impl.py stub and required inputs/fixtures.
4. Run pytest against the generated test_orchestrator.py.
5. Treat a pass only as evidence for assertions that actually executed.
```

Fresh simple generated output can collect and run once explicit user fixtures
and implementations are present. No IDE integration or automated fix loop is
part of the current support claim.

## Spec Change Handling

On regeneration, UCF overwrites `interface.py` and `test_orchestrator.py` but
does not overwrite an existing `impl.py`. The developer must reconcile that
user-owned implementation with changed signatures and sequencing.

A source change can be translated, explicitly rejected (retry is the current
example), or retained without executable behavior. Consult the capability
matrix and focused generator tests before treating a field as supported.
