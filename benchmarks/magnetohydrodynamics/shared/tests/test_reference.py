from __future__ import annotations

import os
import subprocess
from pathlib import Path


SHARED_ROOT = Path(__file__).resolve().parents[1]
FIXTURE_CSV_PATH = SHARED_ROOT / "eval" / "fixtures" / "mhd1d" / "brio_wu_reference.csv"


def _build_reference_solver() -> Path:
    build_dir = SHARED_ROOT / "build"
    subprocess.run(["cmake", "-S", str(SHARED_ROOT), "-B", str(build_dir)], check=True)
    subprocess.run(
        ["cmake", "--build", str(build_dir), "--target", "full_mhd1d_reference"],
        check=True,
    )

    binary_name = (
        "full_mhd1d_reference.exe" if os.name == "nt" else "full_mhd1d_reference"
    )
    binary_path = build_dir / "bin" / binary_name
    assert binary_path.exists()
    return binary_path


def test_shared_reference_solver_matches_fixture(tmp_path: Path) -> None:
    solver_path = _build_reference_solver()
    output_csv_path = tmp_path / "solution.csv"

    completed = subprocess.run(
        [str(solver_path), "200"],
        check=True,
        capture_output=True,
        text=True,
    )
    output_csv_path.write_text(completed.stdout, encoding="utf-8")

    output_rows = output_csv_path.read_text(encoding="utf-8").splitlines()
    reference_rows = FIXTURE_CSV_PATH.read_text(encoding="utf-8").splitlines()

    assert len(output_rows) == len(reference_rows)
    assert output_rows == reference_rows
