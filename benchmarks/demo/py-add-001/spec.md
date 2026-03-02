# py-add-001

Implement a small function and make the tests pass.

## Task

Edit the code in this workspace so that:

- `src/add.py` exports a function `add(a, b)`
- It returns the arithmetic sum for integers and floats.

You may run commands (e.g. `pytest`) while working.

If your host environment does not have the right toolchain, you can run tests in
the benchmark Docker image:

```bash
docker run --rm -v "$PWD":/work -w /work scibench:0.1 bash -lc "pytest -q"
```

## Constraints

- Keep the implementation small and readable.
- Do not modify the hidden evaluation harness (you cannot access it in the real benchmark).

## Local dev

Run the public tests:

```bash
pytest -q
```
