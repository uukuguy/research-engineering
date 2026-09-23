#!/usr/bin/env python3
"""Bounded, terminal-safe file inspection. Output is ASCII JSON, never raw bytes."""
import argparse
import json
from pathlib import Path
import stat
import unicodedata


def preview(path, limit=4096):
    if not 1 <= limit <= 1048576:
        raise ValueError('limit must be between 1 and 1048576 bytes')
    if not stat.S_ISREG(path.stat().st_mode):
        raise ValueError('only regular files can be previewed')
    with path.open('rb') as stream:
        raw = stream.read(limit + 1)
    truncated = len(raw) > limit
    sample = raw[:limit]
    # Incremental decode allows a valid UTF-8 character to cross the preview boundary.
    import codecs
    try:
        text = codecs.getincrementaldecoder('utf-8')().decode(sample, final=not truncated)
        binary = any(unicodedata.category(c).startswith('C') and c not in '\n\r\t' for c in text)
    except UnicodeDecodeError:
        text, binary = '', True
    result = {'path': str(path), 'sample_bytes': len(sample), 'truncated': truncated,
              'kind': 'binary_or_control_bytes' if binary else 'utf8_text_sample'}
    if binary:
        result['hex_prefix'] = sample[:64].hex(' ')
    else:
        result['text'] = text
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('path', type=Path)
    parser.add_argument('--limit', type=int, default=4096)
    args = parser.parse_args()
    try:
        result = preview(args.path, args.limit)
        code = 0
    except (OSError, ValueError) as exc:
        result, code = {'error': str(exc)}, 2
    print(json.dumps(result, ensure_ascii=True))
    return code


if __name__ == '__main__':
    raise SystemExit(main())
