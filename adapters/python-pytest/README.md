# UCF Python/pytest generation adapter

This external adapter implements the exact
`org.ucf.adapter.generation.python-pytest@1.0.0` capability over the accepted
UCF adapter protocol. It renders one deterministic pytest contract for one
Behavior IR action and returns only a content-bearing generation result. It
does not write application or generated files. The exact public boundary and
invocation are documented in `docs/GENERATION.md`; the canonical status claim
remains `docs/CAPABILITIES.md`, CAP-211.

The request configuration is an exact record with:

- `module`: a dotted Python module name;
- `callable`: a Python function name;
- `parameters`: a complete mapping from Behavior input-port names to Python
  keyword parameter names.

The profile currently supports one direct expected output and JSON-compatible
port values. The caller owns publication and execution. It runs with the
current OS user authority and is not a sandbox. Generation alone does not
create a verified result; generation does not create verification evidence or
a Trust claim.

The checked publication transaction is Linux-only: it uses `renameat2` and
POSIX advisory locking in the installed UCF core. The adapter itself is kept
outside the Python wheel. Current evidence covers one Python function and
pytest 9.1.1, not general Python framework or cross-language generation.
