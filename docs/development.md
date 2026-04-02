# Development Guide

This document is for developers maintaining the benchmark harness and task suite.

## Branching Model

- `main`: stable branch, updated via pull requests
- `develop`: primary integration branch for ongoing work
- `feature/<name>`: short-lived feature branches

Merge flow:

1. `feature/<name>` -> `develop`
2. `develop` -> `main`

## Feature Branch Naming

Use `feature/<name>` where `<name>` is descriptive and does not need to be a task id.

Examples:

- `feature/demo`
- `feature/rk2-suite`
- `feature/runner-check-updates`

For task-focused work, descriptive names are preferred, e.g. `feature/demo-py-rk2`.

## CI Policy

CI should run on both branches and PRs targeting them:

- push: `main`, `develop`
- pull_request target: `main`, `develop`

Current policy for CI jobs:

- Real OpenCode smoke tests run in CI by default.
- Keep the non-agent checks deterministic; treat live smoke as an integration
  check that depends on the published SimBench image and runner environment.

Recommended required checks:

- `python3 -m py_compile runner/bench.py`
- `python3 -m unittest -q discover -s tests -p 'test_runner_*.py'`
- `python3 runner/bench.py check`
- formatting checks for Python/C++/Fortran sources

Optional heavier check:

- `docker build -t simbench:0.1 -f docker/Dockerfile .`
- `python3 scripts/build_image.py`

Toolchain image publishing:

- GitHub Actions publishes `ghcr.io/amanotk/simbench:<branch>` on pushes to
  `develop` and `main`.
- CI pulls the published image for runner tests when the toolchain is unchanged.
- Pull request CI tries the head-branch image first, then `develop`, before
  rebuilding locally.
- If `docker/Dockerfile` or `scripts/build_image.py` changes in a branch, CI
  rebuilds `simbench:0.1` locally instead of pulling a stale registry image.

If a developer cannot pull the package directly, authenticate with
`docker login ghcr.io` before pulling from GHCR.

## Local Developer Workflow

Set up host tooling:

```bash
uv sync --extra dev
```

Run local checks before opening PR:

```bash
python3 -m py_compile runner/bench.py
python3 -m unittest -q discover -s tests -p 'test_runner_*.py'
python3 runner/bench.py check
uvx ruff format runner tests
uvx ruff check --fix runner tests
clang-format -i $(git ls-files "*.cpp" "*.hpp" ':!:benchmarks/common/include/**')
uvx fprettify -r benchmarks/demo/f90/workspace/src/*.f90
```

## Branch Protection Recommendations

Apply branch protection to `main` and `develop`:

- require pull requests before merge
- require required CI checks to pass
- optionally require at least one review


## Benchmark Result Publication

Completed benchmark runs can be published for review using the `publish` command.
This section describes the publication workflow, label policy, and review
expectations for maintainers.

### Publication Workflow

1. Run a benchmark task:
   ```bash
   python3 runner/bench.py run sample/opencode.toml demo/py --image simbench:0.1
   ```

2. Validate and render the publication payload:
   ```bash
   python3 runner/bench.py publish runs/<run_id>/demo/py
   ```

3. Create a GitHub issue using the `Benchmark result` template and paste the
   generated body verbatim.

### Label Policy

The publish command generates labels automatically based on run metadata:

| Label | When Applied | Purpose |
|-------|--------------|---------|
| `benchmark-result` | Always | Classifies issue as a benchmark result submission |
| `schema-v1` | Always | Indicates run.json schema version |
| `status-passed` | `status == "passed"` | Run completed successfully |
| `status-failed` | `status != "passed"` | Run did not pass |
| `experimental` | Signals present | Non-leaderboard-eligible run |
| `repo-dirty` | `repo_dirty == true` | Repository had uncommitted changes |

### Review Expectations

**Leaderboard-eligible runs** must meet all criteria:

- `status` is `"passed"`
- `repo_dirty` is `false`
- No publication signals present in the payload (`signals` array is empty)
- `schema_version` matches current supported version (`"1.0.0"`)

Note: the `publication.eligible` field in the payload is always `true`; use the
`signals` array to determine if a run is leaderboard-eligible. Runs with signals
receive the `experimental` label and are not leaderboard candidates.

These runs are candidates for inclusion in the official benchmark leaderboard.

**Experimental runs** are marked with the `experimental` label when:

- `status` is not `"passed"` (e.g., `"failed"`, `"timeout"`)
- `repo_dirty` is `true` (uncommitted changes at completion time)
- Other publication signals are detected

Experimental runs are useful for:

- Development and testing of new tasks
- Regression testing across model versions
- Exploratory benchmarking with known limitations

To make an experimental run leaderboard-eligible:

1. Ensure the repository is clean (`git status` shows no uncommitted changes)
2. Re-run the benchmark with the same configuration
3. Verify the new run has `status: "passed"` and `repo_dirty: false`

### Run Record Schema

The canonical `run.json` schema is defined in `runner/run_record_helpers.py`.
Schema changes require:

- Bumping `schema_version` in the run record helpers
- Updating validation logic in `runner/publish_helpers.py`
- Updating this documentation with the new schema fields
- Ensuring backward compatibility or providing migration guidance

Current schema version: `1.0.0`

The publish command validates required fields in `run.json` and will fail if
the record has missing or invalid fields. Git metadata (commit SHA, branch,
dirty flag) must be valid for publication; runs with unresolved git metadata
cannot be published.

### Testing Publication Helpers

The publish helpers have dedicated tests under `tests/test_runner_publish_helpers.py`.
When modifying publication logic:

1. Run the publish helper tests:
   ```bash
   python3 -m unittest -q tests.test_runner_publish_helpers
   ```

2. Verify schema validation catches invalid records
3. Ensure publication signals are generated correctly
4. Test label generation for all status combinations
5. Verify the payload includes both `body` and `body_payload` fields

Smoke-task agent configs used by tests live under `tests/fixtures/agent_configs/`.
If you need a smoke config while validating publish-related changes, use those
fixture paths rather than the historical `sample/` smoke locations.
