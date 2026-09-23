"""POSIX PTY relay preventing binary output from switching terminal character sets.

Not a general ANSI security sanitizer: cursor/color/OSC controls needed by the TUI
remain available. Raw client logs are untouched. Protection requires this launcher.
"""
from __future__ import annotations

import codecs
import errno
import os
import select
import signal
import sys


class CharsetGuard:
    def __init__(self):
        self.decoder = codecs.getincrementaldecoder('utf-8')(errors='replace')
        self.mode = 'text'
        self.removed = 0

    def feed(self, data, final=False):
        out = []
        for char in self.decoder.decode(data, final=final):
            code = ord(char)
            # Strip SO/SI, raw C1/SS2/SS3 and non-display C0 in every parser state.
            if (code < 32 and char not in '\x1b\n\r\t\b\x07') or 0x7f <= code <= 0x9f:
                self.removed += 1
                continue
            if char == '\x1b':
                self.mode = 'escape'
                continue
            if self.mode == 'escape':
                if 0x20 <= code <= 0x2f:
                    self.mode = 'designation'
                    self.removed += 1
                    continue
                self.mode = 'text'
                if char in 'NOno|}~':  # single/locking shifts to G1/G2/G3
                    self.removed += 1
                    continue
                out.append('\x1b' + char)
            elif self.mode == 'designation':
                # ESC intermediates + final designate character sets/encoding.
                if not 0x20 <= code <= 0x2f:
                    self.mode = 'text'
            else:
                out.append(char)
        if final:
            self.mode = 'text'  # Never flush an incomplete ESC to the real terminal.
        return ''.join(out).encode('utf-8')


def write_all(fd, data):
    while data:
        size = os.write(fd, data)
        data = data[size:]


def run(argv, cwd):
    """Relay the child TUI; preserve input, window resizing, exit code and tty state."""
    import fcntl
    import pty
    import termios
    import tty

    if not os.isatty(0) or not os.isatty(1):
        raise RuntimeError('RE guarded interactive launch requires a terminal on stdin/stdout')
    saved = termios.tcgetattr(0)
    guard = CharsetGuard()
    pid, master = pty.fork()
    if pid == 0:
        try:
            os.chdir(cwd)
            os.execvp(argv[0], argv)
        except Exception:
            os._exit(127)

    def resize(*_):
        size = fcntl.ioctl(0, termios.TIOCGWINSZ, b'\0' * 8)
        fcntl.ioctl(master, termios.TIOCSWINSZ, size)

    def forward(signum, _frame):
        try:
            os.killpg(pid, signum)
        except ProcessLookupError:
            pass

    previous = {s: signal.getsignal(s) for s in (signal.SIGWINCH, signal.SIGTERM, signal.SIGHUP)}
    try:
        signal.signal(signal.SIGWINCH, resize)
        signal.signal(signal.SIGTERM, forward)
        signal.signal(signal.SIGHUP, forward)
        resize()
        tty.setraw(0)
        # Restore ASCII/UTF-8 if an earlier unguarded session left the terminal shifted.
        write_all(1, b'\x0f\x1b(B\x1b)B\x1b%G')
        while True:
            ready, _, _ = select.select([0, master], [], [])
            if master in ready:
                try:
                    data = os.read(master, 65536)
                except OSError as exc:
                    if exc.errno != errno.EIO:
                        raise
                    break
                if not data:
                    break
                write_all(1, guard.feed(data))
            if 0 in ready:
                data = os.read(0, 65536)
                if not data:
                    forward(signal.SIGHUP, None)
                    break
                write_all(master, data)
        write_all(1, guard.feed(b'', final=True))
    finally:
        termios.tcsetattr(0, termios.TCSADRAIN, saved)
        os.close(master)
        for sig, handler in previous.items():
            signal.signal(sig, handler)
        write_all(1, b'\x0f\x1b(B\x1b)B\x1b%G')
    _, status = os.waitpid(pid, 0)
    if guard.removed:
        print(f'RE terminal guard: filtered {guard.removed} control/charset sequences; raw client logs unchanged.')
    code = os.waitstatus_to_exitcode(status)
    return code if code >= 0 else 128 - code


if __name__ == '__main__':
    # Diagnostic/test entry, no model launch unless the caller explicitly names one.
    raise SystemExit(run(sys.argv[1:], os.getcwd()))
