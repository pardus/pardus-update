"""Cross-process exclusion and crash recovery; uses a temporary lock file."""
from pathlib import Path
import os
import selectors
import subprocess
import sys
import tempfile
import unittest

SRC = str(Path(__file__).resolve().parents[1] / "src")
sys.path.insert(0, SRC)
from PackageOperation import package_operation


class PackageOperationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.lock = str(Path(self.temp.name) / "operation.lock")
        self.code = ("import sys; sys.path.insert(0, sys.argv[1]); "
                     "from PackageOperation import package_operation\n"
                     "with package_operation(sys.argv[2]):\n"
                     " print('entered', flush=True)\n")

    def run_child(self):
        return subprocess.run([sys.executable, "-c", self.code, SRC, self.lock],
                              text=True, capture_output=True, timeout=5)

    def test_second_process_is_rejected_before_entering(self):
        with package_operation(self.lock):
            result = self.run_child()
        self.assertEqual(result.returncode, 11)
        self.assertEqual(result.stdout, "")
        self.assertTrue(result.stderr)

    def test_lock_is_not_accessible_to_other_users(self):
        mask = os.umask(0)
        try:
            with package_operation(self.lock):
                self.assertEqual(Path(self.lock).stat().st_mode & 0o777, 0o600)
        finally:
            os.umask(mask)

    def test_normal_exit_releases_lock(self):
        with package_operation(self.lock):
            pass
        self.assertEqual(self.run_child().returncode, 0)

    def test_exception_releases_lock(self):
        with self.assertRaises(RuntimeError):
            with package_operation(self.lock):
                raise RuntimeError("failed operation")
        self.assertEqual(self.run_child().returncode, 0)

    def test_killed_process_leaves_no_stale_lock(self):
        code = self.code + " sys.stdin.read()\n"
        child = subprocess.Popen([sys.executable, "-c", code, SRC, self.lock],
                                 text=True, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                 stderr=subprocess.PIPE)
        try:
            with selectors.DefaultSelector() as selector:
                selector.register(child.stdout, selectors.EVENT_READ)
                self.assertTrue(selector.select(5), "Lock holder did not start")
            self.assertEqual(child.stdout.readline().strip(), "entered")
            self.assertEqual(self.run_child().returncode, 11)
            child.kill()
            child.wait(timeout=5)
            self.assertEqual(self.run_child().returncode, 0)
        finally:
            if child.poll() is None:
                child.kill()
            child.communicate(timeout=5)


if __name__ == "__main__":
    unittest.main(verbosity=2)
