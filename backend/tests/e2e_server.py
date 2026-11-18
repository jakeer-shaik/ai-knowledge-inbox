"""Backend for the Playwright end-to-end tests.

The real app (API, worker, fetcher, chunker, SQLite) with Gemini replaced by the offline
test stand-ins, a throwaway database, and local URLs allowed so tests can ingest pages
from a local web server. Vector creation is slowed down slightly so the UI's live
step progress can be observed.

    python tests/e2e_server.py --port 8100
"""

import argparse
import asyncio
import os
import shutil
import sys
import tempfile
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

EMBED_DELAY_SECONDS = 2.0
ANSWER_DELAY_SECONDS = 0.8


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8100)
    args = parser.parse_args()

    # One fixed throwaway folder, wiped at the start of every run. (Playwright force-kills
    # its servers, so cleanup-on-exit can't be relied on; this way nothing accumulates.)
    data_dir = Path(tempfile.gettempdir()) / "inbox-e2e"
    shutil.rmtree(data_dir, ignore_errors=True)
    data_dir.mkdir()
    serve(args.port, data_dir / "e2e.db")


def serve(port: int, database_path: Path) -> None:
    os.environ.update(
        APP_ENV="test",
        LOG_LEVEL="WARNING",
        GEMINI_API_KEY="e2e-offline",
        DATABASE_PATH=str(database_path),
        FETCH_ALLOW_PRIVATE_HOSTS="true",
        CORS_ORIGINS='["http://localhost:5180"]',
    )

    import uvicorn

    from app import main as app_main
    from app.providers import AIProviders, get_providers
    from tests.fakes import KeywordEmbedder, QuoteAnswerer

    class PacedEmbedder(KeywordEmbedder):
        async def embed_documents(self, texts):
            await asyncio.sleep(EMBED_DELAY_SECONDS)
            return await super().embed_documents(texts)

    class PacedAnswerer(QuoteAnswerer):
        async def answer(self, question, passages, history):
            await asyncio.sleep(ANSWER_DELAY_SECONDS)  # long enough to see the loading state
            return await super().answer(question, passages, history)

    providers = AIProviders(embedder=PacedEmbedder(), answerer=PacedAnswerer())
    app_main.get_providers = lambda: providers
    app = app_main.create_app()
    app.dependency_overrides[get_providers] = lambda: providers

    uvicorn.run(app, host="127.0.0.1", port=port, log_level="warning")


if __name__ == "__main__":
    main()
