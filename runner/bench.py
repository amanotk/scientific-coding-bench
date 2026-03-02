#!/usr/bin/env python3

import argparse
import datetime as _dt
import json
import os
import secrets
import shutil
import subprocess
import sys
from typing import Any
from dataclasses import dataclass
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
BENCH_ROOT = REPO_ROOT / "benchmarks"
RUNS_ROOT = REPO_ROOT / "runs"


@dataclass(frozen=True)
class Task:
    suite: str
    task_id: str
    path: Path
    spec_path: Path
    task_json_path: Path
    workspace_tpl: Path
    eval_dir: Path
    meta: dict


def _coerce_text(v: object) -> str:
    if v is None:
        return ""
    if isinstance(v, bytes):
        return v.decode("utf-8", errors="replace")
    return str(v)


def _load_task(suite: str, task_id: str) -> Task:
    task_path = BENCH_ROOT / suite / task_id
    spec_path = task_path / "spec.md"
    task_json_path = task_path / "task.json"
    workspace_tpl = task_path / "workspace"
    eval_dir = task_path / "eval"

    missing = [
        p
        for p in [spec_path, task_json_path, workspace_tpl, eval_dir]
        if not p.exists()
    ]
    if missing:
        msg = "Task is missing required paths:\n" + "\n".join(f"- {p}" for p in missing)
        raise FileNotFoundError(msg)

    meta: dict[str, Any] = json.loads(task_json_path.read_text(encoding="utf-8"))
    return Task(
        suite=suite,
        task_id=task_id,
        path=task_path,
        spec_path=spec_path,
        task_json_path=task_json_path,
        workspace_tpl=workspace_tpl,
        eval_dir=eval_dir,
        meta=meta,
    )


def _iter_tasks():
    if not BENCH_ROOT.exists():
        return
    for suite_dir in sorted([p for p in BENCH_ROOT.iterdir() if p.is_dir()]):
        for task_dir in sorted([p for p in suite_dir.iterdir() if p.is_dir()]):
            if (task_dir / "spec.md").exists() and (task_dir / "task.json").exists():
                yield (suite_dir.name, task_dir.name)


def cmd_list(_args: argparse.Namespace) -> int:
    for suite, task_id in _iter_tasks():
        print(f"{suite}/{task_id}")
    return 0


def _prepare_run_dir(*, task: Task, run_id: str) -> tuple[Path, Path, Path]:
    run_dir = RUNS_ROOT / run_id / task.suite / task.task_id
    workdir = run_dir / "workdir"
    logs_dir = run_dir / "logs"

    workdir.parent.mkdir(parents=True, exist_ok=True)
    logs_dir.mkdir(parents=True, exist_ok=True)

    if workdir.exists():
        shutil.rmtree(workdir)
    shutil.copytree(task.workspace_tpl, workdir)

    (run_dir / "spec.md").write_text(
        task.spec_path.read_text(encoding="utf-8"), encoding="utf-8"
    )
    (run_dir / "task.json").write_text(
        task.task_json_path.read_text(encoding="utf-8"), encoding="utf-8"
    )
    return run_dir, workdir, logs_dir


def _gen_run_id() -> str:
    ts = _dt.datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    return f"{ts}-{secrets.token_hex(4)}"


def _run_docker_eval(
    *,
    image: str,
    workdir: Path,
    eval_dir: Path,
    eval_cmd: str,
    network: str,
    timeout_sec: int,
    extra_env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess:
    uid = os.getuid() if hasattr(os, "getuid") else 1000
    gid = os.getgid() if hasattr(os, "getgid") else 1000

    docker_cmd = [
        "docker",
        "run",
        "--rm",
        "-u",
        f"{uid}:{gid}",
        "-e",
        "HOME=/tmp",
        "-e",
        "OMP_NUM_THREADS=1",
        "-e",
        "OPENBLAS_NUM_THREADS=1",
        "-e",
        "MKL_NUM_THREADS=1",
        "-e",
        "VECLIB_MAXIMUM_THREADS=1",
        "-e",
        "NUMEXPR_NUM_THREADS=1",
        "-v",
        f"{str(workdir)}:/work:rw",
        "-v",
        f"{str(eval_dir)}:/eval:ro",
        "-w",
        "/work",
    ]
    if network == "off":
        docker_cmd += ["--network", "none"]
    elif network == "on":
        pass
    else:
        raise ValueError("network must be 'on' or 'off'")

    if extra_env:
        for k, v in extra_env.items():
            docker_cmd += ["-e", f"{k}={v}"]

    docker_cmd += [image, "bash", "-lc", eval_cmd]

    return subprocess.run(
        docker_cmd,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=timeout_sec,
    )


def _run_docker_shell(
    *, image: str, workdir: Path, network: str, cmd: list[str]
) -> int:
    uid = os.getuid() if hasattr(os, "getuid") else 1000
    gid = os.getgid() if hasattr(os, "getgid") else 1000

    docker_cmd = [
        "docker",
        "run",
        "--rm",
        "-it",
        "-u",
        f"{uid}:{gid}",
        "-e",
        "HOME=/tmp",
        "-e",
        "OMP_NUM_THREADS=1",
        "-e",
        "OPENBLAS_NUM_THREADS=1",
        "-e",
        "MKL_NUM_THREADS=1",
        "-e",
        "VECLIB_MAXIMUM_THREADS=1",
        "-e",
        "NUMEXPR_NUM_THREADS=1",
        "-v",
        f"{str(workdir)}:/work:rw",
        "-w",
        "/work",
    ]
    if network == "off":
        docker_cmd += ["--network", "none"]
    elif network == "on":
        pass
    else:
        raise ValueError("network must be 'on' or 'off'")

    docker_cmd += [image] + cmd
    return subprocess.call(docker_cmd)


def _run_opencode_run_in_docker(
    *,
    image: str,
    workdir: Path,
    run_dir: Path,
    model: str,
    prompt: str,
    network: str,
    timeout_sec: int,
    opencode_bin: Path,
    opencode_auth: Path | None,
    extra_env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess:
    uid = os.getuid() if hasattr(os, "getuid") else 1000
    gid = os.getgid() if hasattr(os, "getgid") else 1000

    docker_cmd: list[str] = [
        "docker",
        "run",
        "--rm",
        "-u",
        f"{uid}:{gid}",
        "-e",
        "HOME=/tmp",
        "-e",
        "OPENCODE_DISABLE_AUTOUPDATE=1",
        "-e",
        f"OPENCODE_MODEL={model}",
        "-v",
        f"{str(workdir)}:/work:rw",
        "-v",
        f"{str(run_dir)}:/run:ro",
        "-v",
        f"{str(opencode_bin)}:/usr/local/bin/opencode:ro",
        "-w",
        "/work",
    ]

    if opencode_auth is not None:
        docker_cmd += ["-v", f"{str(opencode_auth)}:/opencode-auth.json:ro"]

    if network == "off":
        docker_cmd += ["--network", "none"]
    elif network == "on":
        pass
    else:
        raise ValueError("network must be 'on' or 'off'")

    if extra_env:
        for k, v in extra_env.items():
            docker_cmd += ["-e", f"{k}={v}"]

    # Prepare auth (if mounted) and run opencode in non-interactive mode.
    inner = [
        'mkdir -p "$HOME/.local/share/opencode"',
    ]
    if opencode_auth is not None:
        inner.append('cp /opencode-auth.json "$HOME/.local/share/opencode/auth.json"')
    inner.append(
        'opencode run -m "$OPENCODE_MODEL" --dir /work "$(cat /run/prompt.txt)" -f /run/spec.md'
    )
    docker_cmd += [image, "bash", "-lc", " && ".join(inner)]

    return subprocess.run(
        docker_cmd,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=timeout_sec,
    )


def cmd_run(args: argparse.Namespace) -> int:
    if "/" not in args.task:
        print("Task must be in the form <suite>/<task_id>", file=sys.stderr)
        return 2

    suite, task_id = args.task.split("/", 1)
    task = _load_task(suite, task_id)

    eval_cmd = str(task.meta.get("eval_cmd", ""))
    if not eval_cmd:
        print(f"Missing eval_cmd in {task.task_json_path}", file=sys.stderr)
        return 2

    timeout_sec = int(task.meta.get("time_limit_sec", args.timeout_sec))

    run_id = args.run_id or _gen_run_id()
    run_dir, workdir, logs_dir = _prepare_run_dir(task=task, run_id=run_id)

    try:
        proc = _run_docker_eval(
            image=args.image,
            workdir=workdir,
            eval_dir=task.eval_dir,
            eval_cmd=eval_cmd,
            network=args.network,
            timeout_sec=timeout_sec,
        )
    except FileNotFoundError as e:
        print(f"Failed to run docker: {e}", file=sys.stderr)
        return 1
    except subprocess.TimeoutExpired:
        (logs_dir / "eval.stdout.txt").write_text("", encoding="utf-8")
        (logs_dir / "eval.stderr.txt").write_text("Timed out\n", encoding="utf-8")
        print(f"Timed out after {timeout_sec}s", file=sys.stderr)
        return 1

    (logs_dir / "eval.stdout.txt").write_text(proc.stdout, encoding="utf-8")
    (logs_dir / "eval.stderr.txt").write_text(proc.stderr, encoding="utf-8")
    (logs_dir / "eval.exit_code.txt").write_text(
        str(proc.returncode) + "\n", encoding="utf-8"
    )

    final_rc = 0 if proc.returncode == 0 else 1

    # If eval harness wrote a result.json into /work, persist it alongside logs.
    result_path = workdir / "result.json"
    if result_path.exists():
        shutil.copy2(result_path, run_dir / "result.json")
        try:
            result = json.loads((run_dir / "result.json").read_text(encoding="utf-8"))
            status = result.get("status", "unknown")
            score = result.get("score", None)
            print(f"{suite}/{task_id}: status={status} score={score}")
            if status != "passed":
                final_rc = 1
        except Exception:
            print(f"{suite}/{task_id}: wrote result.json")
    else:
        print(f"{suite}/{task_id}: eval completed (no result.json found)")
        final_rc = 1

    print(str(run_dir))
    return final_rc


def cmd_prepare(args: argparse.Namespace) -> int:
    if "/" not in args.task:
        print("Task must be in the form <suite>/<task_id>", file=sys.stderr)
        return 2
    suite, task_id = args.task.split("/", 1)
    task = _load_task(suite, task_id)
    run_id = args.run_id or _gen_run_id()
    run_dir, workdir, _logs_dir = _prepare_run_dir(task=task, run_id=run_id)
    print(str(workdir))
    print(str(run_dir))
    return 0


def cmd_shell(args: argparse.Namespace) -> int:
    if "/" not in args.task:
        print("Task must be in the form <suite>/<task_id>", file=sys.stderr)
        return 2
    suite, task_id = args.task.split("/", 1)
    task = _load_task(suite, task_id)
    run_id = args.run_id or _gen_run_id()
    _run_dir, workdir, _logs_dir = _prepare_run_dir(task=task, run_id=run_id)

    cmd = args.cmd if args.cmd else ["bash"]
    try:
        return _run_docker_shell(
            image=args.image,
            workdir=workdir,
            network=args.network,
            cmd=cmd,
        )
    except FileNotFoundError as e:
        print(f"Failed to run docker: {e}", file=sys.stderr)
        return 1


def cmd_opencode(args: argparse.Namespace) -> int:
    if "/" not in args.task:
        print("Task must be in the form <suite>/<task_id>", file=sys.stderr)
        return 2

    suite, task_id = args.task.split("/", 1)
    task = _load_task(suite, task_id)

    eval_cmd = str(task.meta.get("eval_cmd", ""))
    if not eval_cmd:
        print(f"Missing eval_cmd in {task.task_json_path}", file=sys.stderr)
        return 2

    timeout_sec = int(task.meta.get("time_limit_sec", args.timeout_sec))
    run_id = args.run_id or _gen_run_id()
    run_dir, workdir, logs_dir = _prepare_run_dir(task=task, run_id=run_id)

    default_prompt = (
        "Solve the attached spec. Edit files in the working directory. "
        "Run the public tests while working and make them pass. "
        "If you need a toolchain, run commands via Docker using the image "
        f"{args.image!r}. Example: "
        f'docker run --rm -v "$PWD":/work -w /work {args.image} bash -lc "pytest -q"'
    )

    prompt = ""
    if args.prompt:
        prompt = args.prompt
    else:
        prompt_file = str(task.meta.get("prompt_file", "")).strip()
        if prompt_file:
            p = task.path / prompt_file
            if p.exists():
                prompt = p.read_text(encoding="utf-8").strip()
            else:
                print(f"prompt_file not found: {p}", file=sys.stderr)
                return 2

        if not prompt:
            prompt = str(task.meta.get("prompt", "")).strip()

        if not prompt:
            prompt = default_prompt

    # Persist the prompt so the container doesn't need to receive it via env.
    (run_dir / "prompt.txt").write_text(prompt + "\n", encoding="utf-8")

    opencode_bin_s = shutil.which("opencode")
    if not opencode_bin_s:
        print("opencode is not installed or not on PATH", file=sys.stderr)
        return 1
    opencode_bin = Path(opencode_bin_s)

    opencode_auth = Path.home() / ".local" / "share" / "opencode" / "auth.json"
    if not opencode_auth.exists():
        opencode_auth = None

    pass_env_keys = [
        "OPENAI_API_KEY",
        "ANTHROPIC_API_KEY",
        "OPENROUTER_API_KEY",
        "GITHUB_TOKEN",
        "AZURE_OPENAI_API_KEY",
        "AZURE_OPENAI_ENDPOINT",
        "AZURE_OPENAI_API_VERSION",
    ]
    extra_env: dict[str, str] = {}
    for k in pass_env_keys:
        v = os.environ.get(k)
        if v:
            extra_env[k] = v

    if extra_env:
        keys = ",".join(sorted(extra_env.keys()))
        (logs_dir / "opencode.forwarded_env.txt").write_text(
            keys + "\n", encoding="utf-8"
        )
        print(f"Forwarding env into agent container: {keys}", file=sys.stderr)

    # Run OpenCode in Docker so the agent session is sandboxed similarly to eval.
    try:
        op = _run_opencode_run_in_docker(
            image=args.image,
            workdir=workdir,
            run_dir=run_dir,
            model=args.model,
            prompt=prompt,
            network=args.network,
            timeout_sec=timeout_sec,
            opencode_bin=opencode_bin,
            opencode_auth=opencode_auth,
            extra_env=extra_env,
        )
    except subprocess.TimeoutExpired as e:
        (logs_dir / "opencode.stdout.txt").write_text(
            _coerce_text(e.stdout), encoding="utf-8"
        )
        (logs_dir / "opencode.stderr.txt").write_text(
            _coerce_text(e.stderr) + "\nTimed out\n", encoding="utf-8"
        )
        (logs_dir / "opencode.exit_code.txt").write_text("timeout\n", encoding="utf-8")
        print(f"Timed out after {timeout_sec}s (opencode)", file=sys.stderr)
        print(str(run_dir))
        return 1

    (logs_dir / "opencode.stdout.txt").write_text(op.stdout, encoding="utf-8")
    (logs_dir / "opencode.stderr.txt").write_text(op.stderr, encoding="utf-8")
    (logs_dir / "opencode.exit_code.txt").write_text(
        str(op.returncode) + "\n", encoding="utf-8"
    )
    if op.returncode != 0:
        print(f"opencode failed with exit code {op.returncode}", file=sys.stderr)
        print(f"Logs: {logs_dir}", file=sys.stderr)
        if op.stderr.strip():
            print(op.stderr.strip(), file=sys.stderr)
        print(str(run_dir))
        return 1

    # Evaluate the same workdir using the hidden harness.
    try:
        proc = _run_docker_eval(
            image=args.image,
            workdir=workdir,
            eval_dir=task.eval_dir,
            eval_cmd=eval_cmd,
            network=args.network,
            timeout_sec=timeout_sec,
        )
    except FileNotFoundError as e:
        print(f"Failed to run docker: {e}", file=sys.stderr)
        return 1
    except subprocess.TimeoutExpired:
        (logs_dir / "eval.stdout.txt").write_text("", encoding="utf-8")
        (logs_dir / "eval.stderr.txt").write_text("Timed out\n", encoding="utf-8")
        print(f"Timed out after {timeout_sec}s", file=sys.stderr)
        return 1

    (logs_dir / "eval.stdout.txt").write_text(proc.stdout, encoding="utf-8")
    (logs_dir / "eval.stderr.txt").write_text(proc.stderr, encoding="utf-8")
    (logs_dir / "eval.exit_code.txt").write_text(
        str(proc.returncode) + "\n", encoding="utf-8"
    )

    final_rc = 0
    result_path = workdir / "result.json"
    if result_path.exists():
        shutil.copy2(result_path, run_dir / "result.json")
        try:
            result = json.loads((run_dir / "result.json").read_text(encoding="utf-8"))
            status = result.get("status", "unknown")
            score = result.get("score", None)
            print(f"{suite}/{task_id}: status={status} score={score}")
            if status != "passed":
                final_rc = 1
        except Exception:
            print(f"{suite}/{task_id}: wrote result.json")
            final_rc = 1
    else:
        print(f"{suite}/{task_id}: eval completed (no result.json found)")
        final_rc = 1

    print(str(run_dir))
    return final_rc


def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser(prog="bench")
    sub = p.add_subparsers(dest="cmd", required=True)

    p_list = sub.add_parser("list", help="List available tasks")
    p_list.set_defaults(fn=cmd_list)

    p_run = sub.add_parser("run", help="Run a task eval in Docker")
    p_run.add_argument("task", help="Task in the form <suite>/<task_id>")
    p_run.add_argument("--image", default="scibench:0.1", help="Docker image tag")
    p_run.add_argument("--network", choices=["on", "off"], default="on")
    p_run.add_argument("--timeout-sec", type=int, default=600)
    p_run.add_argument("--run-id", default="")
    p_run.set_defaults(fn=cmd_run)

    p_prepare = sub.add_parser("prepare", help="Create an isolated run workspace")
    p_prepare.add_argument("task", help="Task in the form <suite>/<task_id>")
    p_prepare.add_argument("--run-id", default="")
    p_prepare.set_defaults(fn=cmd_prepare)

    p_shell = sub.add_parser(
        "shell", help="Open an interactive shell in the task workspace"
    )
    p_shell.add_argument("task", help="Task in the form <suite>/<task_id>")
    p_shell.add_argument("--image", default="scibench:0.1", help="Docker image tag")
    p_shell.add_argument("--network", choices=["on", "off"], default="on")
    p_shell.add_argument("--run-id", default="")
    p_shell.add_argument(
        "cmd",
        nargs="*",
        help="Command to run (use `--` before command flags)",
    )
    p_shell.set_defaults(fn=cmd_shell)

    p_op = sub.add_parser(
        "opencode",
        help="Prepare workdir, run OpenCode one-shot, then eval",
    )
    p_op.add_argument("task", help="Task in the form <suite>/<task_id>")
    p_op.add_argument("--model", "-m", default="openai/gpt-5.3-codex")
    p_op.add_argument(
        "--prompt",
        default="",
        help="Override the one-shot message (otherwise uses task.json/default)",
    )
    p_op.add_argument("--image", default="scibench:0.1", help="Docker image tag")
    p_op.add_argument("--network", choices=["on", "off"], default="on")
    p_op.add_argument("--timeout-sec", type=int, default=600)
    p_op.add_argument("--run-id", default="")
    p_op.set_defaults(fn=cmd_opencode)

    args = p.parse_args(argv)
    return int(args.fn(args))


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
