"""Open a local web dashboard, or explicitly request the terminal diagnostic view."""
import argparse
from pathlib import Path
import subprocess
import sys
import time


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--watch", type=float, default=None, metavar="SECONDS")
    parser.add_argument("--text", action="store_true")
    args = parser.parse_args()
    if args.watch is not None and args.watch < 2:
        parser.error("watch interval must be at least 2 seconds")
    root = Path(__file__).resolve().parents[1]
    if not args.text and args.watch is None:
        from researchlog.web import main as web_main
        return web_main(["--root", str(root)])
    try:
        while True:
            if args.watch and sys.stdout.isatty():
                print("\033[2J\033[H", end="", flush=True)
            code = subprocess.call([sys.executable, str(root / "tools/re"), "dashboard"], cwd=root)
            if args.watch is None:
                return code
            # A failed read replaces the screen with its error, never a stale green view.
            if code:
                print(f"读取/校验异常（exit {code}）；下次刷新将重试。", flush=True)
            time.sleep(args.watch)
    except KeyboardInterrupt:
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
