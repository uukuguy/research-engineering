"""Local, read-only dashboard. No model, daemon, third-party assets or write HTTP API."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import subprocess
import sys
import threading
import time
from urllib.parse import urlsplit, parse_qs

ASSETS = Path(__file__).with_name('web_assets')


def state_dir(root):
    for name in ('.research', 'research'):
        path = root / name
        if (path / 'ACTIVE.json').is_file():
            return path
    raise ValueError('未发现 RE 状态；请先初始化项目。')


def basis(root):
    """Content identity, not file timestamps; never hash or expose arbitrary work/data."""
    folder = state_dir(root)
    files = [folder / name for name in ('ACTIVE.json', 'CURRENT.md', 'ARCHITECT.md',
             'BOUNDARIES.md', 'ENVIRONMENT.md', 'FINDINGS.md')]
    files += list((folder / 'ledger').rglob('EV-*.json'))
    files += list((folder / 'runs').glob('*/manifest.json'))
    files += list((folder / 'runs').glob('*/result.json'))
    files += list((folder / 'delegations').glob('*.json'))
    files += [root / 'TASK.md']
    digest = hashlib.sha256()
    for path in sorted(files):
        if path.is_file():
            if not path.resolve().is_relative_to(root):
                raise ValueError('状态文件指向项目外，停止读取。')
            digest.update(str(path.relative_to(root)).encode())
            digest.update(hashlib.sha256(path.read_bytes()).digest())
    return digest.hexdigest()


def validate_brief(brief):
    if not isinstance(brief, dict) or brief.get('version') != 1:
        raise ValueError('brief.version must be 1')
    if not isinstance(brief.get('source_revision'), str) or len(brief['source_revision']) != 64:
        raise ValueError('source_revision must come from --basis before synthesis')
    for key in ('headline', 'goal', 'capability', 'gap', 'next', 'decision'):
        item = brief.get(key)
        if not isinstance(item, dict) or not isinstance(item.get('text'), str) or not item['text'].strip():
            raise ValueError(f'{key} requires text and refs')
        if not isinstance(item.get('refs'), list) or not item['refs'] or not all(isinstance(x, str) for x in item['refs']):
            raise ValueError(f'{key}.refs must identify the source records')
    for key in ('routes', 'conclusions', 'events'):
        if not isinstance(brief.get(key, {}), dict):
            raise ValueError(f'{key} must be an ID-keyed object')
        for item in brief.get(key, {}).values():
            if not isinstance(item, dict) or not isinstance(item.get('text'), str):
                raise ValueError(f'{key} entries require text')
    if 'activity' in brief:
        item = brief['activity']
        if not isinstance(item, dict) or not isinstance(item.get('text'), str) or not item['text'].strip():
            raise ValueError('activity requires text')


def activity_revision(payload):
    block = payload.get('block') or {}
    identity = {key: block.get(key) for key in ('id', 'objective', 'started_at')}
    return hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()


def display_revisions(payload, events):
    """Bind each translated row to its source, independently of global freshness."""
    def fingerprint(value):
        return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=True).encode()).hexdigest()
    return {group: {row['id']: fingerprint(row) for row in rows}
            for group, rows in (('routes', payload.get('routes', [])),
                                ('conclusions', payload.get('conclusions', [])),
                                ('events', events))}


def current_translations(brief, revisions, fresh):
    if not brief:
        return {}
    saved = brief.get('display_revisions', {})
    return {group: {key: value for key, value in brief.get(group, {}).items()
                    if key in rows and (fresh or saved.get(group, {}).get(key) == rows[key])}
            for group, rows in revisions.items()}


def publish(root, path):
    brief = json.loads(path.read_text())
    validate_brief(brief)
    if brief['source_revision'] != basis(root):
        raise ValueError('源记录已变化；重新读取并综合，不可给旧摘要换新指纹。')
    snapshot = Snapshot(root).get()
    if snapshot['source_revision'] != brief['source_revision']:
        raise ValueError('源记录已变化；重新读取并综合。')
    brief['display_revisions'] = display_revisions(snapshot['payload'], snapshot['events'])
    brief['activity_revision'] = activity_revision(snapshot['payload'])
    brief['generated_at'] = datetime.now(timezone.utc).isoformat()
    dest = state_dir(root) / '.derived/dashboard-brief.json'
    dest.parent.mkdir(parents=True, exist_ok=True)
    temp = dest.with_suffix('.tmp')
    temp.write_text(json.dumps(brief, ensure_ascii=False, indent=2) + '\n')
    temp.replace(dest)
    return dest


class Snapshot:
    def __init__(self, root):
        self.root = root.resolve()
        self.lock = threading.Lock()
        self.cached = None
        self.checked = 0

    def get(self):
        with self.lock:
            if self.cached is not None and time.monotonic() - self.checked < 4:
                return self.cached
            before = basis(self.root)
            proc = subprocess.run([sys.executable, str(self.root / 'tools/re'),
                'dashboard', '--json'], cwd=self.root, capture_output=True, text=True, timeout=20)
            data = json.loads(proc.stdout)
            if not isinstance(data.get('payload'), dict) or 'recorded_status' not in data['payload']:
                raise ValueError('项目状态无法读取，请在会话中检查 RE 状态。')
            after = basis(self.root)
            if before != after:
                raise ValueError('研究记录正在更新；下次刷新重试，不展示混合快照。')
            data['project'] = self.root.name
            data['source_revision'] = after
            data['brief'] = None
            data['brief_status'] = 'missing'
            path = state_dir(self.root) / '.derived/dashboard-brief.json'
            if path.is_file() and path.resolve().is_relative_to(self.root):
                try:
                    brief = json.loads(path.read_text())
                    validate_brief(brief)
                    data['brief'] = brief
                    data['brief_status'] = 'current' if brief['source_revision'] == after else 'stale'
                except (ValueError, OSError):
                    data['brief_status'] = 'invalid'
            data['events'] = self.events(data['payload'])
            data['translations'] = current_translations(data['brief'],
                display_revisions(data['payload'], data['events']), data['brief_status'] == 'current')
            brief = data['brief'] or {}
            data['activity'] = brief.get('activity') if (brief.get('activity_revision') ==
                activity_revision(data['payload'])) else None
            self.cached, self.checked = data, time.monotonic()
            return data

    @staticmethod
    def events(payload):
        events = [{'id': e['id'], 'at': e.get('created_at'), 'kind': 'evidence',
                   'title': e.get('question'), 'detail': e.get('observation'),
                   'outcome': e.get('research_outcome')} for e in payload.get('recent_evidence', [])]
        for route in payload.get('routes', []):
            for i, event in enumerate(route.get('history', [])):
                events.append({'id': f"{route['id']}:{i}", 'at': event.get('at'), 'kind': 'route',
                    'title': route['title'], 'detail': event.get('reason'), 'outcome': event.get('to')})
        def stamp(event):
            try:
                parsed = datetime.fromisoformat(str(event.get('at')).replace('Z', '+00:00'))
                return parsed.timestamp() if parsed.tzinfo else 0
            except ValueError:
                return 0
        return sorted(events, key=stamp, reverse=True)[:20]

    def report(self, finding, index):
        data = self.get()
        entry = next(f for f in data['payload']['conclusions'] if f['id'] == finding)
        if index < 0:
            raise ValueError('Invalid report index')
        record = entry['reports'][index]
        path = (self.root / record['path']).resolve()
        if not path.is_relative_to(self.root) or path.suffix.lower() not in ('.md', '.txt', '.json'):
            raise ValueError('仅允许读取项目内登记的文本研究报告。')
        if path.stat().st_size > 2_000_000:
            raise ValueError('报告过大，请在本地编辑器中查看。')
        raw = path.read_bytes()
        actual = hashlib.sha256(raw).hexdigest()
        expected = record.get('recorded_sha256')
        return {'path': record['path'], 'text': raw.decode('utf-8'),
                'integrity': 'match' if expected == actual else 'changed' if expected else 'unrecorded'}


def handler(snapshot):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def send(self, code, body, mime='application/json; charset=utf-8'):
            if not isinstance(body, bytes):
                body = json.dumps(body, ensure_ascii=False).encode()
            self.send_response(code)
            self.send_header('Content-Type', mime)
            self.send_header('Content-Length', str(len(body)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; img-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'")
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            host = f'127.0.0.1:{self.server.server_port}'
            if self.headers.get('Host') != host or self.headers.get('Origin') not in (None, f'http://{host}'):
                return self.send(403, {'error': '仅限本机同源访问。'})
            url = urlsplit(self.path)
            assets = {'/': ('index.html', 'text/html'), '/app.js': ('app.js', 'text/javascript'),
                      '/style.css': ('style.css', 'text/css')}
            try:
                if url.path in assets:
                    name, mime = assets[url.path]
                    return self.send(200, (ASSETS / name).read_bytes(), mime + '; charset=utf-8')
                if url.path == '/api/snapshot':
                    return self.send(200, snapshot.get())
                if url.path == '/api/report':
                    query = parse_qs(url.query)
                    return self.send(200, snapshot.report(query['finding'][0], int(query['index'][0])))
                return self.send(404, {'error': '不存在该页面。'})
            except (ValueError, OSError, KeyError, IndexError, StopIteration, subprocess.SubprocessError):
                return self.send(503, {'error': '读取失败或记录正在变化。保留上次画面，下次刷新重试；必要时在研究会话检查状态。'})
    return Handler


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path.cwd())
    parser.add_argument('--port', type=int, default=0, help='0 selects a free loopback port')
    parser.add_argument('--basis', action='store_true')
    parser.add_argument('--publish-brief', type=Path)
    args = parser.parse_args(argv)
    root = args.root.resolve()
    if args.basis:
        print(basis(root))
        return 0
    if args.publish_brief:
        print(publish(root, args.publish_brief))
        return 0
    snapshot = Snapshot(root)
    snapshot.get()  # fail early, before printing a working URL
    with ThreadingHTTPServer(('127.0.0.1', args.port), handler(snapshot)) as server:
        print(f'RE Dashboard · http://127.0.0.1:{server.server_port}/', flush=True)
        print('只读本地页面 · 每 5 秒刷新持久记录 · 无模型调用 · Ctrl-C 退出', flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
