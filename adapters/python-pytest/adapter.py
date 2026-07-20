from __future__ import annotations

import hashlib
import json
import re

from ucf.adapter_protocol import (
    AdapterDispatcher,
    CapabilitySelection,
    Method,
    RequestContext,
    ir_value_to_json_profile,
    run_stdio_server,
)
from ucf.generation import (
    GENERATION_CAPABILITY,
    GENERATION_PROFILE_VERSION,
    GENERATION_RESULT_SCHEMA_URI,
    GeneratedFile,
    GenerationResult,
    GenerationVerification,
    derive_generation_result_id,
    generation_request_from_payload,
    generation_result_to_payload,
)
from ucf.ir.models import Digest, Producer

PROFILE_CAPABILITY = "org.ucf.adapter.generation.python-pytest"
PROCEDURE_URI = "urn:ucf:python-pytest:function-test:1.0.0"
VERIFICATION_PROCEDURE_URI = (
    "urn:ucf:python-pytest:execute-generated-test:1.0.0"
)
PRODUCER = Producer(
    kind="producer",
    name="org.ucf.adapter.python-pytest",
    version=GENERATION_PROFILE_VERSION,
)

_CONFIGURATION_FIELDS = {"callable", "module", "parameters"}
_PYTHON_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_PYTHON_MODULE = re.compile(
    r"^[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*$"
)


async def _handle(
    method: Method,
    payload,
    context: RequestContext,
):
    del context
    if method is not Method.GENERATE:
        raise ValueError("python-pytest adapter supports generation only")
    request = generation_request_from_payload(payload)
    if (
        request.profile_capability.name != PROFILE_CAPABILITY
        or request.profile_capability.version != GENERATION_PROFILE_VERSION
        or request.adapter_procedure_uri != PROCEDURE_URI
    ):
        raise ValueError(
            "generation request does not select the python-pytest profile"
        )
    configuration = _decode_configuration(
        request.profile_configuration,
        input_ports={item.port.name for item in request.inputs},
    )
    content = _render_test(
        request,
        module=configuration["module"],
        callable_name=configuration["callable"],
        parameters=configuration["parameters"],
    )
    encoded = content.encode("utf-8")
    path = (
        "test_"
        + re.sub(r"[^A-Za-z0-9_]", "_", request.subject.target_id)
        + ".py"
    )
    result = GenerationResult(
        kind="generation_result",
        generation_version=GENERATION_PROFILE_VERSION,
        schema_uri=GENERATION_RESULT_SCHEMA_URI,
        id=f"generation-result.{'0' * 64}",
        status="complete",
        request=request,
        producer=PRODUCER,
        capability=request.capability,
        profile_capability=request.profile_capability,
        procedure_uri=PROCEDURE_URI,
        files=(
            GeneratedFile(
                kind="generated_file",
                path=path,
                ownership="generator_owned",
                media_type="text/x-python",
                encoding="utf-8",
                byte_size=len(encoded),
                content_digest=Digest(
                    kind="digest",
                    algorithm="sha-256",
                    value=hashlib.sha256(encoded).hexdigest(),
                ),
                content=content,
            ),
        ),
        verification=GenerationVerification(
            kind="generation_verification",
            procedure_uri=VERIFICATION_PROCEDURE_URI,
            working_directory="implementation_root",
            argv=(
                "python3",
                "-B",
                "-m",
                "pytest",
                "-q",
                "{generated_root}",
            ),
        ),
    )
    result = result.model_copy(
        update={"id": derive_generation_result_id(result)}
    )
    return generation_result_to_payload(result)


def _decode_configuration(
    configuration,
    *,
    input_ports: set[str],
) -> dict:
    decoded = ir_value_to_json_profile(configuration)
    if not isinstance(decoded, dict) or set(decoded) != _CONFIGURATION_FIELDS:
        raise ValueError(
            "python-pytest configuration must contain exact fields"
        )
    module = decoded["module"]
    callable_name = decoded["callable"]
    parameters = decoded["parameters"]
    if (
        not isinstance(module, str)
        or _PYTHON_MODULE.fullmatch(module) is None
    ):
        raise ValueError("python-pytest module is not a dotted identifier")
    if (
        not isinstance(callable_name, str)
        or _PYTHON_IDENTIFIER.fullmatch(callable_name) is None
    ):
        raise ValueError("python-pytest callable is not an identifier")
    if not isinstance(parameters, dict):
        raise ValueError("python-pytest parameters must be a record")
    if set(parameters) != input_ports:
        raise ValueError(
            "python-pytest parameters must map every exact input port"
        )
    if any(
        not isinstance(value, str)
        or _PYTHON_IDENTIFIER.fullmatch(value) is None
        for value in parameters.values()
    ):
        raise ValueError(
            "python-pytest parameter names must be identifiers"
        )
    if len(set(parameters.values())) != len(parameters):
        raise ValueError(
            "python-pytest parameter names must be unique"
        )
    return {
        "callable": callable_name,
        "module": module,
        "parameters": parameters,
    }


def _render_test(
    request,
    *,
    module: str,
    callable_name: str,
    parameters: dict[str, str],
) -> str:
    if len(request.expected_outputs) != 1:
        raise ValueError(
            "python-pytest direct-result profile requires one expected output"
        )
    inputs = {
        parameters[item.port.name]: ir_value_to_json_profile(item.value)
        for item in request.inputs
    }
    expected = ir_value_to_json_profile(
        request.expected_outputs[0].value
    )
    inputs_json = json.dumps(
        inputs,
        ensure_ascii=True,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    expected_json = json.dumps(
        expected,
        ensure_ascii=True,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    test_name = re.sub(
        r"[^A-Za-z0-9_]",
        "_",
        request.subject.target_id,
    )
    return (
        '"""Generated UCF contract test. DO NOT EDIT."""\n'
        "\n"
        "from __future__ import annotations\n"
        "\n"
        "import importlib\n"
        "import json\n"
        "\n"
        f"_MODULE = {module!r}\n"
        f"_CALLABLE = {callable_name!r}\n"
        f"_INPUTS_JSON = {inputs_json!r}\n"
        f"_EXPECTED_JSON = {expected_json!r}\n"
        "\n"
        f"def test_{test_name}_contract() -> None:\n"
        "    module = importlib.import_module(_MODULE)\n"
        "    function = getattr(module, _CALLABLE)\n"
        "    inputs = json.loads(_INPUTS_JSON)\n"
        "    expected = json.loads(_EXPECTED_JSON)\n"
        "    assert function(**inputs) == expected\n"
    )


def _dispatcher() -> AdapterDispatcher:
    return AdapterDispatcher(
        adapter=PRODUCER,
        offered_capabilities=(
            CapabilitySelection(
                kind="capability",
                name=GENERATION_CAPABILITY,
                version=GENERATION_PROFILE_VERSION,
            ),
            CapabilitySelection(
                kind="capability",
                name=PROFILE_CAPABILITY,
                version=GENERATION_PROFILE_VERSION,
            ),
        ),
        handler=_handle,
    )


if __name__ == "__main__":
    raise SystemExit(run_stdio_server(_dispatcher()))
