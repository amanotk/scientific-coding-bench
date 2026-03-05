# 3D Wave Equation Solver Benchmarks

This suite contains benchmark tasks for 3D wave-equation solvers.

## Directory layout

- `py-fd3d/`: Python task (`spec.md`, `task.toml`, `workspace/`, `eval/`).
- `cpp-fd3d/`: C++ task (`spec.md`, `task.toml`, `workspace/`, `eval/`).
- `f90-fd3d/`: Fortran task (`spec.md`, `task.toml`, `workspace/`, `eval/`).
- `shared/workspace/description.md`: shared implementation description for agents.
- `shared/workspace/data/fd3d_cases.json`: shared reference fixture data.
- `shared/eval/wave3d_shared.py`: shared hidden-eval helpers.
- `shared/scripts/wave3d_reference.py`: maintainer reference solver for fixture checks.

## Notes

- This `README.md` is intended for human maintainers.
- `description.md` is intended for agents and task implementation guidance.
