"""Test engineering distinctions used by selected vocabulary definitions."""

from contextlib import closing
import json
from pathlib import Path
import sqlite3
from subprocess import run
from tempfile import TemporaryDirectory


def database_operations(directory):
    path = directory / "semantics.sqlite"
    with closing(sqlite3.connect(path, timeout=0)) as owner, closing(
        sqlite3.connect(path, timeout=0)
    ) as peer:
        owner.execute("CREATE TABLE events (id INTEGER PRIMARY KEY, category TEXT, payload BLOB)")
        owner.executemany("INSERT INTO events VALUES (?, ?, zeroblob(4096))",
                          [(event, "failed" if event % 3 == 0 else "ok") for event in range(1, 101)])
        owner.commit()
        before = owner.execute("EXPLAIN QUERY PLAN SELECT id FROM events WHERE category = 'failed'").fetchone()[3]
        owner.execute("CREATE INDEX category_index ON events(category)")
        owner.commit()
        after = owner.execute("EXPLAIN QUERY PLAN SELECT id FROM events WHERE category = 'failed'").fetchone()[3]
        ids = [row[0] for row in owner.execute("SELECT id FROM events WHERE category = 'failed' ORDER BY id")]
        count = owner.execute("SELECT COUNT(*) FROM events WHERE category = 'failed'").fetchone()[0]
        lock_before_any_writer = peer.execute("SELECT 1").fetchone()[0] == 1
        owner.execute("BEGIN IMMEDIATE")
        refused = False
        try:
            peer.execute("BEGIN IMMEDIATE")
        except sqlite3.OperationalError as error:
            refused = "locked" in str(error).lower()
            if not refused:
                raise
        else:
            peer.rollback()
        owner.rollback()
        peer.execute("BEGIN IMMEDIATE")
        peer.rollback()
        # Reading data does not reclaim it. Contrast with dropping the table.
        read_rows = owner.execute("SELECT COUNT(*) FROM events").fetchone()[0]
        free_before = owner.execute("PRAGMA freelist_count").fetchone()[0]
        read_preserves_pages = owner.execute("PRAGMA freelist_count").fetchone()[0] == free_before
        owner.execute("DROP TABLE events")
        owner.commit()
        free_after = owner.execute("PRAGMA freelist_count").fetchone()[0]
    expected = list(range(3, 101, 3))
    return [
        {"word": "索引", "before_index_search": "category_index" in before,
         "after_index_search": "category_index" in after,
         "control_without_index": "category_index" not in before,
         "passed": "category_index" not in before and "category_index" in after},
        {"word": "过滤", "source_rows": 100, "selected_rows": len(ids),
         "identity_returns_unmatched_records": bool(set(range(1, 101)) - set(expected)),
         "passed": ids == expected and len(ids) < 100},
        {"word": "统计", "observation": count, "different_representation": isinstance(count, int),
         "copying_ids_is_not_count": ids != count,
         "passed": isinstance(count, int) and count == len(expected) and ids != count},
        {"word": "未锁定", "reader_before_write_lock": lock_before_any_writer,
         "other_writer_denied_while_held": refused, "other_writer_after_release": True,
         "passed": refused},
        {"word": "回收", "more_reusable_pages_after_drop": free_after > free_before,
         "read_only_did_not_reclaim": read_rows == 100 and read_preserves_pages,
         "passed": free_after > free_before and read_rows == 100 and read_preserves_pages},
    ]


def signature_operation(directory):
    key, public, signature, message = (directory / name for name in ("key", "public", "signature", "message"))
    quiet = {"capture_output": True, "check": True}
    run(["openssl", "genpkey", "-algorithm", "RSA", "-pkeyopt", "rsa_keygen_bits:2048", "-out", str(key)],
        **quiet)
    run(["openssl", "pkey", "-in", str(key), "-pubout", "-out", str(public)], **quiet)
    message.write_bytes(b"approved payload")
    run(["openssl", "dgst", "-sha256", "-sign", str(key), "-out", str(signature), str(message)], **quiet)
    verify = ["openssl", "dgst", "-sha256", "-verify", str(public), "-signature", str(signature), str(message)]
    authentic = run(verify, capture_output=True).returncode == 0
    message.write_bytes(b"modified payload")
    modified = run(verify, capture_output=True).returncode == 0
    return {"word": "签名", "authentic_message_verified": authentic,
            "changed_message_verified": modified, "passed": authentic and not modified}


def main():
    with TemporaryDirectory(prefix="ctc-operations-") as scratch:
        directory = Path(scratch)
        rows = database_operations(directory)
        rows.append(signature_operation(directory))
    payload = b"abcdefghijklmnop"
    first = payload[:8]
    tail = payload[8:]
    rows.append({"word": "截断", "length": len(first), "prefix_hex": first.hex(),
                 "same_length_suffix_is_counterexample": tail != first and len(tail) == len(first),
                 "passed": first == b"abcdefgh" and tail != first})
    print(json.dumps({"engine": "SQLite, OpenSSL and bytes", "operations": rows},
                     indent=2, ensure_ascii=False))
    return int(not all(row["passed"] for row in rows))


if __name__ == "__main__":
    raise SystemExit(main())
