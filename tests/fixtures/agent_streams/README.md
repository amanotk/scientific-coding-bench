# Agent Stream Golden Files

These fixtures capture real agent CLI stdout/stderr so parser and pretty-stream
tests can replay provider-specific output without requiring live auth in CI.

Current fixtures:

- `codex_smoke.stdout.txt`
- `codex_smoke.stderr.txt`
- `claude_smoke.stdout.txt`
- `claude_smoke.stderr.txt`

To refresh them after a CLI or output-format change:

```bash
python3 runner/bench.py run sample/codex.toml test:smoke/py --image simbench:0.1 --result-dir /tmp/simbench-codex-capture
python3 runner/bench.py run sample/claude.toml test:smoke/py --image simbench:0.1 --result-dir /tmp/simbench-claude-capture
```

If your local Claude setup uses a different supported model/backend, run with a
temporary agent TOML that selects that model, for example:

```bash
cat >/tmp/claude-capture.toml <<'EOF'
version = 1
name = "claude"
model = "qwen3.5-plus"
EOF

python3 runner/bench.py run /tmp/claude-capture.toml test:smoke/py --image simbench:0.1 --result-dir /tmp/simbench-claude-capture
```

Then copy the captured logs into this directory:

```bash
cp /tmp/simbench-codex-capture/logs/agent.stdout.txt tests/fixtures/agent_streams/codex_smoke.stdout.txt
cp /tmp/simbench-codex-capture/logs/agent.stderr.txt tests/fixtures/agent_streams/codex_smoke.stderr.txt
cp /tmp/simbench-claude-capture/logs/agent.stdout.txt tests/fixtures/agent_streams/claude_smoke.stdout.txt
cp /tmp/simbench-claude-capture/logs/agent.stderr.txt tests/fixtures/agent_streams/claude_smoke.stderr.txt
```

After updating fixtures, run:

```bash
python3 -m unittest -q tests.test_runner_bench
```
