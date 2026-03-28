# Benchmark Run Flow

This document describes what happens when you run a benchmark task using the
current v0 runner.


## Goals

- Isolation: each run uses a fresh work directory copied from the task template.
- Agentic: the solver can run commands/tests while working.
- Hidden eval: authoritative evaluation is not exposed to the solver.
- Docker-first: toolchains are provided by a single unified Docker image.


## Task Layout (v0)

A task lives under `benchmarks/<suite>/<task_id>/`:

- `spec.md`: problem statement shown to the model
- `task.toml`: metadata (e.g. `eval_cmd`, `time_limit_sec`, optional `prompt`)
- `workspace/`: template copied into a per-run workdir (solver edits here)
- `eval/`: evaluation harness (treated as hidden from the solver)
  - `eval/run.sh`: entrypoint; writes `/work/result.json`
  - `eval/tests/`: hidden tests for scoring


## Runner Outputs

Each run creates a directory under `runs/<run_id>/<suite>/<task_id>/`:

- `workdir/`: the isolated workspace copy that is edited and evaluated
- `logs/`: captured stdout/stderr/exit codes
- `logs/agent.docker_cmd.txt` or `logs/agent.host_cmd.txt`: the agent command line
- `logs/eval.docker_cmd.txt`: the eval command line
- `spec.md`, `task.toml`: copies of the task inputs used for traceability
- `result.json`: the evaluation result (copied from `workdir/result.json`)
- `run.json`: the canonical run record with full provenance metadata

`runs/` is gitignored.


## Phase Overview

There are two phases for a benchmark run:

1) Agent phase: model/agent modifies `workdir/` and can execute commands.
2) Eval phase: hidden harness evaluates `workdir/` and writes `result.json`.

The agent phase may run in Docker or on the host depending on the selected
agents TOML (`mode = "docker"` or `"host"`).

The key property is that `benchmarks/.../eval/` is never mounted into the agent
container.


## `bench.py run` (agent solve + eval)

Command:

```bash
python3 runner/bench.py run sample/opencode.toml <suite>/<task_id> --image simbench:0.1
```

What happens:

- A fresh `workdir/` is created by copying `benchmarks/.../workspace/`.
- The runner loads and merges agent settings from:
  - positional single-agent override TOML, and
  - `agents_default.toml`.
- Agent phase runs first (Docker or host mode according to merged config).
- Eval phase then runs in Docker using hidden harness mounted at `/eval`.
- The harness writes `/work/result.json` and the runner copies it to `runs/.../result.json`.


The runner uses the selected TOML to:

- decide which optional host config files to mount into the agent container
- decide what command to run for that agent
- choose `model`

Optional model tuning can be passed through agent TOML `model_options`.
The runner exposes these to agent commands as:

- `BENCH_MODEL_OPTIONS_JSON` (JSON)
- `$BENCH_MODEL_OPTIONS_ARGS` placeholder in agent `cmd` (runner-injected,
  shell-escaped CLI flags)

To run different agents, prepare different TOML files and pass one as the first
positional argument.

Agents can run in two modes:

- `mode: "docker"` (default): runner executes agent CLIs in the image and can mount optional host config files
- `mode: "host"`: runner executes the agent on the host (still evaluates in Docker)


## `bench.py eval` (eval-only)

Command:

```bash
python3 runner/bench.py eval <suite>/<task_id> --workdir /path/to/workdir --image simbench:0.1
```

What happens:

- No agent is run.
- The runner evaluates the provided `--workdir` using hidden harness for task.
- Results and logs are still written to a fresh run directory.


## Networking

Docker runs always use normal network access for both the agent and eval
containers.

If you want to limit model-side web search or similar features, do that through
the selected agent's `model_options` or provider-specific settings rather than a
runner-level Docker network flag.


## Secrets / Credentials

The runner never stores credentials in the repo. Credentials must be provided at
runtime from your host environment.

### How credentials get into the agent container

For the sample OpenCode config (`sample/opencode.toml`), credential handling uses:

1) OpenCode auth file (recommended for local dev)

- If `~/.local/share/opencode/auth.json` exists on the host, the runner bind-mounts
  it into the container and copies it into:

  - `$HOME/.local/share/opencode/auth.json`

This is created by:

```bash
opencode auth login
```

OpenCode config file (optional):

- If `~/.config/opencode/opencode.json` exists, it is mounted into the agent
  container and `OPENCODE_CONFIG` points to it.
- Otherwise, if `~/.config/opencode/opencode.jsonc` exists, it is mounted and
  `OPENCODE_CONFIG` points to that file.

Other agent local files (sample defaults):

- Claude: if `~/.claude/settings.json` exists, it is mounted and copied to
  `$HOME/.claude/settings.json` inside the agent container.
- Codex: if `~/.codex/auth.json` exists, it is mounted and copied to
  `$HOME/.codex/auth.json` inside the agent container.
- Copilot: if `~/.copilot/config.json` exists, it is mounted and copied to
  `$HOME/.copilot/config.json` inside the agent container.

2) Provider environment variables (useful for CI)

- If the following env vars exist on the host, the runner forwards them into the
  agent container:

  - `OPENAI_API_KEY`
  - `ANTHROPIC_API_KEY`
  - `GITHUB_TOKEN`
  - `AZURE_OPENAI_API_KEY`
  - `AZURE_OPENAI_ENDPOINT`
  - `AZURE_OPENAI_API_VERSION`

The forwarded keys are printed to stderr and recorded in:

- `runs/.../logs/agent.forwarded_env.txt`

Assume anything readable in the container can be exfiltrated. The runner keeps
`runs/` free of credentials by design (do not write secrets into `workdir/` and
do not print secrets into logs).


## Result Format (v0)

The eval harness writes `/work/result.json`.

Minimum eval-written fields:

```json
{ "status": "passed|failed", "score": 0.0 }
```

The runner normalizes copied results to include stable top-level metadata:

- `run_id`: runner-generated ID for the run directory
- `started_at`: UTC timestamp when the run started
- `task`: task reference like `demo/py`
- `agent`: agent name for `bench.py run` (for example `opencode`)
- `model`: resolved model for `bench.py run`

When known, the runner also adds:

- `agent_exit_code`: integer exit code, or a sentinel string like `timeout` or `setup_error`
- `eval_exit_code`: integer exit code, or `timeout`

Optional `metrics` may be added for timings, accuracy, etc.

Runner-added timing metrics:

- `agent_inner_sec`: agent command runtime inside the container (excludes Docker startup)
- `eval_inner_sec`: eval command runtime inside the container (excludes Docker startup)

The runner prints a compact terminal summary after evaluation:

- `status`
- `score`
- run metadata (`run_id`, `started_at`, `task`, optional `agent`, optional `model`)
- optional exit codes
- optional `metrics`
- `run_dir`


## Canonical Run Record (run.json)

In addition to `result.json`, the runner writes a canonical `run.json` artifact
that captures authoritative run-time provenance for publication and review.

### run.json vs result.json

- `result.json`: backward-compatible evaluation result used for immediate feedback
  and historical compatibility. Contains task result (`status`, `score`) and
  runner-added metadata.
- `run.json`: canonical run record with full provenance for publication. Contains
  all `result.json` fields plus repository state and completion metadata required
  for benchmark result submission.

### run.json Schema (v1.0.0)

Required fields:

- `schema_version`: string, always `"1.0.0"` for current schema
- `completed_at`: string, UTC ISO-8601 timestamp (`YYYY-MM-DDTHH:MM:SSZ`)
- `repo_commit_sha`: string, 40-character hex git commit SHA
- `repo_branch`: string, git branch name at completion time
- `repo_dirty`: boolean, `true` if repository had uncommitted changes
- `task`: string, task reference (e.g., `demo/py`)
- `status`: string, run outcome (`"passed"` or `"failed"`)
- `score`: number, evaluation score (typically 0.0 to 1.0)

Inherited from `result.json`:

- `run_id`, `started_at`, `agent`, `model`, `metrics`, and other result fields

Example `run.json`:

```json
{
  "schema_version": "1.0.0",
  "completed_at": "2026-03-28T12:34:56Z",
  "repo_commit_sha": "abc123...40chars",
  "repo_branch": "feature/my-benchmark",
  "repo_dirty": false,
  "task": "demo/py",
  "status": "passed",
  "score": 1.0,
  "run_id": "20260328T123456Z-abc123",
  "started_at": "2026-03-28T12:30:00Z",
  "agent": "opencode",
  "model": "gpt-4"
}
```

The `run.json` artifact is written on every run completion, including failure
paths (setup errors, timeouts, eval failures). The publish command validates
required fields and will fail if the record has missing or invalid fields.


## Publish Workflow

After a benchmark run completes, you can render a publication payload for review
and submission using the `publish` command:

```bash
python3 runner/bench.py publish runs/<run_id>/<suite>/<task_id>
```

The publish command:

1. Loads and validates the `run.json` record from the run directory
2. Checks schema compliance and required fields
3. Generates publication signals (e.g., `repo_dirty`, non-passing status)
4. Renders a deterministic issue payload with title, labels, and body

### Publication Signals

The publish command detects signals that affect review classification:

- `repo_dirty`: repository had uncommitted changes at completion time
- `non_passing_status`: run status is not `"passed"`

Runs with signals are marked as **experimental** and receive the `experimental`
label in the generated issue payload. The `publication.eligible` field in the
payload is always `true`; reviewers should check for the presence of signals
to determine if a run is leaderboard-eligible.

### Issue Labels

The publish command generates labels for the GitHub issue:

- `benchmark-result`: classification as a benchmark result submission
- `schema-v1`: schema version of the run record
- `status-<slug>`: normalized status (e.g., `status-passed`, `status-failed`)
- `experimental`: added when signals are present (non-leaderboard-eligible)
- `repo-dirty`: added when `repo_dirty` is `true`

### Publication Payload

The publish command outputs a structured payload:

- `title`: suggested issue title (e.g., `[passed] demo/py @ abc123def456`)
- `labels`: array of labels to apply
- `body`: JSON body string to paste into the issue
- `body_payload`: structured payload object used to render the body
- `warnings`: non-blocking warnings for reviewer attention
- `eligible`: boolean, always `true` (check `signals` for experimental status)
- `signals`: array of detected publication signals (e.g., `repo_dirty`, `non_passing_status`)
- `run_record`: the validated and normalized run record

Use the generated body verbatim when creating a benchmark result issue via the
`Benchmark result` issue template (`.github/ISSUE_TEMPLATE/benchmark-result.md`).

### Review Expectations

**Leaderboard-eligible runs:**

- `status` must be `"passed"`
- `repo_dirty` must be `false`
- No publication signals present
- Labels: `benchmark-result`, `schema-v1`, `status-passed`

**Experimental runs:**

- May have `status` other than `"passed"` or `repo_dirty: true`
- Marked with `experimental` label
- Useful for development, regression testing, or exploratory work
- Not eligible for leaderboard inclusion until re-run under clean conditions


## Logging Mode

The runner prints internal actions (run paths, resolved commands) and streams
process output in real time by default for both phases,
with phase+stream prefixes:

- `[agent:<name>] stdout: ...` and `[agent:<name>] stderr: ...`
- `[eval] stdout: ...` and `[eval] stderr: ...`

When an agent emits JSONL events (for example, Claude stream-json or Codex JSON
mode), the runner renders a compact live timeline for agent stdout
instead of raw JSON lines:

- `[agent:<name>] thinking: ...`
- `[agent:<name>] tool: ...`
- `[agent:<name>] text: ...`

The runner uses per-agent formatting hooks for richer display on supported
agents (currently specialized handlers for Codex and Copilot), while keeping a
generic fallback for other agents.

If a JSON event shape is not recognized yet, the runner falls back to printing
that raw stdout line so streaming visibility is not lost.

The raw agent stdout/stderr streams are still preserved in `runs/.../logs/`.

Verbose logs are grouped into sections to improve readability:

- `RUN SETUP`
- `AGENT PHASE`
- `EVAL PHASE`

Pass `-q` or `--quiet` to suppress these internal logs.

```bash
python3 runner/bench.py -q run sample/opencode.toml <suite>/<task_id>
```
