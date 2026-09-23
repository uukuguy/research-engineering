import importlib.util
import os
from pathlib import Path
import pty
import select
import signal
import subprocess
import sys
import time
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / 'templates/project-install/tools/re_terminal_guard.py'
spec = importlib.util.spec_from_file_location('guard', SCRIPT)
guard = importlib.util.module_from_spec(spec)
spec.loader.exec_module(guard)


class TerminalGuardTests(unittest.TestCase):
    def test_switches_across_every_chunk_boundary(self):
        raw = b'A\x0eB\x0f\x1b(0C\x1b)0D\x1b$)CE\x1b%GF\x1bnG\x00'
        for cut in range(len(raw) + 1):
            g = guard.CharsetGuard()
            self.assertEqual(g.feed(raw[:cut]) + g.feed(raw[cut:], final=True), b'ABCDEFG')

    def test_utf8_and_tui_sequences_preserved(self):
        raw = '中文─'.encode() + b'\x1b[31mred\x1b[0m\x1b[?1049h\x1b[2;3H\x1b]11;?\x07'
        for cut in range(len(raw) + 1):
            g = guard.CharsetGuard()
            self.assertEqual(g.feed(raw[:cut]) + g.feed(raw[cut:], final=True), raw)

    def test_real_usdcat_bytes_do_not_leave_charset_switches(self):
        path = Path('/usr/bin/usdcat')
        if not path.exists():
            self.skipTest('macOS usdcat not available')
        raw = path.read_bytes().split(b'\n', 1)[0] + b'\n'
        g = guard.CharsetGuard()
        out = b''.join(g.feed(raw[i:i+17]) for i in range(0, len(raw), 17)) + g.feed(b'', final=True)
        for seq in (b'\x0e', b'\x0f', b'\x00', b'\x1b(', b'\x1b)', b'\x1b%', b'\x1b$'):
            self.assertNotIn(seq, out)
        out.decode('utf-8')
        self.assertGreater(g.removed, 0)

    def test_nested_pty_filters_stdout_stderr_and_preserves_input_exit(self):
        master, slave = pty.openpty()
        code = ("import os,sys; os.write(1,b'READY\\x0e\\x1b(0'); "
                "os.write(2,b'ERR\\x0f'); s=input(); print('GOT:'+s); sys.exit(7)")
        child = subprocess.Popen([sys.executable, str(SCRIPT), sys.executable, '-c', code],
                                 stdin=slave, stdout=slave, stderr=slave, start_new_session=True)
        os.close(slave)
        output = bytearray()
        sent = False
        deadline = time.monotonic() + 10
        try:
            while time.monotonic() < deadline:
                ready, _, _ = select.select([master], [], [], .1)
                if ready:
                    try:
                        data = os.read(master, 65536)
                    except OSError:
                        break
                    if not data:
                        break
                    output.extend(data)
                if b'READY' in output and not sent:
                    os.write(master, b'hello\n')
                    os.kill(child.pid, signal.SIGWINCH)
                    sent = True
                if child.poll() is not None and not ready:
                    break
            self.assertEqual(child.wait(timeout=1), 7)
            self.assertIn(b'GOT:hello', output)
            self.assertIn(b'READYERR', output)
            self.assertNotIn(b'\x0e', output)
            self.assertNotIn(b'\x1b(0', output)
        finally:
            if child.poll() is None:
                child.kill()
                child.wait()
            os.close(master)


if __name__ == '__main__':
    unittest.main()
