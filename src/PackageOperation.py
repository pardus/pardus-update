"""Serialize the updater's privileged package operations across processes."""
from contextlib import contextmanager
import errno
import fcntl
from locale import dgettext
import os
import sys


@contextmanager
def package_operation(path="/run/pardus-update.lock"):
    # Keep the file: unlinking a locked file would allow a second lock inode.
    # The kernel releases the lock when the process exits, including on failure.
    with os.fdopen(os.open(path, os.O_WRONLY | os.O_CREAT, 0o600), "w") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as error:
            if error.errno not in (errno.EACCES, errno.EAGAIN):
                raise
            print(dgettext("pardus-update", "Package manager is busy, try again after the process is completed."),
                  file=sys.stderr)
            sys.exit(11)
        yield
