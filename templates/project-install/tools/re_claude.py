"""Optional Claude Code adapter. Research rules live in shared project skills."""
from pathlib import Path
import sys
from re_terminal_guard import run as guarded_run

ROOT = Path(__file__).resolve().parents[1]
PROMPTS = {'start': '/research-resume', 'status': '/research-status'}


def main():
    if len(sys.argv) != 2 or sys.argv[1] not in PROMPTS:
        raise SystemExit('usage: re_claude.py start|status')
    # Let Claude resolve its own project/local/user settings and existing credentials.
    # No model alias, provider switch, API key, permission bypass or fallback injection.
    print('Starting NEW Claude Code session; existing Claude settings/auth apply; terminal charset guard=ON.', flush=True)
    return guarded_run(['claude', PROMPTS[sys.argv[1]]], cwd=ROOT)


if __name__ == '__main__':
    raise SystemExit(main())
