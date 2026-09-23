"""Optional client selector; never resumes a proprietary conversation."""
import argparse
from pathlib import Path
import runpy
import sys


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--client', choices=('codex', 'claude'), default='codex')
    parser.add_argument('action', choices=('start', 'status'))
    args = parser.parse_args()
    script = Path(__file__).with_name(f're_{args.client}.py')
    sys.argv = [str(script), args.action]
    runpy.run_path(str(script), run_name='__main__')


if __name__ == '__main__':
    main()
