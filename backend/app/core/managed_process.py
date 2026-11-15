"""Run a private worker with lifetime containment for all of its descendants."""
import json
import os
import signal
import subprocess
import sys


def _windows_job():
    import ctypes
    from ctypes import wintypes

    class Basic(ctypes.Structure):
        _fields_ = [('process_time', ctypes.c_int64), ('job_time', ctypes.c_int64),
                    ('flags', wintypes.DWORD), ('minimum', ctypes.c_size_t),
                    ('maximum', ctypes.c_size_t), ('active', wintypes.DWORD),
                    ('affinity', ctypes.c_size_t), ('priority', wintypes.DWORD),
                    ('scheduling', wintypes.DWORD)]

    class IO(ctypes.Structure):
        _fields_ = [(name, ctypes.c_uint64) for name in
                    ('reads', 'writes', 'other', 'read_bytes', 'write_bytes', 'other_bytes')]

    class Extended(ctypes.Structure):
        _fields_ = [('basic', Basic), ('io', IO), ('process_memory', ctypes.c_size_t),
                    ('job_memory', ctypes.c_size_t), ('peak_process', ctypes.c_size_t),
                    ('peak_job', ctypes.c_size_t)]

    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.CreateJobObjectW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR]
    kernel.CreateJobObjectW.restype = wintypes.HANDLE
    kernel.SetInformationJobObject.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD]
    kernel.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    handle = kernel.CreateJobObjectW(None, None)
    if not handle:
        raise ctypes.WinError(ctypes.get_last_error())
    limits = Extended()
    limits.basic.flags = 0x2000  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
    if not kernel.SetInformationJobObject(handle, 9, ctypes.byref(limits), ctypes.sizeof(limits)):
        error = ctypes.WinError(ctypes.get_last_error())
        kernel.CloseHandle(handle)
        raise error
    return kernel, handle


def run(command, *, cwd=None, env=None, stdout=None, stderr=None, timeout=None, check=False):
    """A finite internal subprocess.run subset, preserving its exit/timeout rules.

    On Windows the bootstrap cannot start the requested command until it has
    joined our unnamed, non-inherited kill-on-close job. Thus even a Python
    redirector or a grandchild cannot escape a timeout by outliving its parent.
    No process discovery, name matching or unrelated process termination occurs.
    """
    if not isinstance(command, (tuple, list)) or not command or any(not isinstance(value, (str, os.PathLike)) for value in command):
        raise ValueError('A fixed worker argument list is required')
    arguments = [os.fspath(value) for value in command]
    bootstrap = 'import json,subprocess,sys;sys.exit(subprocess.call(json.load(sys.stdin),stdin=subprocess.DEVNULL))'
    job = _windows_job() if os.name == 'nt' else None
    process = None
    try:
        process = subprocess.Popen([sys.executable, '-c', bootstrap], cwd=cwd, env=env,
            stdin=subprocess.PIPE, stdout=stdout, stderr=stderr,
            **({'creationflags': subprocess.CREATE_NO_WINDOW} if job else {'start_new_session': True}))
        if job:
            import ctypes
            if not job[0].AssignProcessToJobObject(job[1], int(process._handle)):
                raise ctypes.WinError(ctypes.get_last_error())
        try:
            output, errors = process.communicate(json.dumps(arguments).encode('utf-8'), timeout=timeout)
        except subprocess.TimeoutExpired as error:
            raise subprocess.TimeoutExpired(arguments, timeout, output=error.output, stderr=error.stderr) from None
        result = subprocess.CompletedProcess(arguments, process.returncode, output, errors)
        if check:
            result.check_returncode()
        return result
    finally:
        if job:
            # Also reap detached workers after a successful parent exit.
            job[0].CloseHandle(job[1])
        elif process is not None:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        if process is not None and process.poll() is None:
            # Assignment can fail before the stdin gate opens; only this exact
            # bootstrap exists then and it has not launched a child.
            process.kill()
            process.wait(timeout=10)
