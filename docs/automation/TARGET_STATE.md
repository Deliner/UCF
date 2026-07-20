# UCF target state

## Product promise

UCF is a language-neutral behavior and change control plane for both new and
existing software. It turns desired behavior, discovered implementation facts,
and verification evidence into a traceable graph. It does not attempt to
replace source code, framework-native tests, OpenAPI, or OpenSpec-style change
proposals.

A team can put a legacy project "on UCF rails" without stopping delivery:
discover the system, review inferred candidates, freeze an honest baseline, and
apply stricter rules only to new or touched behavior. A greenfield team can
start from declared behavior and generate the same evidence graph.

## Foundation decision

UCF's Python package is the reference control-plane implementation, not the
universal execution runtime. Embedding every language and framework in that
package would create a Python-centric plugin monolith and make legacy discovery
both brittle and expensive.

The stable center is therefore a versioned, serialized intermediate
representation (IR). An IR is the language-neutral form of a use case, action,
binding, effect, invariant, observation, and evidence record. External adapters
declare capabilities and exchange IR messages with the core. Adapters own
language parsing, framework conventions, build tools, and runtime probes.

The first proof must span materially different stacks rather than several
Python web frameworks:

- Python with FastAPI or a plain CLI;
- TypeScript with a mainstream HTTP framework;
- one compiled ecosystem, initially Java/Spring or Go, selected by an explicit
  adapter spike;
- at least HTTP, CLI, and asynchronous message/event behavior.

Support means passing a shared conformance suite and a brownfield onboarding
scenario. Merely parsing a language or generating a file does not count.

## Brownfield adoption model

Brownfield onboarding has five explicit stages:

1. Inventory collects files, build metadata, public interfaces, tests, and
   runtime observations without claiming intent.
2. Discovery adapters emit evidence records with source location, adapter
   version, timestamp, and confidence.
3. Reconciliation proposes use cases and mappings. A human accepts, edits, or
   rejects uncertain product semantics.
4. Baseline records known coverage, drift, and violations. It never converts
   unknown behavior into verified behavior.
5. Ratchet policies require new and touched behavior to meet stronger gates
   while the remaining legacy baseline shrinks explicitly.

Discovery must be safe, repeatable, and read-only by default. Runtime capture
requires an explicit environment and data-handling decision.

## Change lifecycle

UCF should adopt the useful part of OpenSpec-like workflows rather than compete
with them:

- a proposal explains why a behavior changes;
- a delta records added, modified, and removed behavior;
- an ordered task graph drives implementation;
- verification attaches evidence to each accepted behavior;
- archive preserves the decision and final state.

Free-form proposal text is appropriate for intent and trade-offs. Typed UCF IR
is appropriate for executable behavior, mappings, and evidence. Import/export
boundaries should allow an existing OpenSpec workflow to remain the change
front end.

## Trust model

UCF reports graduated claims:

- `observed`: an adapter found a fact in code or runtime data;
- `declared`: a specification states intended behavior;
- `mapped`: evidence and intent have an explicit relationship;
- `tested`: a named executable check passed against a named artifact;
- `verified`: a precisely scoped property was proven or exhaustively checked
  under recorded assumptions.

No lower level may be displayed as a higher one. Unknown schema fields, broken
references, duplicate identities, and unsupported adapter capabilities are
errors at trust boundaries.

## Definition of product-ready

The project is ready for a stable release when:

- the versioned IR and adapter protocol have compatibility tests;
- three materially different language stacks pass the conformance suite;
- a representative unmodified legacy application can be inventoried, baselined,
  and ratcheted through one behavior change;
- change proposal through archive is demonstrated end to end;
- generated tests are deterministic and executable;
- all repository quality gates and documentation claim checks are green;
- security, compatibility, migration, packaging, and support policies are
  explicit.

Advanced theorem proving, broad IDE integrations, and every possible adapter are
post-foundation work unless evidence shows they are required for this proof.
