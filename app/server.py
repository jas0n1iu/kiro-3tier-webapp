"""A/S report API. Python 3.9 stdlib plus PyMySQL (installed by the instance user data).

Listens on 127.0.0.1:8000; nginx serves the static page and proxies /api/ here.
The database is optional at runtime: if it is unreachable the report is still returned (saved=false).
Env: DB_HOST, DB_NAME, DB_USER, DB_PASSWORD_PARAM (SSM name), AWS_REGION, INSTANCE_ID.
"""
import datetime as dt
import json
import os
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import report

DB_HOST = os.environ.get("DB_HOST", "")
DB_NAME = os.environ.get("DB_NAME", "asdesk")
DB_USER = os.environ.get("DB_USER", "asapp")
DB_PASSWORD_PARAM = os.environ.get("DB_PASSWORD_PARAM", "")
REGION = os.environ.get("AWS_REGION", "")
INSTANCE_ID = os.environ.get("INSTANCE_ID", "")
MAX_BODY = 8192

_pw_lock = threading.Lock()
_pw_cache = {"value": None, "tried_at": 0.0}


def get_db_password():
    """Read the app DB password from SSM once. Retries at most every 15 s while it is missing."""
    with _pw_lock:
        if _pw_cache["value"]:
            return _pw_cache["value"]
        if not DB_PASSWORD_PARAM or time.time() - _pw_cache["tried_at"] < 15:
            return None
        _pw_cache["tried_at"] = time.time()
        try:
            out = subprocess.run(
                ["aws", "ssm", "get-parameter", "--region", REGION, "--name", DB_PASSWORD_PARAM,
                 "--with-decryption", "--query", "Parameter.Value", "--output", "text"],
                capture_output=True, text=True, timeout=10, check=True)
            _pw_cache["value"] = out.stdout.strip() or None
        except Exception as exc:  # never log the value; the error text holds no secret
            print("ssm read failed: %s" % type(exc).__name__, file=sys.stderr)
        return _pw_cache["value"]


def db_connect():
    import pymysql  # imported lazily so the report logic works without a database
    pw = get_db_password()
    if not DB_HOST or not pw:
        raise RuntimeError("database not configured yet")
    return pymysql.connect(host=DB_HOST, user=DB_USER, password=pw, database=DB_NAME,
                           connect_timeout=3, read_timeout=5, write_timeout=5, autocommit=True)


def save_request(clean, w_status):
    """Insert with a parameterized query. Returns the new row id, or None if the DB is unavailable."""
    try:
        conn = db_connect()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO as_request (product, fault, purchase_date, symptom, urgency, warranty_status) "
                    "VALUES (%s, %s, %s, %s, %s, %s)",
                    (clean["product"], clean["fault"], clean["purchase_date"], clean["symptom"],
                     clean["urgency"], w_status))
                return cur.lastrowid
        finally:
            conn.close()
    except Exception as exc:
        print("db write failed: %s" % type(exc).__name__, file=sys.stderr)
        return None


def recent_requests(limit=10):
    try:
        conn = db_connect()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT id, product, fault, urgency, warranty_status, created_at "
                    "FROM as_request ORDER BY id DESC LIMIT %s", (limit,))
                rows = cur.fetchall()
        finally:
            conn.close()
    except Exception as exc:
        print("db read failed: %s" % type(exc).__name__, file=sys.stderr)
        return None
    out = []
    for rid, product, fault, urgency, status, created in rows:
        out.append({
            "ticket_no": report.ticket_number(created.date(), rid),
            "product": product, "fault": fault, "urgency": urgency,
            "warranty_status": status, "created_at": created.strftime("%Y-%m-%d %H:%M:%S"),
        })
    return out


def create_report(payload, today=None, saver=save_request):
    today = today or dt.date.today()
    clean = report.parse_input(payload, today)
    w = report.warranty(clean["product"], clean["fault"], clean["purchase_date"], today)
    row_id = saver(clean, w["status"])
    result = report.build_report(clean, today, report.ticket_number(today, row_id))
    result["saved"] = row_id is not None
    return result


class Handler(BaseHTTPRequestHandler):
    server_version = "asdesk"

    def _send(self, code, obj):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/api/recent":
            rows = recent_requests()
            return self._send(200, {"available": rows is not None, "items": rows or []})
        if self.path == "/api/info":
            return self._send(200, {"instance_id": INSTANCE_ID})
        self._send(404, {"error": "not found"})

    def do_POST(self):
        if self.path != "/api/report":
            return self._send(404, {"error": "not found"})
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            return self._send(400, {"error": "请求格式不正确"})
        if length <= 0 or length > MAX_BODY:
            return self._send(400, {"error": "请求体大小不合法"})
        try:
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
            return self._send(200, create_report(payload))
        except report.ValidationError as exc:
            return self._send(400, {"error": str(exc)})
        except (ValueError, UnicodeDecodeError):
            return self._send(400, {"error": "请求格式不正确"})
        except Exception as exc:
            print("report failed: %s" % type(exc).__name__, file=sys.stderr)
            return self._send(500, {"error": "服务内部错误"})

    def log_message(self, fmt, *args):  # request lines only; no bodies (they hold user text)
        sys.stderr.write("%s %s\n" % (self.command, self.path))


if __name__ == "__main__":
    ThreadingHTTPServer(("127.0.0.1", 8000), Handler).serve_forever()
