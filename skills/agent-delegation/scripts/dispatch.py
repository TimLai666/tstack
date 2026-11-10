#!/usr/bin/env python3
"""Dispatch from policy.json. Python 3.9+, Windows/macOS/Linux, stdlib only."""
import argparse
import contextlib
import errno
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import uuid

if os.name == "nt":
    import importlib.util
    import msvcrt
    _spec = importlib.util.spec_from_file_location("windows_runtime", Path(__file__).with_name("windows_runtime.py"))
    windows = importlib.util.module_from_spec(_spec)
    _spec.loader.exec_module(windows)
else:
    import fcntl

POLICY_PATH = Path(__file__).with_name("policy.json")
REMINDER = "Check lessons and experience through the project-memory workflow: search for duplicates, record, and read back to confirm."
MARKER = "You are a dispatched worker. Do not dispatch any agent or CLI. Do the work yourself."
HOST_ENV = {"codex": "CODEX_THREAD_ID", "claude": "CLAUDECODE",
            "agy": "ANTIGRAVITY_AGENT", "opencode": "OPENCODE"}
NATIVE_TOOLS = {"codex": "Codex built-in subagent", "claude": "Agent",
                "copilot": "Copilot built-in subagent (Auto)",
                "opencode": "OpenCode built-in subagent", "agy": "Antigravity built-in subagent"}


class DispatchError(Exception):
    """An invalid request or unsafe continuation; never starts another worker."""


class NotStarted(DispatchError):
    """No worker was launched for this level, so the same level may be retried."""


ACTIVE = ("starting", "new", "running")
NOT_INSTALLED_FILE = "not-installed.cache"  # Not *.json: the registry scan reads every *.json as a dispatch.
NOT_INSTALLED_TTL = 7 * 86400

def text_value(value, name):
    if not isinstance(value, str) or not value.strip() or "\0" in value:
        raise DispatchError(name + " must be a non-empty string and must not contain NUL")
    return value


def strings(value, name):
    if not isinstance(value, list):
        raise DispatchError(name + " must be a string array")
    for item in value:
        text_value(item, name)
    return value


def within(path, root):
    return path == root or root in path.parents


def overlap(a, b):
    return within(Path(a), Path(b)) or within(Path(b), Path(a))


def validate_host(host, policy):
    if not isinstance(host, str) or host not in policy["hosts"]:
        raise DispatchError("host must be one of " + ", ".join(policy["hosts"]))
    detected = [name for name, key in HOST_ENV.items() if os.environ.get(key)]
    if len(detected) > 1:
        raise DispatchError("Multiple host identifiers found; find and clear the inherited identifiers first: " + ", ".join(detected))
    if detected and detected[0] != host:
        raise DispatchError("host conflicts with the actual host identifier: " + detected[0])


def scoped_path(raw, project, sandbox=None):
    text_value(raw, "file path")
    p = Path(raw)
    if any(c in raw for c in "*?[]") or ".." in p.parts or ".git" in p.parts:
        raise DispatchError("A file path must not contain wildcards, .. or .git: " + raw)
    if p.is_absolute() and sandbox is None:
        raise DispatchError("allowed_files/test_files must be project-relative paths: " + raw)
    resolved = (p if p.is_absolute() else project / p).resolve()
    root = sandbox or project
    if not within(resolved, root) or (sandbox is None and resolved == project):
        raise DispatchError("A file path is outside the allowed directory: " + raw)
    if within(resolved, project) and ".git" in resolved.relative_to(project).parts:
        raise DispatchError("A file path must not point into .git through a symlink: " + raw)
    return str(resolved)


def validate_request(r, policy):
    required = ("host", "task_type", "project_dir", "role", "prompt",
                "project_memory", "allowed_files", "verification")
    if not isinstance(r, dict):
        raise DispatchError("request must be a JSON object")
    missing = [key for key in required if key not in r]
    if missing:
        raise DispatchError("Missing required fields: " + ", ".join(missing))
    validate_host(r["host"], policy)
    kind = text_value(r["task_type"], "task_type")
    if kind not in policy["tasks"]:
        raise DispatchError("Unknown task_type; use list-types to look it up: " + kind)
    for key in ("project_dir", "role", "prompt"):
        text_value(r[key], key)
    project = Path(r["project_dir"]).expanduser().resolve(strict=True)
    if not project.is_dir():
        raise DispatchError("project_dir must be a directory")
    r["project_dir"] = str(project)
    for key in ("allowed_files", "verification"):
        strings(r[key], key)
    strings(r.get("test_files", []), "test_files")
    if not isinstance(r["project_memory"], list):
        raise DispatchError("project_memory must be an array; fill [] only after confirming there are no relevant lessons")
    for lesson in r["project_memory"]:
        if not isinstance(lesson, dict):
            raise DispatchError("Each project_memory item must be an object")
        for key in ("condition", "lesson", "source"):
            text_value(lesson.get(key), "project_memory." + key)
    models = r.get("models", {})
    if not isinstance(models, dict):
        raise DispatchError("models must be an object of model names available for each tool")
    if models:
        text_value(r.get("model_source"), "model_source")
    for tool, catalog in models.items():
        if tool not in policy["hosts"]:
            raise DispatchError("models contains an unknown tool: " + str(tool))
        strings(catalog, "models." + tool)
    task = policy["tasks"][kind]
    if task["access"] == "read" and r["allowed_files"]:
        raise DispatchError("allowed_files must be [] for a read-only task")
    sandbox = None
    if task["access"] == "sandbox":
        raw = text_value(r.get("sandbox_dir"), "sandbox_dir")
        sandbox = Path(raw).expanduser()
        sandbox = (sandbox if sandbox.is_absolute() else project / sandbox).resolve(strict=True)
        if not sandbox.is_dir() or within(project, sandbox):
            raise DispatchError("sandbox_dir must be a dedicated sandbox and must not contain the whole project")
        r["sandbox_dir"] = str(sandbox)
    elif r.get("sandbox_dir") is not None:
        raise DispatchError("Only sandboxed task types (research, acceptance) accept sandbox_dir")
    paths = [scoped_path(p, project, sandbox) for p in r["allowed_files"]]
    tests = [scoped_path(p, project) for p in r.get("test_files", [])]
    if task["access"] == "implementation" and any(overlap(a, b) for a in paths for b in tests):
        raise DispatchError("allowed_files overlaps the protected test_files")
    if "difficult_implementation" in r and not isinstance(r["difficult_implementation"], bool):
        raise DispatchError("difficult_implementation must be a boolean")
    if "opencode_failure_evidence" in r:
        text_value(r["opencode_failure_evidence"], "opencode_failure_evidence")
        if kind not in ("testing", "implementation") or r.get("difficult_implementation") is not True:
            raise DispatchError("The OpenCode exception applies only to a difficult implementation slot with evidence of a real failure of the same task")
    if "effort" in r:
        if r["effort"] not in ("medium", "high", "xhigh"):
            raise DispatchError("effort must be medium, high or xhigh")
        if r["effort"] != "medium":
            text_value(r.get("effort_reason"), "effort_reason")
    return r, paths or ([str(sandbox)] if sandbox else [])


def check_level(level, count):
    if level is not None and not 1 <= level <= count:
        raise DispatchError(f"Level out of range: this task type has only {count} levels; level must be between 1 and {count}, and the input was {level}.")


def version(model):
    match = re.search(r"(?:gpt-|claude-(?:haiku-|sonnet-|opus-)?|gemini-)(\d+)(?:[.-](\d+))?", model.lower())
    return tuple(int(x or 0) for x in match.groups()) if match else (0, 0)


def select_model(spec, catalog):
    tool, family = spec["tool"], spec["family"]
    minimum = tuple(map(int, spec.get("minimum", "0.0").split(".")))
    if family == "auto":
        return "auto"
    if family == "free":
        candidates = [m for m in catalog if m.startswith("opencode/")]
        return "opencode/big-pickle" if "opencode/big-pickle" in candidates else (sorted(candidates)[-1] if candidates else None)
    if family == "gemini-flash-medium":
        candidates = [m for m in catalog if re.fullmatch(r"gemini-[\w.-]+-flash-medium", m, re.I)]
    elif tool == "codex":
        candidates = [m for m in catalog if re.fullmatch(r"gpt-\d+(?:\.\d+)?-" + family, m) and version(m) >= minimum]
    else:
        candidates = [m for m in catalog if re.fullmatch(r"claude-" + family + r"(?:-[\w.-]+)?", m, re.I) and version(m) >= minimum]
    return max(candidates, key=lambda m: (version(m), m)) if candidates else None


def build_prompt(r, task, state):
    scope = r["allowed_files"]
    lines = [MARKER, "Role: " + r["role"], "Project directory: " + r["project_dir"]]
    if task["access"] == "sandbox":
        lines += ["Sandbox directory: " + r["sandbox_dir"],
                  "No project file may be modified. Write and run things only inside the sandbox directory, and report every file, process and setting you changed."]
    if not scope and task["access"] != "sandbox":
        lines += ["Files you may and may not change: Do not modify any project file. A throwaway script that reproduces a problem may be kept only in a temporary directory outside the project and must be listed in the report."]
    else:
        lines += ["Files you may and may not change: " + json.dumps(scope or [r["sandbox_dir"]], ensure_ascii=False),
                  "Paths not listed must not be modified. Paths are relative to the project directory; an absolute sandbox path is used as given."]
    if task["access"] == "tests":
        lines.append("Write tests only. Do not write the implementation.")
    elif task["access"] == "implementation":
        lines += ["Do not modify the test files. If you think a test is wrong, stop and report.", "Protected test files: " + json.dumps(r.get("test_files", []), ensure_ascii=False)]
    lines += ["Task and acceptance:\n" + r["prompt"], "Related Project Memory:"]
    for lesson in r["project_memory"]:
        lines += ["Condition: " + lesson["condition"], "Confirmed lesson: " + lesson["lesson"], "Source: " + lesson["source"]]
    if not r["project_memory"]:
        lines.append("None (the main agent already searched and filtered).")
    lines += ["Verification commands to run:", *(r["verification"] or ["No runnable commands; provide checkable evidence that meets the task's acceptance criteria."]),
              "Report format: which files changed, the basis for each conclusion, uncertainties, verification results and unverified items.",
              "Report coverage: how many items should be handled, how many were actually handled, the reasons for anything unfinished, and any sources or data not obtained.",
              "Do not output tokens, passwords, keys or configuration values; report only names and where they are.",
              "Lessons and experience from this work: the situation it applies to, failed approaches, confirmed cause, effective approach and verification evidence.",
              "Mark guesses and uncertainties clearly. If there are no new lessons, write \"none\"; do not pad the report. When an old lesson does not apply, include its original key, how the conditions differ, and the verification result.",
              "The main agent verifies and records lessons in Project Memory; do not write to project memory yourself.",
              "Do not commit, stash or reset."]
    if state.get("feedback"):
        lines.append("Continuation information verified by the main agent:")
        for feedback in state["feedback"]:
            lines += ["Previous outcome: " + feedback["outcome"], "Reason and evidence: " + feedback["reason"], feedback.get("feedback", "")]
    return "\n".join(lines)


def private_file(path):
    if path.is_symlink():
        raise DispatchError("A state file must not be a symlink: " + str(path))
    fd = os.open(path, os.O_RDWR | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0), 0o600)
    if os.name == "nt":
        try:
            windows.ensure_private(path)
        except BaseException:
            os.close(fd)
            raise
    elif os.fstat(fd).st_mode & 0o077:
        os.close(fd)
        raise DispatchError("Existing state file permissions must be 0600: " + str(path))
    return os.fdopen(fd, "r+", encoding="utf-8")


@contextlib.contextmanager
def lock_file(path, blocking=True):
    with private_file(path) as handle:
        if os.name == "nt":
            while True:
                try:
                    handle.seek(0)
                    msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
                    break
                except OSError as exc:
                    if exc.errno not in (errno.EACCES, errno.EAGAIN, errno.EDEADLK):
                        raise
                    if not blocking:
                        raise DispatchError("This dispatch is still running and cannot be resumed concurrently") from exc
                    time.sleep(.05)
            try:
                yield
            finally:
                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            return
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | (0 if blocking else fcntl.LOCK_NB))
        except BlockingIOError:
            raise DispatchError("This dispatch is still running and cannot be resumed concurrently")
        yield


def atomic_write(path, data):
    if path.is_symlink():
        raise DispatchError("A state file must not be a symlink")
    fd, temporary = tempfile.mkstemp(prefix=".dispatch-", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            if os.name == "nt":
                windows.ensure_private(Path(temporary))
            json.dump(data, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        with contextlib.suppress(FileNotFoundError):
            os.unlink(temporary)


def default_state_directory():
    if os.name == "nt":
        return Path(os.environ.get("LOCALAPPDATA", str(Path.home() / "AppData/Local"))) / "agent-delegation"
    return Path(os.environ.get("XDG_STATE_HOME", str(Path.home() / ".local/state"))) / "agent-delegation"


def state_directory(raw, project):
    path = Path(raw).expanduser() if raw else default_state_directory()
    if path.is_symlink():
        raise DispatchError("state-dir must not be a symlink")
    if os.name == "nt" and path.exists():
        windows.ensure_private(path)
    path = path.resolve()
    if within(path, Path(project)):
        raise DispatchError("state-dir must be outside the project")
    if os.name == "nt":
        windows.ensure_private(path, directory=True)
        return path
    path.mkdir(parents=True, mode=0o700, exist_ok=True)
    if path.stat().st_mode & 0o077:
        raise DispatchError("An existing state-dir must be a dedicated private directory (0700); its permissions will not be modified")
    return path


def alive(pid):
    if not isinstance(pid, int) or pid < 1:
        return False
    if os.name == "nt":
        return windows.alive(pid)
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True


def path_fingerprint():
    return hashlib.sha256(os.environ.get("PATH", "").encode("utf-8", "surrogateescape")).hexdigest()


def read_not_installed(root):
    try:
        data = json.loads((root / NOT_INSTALLED_FILE).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def known_not_installed(root, tool):
    """The main agent's earlier confirmation, while PATH is unchanged, recent and the command still absent."""
    entry = read_not_installed(root).get(tool)
    if not isinstance(entry, dict) or entry.get("path") != path_fingerprint():
        return None
    age = time.time() - entry.get("verified_at", 0)
    if not 0 <= age <= NOT_INSTALLED_TTL or shutil.which(tool):
        return None
    return entry


def record_not_installed(root, tool, evidence):
    with lock_file(root / ".not-installed.lock"):
        data = read_not_installed(root)
        data[tool] = {"path": path_fingerprint(), "verified_at": time.time(), "evidence": evidence}
        atomic_write(root / NOT_INSTALLED_FILE, data)


def claim(root, path, state, spec, write_paths, native, timeout):
    deadline = time.monotonic() + timeout
    while True:
        if stop_requested(root, state):
            raise NotStarted("The main agent cancelled this dispatch; no worker was started.")
        with lock_file(root / ".registry.lock"):
            leases = []
            for other_path in root.glob("*.json"):
                if other_path == path:
                    continue
                if os.name == "nt":
                    windows.ensure_private(other_path)
                other = json.loads(other_path.read_text(encoding="utf-8"))
                # Built-in subagent handoffs launch nothing this script can watch, so only external workers hold leases.
                active = other.get("cleanup_pending") or (
                    other.get("status") == "running" and
                    (alive(other.get("owner_pid")) or alive(other.get("child_pid"))))
                if active:
                    leases.append(other)
            slots = sum(other.get("current_tool") == spec["tool"] for other in leases)
            conflict = any(overlap(a, b) for other in leases for a in write_paths for b in other.get("write_paths", []))
            if slots < 3 and not conflict:
                state.update(status="native_required" if native else "running", owner_pid=os.getpid(),
                             child_pid=None, current_tool=spec["tool"], write_paths=[] if native else write_paths)
                atomic_write(path, state)
                return
        if time.monotonic() >= deadline:
            raise NotStarted("Timed out waiting for a same-file write or the limit of three concurrent CLI runs; no new worker was started. Dispatch record: " + state["dispatch_id"] + ", retry the same level with --outcome dispatch-failed after the slot frees")
        time.sleep(0.05)


def stop_path(root, state):
    return root / (state["dispatch_id"] + ".stop")


def stop_requested(root, state):
    run = (state.get("run") or {}).get("id")
    try:
        return bool(run) and stop_path(root, state).read_text(encoding="utf-8").strip() == run
    except OSError:
        return False


def snapshot(r, write_paths):
    """Hash all working files, including ignored files and an external sandbox."""
    project = Path(r["project_dir"])
    paths = set()
    deadline = time.monotonic() + 30
    try:
        result = subprocess.run(["git", "-C", str(project), "ls-files", "--cached", "--others", "-z"],
                                capture_output=True, timeout=20)
        if result.returncode:
            return None
        paths.update(project / os.fsdecode(name) for name in result.stdout.split(b"\0") if name)
        # Git represents submodules and nested repositories as directories.
        for path in list(paths):
            if path.is_dir() and not path.is_symlink():
                for child in path.rglob("*"):
                    if time.monotonic() >= deadline:
                        return None
                    paths.add(child)
        for raw in write_paths:
            path = Path(raw)
            paths.add(path)
            if path.is_dir() and not path.is_symlink():
                paths.update(path.rglob("*"))
        digest = hashlib.sha256()
        for args in (["rev-parse", "--verify", "HEAD"], ["status", "--porcelain", "-z"]):
            metadata = subprocess.run(["git", "-C", str(project), *args], capture_output=True, timeout=10)
            digest.update(metadata.stdout)
            digest.update(str(metadata.returncode).encode())
        for path in sorted(paths):
            if time.monotonic() >= deadline:
                return None
            digest.update(os.fsencode(path))
            if path.is_symlink():
                digest.update(b"symlink:" + os.fsencode(os.readlink(path)))
            elif path.is_file():
                digest.update(b"file:")
                digest.update(str(path.stat().st_mode).encode())
                with path.open("rb") as handle:
                    for block in iter(lambda: handle.read(1024 * 1024), b""):
                        if time.monotonic() >= deadline:
                            return None
                        digest.update(block)
            elif path.is_dir():
                digest.update(b"directory")
            elif not path.exists():
                digest.update(b"missing")
            else:
                return None
        return digest.hexdigest()
    except (OSError, subprocess.TimeoutExpired):
        return None


def group_live(pgid):
    """False only after a successful process query finds no executable group members."""
    if not isinstance(pgid, int) or pgid < 1:
        return None
    if os.name == "nt":
        return windows.group_live(pgid)
    try:
        result = subprocess.run(["ps", "-A", "-o", "pgid=,stat="], capture_output=True, text=True, timeout=5)
        if result.returncode:
            return None
        for line in result.stdout.splitlines():
            fields = line.split()
            if len(fields) != 2 or not fields[0].isdigit():
                return None
            if int(fields[0]) == pgid and not fields[1].startswith(("Z", "X")):
                return True
        return False
    except (OSError, subprocess.TimeoutExpired):
        return None


def signal_group(pgid, signum):
    try:
        os.killpg(pgid, signum)
    except ProcessLookupError:
        pass
    except PermissionError as exc:
        # A group can disappear between TERM and KILL. Never ignore a live or unknown group.
        if group_live(pgid) is not False:
            raise DispatchError(f"Could not stop process group {pgid}; the worker is not confirmed stopped: {exc}")


def stop_group(pgid, proc=None):
    signal_group(pgid, signal.SIGTERM)
    if proc is not None:
        with contextlib.suppress(subprocess.TimeoutExpired):
            proc.wait(timeout=2)
    else:
        deadline = time.monotonic() + 2
        while group_live(pgid) is not False and time.monotonic() < deadline:
            time.sleep(0.05)
    if group_live(pgid) is not False:
        signal_group(pgid, signal.SIGKILL)
    deadline = time.monotonic() + 2
    while group_live(pgid) is not False:
        if time.monotonic() >= deadline:
            raise DispatchError(f"Process group {pgid} is not confirmed stopped; keeping the dispatch slot for the main agent to check")
        time.sleep(0.05)


def terminate(proc):
    if os.name == "nt":
        return windows.terminate(proc)
    stop_group(proc.pid, proc)
    proc.wait()


def execute(argv, cwd, root, name, timeout, state, path, fatal=None):
    stdout_path, stderr_path = root / (name + ".stdout.log"), root / (name + ".stderr.log")
    result = {"argv": argv, "returncode": None, "timeout": False, "interrupted": False,
              "launch_error": False, "stdout_path": str(stdout_path), "stderr_path": str(stderr_path)}
    proc = None
    with private_file(stdout_path) as out, private_file(stderr_path) as err:
        try:
            if os.name == "nt":
                proc = windows.start(argv, cwd, out, err)
                state.update(cleanup_pending=True, process_group=proc.pid)
            else:
                proc = subprocess.Popen(argv, cwd=cwd, stdin=subprocess.DEVNULL, stdout=out, stderr=err, start_new_session=True)
                state["process_group"] = proc.pid
            state.update(child_pid=proc.pid, current_log={"stdout": str(stdout_path), "stderr": str(stderr_path)})
            atomic_write(path, state)
            if os.name == "nt":
                windows.release(proc)
            deadline = time.monotonic() + timeout
            while True:
                try:
                    proc.wait(timeout=max(0, min(1, deadline - time.monotonic())))
                    break
                except subprocess.TimeoutExpired:
                    if stop_requested(root, state):
                        result.update(interrupted=True, cancelled=True)
                        break
                    failure = fatal(stdout_path, stderr_path) if fatal else None
                    if failure:
                        result["fatal_error"] = failure
                        break
                    if time.monotonic() >= deadline:
                        raise
            result["returncode"] = proc.returncode
        except subprocess.TimeoutExpired:
            result["timeout"] = True
        except KeyboardInterrupt:
            result["interrupted"] = True
        except OSError as exc:
            if proc is not None:
                raise
            result["launch_error"] = exc.errno in (errno.ENOENT, errno.EACCES, errno.ENOEXEC)
            err.write(str(exc))
            result["returncode"] = 127
        finally:
            if proc is not None:
                state.update(cleanup_pending=True, process_group=proc.pid)
                atomic_write(path, state)
                try:
                    terminate(proc)
                except (DispatchError, OSError) as exc:
                    result["cleanup_error"] = str(exc)
                else:
                    state.update(cleanup_pending=False, process_group=None, child_pid=None)
                result["cleanup_pending"] = state["cleanup_pending"]
                state["current_log"] = None
                atomic_write(path, state)
            else:
                state.update(child_pid=None, current_log=None)
    with stdout_path.open(encoding="utf-8", errors="replace") as handle:
        result["output"] = handle.read(65536)
    with stderr_path.open(encoding="utf-8", errors="replace") as handle:
        result["error"] = handle.read(65536)
    result["output_excerpt"] = stdout_path.stat().st_size > 65536 or stderr_path.stat().st_size > 65536
    return result


def error_event(output):
    errors = []
    for line in output.splitlines():
        try:
            item = json.loads(line)
            if isinstance(item, dict) and (item.get("type") == "error" or item.get("is_error") is True):
                errors.append(item)
        except ValueError:
            pass
    return errors


def opencode_stalled(stdout_path, stderr_path, stall):
    """The main agent's last act was a logged stream error, then nothing for `stall` seconds.

    `opencode run` retries recoverable provider errors on its own, but after a non-retryable one it
    neither prints nor exits. Only the silence after the error is judged, never the error text.
    """
    try:
        last = ""
        with open(stderr_path, encoding="utf-8", errors="replace") as handle:
            for line in handle:
                if line.strip():
                    last = line.strip()
        error_written = os.stat(stderr_path).st_mtime
        if 'message="stream error"' not in last or "agent=title" in last or os.stat(stdout_path).st_mtime > error_written:
            return None
        if time.time() - error_written < stall:
            return None
        return last[:2000] + f" (no output for {stall:g} seconds after this)"
    except OSError:
        return None


MODEL_PROBES = {"opencode": ["opencode", "models"], "agy": ["agy", "models"], "codex": ["codex", "debug", "models"]}


def probe_catalog(tool, output):
    if tool != "codex":
        return [line.split()[0] for line in output.splitlines() if line.strip()]
    try:
        models = json.loads(output).get("models", [])
    except (ValueError, AttributeError):
        return []
    return [m["slug"] for m in models if isinstance(m, dict) and isinstance(m.get("slug"), str) and m.get("visibility") != "hide"]


def cli_argv(spec, model, project, prompt):
    tool, effort = spec["tool"], spec.get("effort")
    if tool == "opencode":
        # Error logs on stderr expose provider failures that `opencode run` otherwise never reports or exits on.
        return [tool, "run", "--print-logs", "--log-level", "ERROR", "--auto", "--dir", project,
                "--agent", "build", "-m", model, "--format", "json", prompt]
    if tool == "agy":
        return [tool, "--model", model, "--mode", "accept-edits", "--dangerously-skip-permissions", "-p=" + prompt]
    if tool == "copilot":
        return [tool, "-C", project, "--model", "auto", "--allow-all-tools", "--trust-folder", "-p", prompt]
    if tool == "codex":
        return [tool, "exec", "--approve-for-me", "-C", project, "-m", model, "-c", "model_reasoning_effort=" + effort, prompt]
    return ["claude", "-p", "--model", model, "--effort", effort, "--permission-mode", "auto", prompt]


def output_result(state, path):
    current = state.get("current_level")
    native = state["status"] == "native_required"
    return {"status": state["status"], "dispatch_id": state["dispatch_id"], "state_path": str(path),
            "task_type": state["request"]["task_type"], "level": current,
            "tool": state.get("current_tool"), "model": state.get("current_model"),
            "family": state.get("current_family"), "effort": state.get("current_effort"),
            "prompt": state.get("prompt", ""), "attempts": state["attempts"],
            "memory_reminder": REMINDER, "reason": state.get("reason", ""),
            "native_tool": NATIVE_TOOLS[state["request"]["host"]] if native else None,
            "instruction": ("Not dispatched yet. Use the current host's built-in subagent with the specified model and the full prompt. When the tool is unavailable, continue to the next level with the actual error."
                            if native else
                            "No worker was started for this level. Retry the same level with --outcome dispatch-failed after the slot frees." if state["status"] == "not_started" else
                            ("The external CLI failed and no file changed. Read the error, output, model_probe and fatal_error of the last attempt to find the cause;"
                             " when launch_error is true, first check \"CLI not installed\" in references/dispatch-flow.md. Once this level is judged unable to run, continue to the next level with dispatch --dispatch-id "
                             + state["dispatch_id"] + " --outcome dispatch-failed --failure-reason '<original error and judgement>';"
                             " when installation is confirmed absent, add --not-installed and later dispatches will skip this tool automatically.")
                            if state["status"] == "cli_failed" else
                            "Still running. Query again with status --wait; when it is judged stuck, use cancel." if state["status"] in ACTIVE else
                            "The main agent personally checks the scope, diff and verification results, then reports the outcome.")}


def with_runtime(result, state):
    """Add progress details for a dispatch that has not reached a reviewable state."""
    if state["status"] not in ACTIVE:
        return result
    log = state.get("current_log") or {}
    phase = ("starting" if state["status"] == "starting" else "queued" if state["status"] == "new" else
             "probing" if log.get("stdout", "").endswith("-models.stdout.log") else "executing" if log else "preparing")
    started = (state.get("run") or {}).get("started_at")
    info = {"elapsed": round(time.time() - started, 1) if started else None, "child_pid": state.get("child_pid")}
    for stream in ("stdout", "stderr"):
        try:
            stat = os.stat(log[stream])
            info[stream + "_bytes"], info[stream + "_age"] = stat.st_size, round(time.time() - stat.st_mtime, 1)
        except (KeyError, OSError):
            info[stream + "_bytes"] = info[stream + "_age"] = None
    result.update(phase=phase, runtime=info)
    return result


def drive(root, path, state, task, write_paths, start, timeout, stall=180):
    r = state["request"]
    for level in range(start, len(task["levels"]) + 1):
        spec = dict(task["levels"][level - 1])
        if spec.get("effort") and spec["effort"] != "low":
            spec["effort"] = r.get("effort", spec["effort"])
        native = spec["tool"] == r["host"]
        known = None if native else known_not_installed(root, spec["tool"])
        if known:
            state["attempts"].append({"level": level, "tool": spec["tool"], "model": None, "native": False,
                                      "skipped": "not_installed", "evidence": known["evidence"],
                                      "verified_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(known["verified_at"]))})
            continue
        state.update(current_level=level, current_tool=spec["tool"], current_model=None, current_family=spec["family"],
                     current_effort=spec.get("effort"), reason="", prompt=build_prompt(r, task, state))
        atomic_write(path, state)
        try:
            claim(root, path, state, spec, write_paths, native, timeout)
        except NotStarted as exc:
            state.update(status="not_started", reason=str(exc), write_paths=[])
            atomic_write(path, state)
            return output_result(state, path)
        attempt = {"level": level, "tool": spec["tool"], "model": None, "native": native}
        state["attempts"].append(attempt)
        atomic_write(path, state)
        before = attempt["snapshot_before"] = snapshot(r, write_paths)
        catalog = r.get("models", {}).get(spec["tool"], [])
        if not native and spec["tool"] in MODEL_PROBES:
            probe = execute(MODEL_PROBES[spec["tool"]], r["project_dir"], root,
                            state["dispatch_id"] + "-" + str(len(state["attempts"])) + "-models",
                            min(timeout, 30), state, path)
            attempt["model_probe"] = probe
            after_probe = snapshot(r, write_paths)
            if probe.get("cleanup_pending") or probe["timeout"] or probe["interrupted"] or before is None or after_probe != before:
                state.update(status="awaiting_review", reason="The model probe did not finish normally, or it cannot be confirmed that the process stopped and the files stayed consistent. Check the raw output, the process and the disk first.")
                atomic_write(path, state)
                return output_result(state, path)
            if probe["returncode"] != 0 or error_event(probe["output"]):
                state.update(status="cli_failed", write_paths=[],
                             reason="The model probe failed and no file changed. The raw output is in the model_probe of the last attempt.")
                atomic_write(path, state)
                return output_result(state, path)
            catalog = probe_catalog(spec["tool"], probe["output"])
        model = select_model(spec, catalog)
        if not model and not native and spec["tool"] == "claude" and spec["family"] == "opus" and "claude" not in r.get("models", {}):
            model = "opus"  # No version floor for this route; Claude resolves its official alias.
        attempt["model"] = state["current_model"] = model
        if native:
            state["reason"] = "" if model else "The supplied host model catalog has no compliant model; check availability and report the actual failure evidence."
            atomic_write(path, state)
            return output_result(state, path)
        if not model:
            attempt["error"] = "The actual model catalog has no model matching this level's family and version floor"
            attempt["catalog"] = catalog
            state["status"] = "new"  # moving on to the next level
            atomic_write(path, state)
            continue
        argv = cli_argv(spec, model, r["project_dir"], state["prompt"])
        attempt.update(execute(argv, r["project_dir"], root,
                               state["dispatch_id"] + "-" + str(len(state["attempts"])), timeout, state, path,
                               (lambda out, err: opencode_stalled(out, err, stall)) if spec["tool"] == "opencode" else None))
        after = snapshot(r, write_paths)
        errors = error_event(attempt["output"])
        failed = attempt["returncode"] != 0 or bool(errors) or bool(attempt.get("fatal_error"))
        attempt["files_changed"] = None if before is None or after is None else after != before
        if failed and not attempt.get("cleanup_pending") and not attempt["timeout"] and not attempt["interrupted"] and before is not None and after == before:
            state.update(status="cli_failed", write_paths=[],
                         reason="The external CLI failed and no file changed. The raw output is in the last attempt.")
            atomic_write(path, state)
            return output_result(state, path)
        state.update(status="awaiting_review", reason=("Cannot confirm the worker stopped; keeping the slot and file scope, check cleanup_error first." if attempt.get("cleanup_pending") else
                     "Timed out or interrupted; the process has stopped. Check the partial work before continuing." if attempt["timeout"] or attempt["interrupted"]
                     else "Verify the result yourself first; neither a normal report nor partially changed files are taken over automatically."))
        atomic_write(path, state)
        return output_result(state, path)
    state.update(status="exhausted", reason="Every level of this task type has failed; the user must decide.")
    atomic_write(path, state)
    return output_result(state, path)


def dispatch(a, policy):
    if a.request is not None:
        if a.outcome or a.failure_reason or a.feedback or a.partial_work_reviewed or a.not_installed:
            raise DispatchError("A new task must not carry continuation outcome arguments")
        raw = sys.stdin.read() if a.request == "-" else Path(a.request).read_text(encoding="utf-8")
        r, paths = validate_request(json.loads(raw), policy)
        task = policy["tasks"][r["task_type"]]
        check_level(a.level, len(task["levels"]))
        start = 1 if a.level is None else a.level
        if start != 1 and not (start == 2 and r.get("difficult_implementation") is True and r.get("opencode_failure_evidence")):
            raise DispatchError("A new task must start at level 1; the OpenCode exception for a difficult implementation slot needs evidence of a real failure of the same task")
        root = state_directory(a.state_dir, r["project_dir"])
        did = str(uuid.uuid4())
        path = root / (did + ".json")
        state = {"dispatch_id": did, "request": r, "status": "new", "attempts": [], "feedback": [],
                 "scope_paths": paths, "verification_failures": {},
                 "policy_fingerprint": hashlib.sha256(POLICY_PATH.read_bytes()).hexdigest()}
        with lock_file(root / (did + ".lock"), False):
            atomic_write(path, state)
            return run(root, path, state, task, paths, start, a)
    if not a.outcome:
        raise DispatchError("A continuation must provide --outcome")
    root, path, did = existing_dispatch(a)
    with lock_file(root / (did + ".lock"), False):
        state = json.loads(path.read_text(encoding="utf-8"))
        r, paths = validate_request(state["request"], policy)
        if paths != state.get("scope_paths"):
            raise DispatchError("The actual location of an authorized path has changed; review the symlink and the original task scope, and do not continue the old dispatch")
        root = state_directory(str(root), r["project_dir"])
        path = root / (did + ".json")
        if state.get("policy_fingerprint") != hashlib.sha256(POLICY_PATH.read_bytes()).hexdigest():
            raise DispatchError("The dispatch rules have changed; review the original dispatch first and do not continue old levels with the new order")
        task = policy["tasks"][r["task_type"]]
        count = len(task["levels"])
        check_level(a.level, count)
        status = state["status"]
        if status == "starting":
            if alive(state.get("owner_pid")):
                raise DispatchError("A background process is taking over this dispatch; it cannot be resumed concurrently")
            state.update(status="not_started", reason="The background process ended before taking over; no worker was started.")
            status = "not_started"
        if status not in ("native_required", "cli_failed", "awaiting_review", "running", "new", "not_started"):
            raise DispatchError("This dispatch has already ended and cannot be started again: " + status)
        if alive(state.get("child_pid")):
            raise DispatchError("The previous child process is still running; check and stop it first")
        if state.get("cleanup_pending"):
            if group_live(state.get("process_group")) is not False:
                raise DispatchError("The previous worker process group is not confirmed stopped; the slot cannot be released and the dispatch cannot be resumed")
            state.update(cleanup_pending=False, process_group=None, child_pid=None)
        if a.outcome == "completed":
            if a.level is not None and a.level != state.get("current_level"):
                raise DispatchError("completed cannot change the level")
            state.update(status="completed", reason="The main agent reported acceptance complete.", write_paths=[])
            atomic_write(path, state)
            return output_result(state, path)
        reason = text_value(a.failure_reason, "--failure-reason")
        current = state.get("current_level", 1)
        if a.not_installed and a.outcome != "dispatch-failed":
            raise DispatchError("--not-installed works only with --outcome dispatch-failed")
        if a.outcome == "dispatch-failed":
            if status not in ("native_required", "cli_failed", "not_started"):
                raise DispatchError("External execution results must be reviewed first and must not be reported as not dispatched")
            if a.not_installed:
                last = state["attempts"][-1] if state["attempts"] else {}
                launch_failed = last.get("launch_error") or (last.get("model_probe") or {}).get("launch_error")
                if status != "cli_failed" or last.get("native") or not launch_failed:
                    raise DispatchError("--not-installed applies only to a cli_failed whose command could not launch (launch_error)")
                record_not_installed(root, last["tool"], reason)
            wanted = current if status == "not_started" else current + 1
        else:
            if not a.partial_work_reviewed:
                raise DispatchError("Check the disk and partial work first, then provide --partial-work-reviewed")
            failures = state["verification_failures"].get(str(current), 0) + 1
            wanted = current if failures < task["verification_retries"] else current + 1
        if a.level is not None and a.level != wanted:
            raise DispatchError(f"Based on the original dispatch's failure record, this run can only specify level {wanted}; levels cannot be skipped or escalated early")
        if a.outcome == "verification-failed":
            state["verification_failures"][str(current)] = failures
        state["feedback"].append({"outcome": a.outcome, "reason": reason, "feedback": a.feedback or ""})
        state.update(status="new", write_paths=[])
        atomic_write(path, state)
        return run(root, path, state, task, paths, wanted, a)


def existing_dispatch(a):
    try:
        did = str(uuid.UUID(a.dispatch_id))
    except ValueError:
        raise DispatchError("dispatch-id must be a valid UUID")
    # Resolve the requested store before opening any existing task. Do not create it on a bogus resume.
    root = Path(a.state_dir).expanduser() if a.state_dir else default_state_directory()
    path = root / (did + ".json")
    if not path.is_file() or path.is_symlink():
        raise DispatchError("The original dispatch state was not found")
    if os.name == "nt":
        windows.ensure_private(root)
        windows.ensure_private(path)
    return root, path, did


def run(root, path, state, task, paths, start, a):
    """Run levels in this process, or hand them to a detached supervisor."""
    state["run"] = {"id": uuid.uuid4().hex, "start": start, "timeout": a.timeout, "stall": a.stall_timeout,
                    "started_at": time.time()}
    with contextlib.suppress(FileNotFoundError):
        stop_path(root, state).unlink()
    if a.foreground or task["levels"][start - 1]["tool"] == state["request"]["host"]:
        return drive(root, path, state, task, paths, start, a.timeout, a.stall_timeout)
    log_path = root / (state["dispatch_id"] + ".supervisor.log")
    argv = [sys.executable, str(Path(__file__).resolve()), "supervise",
            "--dispatch-id", state["dispatch_id"], "--state-dir", str(root)]
    with private_file(log_path) as log:
        log.seek(0, os.SEEK_END)
        # Every stream is redirected so the caller's shell does not wait for the supervisor.
        options = dict(cwd=str(root), stdin=subprocess.DEVNULL, stdout=log, stderr=log)
        try:
            if os.name == "nt":
                flags = 0x00000008 | 0x00000200  # DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP
                try:
                    proc = subprocess.Popen(argv, creationflags=flags | 0x01000000, **options)  # CREATE_BREAKAWAY_FROM_JOB
                except OSError:
                    proc = subprocess.Popen(argv, creationflags=flags, **options)
            else:
                proc = subprocess.Popen(argv, start_new_session=True, **options)
        except OSError as exc:
            state.update(status="not_started", reason="The background process could not be started: " + str(exc))
            atomic_write(path, state)
            raise DispatchError(state["reason"])
    state.update(status="starting", owner_pid=proc.pid, supervisor_started=False, reason="")
    atomic_write(path, state)
    return {"spawned": proc, "root": root, "path": path, "log": log_path, "state": state}


def handshake(spawned):
    """Report the background start once the supervisor owns the dispatch, or report its startup failure."""
    proc, path, state = spawned["spawned"], spawned["path"], spawned["state"]
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        current = json.loads(path.read_text(encoding="utf-8"))
        if current.get("supervisor_started") and current.get("owner_pid") == proc.pid:
            break
        if proc.poll() is not None:
            log = spawned["log"].read_text(encoding="utf-8", errors="replace")[-4000:]
            with contextlib.suppress(DispatchError):
                with lock_file(spawned["root"] / (state["dispatch_id"] + ".lock"), False):
                    current = json.loads(path.read_text(encoding="utf-8"))
                    if current.get("status") == "starting":
                        current.update(status="not_started", reason="The background process ended before taking over; no worker was started.")
                        atomic_write(path, current)
            raise DispatchError("The background process failed to start; no worker was dispatched. Record: " + str(spawned["log"]) + "\n" + log)
        time.sleep(0.05)
    return {"status": "started", "dispatch_id": state["dispatch_id"], "state_path": str(path),
            "task_type": state["request"]["task_type"], "level": state["run"]["start"],
            "supervisor_pid": proc.pid, "supervisor_log": str(spawned["log"]),
            "timeout": state["run"]["timeout"], "memory_reminder": REMINDER,
            "instruction": "Running in the background. Use status --dispatch-id " + state["dispatch_id"] +
                           " --wait <seconds> to get the result; the seconds must not exceed your command tool's limit, query again if it does not finish, and use cancel when it is judged stuck."}


def supervise(a, policy):
    root, path, did = existing_dispatch(a)
    with lock_file(root / (did + ".lock")):
        state = json.loads(path.read_text(encoding="utf-8"))
        if state.get("status") != "starting" or state.get("owner_pid") != os.getpid():
            raise DispatchError("This background process is not the designated owner of the dispatch and ran no level")
        state.update(status="new", supervisor_started=True)
        atomic_write(path, state)
        task = policy["tasks"][state["request"]["task_type"]]
        run = state["run"]
        try:
            return drive(root, path, state, task, state["scope_paths"], run["start"], run["timeout"], run.get("stall", 180))
        except BaseException as exc:
            if state.get("status") in ACTIVE:
                state.update(status="awaiting_review", write_paths=state.get("write_paths", []) if state.get("cleanup_pending") else [],
                             reason="The background process hit an error: " + (str(exc) or type(exc).__name__) + ". Check the raw output, the process and the disk first.")
                atomic_write(path, state)
            raise
        finally:
            with contextlib.suppress(OSError):
                if stop_requested(root, state):
                    stop_path(root, state).unlink()


def repair(root, path, state, r):
    """Settle an active state whose supervisor no longer holds the dispatch lock."""
    status = state["status"]
    if status == "starting":
        if alive(state.get("owner_pid")):
            return state
        state.update(status="not_started", reason="The background process ended before taking over; no worker was started.")
    elif status == "new":
        state.update(status="not_started", write_paths=[], reason="The background process ended before starting a worker; retry the same level with --outcome dispatch-failed.")
    else:
        group = state.get("process_group") or state.get("child_pid")
        live = group_live(group) if group else False
        attempt = state["attempts"][-1] if state["attempts"] else {}
        attempt["supervisor_lost"] = True
        if live is not False:
            state.update(status="awaiting_review", cleanup_pending=True, process_group=group,
                         reason="The background process has ended but the worker is still running. Stop it with cancel first, then check the partial work.")
        else:
            after = snapshot(r, state.get("write_paths", []))
            before = attempt.get("snapshot_before")
            attempt["files_changed"] = None if before is None or after is None else after != before
            state.update(status="awaiting_review", write_paths=[], child_pid=None, process_group=None,
                         cleanup_pending=False, reason="The background process ended unexpectedly and the worker is gone. Check the raw output, the process and the disk first.")
    atomic_write(path, state)
    return state


def settle(root, path, did):
    """Read the state, repairing it when nobody holds the dispatch lock."""
    state = json.loads(path.read_text(encoding="utf-8"))
    if state["status"] in ACTIVE:
        with contextlib.suppress(DispatchError):
            with lock_file(root / (did + ".lock"), False):
                state = json.loads(path.read_text(encoding="utf-8"))
                if state["status"] in ACTIVE:
                    state = repair(root, path, state, state["request"])
    return state


def status(a):
    root, path, did = existing_dispatch(a)
    deadline = time.monotonic() + a.wait
    while True:
        state = settle(root, path, did)
        if state["status"] not in ACTIVE or time.monotonic() >= deadline:
            return with_runtime(output_result(state, path), state)
        time.sleep(0.5)


def cancel(a):
    root, path, did = existing_dispatch(a)
    state = settle(root, path, did)
    if state["status"] in ACTIVE:
        if not (state.get("run") or {}).get("id"):
            raise DispatchError("This dispatch has no cancellable run identifier; stop the original foreground process")
        with private_file(stop_path(root, state)) as handle:
            handle.truncate()
            handle.write(state["run"]["id"])
        deadline = time.monotonic() + 60
        while state["status"] in ACTIVE:
            if time.monotonic() >= deadline:
                raise DispatchError("A cancel request was sent but the stop was not confirmed within 60 seconds; check the process with status")
            time.sleep(0.2)
            state = settle(root, path, did)
    if state.get("cleanup_pending") and state.get("status") not in ACTIVE:
        with lock_file(root / (did + ".lock"), False):
            state = json.loads(path.read_text(encoding="utf-8"))
            group = state.get("process_group")
            if state.get("cleanup_pending") and group:
                if os.name == "nt":
                    if windows.group_live(group) is not False:
                        raise DispatchError("Windows cannot stop this worker from outside; check it manually")
                else:
                    stop_group(group)
                state.update(cleanup_pending=False, process_group=None, child_pid=None,
                             reason=state.get("reason", "") + " The leftover worker was stopped by cancel.")
                atomic_write(path, state)
    return output_result(state, path)


def parser(policy):
    p = argparse.ArgumentParser(description="Dispatch by the levels of each task type. Queries call no model and write no state. Requires Python 3.9+, on Windows 10+/macOS/Linux.",
        epilog="Commands: list-types lists tasks; list-levels lists levels; dispatch starts or continues in the background; status reads results; cancel stops a running dispatch. "
               "supervise is for internal use by dispatch only. Add --help to each command for the full description.")
    sub = p.add_subparsers(dest="command")
    q = sub.add_parser("list-types", help="list every task type and its level count", description="Query only. Shows a human-readable table by default. exit 0.")
    form = q.add_mutually_exclusive_group()
    form.add_argument("--json", action="store_true", help="output the tasks array as JSON")
    form.add_argument("--markdown", action="store_true", help="generate the SKILL.md decision table from policy.json")
    q = sub.add_parser("list-levels", help="list the model families and execution mode for a task type",
                       epilog="Example: dispatch.py list-levels --task-type classification --host codex --json")
    q.add_argument("--task-type", required=True, choices=list(policy["tasks"]), help="task type enum")
    q.add_argument("--host", choices=policy["hosts"], help="optional; marks the host's built-in subagent level")
    q.add_argument("--json", action="store_true", help="output structured levels with native, minimum and effort")
    example = {"host": "codex", "task_type": "classification", "project_dir": "/path/to/project",
               "role": "Researcher who classifies from the source text and evidence", "prompt": "Classify issue A and explain the basis for each item.",
               "project_memory": [{"condition": "When it applies", "lesson": "Confirmed lesson", "source": "Where the evidence is"}],
               "allowed_files": [], "verification": ["check every label against the issue text"],
               "models": {"codex": ["gpt-6-luna"], "claude": ["claude-haiku-5-5"]},
               "model_source": "model catalog the main agent actually verified this turn"}
    q = sub.add_parser("dispatch", help="run an external CLI by the rules, or return a built-in subagent handoff prompt",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description="""A new dispatch requires a request JSON with host, task_type, project_dir, role, prompt, project_memory, allowed_files and verification.
project_memory is a required array; each item has condition/lesson/source, and you fill [] only after confirming there are no relevant lessons.
allowed_files are exact project-relative paths; wildcards, .. and .git are not accepted. A read-only task must use [].
implementation may also list test_files as test paths that must not be changed; testing writes tests only.
research and acceptance require sandbox_dir, which may be a dedicated temporary directory outside the project; when allowed_files is non-empty it must point inside the sandbox.
models maps each tool name to the names of models verified as available; when provided, model_source is required. Claude version floors cannot be guessed from aliases.
The optional effort is medium (default), high or xhigh; raising it requires effort_reason.
Free models, Copilot Auto, Gemini and agy Claude do not get the effort override; the last programming level Opus is fixed at low.
External OpenCode/agy are verified with the models command and Codex with debug models; the result replaces the same-tool list in the request. When it is the host's turn, do not run its own CLI; return only the built-in handoff prompt.
A difficult implementation slot may start at level 2 with difficult_implementation:true and opencode_failure_evidence (evidence of a real failure of the same task).

A start or continuation that launches an external CLI runs in the background by default: it immediately outputs status=started, dispatch_id, supervisor_pid and supervisor_log,
then status --wait gets the result, and cancel is used when it is judged stuck. --outcome completed and a starting level that is the host's built-in subagent output the result directly.
--foreground waits in this process until the end, for tests and debugging.
Other results output a single JSON object: status, dispatch_id, level, tool, model, prompt, attempts, state_path, memory_reminder.
native_required: not dispatched yet; the main agent calls the built-in tool named by native_tool with the full prompt, then reports with --outcome.
This handoff first waits for external dispatches to free that tool's slot and same-file writes; after the handoff it holds no slot and no file lock, and the main agent counts the built-in subagent toward the limit and same-file checks.
not_started: waiting for a same-file write or a concurrency slot timed out, the dispatch was cancelled, or the background process did not take over, so no worker was started for this level; retry the same level with --outcome dispatch-failed.
awaiting_review: the main agent reads the diff and verifies personally; the script does not adopt results automatically, run verification commands or write memory.
An attempts item with skipped set to not_installed: the tool was previously confirmed absent by the main agent with --not-installed, was not started this time, and evidence is the verification content from then.
The record lives in not-installed.cache in the state directory; it expires when PATH changes, the command becomes findable again, or 7 days pass; deleting that file clears it immediately.
cli_failed: an external CLI or model probe failed (non-zero exit, JSON error event, command could not launch, opencode stall), and the snapshot confirms no file changed.
The script does not interpret the error content and does not take over automatically; after reading the raw output of attempts, the main agent continues to the next level with --outcome dispatch-failed.
The snapshot covers every project file (including ignored files) and the sandbox; when the scan times out, review first. It moves to the next level automatically only when the actual model catalog has no compliant model.
Each CLI run stops its process group at the end, and only after the worker is confirmed stopped does it snapshot and hand off; services that must keep running are managed by the main agent.
Partial file changes, timeouts and interruptions are all reviewed first, and a non-Git project that cannot be confirmed consistent is reviewed first too.
exhausted: every level failed; completed: the main agent reported acceptance complete. Neither can be started again.
state/log default to $XDG_STATE_HOME/agent-delegation or ~/.local/state/agent-delegation on macOS/Linux, with 0700/0600.
On Windows they default to %LOCALAPPDATA%/agent-delegation, protected by a private DACL that grants only the current user, SYSTEM and administrators.
Windows uses native file locks and a Job Object to clean up the process tree; exe and standard npm cmd shims are supported, and an unknown batch wrapper is reported for review first.
The same dispatch cannot be resumed concurrently; this directory tracks same-file write queues for external CLIs, at most three per tool.
Unmanaged processes are still checked by the main agent. When an interruption leaves running, check the process and partial work, then report; do not rerun automatically.
exit 0: the above state was produced (not proof the result is good); exit 2: argument, state or file error, and dispatch did not continue.
""", epilog="request example (replace with the actual project, task and this turn's model catalog):\n" + json.dumps(example, ensure_ascii=False, indent=2) +
        "\n\nExamples:\n  dispatch.py dispatch --request task.json\n  dispatch.py status --dispatch-id <UUID> --wait 100\n  dispatch.py dispatch --dispatch-id <UUID> --level 3 --outcome dispatch-failed --failure-reason 'raw built-in tool error'\n  dispatch.py dispatch --dispatch-id <UUID> --outcome verification-failed --failure-reason 'verification command and failure output' --partial-work-reviewed\n  dispatch.py dispatch --dispatch-id <UUID> --outcome completed")
    group = q.add_mutually_exclusive_group(required=True)
    group.add_argument("--request", metavar="FILE|-", help="new task JSON file; - reads from stdin")
    group.add_argument("--dispatch-id", metavar="UUID", help="continue the original dispatch, reusing its request and all failure evidence")
    q.add_argument("--level", type=int, help="the task level to run, starting at 1; a new task defaults to 1, a continuation is computed from the failure count, and a value outside the supported range is an error")
    q.add_argument("--outcome", choices=["dispatch-failed", "verification-failed", "completed"],
                   help="required for a continuation. dispatch-failed is used for native_required, cli_failed (next level) and not_started (retry the same level); "
                        "verification failure requires checking the partial work first; completed means the main agent accepted the result")
    q.add_argument("--failure-reason", help="required for a failed outcome; provide the actual error or verification output")
    q.add_argument("--not-installed", action="store_true",
                   help="optional, only with dispatch-failed. Add it when the main agent has verified in references/dispatch-flow.md under \"CLI not installed\" that this tool really is absent; "
                        "--failure-reason records the verification commands and results. While PATH is unchanged and the command is still missing, new dispatches within 7 days skip this tool and attach this evidence in attempts")
    q.add_argument("--feedback", help="optional; verified lessons, kept partial work and correction requests, accumulated into the next worker's prompt")
    q.add_argument("--partial-work-reviewed", action="store_true", help="required for verification-failed; the main agent has checked the process, the disk and the partial work")
    q.add_argument("--state-dir", help="optional; a dedicated private state directory outside the project, also the concurrency coordination scope for this dispatch group")
    q.add_argument("--timeout", type=float, default=1800,
                   help="the seconds allowed for each external CLI run, also used while waiting for a slot, default 1800; the model probe takes at most 30 seconds. Do not shorten it to fit the time limit of the calling command tool")
    q.add_argument("--stall-timeout", type=float, default=180,
                   help="after opencode logs a main-task error, how many seconds of no new output pass before it is stopped and marked cli_failed, default 180")
    q.add_argument("--foreground", action="store_true", help="wait in this process and output the result, for tests and debugging; ordinary dispatches use the background")
    q = sub.add_parser("status", help="query a dispatch's status, optionally waiting for the result",
        description="Outputs JSON with the same structure as dispatch. While still running it also has phase (starting/queued/preparing/probing/executing) "
                    "and runtime (elapsed, child_pid, the stdout/stderr byte counts and seconds since the last output). "
                    "When the background process ends unexpectedly but the worker is still there, it is marked awaiting_review and cleanup_pending is kept; "
                    "when the worker is gone it is marked awaiting_review from the file snapshot; ending before a worker starts is marked not_started. exit 0: the status was output; exit 2: the dispatch does not exist or an argument is wrong.",
        epilog="Example: dispatch.py status --dispatch-id <UUID> --wait 100")
    q.add_argument("--dispatch-id", required=True, metavar="UUID", help="the dispatch identifier printed by dispatch")
    q.add_argument("--state-dir", help="optional; the same state directory as dispatch")
    q.add_argument("--wait", type=float, default=0, help="the maximum seconds to wait while still running, default 0; do not exceed your command tool's time limit")
    q = sub.add_parser("cancel", help="stop a running dispatch",
        description="Send a cancel request, wait for the background process to stop the whole worker process group and snapshot, then output the result (usually awaiting_review, or not_started while queued). "
                    "When the background process is gone but a worker remains, stop the leftover process group directly. A finished dispatch only outputs its current state. exit 2: the stop was not confirmed within 60 seconds or could not be done.",
        epilog="Example: dispatch.py cancel --dispatch-id <UUID>")
    q.add_argument("--dispatch-id", required=True, metavar="UUID", help="the dispatch identifier printed by dispatch")
    q.add_argument("--state-dir", help="optional; the same state directory as dispatch")
    q = sub.add_parser("supervise", help="internal use: the background process started by dispatch", description="Only for the background process started by dispatch; do not call it directly.")
    q.add_argument("--dispatch-id", required=True)
    q.add_argument("--state-dir", required=True)
    return p


def main(argv=None):
    policy = json.loads(POLICY_PATH.read_text(encoding="utf-8"))
    p = parser(policy)
    a = p.parse_args(argv)
    if not a.command:
        p.print_help()
        return 0
    if a.command == "list-types":
        rows = [{"task_type": name, "label": task["label"], "levels": len(task["levels"]),
                 "order": task["levels"]} for name, task in policy["tasks"].items()]
        if a.json:
            print(json.dumps({"tasks": rows}, ensure_ascii=False))
        else:
            print("| Task type | Fits these requests | Levels | Handoff order |\n| --- | --- | --- | --- |")
            for row in rows:
                order = " → ".join(f"{i}. {item['tool']} / {item['family']}" for i, item in enumerate(row["order"], 1))
                print(f"| `{row['task_type']}` | {row['label']} | {row['levels']} | {order} |")
        return 0
    if a.command == "list-levels":
        rows = [dict(spec, level=i, native=spec["tool"] == a.host if a.host else None,
                     execution="native" if spec["tool"] == a.host else "external")
                for i, spec in enumerate(policy["tasks"][a.task_type]["levels"], 1)]
        if a.json:
            print(json.dumps({"task_type": a.task_type, "levels": rows}, ensure_ascii=False))
        else:
            for row in rows:
                print(f"{row['level']}. {row['tool']} / {row['family']} | {row['execution']} | effort={row.get('effort')} | minimum={row.get('minimum', 'none')}")
        return 0
    try:
        if a.command == "supervise":
            supervise(a, policy)
            return 0
        if a.command == "status":
            if not math.isfinite(a.wait) or a.wait < 0:
                raise DispatchError("--wait must be a finite non-negative number")
            result = status(a)
        elif a.command == "cancel":
            result = cancel(a)
        else:
            if not math.isfinite(a.timeout) or a.timeout <= 0:
                raise DispatchError("--timeout must be a finite positive number")
            if not math.isfinite(a.stall_timeout) or a.stall_timeout <= 0:
                raise DispatchError("--stall-timeout must be a finite positive number")
            result = dispatch(a, policy)
            if "spawned" in result:
                result = handshake(result)
        print(json.dumps(result, ensure_ascii=False))
        return 0
    except (DispatchError, OSError, ValueError, KeyError) as exc:
        print("Error: " + str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    if os.name == "nt":
        for stream in (sys.stdin, sys.stdout, sys.stderr):
            stream.reconfigure(encoding="utf-8")
    def interrupted(_signum, _frame):
        raise KeyboardInterrupt
    signal.signal(signal.SIGTERM, interrupted)
    raise SystemExit(main())
