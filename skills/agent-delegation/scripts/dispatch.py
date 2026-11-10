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
REMINDER = "核對教訓與經驗，依 project-memory 流程搜尋去重、記錄並讀回確認。"
MARKER = "你是被派工的執行者，不得再派工給任何 agent 或 CLI，自己完成"
HOST_ENV = {"codex": "CODEX_THREAD_ID", "claude": "CLAUDECODE",
            "agy": "ANTIGRAVITY_AGENT", "opencode": "OPENCODE"}
NATIVE_TOOLS = {"codex": "Codex 內建 subagent", "claude": "Agent",
                "copilot": "Copilot 內建 subagent（Auto）",
                "opencode": "OpenCode 內建 subagent", "agy": "Antigravity 內建 subagent"}


class DispatchError(Exception):
    """An invalid request or unsafe continuation; never starts another worker."""


class NotStarted(DispatchError):
    """No worker was launched for this level, so the same level may be retried."""


ACTIVE = ("starting", "new", "running")
NOT_INSTALLED_FILE = "not-installed.cache"  # Not *.json: the registry scan reads every *.json as a dispatch.
NOT_INSTALLED_TTL = 7 * 86400

def text_value(value, name):
    if not isinstance(value, str) or not value.strip() or "\0" in value:
        raise DispatchError(name + " 必須是非空字串，且不能含 NUL")
    return value


def strings(value, name):
    if not isinstance(value, list):
        raise DispatchError(name + " 必須是字串陣列")
    for item in value:
        text_value(item, name)
    return value


def within(path, root):
    return path == root or root in path.parents


def overlap(a, b):
    return within(Path(a), Path(b)) or within(Path(b), Path(a))


def validate_host(host, policy):
    if not isinstance(host, str) or host not in policy["hosts"]:
        raise DispatchError("host 必須是 " + ", ".join(policy["hosts"]))
    detected = [name for name, key in HOST_ENV.items() if os.environ.get(key)]
    if len(detected) > 1:
        raise DispatchError("有多個宿主識別，請先查明並清除繼承的識別：" + ", ".join(detected))
    if detected and detected[0] != host:
        raise DispatchError("host 與實際宿主識別衝突：" + detected[0])


def scoped_path(raw, project, sandbox=None):
    text_value(raw, "檔案路徑")
    p = Path(raw)
    if any(c in raw for c in "*?[]") or ".." in p.parts or ".git" in p.parts:
        raise DispatchError("檔案路徑不能包含萬用字元、.. 或 .git：" + raw)
    if p.is_absolute() and sandbox is None:
        raise DispatchError("allowed_files/test_files 必須是專案相對路徑：" + raw)
    resolved = (p if p.is_absolute() else project / p).resolve()
    root = sandbox or project
    if not within(resolved, root) or (sandbox is None and resolved == project):
        raise DispatchError("檔案路徑超出允許目錄：" + raw)
    if within(resolved, project) and ".git" in resolved.relative_to(project).parts:
        raise DispatchError("檔案路徑不可透過 symlink 指向 .git：" + raw)
    return str(resolved)


def validate_request(r, policy):
    required = ("host", "task_type", "project_dir", "role", "prompt",
                "project_memory", "allowed_files", "verification")
    if not isinstance(r, dict):
        raise DispatchError("request 必須是 JSON object")
    missing = [key for key in required if key not in r]
    if missing:
        raise DispatchError("缺少必填欄位：" + ", ".join(missing))
    validate_host(r["host"], policy)
    kind = text_value(r["task_type"], "task_type")
    if kind not in policy["tasks"]:
        raise DispatchError("未知 task_type，使用 list-types 查詢：" + kind)
    for key in ("project_dir", "role", "prompt"):
        text_value(r[key], key)
    project = Path(r["project_dir"]).expanduser().resolve(strict=True)
    if not project.is_dir():
        raise DispatchError("project_dir 必須是目錄")
    r["project_dir"] = str(project)
    for key in ("allowed_files", "verification"):
        strings(r[key], key)
    strings(r.get("test_files", []), "test_files")
    if not isinstance(r["project_memory"], list):
        raise DispatchError("project_memory 必須是陣列，查過無相關經驗才填 []")
    for lesson in r["project_memory"]:
        if not isinstance(lesson, dict):
            raise DispatchError("project_memory 每項必須是 object")
        for key in ("condition", "lesson", "source"):
            text_value(lesson.get(key), "project_memory." + key)
    models = r.get("models", {})
    if not isinstance(models, dict):
        raise DispatchError("models 必須是各工具可用模型的 object")
    if models:
        text_value(r.get("model_source"), "model_source")
    for tool, catalog in models.items():
        if tool not in policy["hosts"]:
            raise DispatchError("models 含未知工具：" + str(tool))
        strings(catalog, "models." + tool)
    task = policy["tasks"][kind]
    if task["access"] == "read" and r["allowed_files"]:
        raise DispatchError("唯讀任務的 allowed_files 必須是 []")
    sandbox = None
    if task["access"] == "sandbox":
        raw = text_value(r.get("sandbox_dir"), "sandbox_dir")
        sandbox = Path(raw).expanduser()
        sandbox = (sandbox if sandbox.is_absolute() else project / sandbox).resolve(strict=True)
        if not sandbox.is_dir() or within(project, sandbox):
            raise DispatchError("sandbox_dir 必須是專用沙盒，不可包含整個專案")
        r["sandbox_dir"] = str(sandbox)
    elif r.get("sandbox_dir") is not None:
        raise DispatchError("只有帶沙盒的任務類型（research、acceptance）接受 sandbox_dir")
    paths = [scoped_path(p, project, sandbox) for p in r["allowed_files"]]
    tests = [scoped_path(p, project) for p in r.get("test_files", [])]
    if task["access"] == "implementation" and any(overlap(a, b) for a in paths for b in tests):
        raise DispatchError("allowed_files 與受保護的 test_files 重疊")
    if "difficult_implementation" in r and not isinstance(r["difficult_implementation"], bool):
        raise DispatchError("difficult_implementation 必須是 boolean")
    if "opencode_failure_evidence" in r:
        text_value(r["opencode_failure_evidence"], "opencode_failure_evidence")
        if kind not in ("testing", "implementation") or r.get("difficult_implementation") is not True:
            raise DispatchError("OpenCode 例外只適用有同任務失敗證據的困難寫程式格子")
    if "effort" in r:
        if r["effort"] not in ("medium", "high", "xhigh"):
            raise DispatchError("effort 必須是 medium、high 或 xhigh")
        if r["effort"] != "medium":
            text_value(r.get("effort_reason"), "effort_reason")
    return r, paths or ([str(sandbox)] if sandbox else [])


def check_level(level, count):
    if level is not None and not 1 <= level <= count:
        raise DispatchError(f"此任務類型只有 {count} 檔，level 必須介於 1–{count}，目前輸入為 {level}。")


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
    lines = [MARKER, "角色設定：" + r["role"], "專案目錄：" + r["project_dir"]]
    if task["access"] == "sandbox":
        lines += ["沙盒目錄：" + r["sandbox_dir"], "專案檔一律不可修改。僅可在指定沙盒內試探，回報所有檔案、程序與設定副作用。"]
    if not scope and task["access"] != "sandbox":
        lines += ["可改與不可改的檔案：不得修改任何檔案。"]
    else:
        lines += ["可改與不可改的檔案：" + json.dumps(scope or [r["sandbox_dir"]], ensure_ascii=False),
                  "沒列到的路徑一律不可修改。路徑相對於專案目錄，沙盒絕對路徑依原值使用。"]
    if task["access"] == "tests":
        lines.append("只寫測試，不寫實作。")
    elif task["access"] == "implementation":
        lines += ["不得修改測試檔，認為測試錯就停下回報。", "受保護的測試檔：" + json.dumps(r.get("test_files", []), ensure_ascii=False)]
    lines += ["任務與驗收：\n" + r["prompt"], "相關 Project Memory："]
    for lesson in r["project_memory"]:
        lines += ["適用情境：" + lesson["condition"], "已確認經驗：" + lesson["lesson"], "來源：" + lesson["source"]]
    if not r["project_memory"]:
        lines.append("無（主 agent 已搜尋並篩選）。")
    lines += ["要跑的驗證指令：", *(r["verification"] or ["無可執行指令，依任務的驗收條件提供可核對證據。"]),
              "回報格式：改了哪些檔案、每個結論的依據、不確定處、驗證結果及未驗證項目。",
              "回報覆蓋範圍：應處理幾項、實際處理幾項、未完成的原因、未取得的來源或資料。",
              "不得輸出權杖、密碼、金鑰或設定值，只回報名稱與所在位置。",
              "回報過程中遇到的教訓與經驗：適用情境、失敗做法、已確認原因、有效做法與驗證證據。",
              "推測與不確定處請明確標示。沒有新經驗就寫「無」，不湊數。舊記憶不適用時附原 key、條件差異及查證結果。",
              "經驗由主 agent 核對並記錄進 Project Memory，不要自行寫入 project memory。",
              "不要 commit，也不要 stash 或 reset"]
    if state.get("feedback"):
        lines.append("主 agent 已核對的接續資訊：")
        for feedback in state["feedback"]:
            lines += ["前次結果：" + feedback["outcome"], "原因及證據：" + feedback["reason"], feedback.get("feedback", "")]
    return "\n".join(lines)


def private_file(path):
    if path.is_symlink():
        raise DispatchError("狀態檔不可是 symlink：" + str(path))
    fd = os.open(path, os.O_RDWR | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0), 0o600)
    if os.name == "nt":
        try:
            windows.ensure_private(path)
        except BaseException:
            os.close(fd)
            raise
    elif os.fstat(fd).st_mode & 0o077:
        os.close(fd)
        raise DispatchError("既有狀態檔權限必須是 0600：" + str(path))
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
                        raise DispatchError("此派工正在執行，不可同時接續") from exc
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
            raise DispatchError("此派工正在執行，不可同時接續")
        yield


def atomic_write(path, data):
    if path.is_symlink():
        raise DispatchError("狀態檔不可是 symlink")
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
        raise DispatchError("state-dir 不可是 symlink")
    if os.name == "nt" and path.exists():
        windows.ensure_private(path)
    path = path.resolve()
    if within(path, Path(project)):
        raise DispatchError("state-dir 必須位於專案外")
    if os.name == "nt":
        windows.ensure_private(path, directory=True)
        return path
    path.mkdir(parents=True, mode=0o700, exist_ok=True)
    if path.stat().st_mode & 0o077:
        raise DispatchError("既有 state-dir 必須是專用私有目錄（0700），不會修改它的權限")
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
            raise NotStarted("主 agent 已取消；尚未啟動執行者。")
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
            raise NotStarted("等待同檔寫入或 CLI 三條併行上限逾時；未啟動新執行者。派工紀錄：" + state["dispatch_id"] + "，解除佔用後用 --outcome dispatch-failed 在同一層重來")
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
            raise DispatchError(f"無法停止程序群 {pgid}，尚未確認工作程序結束：{exc}")


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
            raise DispatchError(f"尚未確認程序群 {pgid} 已停止，保留派工名額供主 agent 檢查")
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
        return last[:2000] + f"（之後 {stall:g} 秒沒有任何輸出）"
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
            "instruction": ("尚未派出。請使用目前宿主的內建 subagent、指定模型與完整 prompt。工具不可用時帶實際錯誤接續下一檔。"
                            if native else
                            "此層尚未啟動執行者。解除佔用後用 --outcome dispatch-failed 在同一層重來。" if state["status"] == "not_started" else
                            ("外部 CLI 失敗，檔案沒有變動。讀 attempts 最後一筆的 error、output、model_probe 與 fatal_error 判斷原因；"
                             "launch_error 為 true 時先依 references/dispatch-flow.md「CLI 未安裝」查證。判定這一層無法執行後，用 dispatch --dispatch-id "
                             + state["dispatch_id"] + " --outcome dispatch-failed --failure-reason '<錯誤原文與判斷>' 接下一層；"
                             "查證確認未安裝時另加 --not-installed，之後的派工會自動跳過此工具。")
                            if state["status"] == "cli_failed" else
                            "仍在執行。再用 status --wait 查詢；判定卡住時用 cancel。" if state["status"] in ACTIVE else
                            "主 agent 親自核對範圍、diff 與驗證結果，再回報 outcome。")}


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
                state.update(status="awaiting_review", reason="模型探測未正常結束，或無法確認程序已停止及檔案保持一致。先檢查原始輸出、程序與磁碟。")
                atomic_write(path, state)
                return output_result(state, path)
            if probe["returncode"] != 0 or error_event(probe["output"]):
                state.update(status="cli_failed", write_paths=[],
                             reason="模型探測失敗，檔案沒有變動。原始輸出在 attempts 最後一筆的 model_probe。")
                atomic_write(path, state)
                return output_result(state, path)
            catalog = probe_catalog(spec["tool"], probe["output"])
        model = select_model(spec, catalog)
        if not model and not native and spec["tool"] == "claude" and spec["family"] == "opus" and "claude" not in r.get("models", {}):
            model = "opus"  # No version floor for this route; Claude resolves its official alias.
        attempt["model"] = state["current_model"] = model
        if native:
            state["reason"] = "" if model else "目前提供的宿主模型清單沒有合規模型，請查證可用性並回報實際失敗證據。"
            atomic_write(path, state)
            return output_result(state, path)
        if not model:
            attempt["error"] = "實際模型清單沒有符合此層級種類及版本限制的模型"
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
                         reason="外部 CLI 失敗，檔案沒有變動。原始輸出在 attempts 最後一筆。")
            atomic_write(path, state)
            return output_result(state, path)
        state.update(status="awaiting_review", reason=("無法確認工作程序已停止，保留名額與檔案範圍，請先檢查 cleanup_error。" if attempt.get("cleanup_pending") else
                     "逾時或中斷，程序已停止。檢查半成品後再接續。" if attempt["timeout"] or attempt["interrupted"]
                     else "先親自驗證成果；正常回報與部分改檔都不可自動接手。"))
        atomic_write(path, state)
        return output_result(state, path)
    state.update(status="exhausted", reason="此任務類型的所有層級都已失敗，請由使用者決定。")
    atomic_write(path, state)
    return output_result(state, path)


def dispatch(a, policy):
    if a.request is not None:
        if a.outcome or a.failure_reason or a.feedback or a.partial_work_reviewed or a.not_installed:
            raise DispatchError("新任務不可帶接續結果參數")
        raw = sys.stdin.read() if a.request == "-" else Path(a.request).read_text(encoding="utf-8")
        r, paths = validate_request(json.loads(raw), policy)
        task = policy["tasks"][r["task_type"]]
        check_level(a.level, len(task["levels"]))
        start = 1 if a.level is None else a.level
        if start != 1 and not (start == 2 and r.get("difficult_implementation") is True and r.get("opencode_failure_evidence")):
            raise DispatchError("新任務必須從第 1 檔開始；困難寫程式格子的 OpenCode 例外需附同任務實際失敗證據")
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
        raise DispatchError("接續必須提供 --outcome")
    root, path, did = existing_dispatch(a)
    with lock_file(root / (did + ".lock"), False):
        state = json.loads(path.read_text(encoding="utf-8"))
        r, paths = validate_request(state["request"], policy)
        if paths != state.get("scope_paths"):
            raise DispatchError("授權路徑的實際位置已改變，請審查 symlink 與原任務範圍，不可沿用舊派工")
        root = state_directory(str(root), r["project_dir"])
        path = root / (did + ".json")
        if state.get("policy_fingerprint") != hashlib.sha256(POLICY_PATH.read_bytes()).hexdigest():
            raise DispatchError("分派規則已變更，請先審查原派工，不可用新順序接續舊層級")
        task = policy["tasks"][r["task_type"]]
        count = len(task["levels"])
        check_level(a.level, count)
        status = state["status"]
        if status == "starting":
            if alive(state.get("owner_pid")):
                raise DispatchError("背景程序正在接手執行此派工，不可同時接續")
            state.update(status="not_started", reason="背景程序未接手就結束；尚未啟動執行者。")
            status = "not_started"
        if status not in ("native_required", "cli_failed", "awaiting_review", "running", "new", "not_started"):
            raise DispatchError("此派工已結束，不可重複啟動：" + status)
        if alive(state.get("child_pid")):
            raise DispatchError("前一個子程序仍在執行，請先檢查並停止")
        if state.get("cleanup_pending"):
            if group_live(state.get("process_group")) is not False:
                raise DispatchError("尚未確認前一個工作程序群已停止，不可釋放名額或接續")
            state.update(cleanup_pending=False, process_group=None, child_pid=None)
        if a.outcome == "completed":
            if a.level is not None and a.level != state.get("current_level"):
                raise DispatchError("completed 不能改變層級")
            state.update(status="completed", reason="主 agent 已回報驗收完成。", write_paths=[])
            atomic_write(path, state)
            return output_result(state, path)
        reason = text_value(a.failure_reason, "--failure-reason")
        current = state.get("current_level", 1)
        if a.not_installed and a.outcome != "dispatch-failed":
            raise DispatchError("--not-installed 只能搭配 --outcome dispatch-failed")
        if a.outcome == "dispatch-failed":
            if status not in ("native_required", "cli_failed", "not_started"):
                raise DispatchError("外部執行成果必須先審查，不能冒充未派出")
            if a.not_installed:
                last = state["attempts"][-1] if state["attempts"] else {}
                launch_failed = last.get("launch_error") or (last.get("model_probe") or {}).get("launch_error")
                if status != "cli_failed" or last.get("native") or not launch_failed:
                    raise DispatchError("--not-installed 只適用於指令無法啟動（launch_error）的 cli_failed")
                record_not_installed(root, last["tool"], reason)
            wanted = current if status == "not_started" else current + 1
        else:
            if not a.partial_work_reviewed:
                raise DispatchError("先檢查磁碟與半成品，再提供 --partial-work-reviewed")
            failures = state["verification_failures"].get(str(current), 0) + 1
            wanted = current if failures < task["verification_retries"] else current + 1
        if a.level is not None and a.level != wanted:
            raise DispatchError(f"依原派工的失敗紀錄，本次只能指定 level {wanted}，不得跳級或提早升級")
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
        raise DispatchError("dispatch-id 必須是有效 UUID")
    # Resolve the requested store before opening any existing task. Do not create it on a bogus resume.
    root = Path(a.state_dir).expanduser() if a.state_dir else default_state_directory()
    path = root / (did + ".json")
    if not path.is_file() or path.is_symlink():
        raise DispatchError("找不到原派工狀態")
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
            state.update(status="not_started", reason="背景程序無法啟動：" + str(exc))
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
                        current.update(status="not_started", reason="背景程序未接手就結束；尚未啟動執行者。")
                        atomic_write(path, current)
            raise DispatchError("背景程序啟動失敗，未派出執行者。紀錄：" + str(spawned["log"]) + "\n" + log)
        time.sleep(0.05)
    return {"status": "started", "dispatch_id": state["dispatch_id"], "state_path": str(path),
            "task_type": state["request"]["task_type"], "level": state["run"]["start"],
            "supervisor_pid": proc.pid, "supervisor_log": str(spawned["log"]),
            "timeout": state["run"]["timeout"], "memory_reminder": REMINDER,
            "instruction": "背景執行中。用 status --dispatch-id " + state["dispatch_id"] +
                           " --wait <秒數> 取得結果，秒數不超過自己指令工具的上限，等不到就再查；判定卡住時用 cancel。"}


def supervise(a, policy):
    root, path, did = existing_dispatch(a)
    with lock_file(root / (did + ".lock")):
        state = json.loads(path.read_text(encoding="utf-8"))
        if state.get("status") != "starting" or state.get("owner_pid") != os.getpid():
            raise DispatchError("此背景程序不是派工的指定接手者，未執行任何層級")
        state.update(status="new", supervisor_started=True)
        atomic_write(path, state)
        task = policy["tasks"][state["request"]["task_type"]]
        run = state["run"]
        try:
            return drive(root, path, state, task, state["scope_paths"], run["start"], run["timeout"], run.get("stall", 180))
        except BaseException as exc:
            if state.get("status") in ACTIVE:
                state.update(status="awaiting_review", write_paths=state.get("write_paths", []) if state.get("cleanup_pending") else [],
                             reason="背景程序發生錯誤：" + (str(exc) or type(exc).__name__) + "。先檢查原始輸出、程序與磁碟。")
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
        state.update(status="not_started", reason="背景程序未接手就結束；尚未啟動執行者。")
    elif status == "new":
        state.update(status="not_started", write_paths=[], reason="背景程序在啟動執行者前結束；可用 --outcome dispatch-failed 在同一層重來。")
    else:
        group = state.get("process_group") or state.get("child_pid")
        live = group_live(group) if group else False
        attempt = state["attempts"][-1] if state["attempts"] else {}
        attempt["supervisor_lost"] = True
        if live is not False:
            state.update(status="awaiting_review", cleanup_pending=True, process_group=group,
                         reason="背景程序已結束，但工作程序仍在執行。先用 cancel 停止，再檢查半成品。")
        else:
            after = snapshot(r, state.get("write_paths", []))
            before = attempt.get("snapshot_before")
            attempt["files_changed"] = None if before is None or after is None else after != before
            state.update(status="awaiting_review", write_paths=[], child_pid=None, process_group=None,
                         cleanup_pending=False, reason="背景程序意外結束，工作程序已不在。先檢查原始輸出、程序與磁碟。")
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
            raise DispatchError("此派工沒有可取消的執行識別，請停止原本的前景程序")
        with private_file(stop_path(root, state)) as handle:
            handle.truncate()
            handle.write(state["run"]["id"])
        deadline = time.monotonic() + 60
        while state["status"] in ACTIVE:
            if time.monotonic() >= deadline:
                raise DispatchError("已送出取消請求，但 60 秒內未確認停止；用 status 檢查程序")
            time.sleep(0.2)
            state = settle(root, path, did)
    if state.get("cleanup_pending") and state.get("status") not in ACTIVE:
        with lock_file(root / (did + ".lock"), False):
            state = json.loads(path.read_text(encoding="utf-8"))
            group = state.get("process_group")
            if state.get("cleanup_pending") and group:
                if os.name == "nt":
                    if windows.group_live(group) is not False:
                        raise DispatchError("Windows 無法從外部停止此工作程序，請手動檢查")
                else:
                    stop_group(group)
                state.update(cleanup_pending=False, process_group=None, child_pid=None,
                             reason=state.get("reason", "") + " 已由 cancel 停止殘留的工作程序。")
                atomic_write(path, state)
    return output_result(state, path)


def parser(policy):
    p = argparse.ArgumentParser(description="依任務類型的層級派工。查詢不呼叫模型、不寫狀態。需要 Python 3.9+，支援 Windows 10+/macOS/Linux。",
        epilog="操作：list-types 列任務；list-levels 列層級；dispatch 在背景發起或接續；status 查結果；cancel 停止執行中的派工。"
               "supervise 僅供 dispatch 內部使用。各操作加 --help 查完整說明。")
    sub = p.add_subparsers(dest="command")
    q = sub.add_parser("list-types", help="列出所有任務類型及各自層級數", description="純查詢。預設顯示人可讀表格。exit 0。")
    form = q.add_mutually_exclusive_group()
    form.add_argument("--json", action="store_true", help="輸出 JSON tasks 陣列")
    form.add_argument("--markdown", action="store_true", help="從 policy.json 產生 SKILL.md 決策表")
    q = sub.add_parser("list-levels", help="列出指定任務類型的模型種類及執行方式",
                       epilog="範例：dispatch.py list-levels --task-type classification --host codex --json")
    q.add_argument("--task-type", required=True, choices=list(policy["tasks"]), help="任務類型 enum")
    q.add_argument("--host", choices=policy["hosts"], help="選填，標記宿主內建 subagent 層級")
    q.add_argument("--json", action="store_true", help="輸出結構化 levels，含 native、minimum、effort")
    example = {"host": "codex", "task_type": "classification", "project_dir": "/path/to/project",
               "role": "依原文與證據分類的研究員", "prompt": "分類 issue A，逐項說明依據。",
               "project_memory": [{"condition": "適用條件", "lesson": "已確認經驗", "source": "證據位置"}],
               "allowed_files": [], "verification": ["核對每個標籤與 issue 原文"],
               "models": {"codex": ["gpt-6-luna"], "claude": ["claude-haiku-5-5"]},
               "model_source": "主 agent 本輪實際查證的模型清單"}
    q = sub.add_parser("dispatch", help="依規則執行外部 CLI，或交回內建 subagent 呼叫提示",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description="""新派工必填 request JSON：host、task_type、project_dir、role、prompt、project_memory、allowed_files、verification。
project_memory 必填陣列，每項含 condition/lesson/source，查過無經驗才填 []。
allowed_files 為精確專案相對路徑，不接受萬用字元、.. 或 .git。唯讀任務必須 []。
implementation 可另列 test_files 作為不可改的測試路徑；testing 只寫測試。
research 與 acceptance 必填 sandbox_dir，可用專案外的專用暫存目錄；allowed_files 非空時必須指向沙盒內。
models 為已查證可用模型的工具名→名稱陣列，提供時必填 model_source。Claude 版本下限不能用別名推測。
可選 effort 為 medium（預設）、high、xhigh，調高須附 effort_reason。
免費模型、Copilot Auto、Gemini 與 agy Claude 不套 effort 覆寫，寫程式最後一檔 Opus 固定 low。
外部 OpenCode/agy 由 models 指令、Codex 由 debug models 查證，結果取代 request 的同工具清單。輪到宿主時不執行自己的 CLI，僅回傳內建交接提示。
困難寫程式格子可用 difficult_implementation:true、opencode_failure_evidence（同任務實際失敗證據）從第 2 檔開始。

會啟動外部 CLI 的發起與接續預設在背景執行：立即輸出 status=started、dispatch_id、supervisor_pid 與 supervisor_log，
之後用 status --wait 取得結果，判定卡住時用 cancel。--outcome completed 與起始層級是宿主內建 subagent 時直接輸出結果。
--foreground 改為在本程序等到結束，供測試與除錯。
其餘結果輸出單一 JSON：status、dispatch_id、level、tool、model、prompt、attempts、state_path、memory_reminder。
native_required：尚未派出，由主 agent 用 native_tool 指示的內建工具與完整 prompt 呼叫，完成後用 --outcome 回報。
此交接會先等外部派工讓出該工具名額與同檔寫入，交出後不佔名額也不鎖檔，主 agent 自行把內建 subagent 計入上限與同檔檢查。
not_started：等待同檔寫入或併行名額逾時、已取消或背景程序未接手，此層沒有執行者啟動；用 --outcome dispatch-failed 在同一層重來。
awaiting_review：由主 agent 看 diff、親自驗證；script 不自動採用、不執行 verification 指令、不寫記憶。
attempts 裡 skipped 為 not_installed 的項目：此工具先前經主 agent 以 --not-installed 確認未安裝，本次未啟動，evidence 是當時的查證內容。
紀錄存在狀態目錄的 not-installed.cache，PATH 改變、指令重新找得到或超過 7 天就失效；刪除該檔可立即清除。
cli_failed：外部 CLI 或模型探測失敗（非 0 結束、JSON 錯誤事件、指令無法啟動、opencode 停滯），且快照確認檔案沒變。
script 不解讀錯誤內容、不自動接手；主 agent 讀 attempts 的原始輸出判斷後，用 --outcome dispatch-failed 接下一層。
快照涵蓋所有專案檔案（含忽略檔）與沙盒，掃描逾時就先審查。實際模型清單沒有合規模型時才自動換下一層。
每次 CLI 結束會停止其程序群，確認工作程序結束後才快照及接手；需持續執行的服務由主 agent 管理。
部分改檔、逾時與中斷均先審查，非 Git 專案無法確認一致時也先審查。
exhausted：所有層級失敗；completed：主 agent 已回報驗收完成。兩者不可再啟動。
state/log 在 macOS/Linux 預設為 $XDG_STATE_HOME/agent-delegation 或 ~/.local/state/agent-delegation，0700/0600。
Windows 預設為 %LOCALAPPDATA%/agent-delegation，以私有 DACL 保護，只授權目前使用者、SYSTEM 與系統管理員。
Windows 使用原生檔案鎖與 Job Object 清理程序樹；支援 exe 與標準 npm cmd shim，未知 batch 包裝先回報審查。
同一 dispatch 不允許並行接續；此目錄追蹤外部 CLI 的同檔寫入排隊，各工具最多三條。
未納管程序仍由主 agent 檢查。中斷留下 running 時須檢查程序與半成品後回報，不自動重跑。
exit 0：已產生上述狀態（不代表成果合格）；exit 2：參數、狀態或檔案錯誤，未繼續派工。
""", epilog="request 範例（請替換為實際專案、任務與本輪模型清單）：\n" + json.dumps(example, ensure_ascii=False, indent=2) +
        "\n\n範例：\n  dispatch.py dispatch --request task.json\n  dispatch.py status --dispatch-id <UUID> --wait 100\n  dispatch.py dispatch --dispatch-id <UUID> --level 3 --outcome dispatch-failed --failure-reason '內建工具原始錯誤'\n  dispatch.py dispatch --dispatch-id <UUID> --outcome verification-failed --failure-reason '驗證指令及失敗輸出' --partial-work-reviewed\n  dispatch.py dispatch --dispatch-id <UUID> --outcome completed")
    group = q.add_mutually_exclusive_group(required=True)
    group.add_argument("--request", metavar="FILE|-", help="新任務 JSON 檔案，- 從 stdin 讀取")
    group.add_argument("--dispatch-id", metavar="UUID", help="接續原派工，重用原 request 與全部失敗證據")
    q.add_argument("--level", type=int, help="要執行的任務內層級，從 1 起；新任務預設 1，接續依失敗次數計算，超出支援範圍報錯")
    q.add_argument("--outcome", choices=["dispatch-failed", "verification-failed", "completed"],
                   help="接續必填。dispatch-failed 用於 native_required、cli_failed（接下一層）與 not_started（同一層重來）；"
                        "驗證失敗需先檢查半成品；completed 表示主 agent 驗收完成")
    q.add_argument("--failure-reason", help="失敗結果必填，提供實際錯誤或驗證輸出")
    q.add_argument("--not-installed", action="store_true",
                   help="選填，只搭配 dispatch-failed。主 agent 已依 references/dispatch-flow.md「CLI 未安裝」查證此工具確實沒安裝時加上，"
                        "--failure-reason 寫查證指令與結果。PATH 不變且指令仍找不到時，7 天內的新派工自動跳過此工具並在 attempts 附上這份證據")
    q.add_argument("--feedback", help="選填，已核對的教訓、保留的半成品與修正要求，會累積帶進接手 prompt")
    q.add_argument("--partial-work-reviewed", action="store_true", help="verification-failed 必填，主 agent 已檢查程序、磁碟及半成品")
    q.add_argument("--state-dir", help="選填，專案外的專用私有狀態目錄，也作為此群派工的併行協調範圍")
    q.add_argument("--timeout", type=float, default=1800,
                   help="每次執行外部 CLI 的上限秒數，等待名額也用同一值，預設 1800；模型探測最多 30 秒。不要為了配合呼叫端指令工具的時間上限而縮短")
    q.add_argument("--stall-timeout", type=float, default=180,
                   help="opencode 記下主任務錯誤後，持續多少秒完全沒有新輸出就停止並標為 cli_failed，預設 180")
    q.add_argument("--foreground", action="store_true", help="在本程序等到結果才輸出，供測試與除錯；一般派工用背景")
    q = sub.add_parser("status", help="查詢派工狀態，可等待結果",
        description="輸出與 dispatch 相同結構的 JSON。仍在執行時另含 phase（starting/queued/preparing/probing/executing）"
                    "與 runtime（elapsed、child_pid、stdout/stderr 的位元組數及距最後輸出秒數）。"
                    "背景程序意外結束時，工作程序仍在就標為 awaiting_review 並保留 cleanup_pending，"
                    "工作程序已不在就依檔案快照標為 awaiting_review；啟動執行者前結束標為 not_started。exit 0：已輸出狀態；exit 2：派工不存在或參數錯誤。",
        epilog="範例：dispatch.py status --dispatch-id <UUID> --wait 100")
    q.add_argument("--dispatch-id", required=True, metavar="UUID", help="dispatch 輸出的派工識別碼")
    q.add_argument("--state-dir", help="選填，與 dispatch 相同的狀態目錄")
    q.add_argument("--wait", type=float, default=0, help="仍在執行時最多等待的秒數，預設 0；不要超過自己指令工具的時間上限")
    q = sub.add_parser("cancel", help="停止執行中的派工",
        description="送出取消請求，等背景程序停止整個工作程序群並快照後輸出結果（通常為 awaiting_review，排隊中為 not_started）。"
                    "背景程序已不在而工作程序殘留時，直接停止殘留程序群。已結束的派工只輸出現況。exit 2：60 秒內未確認停止或無法停止。",
        epilog="範例：dispatch.py cancel --dispatch-id <UUID>")
    q.add_argument("--dispatch-id", required=True, metavar="UUID", help="dispatch 輸出的派工識別碼")
    q.add_argument("--state-dir", help="選填，與 dispatch 相同的狀態目錄")
    q = sub.add_parser("supervise", help="內部使用：由 dispatch 啟動的背景程序", description="僅供 dispatch 啟動的背景程序使用，不要直接呼叫。")
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
            print("| 任務類型 | 適用需求 | 層級數 | 接手順序 |\n| --- | --- | --- | --- |")
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
                print(f"{row['level']}. {row['tool']} / {row['family']} | {row['execution']} | effort={row.get('effort')} | minimum={row.get('minimum', '無')}")
        return 0
    try:
        if a.command == "supervise":
            supervise(a, policy)
            return 0
        if a.command == "status":
            if not math.isfinite(a.wait) or a.wait < 0:
                raise DispatchError("--wait 必須是有限的非負數")
            result = status(a)
        elif a.command == "cancel":
            result = cancel(a)
        else:
            if not math.isfinite(a.timeout) or a.timeout <= 0:
                raise DispatchError("--timeout 必須是有限正數")
            if not math.isfinite(a.stall_timeout) or a.stall_timeout <= 0:
                raise DispatchError("--stall-timeout 必須是有限正數")
            result = dispatch(a, policy)
            if "spawned" in result:
                result = handshake(result)
        print(json.dumps(result, ensure_ascii=False))
        return 0
    except (DispatchError, OSError, ValueError, KeyError) as exc:
        print("錯誤：" + str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    if os.name == "nt":
        for stream in (sys.stdin, sys.stdout, sys.stderr):
            stream.reconfigure(encoding="utf-8")
    def interrupted(_signum, _frame):
        raise KeyboardInterrupt
    signal.signal(signal.SIGTERM, interrupted)
    raise SystemExit(main())
