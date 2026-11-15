"""Worker containment must not leave a redirector's child after completion."""
import os
from pathlib import Path
import subprocess
import sys
import time

import pytest
from app.core.managed_process import run


def alive(pid):
    if os.name == 'nt':
        import ctypes
        from ctypes import wintypes
        kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        kernel.OpenProcess.restype = wintypes.HANDLE
        kernel.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
        kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        handle = kernel.OpenProcess(0x100000, False, pid)
        if not handle:
            return False
        try:
            return kernel.WaitForSingleObject(handle, 0) == 0x102
        finally:
            kernel.CloseHandle(handle)
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False


@pytest.mark.parametrize('timeout', [True, False])
def test_private_worker_descendants_are_reaped(tmp_path, timeout):
    pidfile = tmp_path / 'owned-child.pid'
    child = "import os,time;from pathlib import Path;Path(" + repr(str(pidfile)) + ").write_text(str(os.getpid()));time.sleep(60)"
    parent = 'import subprocess,sys,time;subprocess.Popen([sys.executable,"-c",' + repr(child) + ']);time.sleep(' + ('60' if timeout else '1') + ')'
    command = [sys.executable, '-c', parent]
    if timeout:
        with pytest.raises(subprocess.TimeoutExpired) as error:
            run(command, timeout=3)
        assert error.value.cmd == command and error.value.timeout == 3
    else:
        assert run(command, timeout=10, check=True).returncode == 0
    assert pidfile.exists(), 'The test must exercise an actual child, not just its launcher'
    pid = int(pidfile.read_text())
    deadline = time.monotonic() + 5
    while alive(pid) and time.monotonic() < deadline:
        time.sleep(.02)
    assert not alive(pid)


def test_worker_preserves_output_and_checked_exit_code():
    result = run([sys.executable, '-c', 'print("worker proof")'], stdout=subprocess.PIPE, timeout=10)
    assert result.stdout.strip() == b'worker proof' and result.returncode == 0
    with pytest.raises(subprocess.CalledProcessError) as error:
        run([sys.executable, '-c', 'raise SystemExit(7)'], timeout=10, check=True)
    assert error.value.returncode == 7
