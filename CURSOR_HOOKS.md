# Cursor IDE Hooks — AI Agent Discipline System

## 1. Overview

Cursor IDE hooks (beta, available since v1.7+) execute custom scripts at specific
lifecycle events during AI agent operations. They provide a mechanism to enforce
coding standards, prevent lazy patterns, and gate task completion.

- Each hook receives a **JSON payload via stdin** containing metadata such as
  `conversation_id`, `file_path`, `command`, and other event-specific fields.
- **Exit 0** — operation proceeds normally.
- **Exit 1** — agent is **blocked** and receives the script's stdout as an error.

The agent cannot bypass the check. The error message guides it toward the fix.

---

## 2. Hook Configuration

Hooks live in `.cursor/hooks.json` at the project root.

```json
{
  "hooks": {
    "afterFileEdit":        [],
    "beforeReadFile":       [],
    "beforeShellExecution": [],
    "beforeSubmitPrompt":   [],
    "stop":                 []
  }
}
```

Each entry is `{ "script": "path/to/script.sh", "description": "..." }`.

| Event                  | Fires When                     | Key Payload Fields             |
|------------------------|--------------------------------|--------------------------------|
| `afterFileEdit`        | Agent writes/modifies a file   | `conversation_id`, `file_path` |
| `beforeReadFile`       | Agent reads a file             | `conversation_id`, `file_path` |
| `beforeShellExecution` | Agent runs a terminal command  | `conversation_id`, `command`   |
| `beforeSubmitPrompt`   | Agent submits a prompt         | `conversation_id`, `prompt`    |
| `stop`                 | Agent signals task completion  | `conversation_id`              |

---

## 3. Session Tracking Infrastructure

Every downstream hook needs to know which files the agent touched. The
`afterFileEdit` hook below builds that registry.

### `track-session-files.sh`

```bash
#!/usr/bin/env bash
set -euo pipefail

payload=$(cat)
conversation_id=$(echo "$payload" | jq -r '.conversation_id')
file_path=$(echo "$payload" | jq -r '.file_path')

session_dir=".cursor/session_state"
mkdir -p "$session_dir"
session_file="$session_dir/${conversation_id}.txt"

grep -qxF "$file_path" "$session_file" 2>/dev/null || echo "$file_path" >> "$session_file"
exit 0
```

### `get-session-files.sh` (helper used by all other hooks)

```bash
#!/usr/bin/env bash
set -euo pipefail
session_file=".cursor/session_state/${1}.txt"
[[ -f "$session_file" ]] && cat "$session_file"
exit 0
```

---

## 4. Hook: `stop` (Task Completion Enforcement)

The agent cannot finish its turn until all `stop` hooks pass.

### 4.1 Unfinished Tasks Enforcer

Blocks if session markdown files contain unchecked `[ ]` checkboxes.
Agent must mark them `[x]` (done) or `[-]` (skipped).

### 4.2 Lazy Coding Detector

Scans modified files for placeholder patterns: `// ...`, `/* implement later */`,
`// existing code`, `TODO: implement`, `raise NotImplementedError`.

```bash
#!/usr/bin/env bash
set -euo pipefail

payload=$(cat)
cid=$(echo "$payload" | jq -r '.conversation_id')
files=$(.cursor/hooks/get-session-files.sh "$cid")

patterns='// \.\.\.|/\* implement later \*/|// existing code|TODO: implement|raise NotImplementedError'
found=0

while IFS= read -r f; do
  [[ -f "$f" ]] || continue
  matches=$(grep -nEi "$patterns" "$f" 2>/dev/null || true)
  if [[ -n "$matches" ]]; then
    echo "BLOCKED: Lazy placeholder in $f:"
    echo "$matches"
    found=1
  fi
done <<< "$files"

exit "$found"
```

### 4.3 Build Breaker Trap

Runs `ruff check` and `basedpyright` on modified `.py` files. Agent cannot stop
if its code has lint or type errors.

### 4.4 TDD Enforcer

If the agent modified source files but created/updated zero test files, it gets
blocked. Checks for `test_*`, `*_test.*`, and `tests/` path patterns.

### 4.5 Clean Code Enforcer

Scans non-test files for debug artifacts: `console.log()`, `print()`,
`debugger`, `breakpoint()`, `import pdb`. Blocks if any are found.

### 4.6 Orphan File Catcher

Checks if newly created files are imported/referenced anywhere in the project.
Skips `__init__.py`, `conftest.py`, and test files.

### 4.7 Secret Detector

Regex scan for hardcoded credentials (AWS keys `AKIA...`, OpenAI keys `sk-...`,
GitHub tokens `ghp_...`, inline `password=`, `api_key=`, `token=`).
Also useful as an `afterFileEdit` hook for real-time detection.

### 4.8 ENV Sync Enforcer

If new `process.env.*` or `os.environ` references appear, checks they exist in
`.env.example`. Blocks with the missing variable name.

### 4.9 DB Migration Enforcer

If files matching `*models*`, `*schema*`, or `*entities*` were modified, checks
that at least one file matching `*migration*` or `*alembic/versions*` also
appears in the session. Blocks if schema changed without a migration.

### 4.10 UCF Integration

```bash
#!/usr/bin/env bash
set -euo pipefail

payload=$(cat)
cid=$(echo "$payload" | jq -r '.conversation_id')

ucf validate --session-only --session-id "$cid" || { echo "BLOCKED: UCF validation failed."; exit 1; }
ucf drift --detect --session-only --session-id "$cid" || { echo "BLOCKED: UCF drift detected."; exit 1; }
ucf test --affected-only --session-id "$cid" || { echo "BLOCKED: Affected tests failed."; exit 1; }

exit 0
```

---

## 5. Hook: `afterFileEdit` (Real-Time Guards)

Fire immediately after every file write — real-time guardrails.

### 5.1 Anti-Blind-Edit Guard

Ensures the agent read a file before editing it. Uses a `beforeReadFile` hook
that logs reads to `.cursor/session_state/reads/{conversation_id}.txt`.
The `afterFileEdit` hook checks if `file_path` appears in that log.

```bash
#!/usr/bin/env bash
set -euo pipefail

payload=$(cat)
cid=$(echo "$payload" | jq -r '.conversation_id')
file_path=$(echo "$payload" | jq -r '.file_path')

reads_file=".cursor/session_state/reads/${cid}.txt"

if [[ ! -f "$reads_file" ]] || ! grep -qxF "$file_path" "$reads_file"; then
  echo "BLOCKED: You edited $file_path without reading it first."
  exit 1
fi
exit 0
```

### 5.2 Mass Deletion Failsafe

Compares file size to the `HEAD` version. If the file shrunk by more than 40%,
runs `git checkout HEAD -- "$file_path"` to revert and alerts the agent.

```bash
#!/usr/bin/env bash
set -euo pipefail

payload=$(cat)
file_path=$(echo "$payload" | jq -r '.file_path')
[[ -f "$file_path" ]] || exit 0

current=$(wc -c < "$file_path")
original=$(git show "HEAD:$file_path" 2>/dev/null | wc -c || echo 0)
[[ "$original" -eq 0 ]] && exit 0

threshold=$(( original * 60 / 100 ))
if [[ "$current" -lt "$threshold" ]]; then
  git checkout HEAD -- "$file_path"
  echo "BLOCKED: $file_path shrunk >40% ($original→$current bytes). Reverted."
  exit 1
fi
exit 0
```

### 5.3 Complexity Bouncer

Parses edited `.py` files with `awk`, tracking lines per `def` block. If any
function exceeds 60 lines, the hook blocks with the function name and count.

---

## 6. Hook: `beforeReadFile` (Context Protection)

### 6.1 Anti-Bloat Guard

Blocks reading files larger than 50KB to prevent context window pollution.

```bash
#!/usr/bin/env bash
set -euo pipefail

payload=$(cat)
file_path=$(echo "$payload" | jq -r '.file_path')
[[ -f "$file_path" ]] || exit 0

size=$(wc -c < "$file_path")
if [[ "$size" -gt 51200 ]]; then
  echo "BLOCKED: $file_path is $(( size / 1024 ))KB (limit 50KB). Use grep or read a range."
  exit 1
fi
exit 0
```

---

## 7. Hook: `beforeShellExecution` (Terminal Sandbox)

### 7.1 Destructive Command Blocker

Blocks: `rm -rf /`, `reset --hard`, `push --force`/`push -f`, `DROP TABLE`,
`dd if=`, `chmod -R 777`, and similar patterns via regex matching on the
`command` field.

### 7.2 Infinite Loop Breaker

Tracks command hashes per session. If the same command appears 3+ times in the
failure log, it blocks with a "change strategy" message.

```bash
#!/usr/bin/env bash
set -euo pipefail

payload=$(cat)
cid=$(echo "$payload" | jq -r '.conversation_id')
command=$(echo "$payload" | jq -r '.command')

fail_dir=".cursor/session_state/failures"
mkdir -p "$fail_dir"
fail_file="$fail_dir/${cid}.log"
cmd_hash=$(echo "$command" | md5sum | cut -d' ' -f1)

fail_count=$(grep -c "^${cmd_hash}$" "$fail_file" 2>/dev/null || echo 0)
if [[ "$fail_count" -ge 3 ]]; then
  echo "BLOCKED: Command failed $fail_count times. Change strategy."
  exit 1
fi

echo "$cmd_hash" >> "$fail_file"
exit 0
```

### 7.3 Global Test Blocker

Blocks bare test commands (`pytest`, `jest`, `npm test`, `yarn test`) that run
the entire suite. Requires specifying a target file.

---

## 8. Hook: `beforeSubmitPrompt` (Context Injection)

### 8.1 Dynamic Context Memento

Reads `.cursor/session_state/{conversation_id}_plan.md` and prepends a
`<SYSTEM_MEMENTO>` block to the prompt, preventing context drift in long
conversations. Uses `jq --arg` to inject the plan into the prompt field.

```bash
#!/usr/bin/env bash
set -euo pipefail

payload=$(cat)
cid=$(echo "$payload" | jq -r '.conversation_id')
plan_file=".cursor/session_state/${cid}_plan.md"

if [[ -f "$plan_file" ]]; then
  memento="<SYSTEM_MEMENTO>$(cat "$plan_file")</SYSTEM_MEMENTO>"
  echo "$payload" | jq --arg m "$memento" '.prompt = $m + "\n\n" + .prompt'
else
  echo "$payload"
fi
exit 0
```

---

## 9. Git Pre-commit Hooks (Complementary)

Standard `.git/hooks/pre-commit` hooks that guard the commit boundary.

### 9.1 Unfinished Tasks Blocker

Same logic as section 4.1 but scoped to `git diff --cached --name-only *.md`.
Prevents committing markdown files with open `[ ]` checkboxes.

### 9.2 Dependency Lock

Checks if newly added packages (from `requirements*.txt` or `package.json`
diffs) appear in `.cursor/approved-dependencies.txt`. Blocks unapproved deps.

---

## 10. Full `hooks.json`

```json
{
  "hooks": {
    "afterFileEdit": [
      { "script": ".cursor/hooks/track-session-files.sh" },
      { "script": ".cursor/hooks/anti-blind-edit.sh" },
      { "script": ".cursor/hooks/mass-deletion-failsafe.sh" },
      { "script": ".cursor/hooks/complexity-bouncer.sh" },
      { "script": ".cursor/hooks/secret-detector.sh" }
    ],
    "beforeReadFile": [
      { "script": ".cursor/hooks/log-reads.sh" },
      { "script": ".cursor/hooks/anti-bloat-guard.sh" }
    ],
    "beforeShellExecution": [
      { "script": ".cursor/hooks/destructive-command-blocker.sh" },
      { "script": ".cursor/hooks/infinite-loop-breaker.sh" },
      { "script": ".cursor/hooks/global-test-blocker.sh" }
    ],
    "beforeSubmitPrompt": [
      { "script": ".cursor/hooks/dynamic-context-memento.sh" }
    ],
    "stop": [
      { "script": ".cursor/hooks/unfinished-tasks.sh" },
      { "script": ".cursor/hooks/lazy-coding-detector.sh" },
      { "script": ".cursor/hooks/build-breaker-trap.sh" },
      { "script": ".cursor/hooks/tdd-enforcer.sh" },
      { "script": ".cursor/hooks/clean-code-enforcer.sh" },
      { "script": ".cursor/hooks/orphan-file-catcher.sh" },
      { "script": ".cursor/hooks/secret-detector.sh" },
      { "script": ".cursor/hooks/env-sync-enforcer.sh" },
      { "script": ".cursor/hooks/db-migration-enforcer.sh" },
      { "script": ".cursor/hooks/ucf-integration.sh" }
    ]
  }
}
```

---

## 11. Script Template

```bash
#!/usr/bin/env bash
set -euo pipefail

payload=$(cat)
conversation_id=$(echo "$payload" | jq -r '.conversation_id')
file_path=$(echo "$payload" | jq -r '.file_path // empty')
command=$(echo "$payload" | jq -r '.command // empty')

session_files=$(.cursor/hooks/get-session-files.sh "$conversation_id")

# --- Check logic here ---

exit 0

# To block:
# echo "BLOCKED: Reason."
# exit 1
```

**Conventions:**

- `set -euo pipefail` — hooks must fail loudly on unexpected errors.
- Read full payload with `cat` before accessing fields via `jq`.
- Use `jq -r '.field // empty'` for optional fields.
- Prefix errors with `BLOCKED:` so the agent sees the gate clearly.
- Scope checks to session files to avoid false positives from pre-existing issues.
- Keep hooks fast — they run synchronously and block the agent.
