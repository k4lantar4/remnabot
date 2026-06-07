import json
import sqlite3
from pathlib import Path

from tools.migration.extract_xui import extract_clients_from_db


def test_extract_clients_from_db(tmp_path: Path):
    db_path = tmp_path / 'server14-test.db'
    conn = sqlite3.connect(db_path)
    conn.execute('CREATE TABLE inbounds (id INTEGER PRIMARY KEY, settings TEXT)')
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
    conn.execute('INSERT INTO inbounds (settings) VALUES (?)', (json.dumps(settings),))
    conn.execute(
        'CREATE TABLE client_traffics (email TEXT, up INTEGER, down INTEGER, enable INTEGER, expiryTime INTEGER)'
    )
    conn.execute("INSERT INTO client_traffics VALUES ('user@test', 1000, 2000, 1, 1779740908)")
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
