import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest
from fastapi.testclient import TestClient

from tests.fakes import KeywordEmbedder, QuoteAnswerer

ARTICLE_HTML = """<!doctype html>
<html><head><title>Connection Pooling Guide</title></head>
<body><nav>Home | Blog | About</nav>
<article>
<h1>Connection Pooling Guide</h1>
<p>PgBouncer sits between the application and Postgres and keeps a small pool of server connections open.
In transaction pooling mode a server connection is assigned to a client only for the duration of a transaction.</p>
<p>Size the application pool per instance so that instances multiplied by pool size stays below max_connections.
Prepared statements do not survive transaction pooling, so disable them in the database driver.</p>
<p>Monitor the waiting clients metric: if it grows, the pool is too small or transactions are too long.</p>
</article>
<footer>Copyright Example Corp</footer></body></html>"""

PAGES = {
    "/article": ("text/html; charset=utf-8", ARTICLE_HTML),
    "/notes.txt": ("text/plain", "Plain text page. " * 10),
    "/data.json": ("application/json", '{"not": "a page"}'),
    "/empty": ("text/html", "<html><body><div id=app></div><script>render()</script></body></html>"),
}


class _PageHandler(BaseHTTPRequestHandler):
    def do_GET(self):  # noqa: N802 (stdlib naming)
        page = PAGES.get(self.path)
        if page is None:
            self.send_response(404)
            self.end_headers()
            return
        content_type, body = page
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.end_headers()
        self.wfile.write(body.encode())

    def log_message(self, *args):
        pass


@pytest.fixture(scope="session")
def page_server():
    """A local website, so URL ingestion is tested end to end without the internet."""
    server = ThreadingHTTPServer(("127.0.0.1", 0), _PageHandler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_address[1]}"
    server.shutdown()


@pytest.fixture
def make_client(tmp_path, monkeypatch):
    """Build an app with its own SQLite file and offline Gemini stand-ins (no key or network)."""
    opened: list[TestClient] = []

    def _make(*, embedder=None, answerer=None, **env: str) -> TestClient:
        settings_env = {
            "APP_ENV": "test",
            "LOG_LEVEL": "WARNING",
            "DATABASE_PATH": str(tmp_path / "test.db"),
            "GEMINI_API_KEY": "test-key",
            **env,
        }
        for key, value in settings_env.items():
            monkeypatch.setenv(key, value)

        from app.core.config import get_settings

        get_settings.cache_clear()

        from app import main
        from app.providers import AIProviders, get_providers

        providers = AIProviders(embedder=embedder or KeywordEmbedder(), answerer=answerer or QuoteAnswerer())
        monkeypatch.setattr(main, "get_providers", lambda: providers)  # used by the worker at startup
        app = main.create_app()
        app.dependency_overrides[get_providers] = lambda: providers  # used by /query

        client = TestClient(app)
        client.__enter__()
        opened.append(client)
        return client

    yield _make

    for client in opened:
        client.__exit__(None, None, None)
    from app.core.config import get_settings

    get_settings.cache_clear()


@pytest.fixture
def client(make_client):
    return make_client()


def wait_for_status(client: TestClient, item_id: str, timeout: float = 5.0) -> dict:
    """Poll like the frontend does until the item leaves pending/processing."""
    deadline = time.monotonic() + timeout
    item: dict = {}
    while time.monotonic() < deadline:
        item = client.get(f"/items/{item_id}").json()["item"]
        if item["status"] in ("ready", "failed"):
            return item
        time.sleep(0.05)
    raise AssertionError(f"item {item_id} still {item.get('status')} after {timeout}s")


def step_statuses(item: dict) -> dict[str, str]:
    return {step["name"]: step["status"] for step in item["steps"]}
