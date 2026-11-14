"""Bounded regular-file reads for explicitly selected, read-only CLI inputs."""
import os
from pathlib import Path
import stat


def read_bounded(source, limit):
    """Reject special files before opening; permit ordinary symlinks to files.

    This bounds bytes, not filesystem latency or hostile concurrent mutation.
    POSIX nonblocking open also prevents FIFO waits after path replacement.
    """
    if type(limit) is not int or limit < 0:
        raise ValueError('invalid input byte limit')
    info = Path(source).stat()
    if not stat.S_ISREG(info.st_mode):
        raise ValueError('input source must be a regular file')
    if info.st_size > limit:
        raise ValueError('input exceeds byte limit')
    def bounded_open(path, flags):
        return os.open(path, flags | getattr(os, 'O_NONBLOCK', 0))
    with open(source, 'rb', opener=bounded_open) as stream:
        opened = os.fstat(stream.fileno())
        if not stat.S_ISREG(opened.st_mode):
            raise ValueError('input source must be a regular file')
        if opened.st_size > limit:
            raise ValueError('input exceeds byte limit')
        raw = stream.read(limit + 1)
    if len(raw) > limit:
        raise ValueError('input exceeds byte limit')
    return raw
