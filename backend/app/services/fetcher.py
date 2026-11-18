"""Server-side URL fetching and readable-text extraction.

Guards: public hosts only (basic SSRF protection), timeout, max body size,
HTML/plain-text only, and a minimum amount of extractable text.
"""

import asyncio
import ipaddress
import socket
from dataclasses import dataclass
from urllib.parse import urlparse

import httpx
import trafilatura

from app.services.text import normalize_whitespace
from app.services.text_cleanup import clean_extracted_text

USER_AGENT = "KnowledgeInbox/0.1 (personal knowledge tool)"
ALLOWED_CONTENT_TYPES = {"text/html", "application/xhtml+xml", "text/plain"}
MIN_TEXT_CHARS = 50


class FetchError(Exception):
    """A URL could not be turned into text. The message is safe to show to the user."""


@dataclass(frozen=True)
class FetchedPage:
    url: str
    title: str | None
    text: str


async def fetch_page(
    url: str, *, timeout_seconds: float, max_bytes: int, allow_private_hosts: bool = False
) -> FetchedPage:
    host = urlparse(url).hostname or ""
    if not allow_private_hosts:
        await _ensure_public_host(host)

    try:
        async with httpx.AsyncClient(
            follow_redirects=True,
            max_redirects=5,
            timeout=timeout_seconds,
            headers={"User-Agent": USER_AGENT, "Accept": "text/html,text/plain;q=0.9"},
        ) as client:
            async with client.stream("GET", url) as response:
                if response.status_code >= 400:
                    raise FetchError(f"The page returned HTTP {response.status_code}.")
                content_type = response.headers.get("content-type", "").split(";")[0].strip().lower()
                if content_type not in ALLOWED_CONTENT_TYPES:
                    raise FetchError(
                        f"Unsupported content type '{content_type or 'unknown'}'. Only HTML and plain-text pages can be saved."
                    )
                body = await _read_limited(response, max_bytes)
                encoding = response.encoding or "utf-8"
    except httpx.TimeoutException as exc:
        raise FetchError(f"The page didn't respond within {timeout_seconds:g} seconds.") from exc
    except httpx.TooManyRedirects as exc:
        raise FetchError("The page redirected too many times.") from exc
    except httpx.RequestError as exc:
        raise FetchError(f"Couldn't connect to {host}.") from exc

    raw = body.decode(encoding, errors="replace")
    if content_type == "text/plain":
        title, text = None, normalize_whitespace(raw)
    else:
        # trafilatura is CPU-bound; keep it off the event loop.
        title, text = await asyncio.to_thread(_extract_html, raw)

    if len(text) < MIN_TEXT_CHARS:
        raise FetchError("Couldn't find readable text on the page. It may need JavaScript or a login.")
    return FetchedPage(url=url, title=title, text=text)


async def _read_limited(response: httpx.Response, max_bytes: int) -> bytes:
    body = bytearray()
    async for part in response.aiter_bytes():
        body.extend(part)
        if len(body) > max_bytes:
            raise FetchError(f"The page is larger than the {max_bytes / 1_000_000:g} MB limit.")
    return bytes(body)


def _extract_html(html: str) -> tuple[str | None, str]:
    text = trafilatura.extract(html, include_comments=False, include_tables=True, favor_recall=True) or ""
    metadata = trafilatura.extract_metadata(html)
    return _clean_title(metadata.title if metadata else None), clean_extracted_text(text)


def _clean_title(title: str | None) -> str | None:
    """Drop heading-anchor symbols docs sites append (e.g. 'Background Tasks¶')."""
    if not title:
        return None
    return title.strip().rstrip("¶#§").strip() or None


async def _ensure_public_host(host: str) -> None:
    """Refuse loopback/private/link-local targets so the server can't be used to probe its own network."""
    if not host:
        raise FetchError("The link has no host name.")
    try:
        infos = await asyncio.to_thread(socket.getaddrinfo, host, None)
    except socket.gaierror as exc:
        raise FetchError(f"Couldn't find the website {host}.") from exc

    for info in infos:
        address = ipaddress.ip_address(info[4][0])
        if address.is_private or address.is_loopback or address.is_link_local or address.is_reserved:
            raise FetchError("Links to private or local network addresses can't be saved.")
