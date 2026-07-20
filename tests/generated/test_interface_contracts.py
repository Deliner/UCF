"""Contract checks for user-owned generated-suite implementations."""

from __future__ import annotations

import importlib
import inspect
from pathlib import Path
from types import ModuleType
from typing import Any, get_type_hints

import pytest

GENERATED_ROOT = Path(__file__).parent
GENERATED_PACKAGES = tuple(
    path.name
    for path in sorted(GENERATED_ROOT.iterdir())
    if path.is_dir()
    and (path / "interface.py").is_file()
    and (path / "impl.py").is_file()
)


def _generated_interface(module: ModuleType) -> type[Any]:
    interfaces = [
        value
        for value in vars(module).values()
        if inspect.isclass(value)
        and value.__module__ == module.__name__
        and value.__name__.endswith("Interface")
    ]
    assert len(interfaces) == 1
    return interfaces[0]


def _implementation_classes(
    module: ModuleType, interface: type[Any]
) -> list[type[Any]]:
    return [
        value
        for value in vars(module).values()
        if inspect.isclass(value)
        and value.__module__ == module.__name__
        and issubclass(value, interface)
        and value is not interface
    ]


def _assert_method_contract(
    interface: type[Any], implementation: type[Any], method_name: str
) -> None:
    expected_method = getattr(interface, method_name)
    actual_method = getattr(implementation, method_name)
    expected = inspect.signature(expected_method)
    actual = inspect.signature(actual_method)

    assert tuple(actual.parameters) == tuple(expected.parameters)
    for name, expected_parameter in expected.parameters.items():
        actual_parameter = actual.parameters[name]
        assert actual_parameter.kind is expected_parameter.kind
        assert actual_parameter.default == expected_parameter.default

    assert get_type_hints(actual_method) == get_type_hints(expected_method)


@pytest.mark.parametrize("package_name", GENERATED_PACKAGES)
def test_user_implementations_match_generated_interfaces(package_name: str) -> None:
    interface_module = importlib.import_module(
        f"tests.generated.{package_name}.interface"
    )
    implementation_module = importlib.import_module(
        f"tests.generated.{package_name}.impl"
    )
    interface = _generated_interface(interface_module)
    implementations = _implementation_classes(implementation_module, interface)

    assert implementations
    abstract_methods = [
        name
        for name, value in vars(interface).items()
        if getattr(value, "__isabstractmethod__", False)
    ]
    for implementation in implementations:
        for method_name in abstract_methods:
            _assert_method_contract(interface, implementation, method_name)
