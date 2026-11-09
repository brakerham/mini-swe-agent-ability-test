from pathlib import Path
import sys
import tempfile
import unittest

from benchmark.process import execute, MAX_CAPTURE_BYTES


class ProcessTests(unittest.TestCase):
    def test_exit_and_streams_are_separate(self):
        result = execute([sys.executable, "-c", "import sys; print('out'); print('err',file=sys.stderr); sys.exit(7)"])
        self.assertEqual(result["returncode"], 7)
        self.assertEqual(result["stdout"].strip(), "out")
        self.assertEqual(result["stderr"].strip(), "err")

    def test_binary_input_reaches_child(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "input"
            path.write_bytes(b"\x00\xff\x01")
            result = execute([sys.executable, "-c", "import sys; print(sys.stdin.buffer.read().hex())"], input_file=path)
        self.assertEqual(result["stdout"].strip(), "00ff01")

    def test_capture_is_bounded_in_memory_and_marks_truncation(self):
        result = execute([sys.executable, "-c", f"print('x'*{MAX_CAPTURE_BYTES*2})"])
        self.assertTrue(result["output_truncated"])
        self.assertLess(len(result["stdout"]), MAX_CAPTURE_BYTES + 100)

    def test_deadline_is_reported(self):
        result = execute([sys.executable, "-c", "import time; time.sleep(10)"], timeout=0.1)
        self.assertTrue(result["timed_out"])
        self.assertNotEqual(result["returncode"], 0)


if __name__ == "__main__":
    unittest.main()
