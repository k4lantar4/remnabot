from __future__ import annotations

import json
import re
import sqlite3
from pathlib import Path

from tools.migration.config import SERVER_VIP, SKIP_SERVER_IDS, XUI_BACKUP_DIR
from tools.migration.models import XuiClient

SERVER_ID_RE = re.compile(r'server(\d+)-')


def _parse_server_id(path: Path) -> int:
    m = SERVER_ID_RE.search(path.name)
    if not m:
        raise ValueError(f'cannot parse server id from {path.name}')
    return int(m.group(1))


def _table_columns(conn: sqlite3.Connection, table: str) -> set[str]:
    return {r[1] for r in conn.execute(f'PRAGMA table_info({table})')}


def extract_clients_from_db(db_path: Path, server_id: int, vip: int) -> list[XuiClient]:
    conn = sqlite3.connect(f'file:{db_path.resolve()}?mode=ro', uri=True)
    conn.row_factory = sqlite3.Row
    try:
        tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if 'inbounds' not in tables:
            return []

        traffic: dict[str, sqlite3.Row] = {}
        if 'client_traffics' in tables:
            cols = _table_columns(conn, 'client_traffics')
            select_cols = ['email', 'up', 'down', 'enable']
            if 'expiryTime' in cols:
                select_cols.append('expiryTime')
            elif 'expiry_time' in cols:
                select_cols.append('expiry_time')
            if 'total' in cols:
                select_cols.append('total')
            query = f"SELECT {', '.join(select_cols)} FROM client_traffics"
            for row in conn.execute(query):
                traffic[row['email']] = row

        clients: list[XuiClient] = []
        for (settings_json,) in conn.execute('SELECT settings FROM inbounds WHERE settings IS NOT NULL'):
            if not settings_json:
                continue
            try:
                settings = json.loads(settings_json)
            except json.JSONDecodeError:
                continue
            for raw in settings.get('clients') or []:
                email = (raw.get('email') or '').strip()
                uuid = (raw.get('id') or '').strip()
                if not email or not uuid:
                    continue
                tr = traffic.get(email)
                up = int(tr['up']) if tr else 0
                down = int(tr['down']) if tr else 0
                enable = bool(raw.get('enable', True))
                if tr is not None:
                    enable = bool(tr['enable'])
                expiry_ms = int(raw.get('expiryTime') or 0)
                if tr is not None:
                    tr_exp = tr['expiryTime'] if 'expiryTime' in tr.keys() else tr['expiry_time'] if 'expiry_time' in tr.keys() else 0
                    if tr_exp:
                        expiry_ms = int(tr_exp)
                        if expiry_ms < 10_000_000_000:
                            expiry_ms *= 1000
                total_gb = int(raw.get('totalGB') or 0)
                if tr is not None and 'total' in tr.keys() and tr['total']:
                    total_gb = max(total_gb, int(int(tr['total']) / (1024**3)))
                clients.append(
                    XuiClient(
                        server_id=server_id,
                        email=email,
                        uuid=uuid,
                        enable=enable,
                        expiry_ms=expiry_ms,
                        up=up,
                        down=down,
                        total=total_gb,
                        vip=vip,
                    )
                )
        return clients
    finally:
        conn.close()


def extract_all_xui_clients(backup_dir: Path = XUI_BACKUP_DIR) -> list[XuiClient]:
    all_clients: list[XuiClient] = []
    for db_path in sorted(backup_dir.glob('server*.db')):
        server_id = _parse_server_id(db_path)
        if server_id in SKIP_SERVER_IDS:
            continue
        vip = SERVER_VIP.get(server_id, 20)
        try:
            all_clients.extend(extract_clients_from_db(db_path.resolve(), server_id, vip))
        except sqlite3.OperationalError:
            continue
    return all_clients
