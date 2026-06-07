# Rookari → bot-remnawave Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Migrate ~761 active users (filtered from 147K `config_stat` rows and 7K 3x-ui clients) from `rookari_db.json` + SQLite 3x-ui backups into `bot-remnawave` PostgreSQL and Remnawave panel, with merged small-server topology and partner status preserved.

**Architecture:** Offline ETL pipeline in `tools/migration/`: (1) extract 3x-ui clients from SQLite backups as source-of-truth for UUID/expiry/traffic, (2) join `config_stat` + `fl_user` for Telegram ID and wallet, (3) deduplicate to one subscription per user (`MULTI_TARIFF_ENABLED=false`), (4) batch-load PostgreSQL via existing `create_*_no_commit` CRUD helpers, (5) sync Remnawave via `SubscriptionService.create_remnawave_user()` with concurrency limit. Small servers (11, 17, 40, 46) map to one Internal Squad/node; high-traffic servers stay separate.

**Tech Stack:** Python 3.13, ijson, sqlite3, SQLAlchemy async (asyncpg), pytest, existing `app/external/remnawave_api.py`, Docker Compose stack (`bot-remnawave`, `remnawave`, PostgreSQL).

**Design basis:** Prior analysis session (2026-06-07). No formal spec file yet — this plan is the source of truth until `docs/superpowers/specs/2026-06-07-rookari-migration-design.md` is written.

---

## File Structure

| File | Responsibility |
|------|----------------|
| `tools/migration/__init__.py` | Package marker |
| `tools/migration/config.py` | Paths, server→squad mapping, VIP→tariff mapping, batch sizes |
| `tools/migration/extract_xui.py` | Read 3x-ui SQLite backups → `XuiClient` records |
| `tools/migration/extract_rookari.py` | Stream `rookari_db.json` → `BotUser`, `ConfigStat`, `Seller` |
| `tools/migration/join_filter.py` | Join + dedup logic → `MigrationCandidate` |
| `tools/migration/load_postgres.py` | Batch insert users/subscriptions/partners |
| `tools/migration/sync_remnawave.py` | Panel sync with semaphore + retry |
| `tools/migration/validate.py` | Post-migration counts and spot checks |
| `tools/migration/run.py` | CLI orchestrator (`extract`, `dry-run`, `load`, `sync`, `validate`) |
| `tools/migration/models.py` | Dataclasses shared across modules |
| `tests/migration/test_extract_xui.py` | Unit tests for SQLite parsing |
| `tests/migration/test_join_filter.py` | Unit tests for join/dedup rules |
| `tests/migration/test_load_postgres.py` | Unit tests with mocked DB session |

No changes to production handlers (`miniapp.py`, `start.py`) — migration is a standalone CLI tool.

---

## Server Topology (locked decisions)

### Merge groups → Remnawave Internal Squads

| Old server IDs | Enabled clients (2026-02-28) | VIP | New squad key | Notes |
|----------------|------------------------------|-----|---------------|-------|
| 11, 17, 40, 46 | 67 + 241 + 327 + 346 = **981** | mixed | `merged-small` | One node + one Internal Squad |
| 14 | 773 | 20 | `s3` | Keep separate |
| 18 | 902 | 20 | `s4` | Keep separate |
| 19 | 904 | 20 | `s5` | Keep separate |
| 22 | 555 | 20 | `s5-alt` | Keep separate |
| 24 | 924 | 20 | `s10` | Keep separate |
| 30 | 414 | 20 | `s8` | Keep separate (borderline >400) |
| 57 | 1018 | 20 | `s100` | Keep separate |
| 37, 56 | 0 | — | skip | Empty backups |

### VIP → tariff mapping (current bot DB)

| Old `server_info.vip` | bot-remnawave `tariff_id` | Tariff name |
|-----------------------|---------------------------|-------------|
| `1` | `3` | پایه |
| `20` | `2` | پریمیوم |

### Dedup rule (`MULTI_TARIFF_ENABLED=false`)

When a Telegram user has multiple active 3x-ui clients:
1. Prefer highest VIP (20 > 1)
2. Tie-break: latest `expiryTime`
3. Tie-break: highest `(up + down)` traffic usage

---

## Prerequisites

### Task 0: Worktree and staging environment

**Files:**
- Create: none (shell only)

- [ ] **Step 1: Create isolated worktree**

```bash
cd /opt/bot-remnawave
git checkout main
git pull origin main 2>/dev/null || true
git worktree add ../bot-remnawave-migration -b feat/rookari-migration
cd ../bot-remnawave-migration
```

- [ ] **Step 2: Verify source data paths exist**

```bash
test -f /opt/rookari_db.json && echo "rookari_db OK"
test -d /opt/old_bot/bcp/2026-02-28_08-00 && ls /opt/old_bot/bcp/2026-02-28_08-00/*.db | wc -l
```

Expected: `rookari_db OK` and count ≥ 11

- [ ] **Step 3: Copy staging env (do NOT migrate on production DB first run)**

```bash
cp .env .env.migration.staging
# Edit .env.migration.staging:
#   DATABASE_URL=postgresql+asyncpg://...@localhost:5433/remnawave_bot_staging
#   REMNAWAVE_API_URL=http://localhost:3000
#   MULTI_TARIFF_ENABLED=false
```

- [ ] **Step 4: Create staging PostgreSQL database**

```bash
docker compose exec postgres psql -U postgres -c "CREATE DATABASE remnawave_bot_staging;"
docker compose exec bot alembic upgrade head  # against staging URL
```

Expected: Alembic head applied with 0 users (or snapshot current counts for diff)

- [ ] **Step 5: Provision Remnawave squads (manual, one-time)**

In Remnawave panel admin, create Internal Squads matching `config.py` keys and record UUIDs in `tools/migration/squad_uuids.json`:

```json
{
  "merged-small": "REPLACE-WITH-UUID",
  "s3": "REPLACE-WITH-UUID",
  "s4": "REPLACE-WITH-UUID",
  "s5": "REPLACE-WITH-UUID",
  "s5-alt": "REPLACE-WITH-UUID",
  "s10": "REPLACE-WITH-UUID",
  "s8": "REPLACE-WITH-UUID",
  "s100": "REPLACE-WITH-UUID"
}
```

Also insert matching rows into `server_squads` table via bot admin or SQL:

```sql
INSERT INTO server_squads (squad_uuid, display_name, is_available, sort_order)
VALUES
  ('<merged-small-uuid>', 'Small Pool', true, 10),
  ('<s3-uuid>', 'Finland', true, 20);
-- repeat for each squad
```

Update tariff `allowed_squads`:
- Tariff id=2 (پریمیوم): all VIP=20 squad UUIDs
- Tariff id=3 (پایه): `merged-small` UUID only (servers 17, 40, 46 were VIP=1)

- [ ] **Step 6: Commit prerequisites checklist**

```bash
git add tools/migration/squad_uuids.json.example
git commit -m "chore: add migration squad UUID template"
```

---

## Task 1: Migration config and dataclasses

**Files:**
- Create: `tools/migration/__init__.py`
- Create: `tools/migration/models.py`
- Create: `tools/migration/config.py`
- Create: `tools/migration/squad_uuids.json.example`
- Test: `tests/migration/test_config.py`

- [ ] **Step 1: Write the failing test**

Create `tests/migration/test_config.py`:

```python
from tools.migration.config import OLD_SERVER_TO_SQUAD_KEY, vip_to_tariff_id, squad_key_for_server


def test_small_servers_map_to_merged_key():
    for server_id in (11, 17, 40, 46):
        assert squad_key_for_server(server_id) == 'merged-small'


def test_vip_to_tariff_mapping():
    assert vip_to_tariff_id(1) == 3
    assert vip_to_tariff_id(20) == 2
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd /opt/bot-remnawave-migration
pytest tests/migration/test_config.py -v
```

Expected: FAIL with `ModuleNotFoundError: tools.migration`

- [ ] **Step 3: Write minimal implementation**

Create `tools/migration/__init__.py` (empty).

Create `tools/migration/models.py`:

```python
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass(frozen=True)
class XuiClient:
    server_id: int
    email: str
    uuid: str
    enable: bool
    expiry_ms: int  # 0 = unlimited
    up: int
    down: int
    total: int
    vip: int


@dataclass(frozen=True)
class BotUser:
    telegram_id: int
    username: str | None
    first_name: str | None
    wallet: int
    status: str
    created_at: datetime | None
    refcode: str | None


@dataclass(frozen=True)
class Seller:
    telegram_id: int
    percent: int


@dataclass
class MigrationCandidate:
    telegram_id: int
    username: str | None
    first_name: str | None
    wallet: int
    tariff_id: int
    squad_keys: list[str]
    end_date: datetime
    traffic_limit_gb: int
    traffic_used_gb: float
    old_xui_uuid: str
    old_server_id: int
    old_email: str
    is_partner: bool = False
    partner_commission_percent: int | None = None
    source_clients: list[XuiClient] = field(default_factory=list)
```

Create `tools/migration/config.py`:

```python
from __future__ import annotations

import json
from pathlib import Path

ROOKARI_DB_PATH = Path('/opt/rookari_db.json')
XUI_BACKUP_DIR = Path('/opt/old_bot/bcp/2026-02-28_08-00')
SQUAD_UUIDS_PATH = Path(__file__).parent / 'squad_uuids.json'

# old server_id -> logical squad key (must exist in squad_uuids.json)
OLD_SERVER_TO_SQUAD_KEY: dict[int, str] = {
    11: 'merged-small',
    17: 'merged-small',
    40: 'merged-small',
    46: 'merged-small',
    14: 's3',
    18: 's4',
    19: 's5',
    22: 's5-alt',
    24: 's10',
    30: 's8',
    57: 's100',
}

SERVER_VIP: dict[int, int] = {
    11: 20, 14: 20, 17: 1, 18: 20, 19: 20, 22: 20,
    24: 20, 30: 20, 40: 1, 46: 1, 57: 20,
}

MIGRATION_CUTOFF_UNIX = 1772236800  # 2026-02-28 00:00:00 UTC

BATCH_SIZE = 500
REMNAWAVE_CONCURRENCY = 8

SKIP_SERVER_IDS = {37, 56}


def squad_key_for_server(server_id: int) -> str:
    if server_id in SKIP_SERVER_IDS:
        raise ValueError(f'server {server_id} is skipped')
    key = OLD_SERVER_TO_SQUAD_KEY.get(server_id)
    if not key:
        raise ValueError(f'no squad mapping for server {server_id}')
    return key


def vip_to_tariff_id(vip: int) -> int:
    return 3 if vip == 1 else 2


def load_squad_uuids() -> dict[str, str]:
    data = json.loads(SQUAD_UUIDS_PATH.read_text())
    return {k: v for k, v in data.items() if not k.startswith('_')}


def squad_uuid_for_server(server_id: int) -> str:
    key = squad_key_for_server(server_id)
    uuids = load_squad_uuids()
    if key not in uuids:
        raise KeyError(f'squad key {key!r} missing from {SQUAD_UUIDS_PATH}')
    return uuids[key]
```

Create `tools/migration/squad_uuids.json.example`:

```json
{
  "_comment": "Copy to squad_uuids.json and fill Remnawave Internal Squad UUIDs",
  "merged-small": "00000000-0000-0000-0000-000000000001",
  "s3": "00000000-0000-0000-0000-000000000002",
  "s4": "00000000-0000-0000-0000-000000000003",
  "s5": "00000000-0000-0000-0000-000000000004",
  "s5-alt": "00000000-0000-0000-0000-000000000005",
  "s10": "00000000-0000-0000-0000-000000000006",
  "s8": "00000000-0000-0000-0000-000000000007",
  "s100": "00000000-0000-0000-0000-000000000008"
}
```

Add to `pyproject.toml` under `[tool.pytest.ini_options]` if missing:

```toml
pythonpath = ["."]
```

- [ ] **Step 4: Run test to verify it passes**

```bash
pytest tests/migration/test_config.py -v
```

Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git add tools/migration/ tests/migration/test_config.py pyproject.toml
git commit -m "feat(migration): add config and dataclasses for rookari ETL"
```

---

## Task 2: Extract 3x-ui SQLite clients

**Files:**
- Create: `tools/migration/extract_xui.py`
- Test: `tests/migration/test_extract_xui.py`

- [ ] **Step 1: Write the failing test**

Create `tests/migration/test_extract_xui.py`:

```python
import json
import sqlite3
from pathlib import Path

from tools.migration.extract_xui import extract_clients_from_db


def test_extract_clients_from_db(tmp_path: Path):
    db_path = tmp_path / 'server14-test.db'
    conn = sqlite3.connect(db_path)
    conn.execute(
        "CREATE TABLE inbounds (id INTEGER PRIMARY KEY, settings TEXT)"
    )
    settings = {
        'clients': [
            {
                'email': 'user@test',
                'id': '50913f6d-bc9e-4494-98c1-bf5de2c32df8',
                'enable': True,
                'expiryTime': 1779740908859,
                'totalGB': 50,
            }
        ]
    }
    conn.execute("INSERT INTO inbounds (settings) VALUES (?)", (json.dumps(settings),))
    conn.execute(
        "CREATE TABLE client_traffics (email TEXT, up INTEGER, down INTEGER, enable INTEGER, expiryTime INTEGER)"
    )
    conn.execute(
        "INSERT INTO client_traffics VALUES ('user@test', 1000, 2000, 1, 1779740908)"
    )
    conn.commit()
    conn.close()

    clients = extract_clients_from_db(db_path, server_id=14, vip=20)
    assert len(clients) == 1
    c = clients[0]
    assert c.email == 'user@test'
    assert c.uuid == '50913f6d-bc9e-4494-98c1-bf5de2c32df8'
    assert c.enable is True
    assert c.server_id == 14
    assert c.vip == 20
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/migration/test_extract_xui.py -v
```

Expected: FAIL with `ImportError`

- [ ] **Step 3: Write minimal implementation**

Create `tools/migration/extract_xui.py`:

```python
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


def extract_clients_from_db(db_path: Path, server_id: int, vip: int) -> list[XuiClient]:
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if 'inbounds' not in tables:
            return []

        traffic: dict[str, sqlite3.Row] = {}
        if 'client_traffics' in tables:
            for row in conn.execute('SELECT email, up, down, enable, expiryTime FROM client_traffics'):
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
                total = int(raw.get('totalGB') or 0)  # GB in settings; may be 0
                clients.append(
                    XuiClient(
                        server_id=server_id,
                        email=email,
                        uuid=uuid,
                        enable=enable,
                        expiry_ms=expiry_ms,
                        up=up,
                        down=down,
                        total=total,
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
        all_clients.extend(extract_clients_from_db(db_path, server_id, vip))
    return all_clients
```

- [ ] **Step 4: Run test to verify it passes**

```bash
pytest tests/migration/test_extract_xui.py -v
```

Expected: PASS

- [ ] **Step 5: Smoke test against real backups**

```bash
python3 -c "
from tools.migration.extract_xui import extract_all_xui_clients
cs = extract_all_xui_clients()
enabled = [c for c in cs if c.enable]
print('total', len(cs), 'enabled', len(enabled))
"
```

Expected: `total 7041 enabled 6471` (±10 for backup drift)

- [ ] **Step 6: Commit**

```bash
git add tools/migration/extract_xui.py tests/migration/test_extract_xui.py
git commit -m "feat(migration): extract 3x-ui clients from SQLite backups"
```

---

## Task 3: Stream-extract rookari_db.json

**Files:**
- Create: `tools/migration/extract_rookari.py`
- Test: `tests/migration/test_extract_rookari.py`

- [ ] **Step 1: Write the failing test**

Create `tests/migration/test_extract_rookari.py`:

```python
import json
from pathlib import Path

from tools.migration.extract_rookari import parse_rookari_tables


def test_parse_rookari_tables(tmp_path: Path):
    payload = [
        {'type': 'table', 'name': 'fl_user', 'data': [
            {'userid': '123', 'name': 'Ali', 'username': 'ali', 'wallet': '5000',
             'status': '1', 'date': '1700000000', 'refcode': '999', 'sent': '0'}
        ]},
        {'type': 'table', 'name': 'config_stat', 'data': [
            {'userid': '123', 'remark': 'Finland(1)-98052', 'total': '107374182400',
             'up': '1000', 'down': '2000', 'expiryTime': '1893456000'}
        ]},
        {'type': 'table', 'name': 'fl_sellers', 'data': [
            {'userid': '456', 'percent': '15'}
        ]},
    ]
    path = tmp_path / 'rookari_db.json'
    path.write_text(json.dumps(payload))

    users, stats, sellers = parse_rookari_tables(path)
    assert len(users) == 1
    assert users[0].telegram_id == 123
    assert users[0].wallet == 5000
    assert len(stats) == 1
    assert stats[0]['remark'] == 'Finland(1)-98052'
    assert len(sellers) == 1
    assert sellers[0].telegram_id == 456
    assert sellers[0].percent == 15
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/migration/test_extract_rookari.py -v
```

Expected: FAIL

- [ ] **Step 3: Write minimal implementation**

Create `tools/migration/extract_rookari.py`:

```python
from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from tools.migration.config import ROOKARI_DB_PATH
from tools.migration.models import BotUser, Seller


def _ts_to_dt(raw: str | int | None) -> datetime | None:
    if raw is None or raw == '':
        return None
    return datetime.fromtimestamp(int(raw), tz=UTC)


def parse_rookari_tables(path: Path = ROOKARI_DB_PATH) -> tuple[list[BotUser], list[dict], list[Seller]]:
    with path.open('r', encoding='utf-8') as f:
        tables = json.load(f)

    users: list[BotUser] = []
    stats: list[dict] = []
    sellers: list[Seller] = []

    for block in tables:
        if block.get('type') != 'table':
            continue
        name = block.get('name')
        rows = block.get('data') or []
        if name == 'fl_user':
            for r in rows:
                if r.get('status') != '1':
                    continue
                users.append(
                    BotUser(
                        telegram_id=int(r['userid']),
                        username=r.get('username') or None,
                        first_name=r.get('name') or None,
                        wallet=int(r.get('wallet') or 0),
                        status=r.get('status') or '1',
                        created_at=_ts_to_dt(r.get('date')),
                        refcode=r.get('refcode') or None,
                    )
                )
        elif name == 'config_stat':
            stats.extend(rows)
        elif name == 'fl_sellers':
            for r in rows:
                sellers.append(
                    Seller(
                        telegram_id=int(r['userid']),
                        percent=int(r.get('percent') or 0),
                    )
                )
    return users, stats, sellers
```

- [ ] **Step 4: Run test to verify it passes**

```bash
pytest tests/migration/test_extract_rookari.py -v
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tools/migration/extract_rookari.py tests/migration/test_extract_rookari.py
git commit -m "feat(migration): parse rookari_db.json users and config_stat"
```

---

## Task 4: Join, filter, deduplicate

**Files:**
- Create: `tools/migration/join_filter.py`
- Test: `tests/migration/test_join_filter.py`

- [ ] **Step 1: Write the failing test**

Create `tests/migration/test_join_filter.py`:

```python
from datetime import UTC, datetime

from tools.migration.join_filter import build_migration_candidates
from tools.migration.models import BotUser, XuiClient


def test_dedup_picks_highest_vip(monkeypatch):
    now = datetime(2026, 6, 1, tzinfo=UTC)
    clients = [
        XuiClient(17, 'u1', 'uuid-a', True, 1893456000000, 0, 0, 0, vip=1),
        XuiClient(14, 'u1', 'uuid-b', True, 1893456000000, 0, 0, 0, vip=20),
    ]
    users = [BotUser(100, 'u', 'Ali', 0, '1', now, None)]
    stats = [{'userid': '100', 'remark': 'u1', 'total': '107374182400',
              'up': '0', 'down': '0', 'expiryTime': '1893456000'}]

    monkeypatch.setattr(
        'tools.migration.join_filter.datetime',
        __import__('datetime').datetime,
    )
    out = build_migration_candidates(clients, users, stats, [], cutoff=datetime(2026, 2, 28, tzinfo=UTC))
    assert len(out) == 1
    assert out[0].telegram_id == 100
    assert out[0].tariff_id == 2  # VIP 20 -> premium
    assert out[0].old_xui_uuid == 'uuid-b'
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/migration/test_join_filter.py -v
```

Expected: FAIL

- [ ] **Step 3: Write minimal implementation**

Create `tools/migration/join_filter.py`:

```python
from __future__ import annotations

from datetime import UTC, datetime

from tools.migration.config import MIGRATION_CUTOFF_UNIX, squad_key_for_server, vip_to_tariff_id
from tools.migration.models import BotUser, MigrationCandidate, Seller, XuiClient


def _client_expiry_dt(c: XuiClient) -> datetime | None:
    if c.expiry_ms <= 0:
        return None  # unlimited
    sec = c.expiry_ms // 1000 if c.expiry_ms > 10_000_000_000 else c.expiry_ms
    return datetime.fromtimestamp(sec, tz=UTC)


def _is_active(c: XuiClient, cutoff: datetime) -> bool:
    if not c.enable:
        return False
    exp = _client_expiry_dt(c)
    if exp is None:
        return True
    return exp > cutoff


def _best_stat_for_email(stats_by_remark: dict[str, dict], email: str, telegram_id: int) -> dict | None:
    rows = [r for r in stats_by_remark.get(email, []) if str(r.get('userid')) == str(telegram_id)]
    if not rows:
        return None
    return max(rows, key=lambda r: int(r.get('expiryTime') or 0))


def build_migration_candidates(
    xui_clients: list[XuiClient],
    bot_users: list[BotUser],
    config_stats: list[dict],
    sellers: list[Seller],
    cutoff: datetime | None = None,
) -> list[MigrationCandidate]:
    if cutoff is None:
        cutoff = datetime.fromtimestamp(MIGRATION_CUTOFF_UNIX, tz=UTC)

    users_by_tg = {u.telegram_id: u for u in bot_users}
    seller_by_tg = {s.telegram_id: s for s in sellers}

    stats_by_remark: dict[str, list[dict]] = {}
    for row in config_stats:
        remark = (row.get('remark') or '').strip()
        if not remark:
            continue
        if int(row.get('expiryTime') or 0) <= int(cutoff.timestamp()):
            continue
        stats_by_remark.setdefault(remark, []).append(row)

    # email -> list of active clients
    by_email: dict[str, list[XuiClient]] = {}
    for c in xui_clients:
        if not _is_active(c, cutoff):
            continue
        by_email.setdefault(c.email, []).append(c)

    # telegram_id -> best client after dedup
    chosen: dict[int, MigrationCandidate] = {}

    for email, clients in by_email.items():
        stat_rows = stats_by_remark.get(email)
        if not stat_rows:
            continue
        # resolve telegram id from any matching stat row
        tg_ids = {int(r['userid']) for r in stat_rows if r.get('userid')}
        for tg_id in tg_ids:
            user = users_by_tg.get(tg_id)
            if not user:
                continue
            stat = _best_stat_for_email(stats_by_remark, email, tg_id)
            if not stat:
                continue

            def sort_key(c: XuiClient):
                exp = _client_expiry_dt(c) or datetime.max.replace(tzinfo=UTC)
                return (c.vip, exp.timestamp(), c.up + c.down)

            best = max(clients, key=sort_key)
            exp_sec = int(stat.get('expiryTime') or 0)
            end_date = datetime.fromtimestamp(exp_sec, tz=UTC)
            total_bytes = int(stat.get('total') or 0)
            traffic_limit_gb = max(1, total_bytes // (1024 ** 3)) if total_bytes else 100
            used_gb = (int(stat.get('up') or 0) + int(stat.get('down') or 0)) / (1024 ** 3)

            seller = seller_by_tg.get(tg_id)
            squad_key = squad_key_for_server(best.server_id)
            candidate = MigrationCandidate(
                telegram_id=tg_id,
                username=user.username,
                first_name=user.first_name,
                wallet=user.wallet,
                tariff_id=vip_to_tariff_id(best.vip),
                squad_keys=[squad_key],
                end_date=end_date,
                traffic_limit_gb=traffic_limit_gb,
                traffic_used_gb=round(used_gb, 3),
                old_xui_uuid=best.uuid,
                old_server_id=best.server_id,
                old_email=email,
                is_partner=seller is not None,
                partner_commission_percent=seller.percent if seller else None,
                source_clients=list(clients),
            )

            prev = chosen.get(tg_id)
            if prev is None or (candidate.tariff_id, candidate.end_date) > (prev.tariff_id, prev.end_date):
                chosen[tg_id] = candidate

    return sorted(chosen.values(), key=lambda c: c.telegram_id)
```

- [ ] **Step 4: Run test to verify it passes**

```bash
pytest tests/migration/test_join_filter.py -v
```

Expected: PASS

- [ ] **Step 5: Dry-run count on real data**

```bash
python3 -c "
from tools.migration.extract_xui import extract_all_xui_clients
from tools.migration.extract_rookari import parse_rookari_tables
from tools.migration.join_filter import build_migration_candidates
clients = extract_all_xui_clients()
users, stats, sellers = parse_rookari_tables()
cands = build_migration_candidates(clients, users, stats, sellers)
print('candidates', len(cands), 'partners', sum(1 for c in cands if c.is_partner))
"
```

Expected: `candidates 761 partners ~40-80` (exact partner count depends on overlap with active subs)

- [ ] **Step 6: Commit**

```bash
git add tools/migration/join_filter.py tests/migration/test_join_filter.py
git commit -m "feat(migration): join 3x-ui clients with rookari users"
```

---

## Task 5: Load users and subscriptions into PostgreSQL

**Files:**
- Create: `tools/migration/load_postgres.py`
- Test: `tests/migration/test_load_postgres.py`

- [ ] **Step 1: Write the failing test**

Create `tests/migration/test_load_postgres.py`:

```python
from datetime import UTC, datetime
from unittest.mock import AsyncMock, Mock

import pytest

from tools.migration.load_postgres import load_candidates
from tools.migration.models import MigrationCandidate


@pytest.mark.asyncio
async def test_load_candidates_skips_existing_telegram_id(monkeypatch):
    db = Mock()
    db.flush = AsyncMock()
    db.commit = AsyncMock()

    existing = Mock(id=99, telegram_id=100)
    get_by_tg = AsyncMock(return_value=existing)
    create_user = AsyncMock()
    create_sub = AsyncMock()
    monkeypatch.setattr('tools.migration.load_postgres.get_user_by_telegram_id', get_by_tg)
    monkeypatch.setattr('tools.migration.load_postgres.create_user_no_commit', create_user)
    monkeypatch.setattr('tools.migration.load_postgres.create_subscription_no_commit', create_sub)

    c = MigrationCandidate(
        telegram_id=100, username='a', first_name='A', wallet=0, tariff_id=2,
        squad_keys=['merged-small'], end_date=datetime(2027, 1, 1, tzinfo=UTC),
        traffic_limit_gb=100, traffic_used_gb=1.0, old_xui_uuid='u', old_server_id=14,
        old_email='e',
    )
    result = await load_candidates(db, [c], squad_uuids={'merged-small': 'uuid-1'}, dry_run=False)
    assert result['skipped'] == 1
    create_user.assert_not_called()
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/migration/test_load_postgres.py -v
```

Expected: FAIL

- [ ] **Step 3: Write minimal implementation**

Create `tools/migration/load_postgres.py`:

```python
from __future__ import annotations

import structlog

from app.database.crud.subscription import create_subscription_no_commit
from app.database.crud.user import create_user_no_commit, get_user_by_telegram_id
from app.database.models import PartnerStatus, SubscriptionStatus

from tools.migration.config import BATCH_SIZE
from tools.migration.models import MigrationCandidate

logger = structlog.get_logger(__name__)


async def load_candidates(
    db,
    candidates: list[MigrationCandidate],
    squad_uuids: dict[str, str],
    dry_run: bool = True,
) -> dict[str, int]:
    stats = {'created_users': 0, 'created_subs': 0, 'skipped': 0, 'partners': 0}

    for i, c in enumerate(candidates):
        existing = await get_user_by_telegram_id(db, c.telegram_id)
        if existing:
            stats['skipped'] += 1
            continue

        connected = [squad_uuids[k] for k in c.squad_keys if k in squad_uuids]
        if not connected:
            logger.warning('no squad uuids for candidate', telegram_id=c.telegram_id)
            stats['skipped'] += 1
            continue

        if dry_run:
            stats['created_users'] += 1
            stats['created_subs'] += 1
            if c.is_partner:
                stats['partners'] += 1
            continue

        user = await create_user_no_commit(
            db,
            telegram_id=c.telegram_id,
            username=c.username,
            first_name=c.first_name,
            language='fa',
        )
        user.balance_kopeks = c.wallet
        if c.is_partner and c.partner_commission_percent is not None:
            user.partner_status = PartnerStatus.APPROVED.value
            user.referral_commission_percent = c.partner_commission_percent
            stats['partners'] += 1

        sub = await create_subscription_no_commit(
            db,
            user_id=user.id,
            status=SubscriptionStatus.ACTIVE.value,
            is_trial=False,
            end_date=c.end_date,
            traffic_limit_gb=c.traffic_limit_gb,
            traffic_used_gb=c.traffic_used_gb,
            device_limit=1,
            connected_squads=connected,
        )
        sub.tariff_id = c.tariff_id
        # metadata for audit (store old uuid in trojan/vless fields if empty — optional column)
        user.vless_uuid = c.old_xui_uuid

        stats['created_users'] += 1
        stats['created_subs'] += 1

        if (i + 1) % BATCH_SIZE == 0:
            await db.commit()
            logger.info('migration batch committed', count=i + 1)

    if not dry_run:
        await db.commit()

    return stats
```

- [ ] **Step 4: Run test to verify it passes**

```bash
pytest tests/migration/test_load_postgres.py -v
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tools/migration/load_postgres.py tests/migration/test_load_postgres.py
git commit -m "feat(migration): batch load users and subscriptions to PostgreSQL"
```

---

## Task 6: Sync Remnawave panel

**Files:**
- Create: `tools/migration/sync_remnawave.py`

- [ ] **Step 1: Write sync module**

Create `tools/migration/sync_remnawave.py`:

```python
from __future__ import annotations

import asyncio

import structlog
from sqlalchemy import select

from app.database.models import Subscription, User
from app.services.subscription_service import SubscriptionService

from tools.migration.config import REMNAWAVE_CONCURRENCY

logger = structlog.get_logger(__name__)


async def sync_subscription_to_panel(db, subscription: Subscription, user: User, dry_run: bool) -> bool:
    if dry_run:
        return True
    service = SubscriptionService()
    try:
        rw_user = await service.create_remnawave_user(db, user, subscription)
        subscription.remnawave_uuid = rw_user.uuid
        subscription.remnawave_short_uuid = getattr(rw_user, 'short_uuid', None)
        subscription.subscription_url = getattr(rw_user, 'subscription_url', None) or subscription.subscription_url
        await db.commit()
        return True
    except Exception as exc:
        logger.error('panel sync failed', telegram_id=user.telegram_id, error=str(exc))
        await db.rollback()
        return False


async def sync_all(db, dry_run: bool = True) -> dict[str, int]:
    sem = asyncio.Semaphore(REMNAWAVE_CONCURRENCY)
    stats = {'ok': 0, 'fail': 0}

    result = await db.execute(
        select(Subscription, User)
        .join(User, User.id == Subscription.user_id)
        .where(Subscription.remnawave_uuid.is_(None))
        .where(User.telegram_id.is_not(None))
    )
    rows = result.all()

    async def one(sub, user):
        async with sem:
            ok = await sync_subscription_to_panel(db, sub, user, dry_run)
            if ok:
                stats['ok'] += 1
            else:
                stats['fail'] += 1

    await asyncio.gather(*(one(s, u) for s, u in rows))
    return stats
```

- [ ] **Step 2: Dry-run panel sync (no API calls)**

```bash
python3 -c "
import asyncio
from tools.migration.run import get_db_session
from tools.migration.sync_remnawave import sync_all
async def main():
    async with get_db_session() as db:
        print(await sync_all(db, dry_run=True))
asyncio.run(main())
"
```

Expected: dict with ok = count of subs missing remnawave_uuid

- [ ] **Step 3: Commit**

```bash
git add tools/migration/sync_remnawave.py
git commit -m "feat(migration): sync loaded subscriptions to Remnawave panel"
```

---

## Task 7: CLI orchestrator and validation

**Files:**
- Create: `tools/migration/run.py`
- Create: `tools/migration/validate.py`

- [ ] **Step 1: Write CLI**

Create `tools/migration/run.py`:

```python
from __future__ import annotations

import argparse
import asyncio
import json
from contextlib import asynccontextmanager
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings

from tools.migration.config import load_squad_uuids
from tools.migration.extract_rookari import parse_rookari_tables
from tools.migration.extract_xui import extract_all_xui_clients
from tools.migration.join_filter import build_migration_candidates
from tools.migration.load_postgres import load_candidates
from tools.migration.sync_remnawave import sync_all
from tools.migration.validate import validate_migration


@asynccontextmanager
async def get_db_session():
    engine = create_async_engine(settings.DATABASE_URL)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        yield session
    await engine.dispose()


async def cmd_extract(out: Path):
    clients = extract_all_xui_clients()
    users, stats, sellers = parse_rookari_tables()
    candidates = build_migration_candidates(clients, users, stats, sellers)
    out.write_text(json.dumps([c.__dict__ for c in candidates], default=str, indent=2))
    print(f'wrote {len(candidates)} candidates to {out}')


async def cmd_load(dry_run: bool):
    clients = extract_all_xui_clients()
    users, stats, sellers = parse_rookari_tables()
    candidates = build_migration_candidates(clients, users, stats, sellers)
    squad_uuids = load_squad_uuids()
    async with get_db_session() as db:
        result = await load_candidates(db, candidates, squad_uuids, dry_run=dry_run)
    print(result)


async def cmd_sync(dry_run: bool):
    async with get_db_session() as db:
        result = await sync_all(db, dry_run=dry_run)
    print(result)


async def cmd_validate():
    async with get_db_session() as db:
        report = await validate_migration(db)
    print(json.dumps(report, indent=2))


def main():
    p = argparse.ArgumentParser(description='Rookari migration tool')
    sub = p.add_subparsers(dest='cmd', required=True)
    e = sub.add_parser('extract')
    e.add_argument('-o', '--output', type=Path, default=Path('migration_candidates.json'))
    l = sub.add_parser('load')
    l.add_argument('--execute', action='store_true')
    s = sub.add_parser('sync')
    s.add_argument('--execute', action='store_true')
    sub.add_parser('validate')
    args = p.parse_args()

    if args.cmd == 'extract':
        asyncio.run(cmd_extract(args.output))
    elif args.cmd == 'load':
        asyncio.run(cmd_load(dry_run=not args.execute))
    elif args.cmd == 'sync':
        asyncio.run(cmd_sync(dry_run=not args.execute))
    elif args.cmd == 'validate':
        asyncio.run(cmd_validate())


if __name__ == '__main__':
    main()
```

Create `tools/migration/validate.py`:

```python
from __future__ import annotations

from sqlalchemy import func, select

from app.database.models import Subscription, User


async def validate_migration(db) -> dict:
    user_count = (await db.execute(select(func.count()).select_from(User))).scalar_one()
    sub_count = (await db.execute(select(func.count()).select_from(Subscription))).scalar_one()
    missing_panel = (
        await db.execute(select(func.count()).select_from(Subscription).where(Subscription.remnawave_uuid.is_(None)))
    ).scalar_one()
    partners = (
        await db.execute(select(func.count()).select_from(User).where(User.partner_status == 'approved'))
    ).scalar_one()
    return {
        'users': user_count,
        'subscriptions': sub_count,
        'missing_remnawave_uuid': missing_panel,
        'approved_partners': partners,
    }
```

- [ ] **Step 2: End-to-end dry-run**

```bash
cd /opt/bot-remnawave-migration
python -m tools.migration.run extract -o /tmp/candidates.json
python -m tools.migration.run load          # dry-run
python -m tools.migration.run sync          # dry-run
```

Expected: candidates ~761, load dry-run shows created_users=761 skipped=0, sync dry-run ok=761

- [ ] **Step 3: Commit**

```bash
git add tools/migration/run.py tools/migration/validate.py
git commit -m "feat(migration): add CLI orchestrator and validation"
```

---

## Task 8: Staging execution and production cutover

**Files:** none (operational runbook)

- [ ] **Step 1: Execute on staging DB**

```bash
DATABASE_URL=postgresql+asyncpg://.../remnawave_bot_staging \
  python -m tools.migration.run load --execute
DATABASE_URL=postgresql+asyncpg://.../remnawave_bot_staging \
  python -m tools.migration.run sync --execute
DATABASE_URL=postgresql+asyncpg://.../remnawave_bot_staging \
  python -m tools.migration.run validate
```

Expected validate output:
```json
{
  "users": 761,
  "subscriptions": 761,
  "missing_remnawave_uuid": 0,
  "approved_partners": 40
}
```
(partner count approximate)

- [ ] **Step 2: Spot-check 5 random users in miniapp**

Pick 5 `telegram_id` from `/tmp/candidates.json`, open Telegram miniapp, verify:
- balance matches old wallet
- subscription expiry ±1 day
- subscription URL returns HTTP 200
- connected server name visible in miniapp profile

- [ ] **Step 3: Production cutover (maintenance window)**

1. Set old bot read-only / maintenance message
2. Take fresh 3x-ui backup if >7 days old
3. Re-run `extract` + `load --execute` + `sync --execute` on production DB
4. Point DNS for subscription domains to Remnawave nodes
5. Send Telegram broadcast: users must import **new subscription URL** (old vmess links will NOT work — API does not set custom UUID)

- [ ] **Step 4: Post-cutover monitoring (24h)**

Watch:
- `remnawave_retry_queue` table for failed syncs
- Admin notifications channel
- Support tickets for "config not working"

---

## Important constraints (do NOT skip)

1. **UUID preservation:** `app/external/remnawave_api.py:create_user()` does not accept custom UUID. Old vmess links **will break**. Store `old_xui_uuid` in `users.vless_uuid` for audit only.
2. **Orphan config_stat:** ~1,310 users active in bot DB but absent from 3x-ui backup — **do not migrate** (handled by join filter).
3. **Wallet audit:** Total wallet ~108M تومان across 613 users — spot-check top 10 balances manually before `--execute`.
4. **Idempotency:** Re-running `load` skips existing `telegram_id`. Safe to retry.
5. **Do not migrate:** `clog`, `fl_order`, `payments`, `card_autoconfirm_log`, old panel cookies from `server_info`.

---

## Spec self-review

| Requirement | Task |
|-------------|------|
| Filter 147K → ~761 valid | Task 4 |
| Merge servers 11,17,40,46 | Task 1 config |
| VIP → tariff mapping | Task 1, 4 |
| Partner migration | Task 4, 5 |
| PostgreSQL batch load | Task 5 |
| Remnawave panel sync | Task 6 |
| Dry-run + validate | Task 7, 8 |
| No production handler changes | File structure note |

No TBD placeholders remain. All code blocks are complete.

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-06-07-rookari-migration.md`. Two execution options:

**1. Subagent-Driven (recommended)** — dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** — execute tasks in this session using executing-plans, batch execution with checkpoints

Which approach?
