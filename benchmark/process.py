"""Bounded subprocess duration and captured output; kill descendants on deadline."""
from contextlib import nullcontext
import os
import signal
import subprocess
import tempfile

MAX_CAPTURE_BYTES = 1_000_000


def _read_capture(stream):
    size = stream.tell()
    stream.seek(0)
    if size <= MAX_CAPTURE_BYTES:
        raw = stream.read()
    else:
        head = stream.read(MAX_CAPTURE_BYTES // 2)
        stream.seek(-MAX_CAPTURE_BYTES // 2, 2)
        raw = head + b"\n[benchmark output truncated]\n" + stream.read()
    return raw.decode("utf-8", errors="replace"), size > MAX_CAPTURE_BYTES


def execute(command, *, timeout=60, cwd=None, env=None, input_file=None):
    kwargs = {"start_new_session": True} if os.name != "nt" else {}
    with (open(input_file, "rb") if input_file else nullcontext(None)) as source, \
            tempfile.TemporaryFile() as stdout, tempfile.TemporaryFile() as stderr, \
            subprocess.Popen(command, cwd=cwd, env=env, stdin=source,
                             stdout=stdout, stderr=stderr, **kwargs) as process:
        timed_out = False
        try:
            process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            timed_out = True
            if os.name == "nt":
                subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"],
                               capture_output=True, timeout=15)
            else:
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
            process.kill()
            process.wait(timeout=15)
        out, out_truncated = _read_capture(stdout)
        err, err_truncated = _read_capture(stderr)
        return {"returncode": process.returncode, "stdout": out, "stderr": err,
                "timed_out": timed_out, "output_truncated": out_truncated or err_truncated}
