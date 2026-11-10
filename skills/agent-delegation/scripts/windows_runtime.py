"""Windows primitives for dispatch (stdlib only, Windows 10+)."""
import ctypes as C
from ctypes import wintypes as W
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time

kernel = C.WinDLL("kernel32", use_last_error=True)
advapi = C.WinDLL("advapi32", use_last_error=True)


def api(dll, name, restype, *argtypes):
    func = getattr(dll, name)
    func.restype, func.argtypes = restype, argtypes
    return func


close = api(kernel, "CloseHandle", W.BOOL, W.HANDLE)
local_free = api(kernel, "LocalFree", W.HLOCAL, W.HLOCAL)
open_process = api(kernel, "OpenProcess", W.HANDLE, W.DWORD, W.BOOL, W.DWORD)
wait_handle = api(kernel, "WaitForSingleObject", W.DWORD, W.HANDLE, W.DWORD)
open_token = api(advapi, "OpenProcessToken", W.BOOL, W.HANDLE, W.DWORD, C.POINTER(W.HANDLE))
token_info = api(advapi, "GetTokenInformation", W.BOOL, W.HANDLE, C.c_int, W.LPVOID, W.DWORD, C.POINTER(W.DWORD))
sid_string = api(advapi, "ConvertSidToStringSidW", W.BOOL, W.LPVOID, C.POINTER(W.LPWSTR))
convert_sd = api(advapi, "ConvertStringSecurityDescriptorToSecurityDescriptorW", W.BOOL,
                 W.LPCWSTR, W.DWORD, C.POINTER(W.LPVOID), C.POINTER(W.DWORD))
get_security = api(advapi, "GetNamedSecurityInfoW", W.DWORD, W.LPCWSTR, C.c_int, W.DWORD,
                   W.LPVOID, W.LPVOID, C.POINTER(W.LPVOID), W.LPVOID, C.POINTER(W.LPVOID))
get_ace = api(advapi, "GetAce", W.BOOL, W.LPVOID, W.DWORD, C.POINTER(W.LPVOID))


def checked(ok):
    if not ok:
        raise C.WinError(C.get_last_error())
    return ok


def sid_text(sid):
    text = W.LPWSTR()
    checked(sid_string(sid, C.byref(text)))
    try:
        return text.value
    finally:
        local_free(C.cast(text, W.HLOCAL))


def user_sid():
    token, size = W.HANDLE(), W.DWORD()
    checked(open_token(W.HANDLE(-1), 8, C.byref(token)))
    try:
        token_info(token, 1, None, 0, C.byref(size))
        data = C.create_string_buffer(size.value)
        checked(token_info(token, 1, data, size, C.byref(size)))
        return sid_text(C.cast(data, C.POINTER(W.LPVOID))[0])
    finally:
        close(token)


class SecurityAttributes(C.Structure):
    _fields_ = [("length", W.DWORD), ("descriptor", W.LPVOID), ("inherit", W.BOOL)]


class ACL(C.Structure):
    _fields_ = [("revision", W.BYTE), ("pad", W.BYTE), ("size", W.WORD),
                ("count", W.WORD), ("pad2", W.WORD)]


def ensure_private(path, directory=False):
    """Create a private directory; refuse existing ACLs granting other users access."""
    if path.exists() and getattr(path.lstat(), "st_file_attributes", 0) & 0x400:
        raise OSError("狀態路徑不可是 reparse point：" + str(path))
    if directory and not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        descriptor = W.LPVOID()
        sddl = "D:P(A;OICI;FA;;;SY)(A;OICI;FA;;;BA)(A;OICI;FA;;;" + user_sid() + ")"
        checked(convert_sd(sddl, 1, C.byref(descriptor), None))
        try:
            attrs = SecurityAttributes(C.sizeof(SecurityAttributes), descriptor, False)
            create = api(kernel, "CreateDirectoryW", W.BOOL, W.LPCWSTR, C.POINTER(SecurityAttributes))
            if not create(str(path), C.byref(attrs)) and C.get_last_error() != 183:
                raise C.WinError(C.get_last_error())
        finally:
            local_free(descriptor)
    # DACL checks replace POSIX mode bits. System and administrators are trusted.
    acl, descriptor, owner = W.LPVOID(), W.LPVOID(), W.LPVOID()
    error = get_security(str(path), 1, 5, C.byref(owner), None, C.byref(acl), None, C.byref(descriptor))
    if error:
        raise C.WinError(error)
    try:
        if not acl:
            raise OSError("狀態路徑必須有私有 DACL：" + str(path))
        trusted = {user_sid(), "S-1-5-18", "S-1-5-32-544"}
        if not owner or sid_text(owner) not in trusted:
            raise OSError("狀態路徑擁有者不符目前使用者或系統管理員：" + str(path))
        for i in range(C.cast(acl, C.POINTER(ACL)).contents.count):
            ace = W.LPVOID()
            checked(get_ace(acl, i, C.byref(ace)))
            header = C.string_at(ace, 4)
            if header[1] & 8:  # INHERIT_ONLY_ACE does not apply to this object.
                continue
            if header[0] == 1:  # Deny ACE grants no access.
                continue
            if header[0] != 0 or sid_text(ace.value + 8) not in trusted:
                raise OSError("既有狀態路徑授權其他使用者存取，不會修改其權限：" + str(path))
    finally:
        local_free(descriptor)


def alive(pid):
    handle = open_process(0x100000, False, pid)
    if not handle:
        if C.get_last_error() == 87:
            return False
        if C.get_last_error() == 5:
            return True
        raise C.WinError(C.get_last_error())
    try:
        result = wait_handle(handle, 0)
        if result == 0xffffffff:
            raise C.WinError(C.get_last_error())
        return result == 258
    finally:
        close(handle)


class BasicLimits(C.Structure):
    _fields_ = [("process_time", C.c_int64), ("job_time", C.c_int64), ("flags", W.DWORD),
                ("min_working_set", C.c_size_t), ("max_working_set", C.c_size_t),
                ("active_limit", W.DWORD), ("affinity", C.c_size_t),
                ("priority", W.DWORD), ("scheduling", W.DWORD)]


class ExtendedLimits(C.Structure):
    _fields_ = [("basic", BasicLimits), ("io", C.c_uint64 * 6),
                ("process_memory", C.c_size_t), ("job_memory", C.c_size_t),
                ("peak_process_memory", C.c_size_t), ("peak_job_memory", C.c_size_t)]


class Accounting(C.Structure):
    _fields_ = [("times", C.c_int64 * 4), ("page_faults", W.DWORD), ("total", W.DWORD),
                ("active", W.DWORD), ("terminated", W.DWORD)]


create_job = api(kernel, "CreateJobObjectW", W.HANDLE, W.LPVOID, W.LPCWSTR)
open_job = api(kernel, "OpenJobObjectW", W.HANDLE, W.DWORD, W.BOOL, W.LPCWSTR)
set_job = api(kernel, "SetInformationJobObject", W.BOOL, W.HANDLE, C.c_int, W.LPVOID, W.DWORD)
query_job = api(kernel, "QueryInformationJobObject", W.BOOL, W.HANDLE, C.c_int, W.LPVOID, W.DWORD, W.LPVOID)
assign_job = api(kernel, "AssignProcessToJobObject", W.BOOL, W.HANDLE, W.HANDLE)
terminate_job = api(kernel, "TerminateJobObject", W.BOOL, W.HANDLE, W.UINT)


def job_name(pid):
    return "Local\\agent-delegation-" + str(pid)


def active_count(job):
    info = Accounting()
    checked(query_job(job, 1, C.byref(info), C.sizeof(info), None))
    return info.active


def group_live(pid):
    job = open_job(4, False, job_name(pid))
    if not job:
        return False if C.get_last_error() == 2 else None
    try:
        return active_count(job) != 0
    except OSError:
        return None
    finally:
        close(job)


def executable_argv(argv):
    """Resolve executable files and standard npm shims without passing prompts to cmd.exe."""
    program = shutil.which(argv[0])
    if not program:
        raise FileNotFoundError(2, "找不到 CLI", argv[0])
    path = Path(program)
    if path.suffix.lower() in (".cmd", ".bat"):
        content = path.read_text(encoding="utf-8-sig").strip()
        header = "@ECHO off\nGOTO start\n:find_dp0\nSET dp0=%~dp0\nEXIT /b\n:start\nSETLOCAL\nCALL :find_dp0\n"
        direct = re.fullmatch(re.escape(header) + r'"%dp0%\\([^"\r\n]+\.exe)" +%\*', content, re.I)
        if direct:
            return [str((path.parent / direct[1]).resolve(strict=True)), *argv[1:]]
        node_block = ('IF EXIST "%dp0%\\node.exe" (\n  SET "_prog=%dp0%\\node.exe"\n) ELSE (\n'
                      '  SET "_prog=node"\n  SET PATHEXT=%PATHEXT:;.JS;=;%\n)\n\n'
                      'endLocal & goto #_undefined_# 2>NUL || title %COMSPEC% & "%_prog%" ')
        match = re.fullmatch(re.escape(header + node_block) +
                             r'"%dp0%\\([^"\r\n]+\.(?:js|cjs|mjs))" +%\*', content, re.I)
        if not match:
            raise OSError("無法安全辨識此 batch CLI，請安裝可執行檔或標準 npm shim：" + program)
        entry = (path.parent / match[1]).resolve(strict=True)
        node = path.parent / "node.exe"
        runtime = str(node) if node.is_file() else shutil.which("node.exe")
        if not runtime or Path(runtime).suffix.lower() != ".exe":
            raise FileNotFoundError(2, "npm CLI 需要 node.exe", str(path))
        return [runtime, str(entry), *argv[1:]]
    return [program, *argv[1:]]


def start(argv, cwd, out, err):
    # The isolated bootstrap cannot launch the CLI until the parent assigns its job.
    proc = subprocess.Popen([sys.executable, "-I", "-S", str(Path(__file__).resolve()), "--worker"],
                            cwd=cwd, stdin=subprocess.PIPE, stdout=out, stderr=err,
                            creationflags=subprocess.CREATE_NO_WINDOW)
    job = None
    try:
        job = checked(create_job(None, job_name(proc.pid)))
        if C.get_last_error() == 183:
            raise OSError("Windows Job 名稱已被占用，不會沿用既有 Job")
        limits = ExtendedLimits()
        limits.basic.flags = 0x2000  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        checked(set_job(job, 9, C.byref(limits), C.sizeof(limits)))
        checked(assign_job(job, W.HANDLE(int(proc._handle))))
        proc.dispatch_job = job
        proc.dispatch_argv = executable_argv(argv)
        return proc
    except BaseException:
        proc.kill()
        proc.wait()
        proc.stdin.close()
        if job:
            close(job)
        raise


def release(proc):
    proc.stdin.write(json.dumps(proc.dispatch_argv).encode("utf-8"))
    proc.stdin.close()


def terminate(proc):
    job = proc.dispatch_job
    checked(terminate_job(job, 1))
    deadline = time.monotonic() + 5
    while active_count(job):
        if time.monotonic() >= deadline:
            raise OSError("尚未確認 Windows Job 的所有工作程序已停止")
        time.sleep(.05)
    proc.wait(timeout=5)
    close(job)
    proc.dispatch_job = None


if __name__ == "__main__":
    # EOF before a JSON payload means the parent failed before authorizing launch.
    payload = sys.stdin.buffer.read()
    if payload:
        try:
            raise SystemExit(subprocess.call(json.loads(payload), stdin=subprocess.DEVNULL,
                                            env=dict(os.environ, PYTHONUTF8="1")))
        except OSError as exc:
            print(str(exc), file=sys.stderr)
            raise SystemExit(127)
