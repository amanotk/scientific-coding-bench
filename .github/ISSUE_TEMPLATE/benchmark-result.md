---
name: Benchmark result
about: Publish a completed benchmark run using the canonical result payload
title: "[result] "
labels: ["result", "schema-v1"]
assignees: []
---

# Repository conventions

Use this template only for published benchmark results.

- Keep the issue title prefixed with `[result]`.
- Paste the JSON emitted by `runner/bench.py publish` exactly as generated.
- Do not use this template for bugs, features, or other issue types.
- Add `track:experimental` when the generated payload includes signals or warnings that make the run non-leaderboard-eligible.
- Leave leaderboard-eligible runs marked only with the required result classification and the generated publish labels.

## Paste the generated payload

Replace this block with the exact JSON body from the publish command.

```json
{
  "schema_version": "1.0.0",
  "issue": {
    "title": "<paste generated title>",
    "labels": [
      "result",
      "schema-v1",
      "status:<state>",
      "track:official"
    ]
  },
  "publication": {
    "eligible": true,
    "signals": [],
    "warnings": []
  },
  "run_record": {
    "<paste the canonical run record here>"
  }
}
```

### Check before submitting

- [ ] `schema_version` matches the published record
- [ ] `issue.title` matches the generated publish title
- [ ] `issue.labels` includes the generated publish labels
- [ ] `publication.signals` and `publication.warnings` are unchanged
- [ ] `run_record` is pasted verbatim from the generated payload
- [ ] The issue title begins with `[result]`
