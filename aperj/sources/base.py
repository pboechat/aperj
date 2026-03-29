"""Base class for all apartment listing scrapers."""

from __future__ import annotations

import abc
import asyncio
import json as _json
import logging
import random
from typing import Any

import aiohttp
from bs4 import BeautifulSoup
from curl_cffi.requests import AsyncSession as CffiSession

from aperj.config import get_auth, get_source_config, load_cookies
from aperj.models import Listing

logger = logging.getLogger(__name__)

# Shared browser-like headers to reduce bot detection.
DEFAULT_HEADERS: dict[str, str] = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
    "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
    "Upgrade-Insecure-Requests": "1",
    "Cache-Control": "max-age=0",
}

MAX_RETRIES = 2
RETRY_BACKOFF = 2.0

# Browser to impersonate when using curl_cffi (TLS fingerprint).
_CFFI_IMPERSONATE = "chrome131"

# Default FlareSolverr endpoint (overridden by config["flaresolverr_url"]).
_DEFAULT_FLARESOLVERR_URL = "http://localhost:8191/v1"


class BaseSource(abc.ABC):
    """Abstract base class that every source scraper must implement."""

    # Subclasses MUST set these:
    name: str = ""
    base_url: str = ""

    def __init__(self, config: dict[str, Any]) -> None:
        self.config = config
        self.source_config = get_source_config(config, self.name)
        self.auth = get_auth(config, self.name)
        self.cookies = load_cookies(self.name)
        self.max_results: int = int(config.get("max_results_per_source", 50))
        self.flaresolverr_url: str = config.get("flaresolverr_url", "")
        self.logger = logging.getLogger(f"aperj.sources.{self.name}")

    # ------------------------------------------------------------------
    # Helpers available to all subclasses
    # ------------------------------------------------------------------

    def _build_session(self) -> aiohttp.ClientSession:
        """Create an ``aiohttp.ClientSession`` pre-configured with headers and cookies."""
        cookie_jar = aiohttp.CookieJar(unsafe=True)
        session = aiohttp.ClientSession(
            headers=DEFAULT_HEADERS,
            cookie_jar=cookie_jar,
        )
        # Inject loaded cookies
        for k, v in self.cookies.items():
            session.cookie_jar.update_cookies({k: v})
        return session

    async def _fetch(
        self,
        session: aiohttp.ClientSession,
        url: str,
        *,
        allow_redirects: bool = True,
    ) -> str:
        """Fetch a URL and return its body as text, with retry on transient errors.

        On persistent 403 responses the method transparently falls back to
        ``curl_cffi`` which impersonates a real browser TLS fingerprint,
        bypassing most WAF / bot-detection systems.
        """
        for attempt in range(MAX_RETRIES + 1):
            self.logger.debug("GET %s (attempt %d)", url, attempt + 1)
            try:
                async with session.get(
                    url,
                    timeout=aiohttp.ClientTimeout(total=30),
                    allow_redirects=allow_redirects,
                ) as resp:
                    if resp.status == 403 and attempt < MAX_RETRIES:
                        wait = RETRY_BACKOFF * (attempt + 1) + random.uniform(0.5, 1.5)
                        self.logger.debug("Got 403, retrying in %.1fs …", wait)
                        await asyncio.sleep(wait)
                        continue
                    if resp.status == 403:
                        # aiohttp exhausted - try curl_cffi with browser TLS
                        return await self._cffi_fetch_text(url, allow_redirects=allow_redirects)
                    resp.raise_for_status()
                    return await resp.text()
            except (aiohttp.ClientConnectionError, asyncio.TimeoutError):
                if attempt < MAX_RETRIES:
                    wait = RETRY_BACKOFF * (attempt + 1)
                    self.logger.debug("Connection error, retrying in %.1fs …", wait)
                    await asyncio.sleep(wait)
                    continue
                raise
        # Unreachable but satisfies type checker
        raise aiohttp.ClientError("Max retries exceeded")

    async def _fetch_json(self, session: aiohttp.ClientSession, url: str) -> Any:
        """Fetch a URL and return parsed JSON, with retry on transient errors."""
        for attempt in range(MAX_RETRIES + 1):
            self.logger.debug("GET (json) %s (attempt %d)", url, attempt + 1)
            try:
                async with session.get(
                    url, timeout=aiohttp.ClientTimeout(total=30)
                ) as resp:
                    if resp.status == 403 and attempt < MAX_RETRIES:
                        wait = RETRY_BACKOFF * (attempt + 1) + random.uniform(0.5, 1.5)
                        self.logger.debug("Got 403, retrying in %.1fs …", wait)
                        await asyncio.sleep(wait)
                        continue
                    if resp.status == 403:
                        return await self._cffi_fetch_json(url, extra_headers=dict(session.headers))
                    resp.raise_for_status()
                    return await resp.json(content_type=None)
            except (aiohttp.ClientConnectionError, asyncio.TimeoutError):
                if attempt < MAX_RETRIES:
                    wait = RETRY_BACKOFF * (attempt + 1)
                    self.logger.debug("Connection error, retrying in %.1fs …", wait)
                    await asyncio.sleep(wait)
                    continue
                raise
        raise aiohttp.ClientError("Max retries exceeded")

    # ------------------------------------------------------------------
    # curl_cffi fallback helpers (browser TLS impersonation)
    # ------------------------------------------------------------------

    async def _cffi_fetch_text(
        self,
        url: str,
        *,
        allow_redirects: bool = True,
        extra_headers: dict[str, str] | None = None,
    ) -> str:
        """Fetch *url* via ``curl_cffi`` with browser impersonation and return text.

        Falls back to FlareSolverr when ``curl_cffi`` also gets a 403.
        """
        self.logger.debug("curl_cffi GET %s (impersonate=%s)", url, _CFFI_IMPERSONATE)
        headers = dict(DEFAULT_HEADERS)
        if extra_headers:
            headers.update(extra_headers)
        try:
            async with CffiSession() as s:
                resp = await s.get(
                    url,
                    headers=headers,
                    impersonate=_CFFI_IMPERSONATE,
                    allow_redirects=allow_redirects,
                    timeout=30,
                )
                resp.raise_for_status()
                return resp.text
        except Exception:
            if self.flaresolverr_url:
                return await self._flaresolverr_fetch(url)
            raise

    async def _cffi_fetch_json(
        self,
        url: str,
        *,
        extra_headers: dict[str, str] | None = None,
    ) -> Any:
        """Fetch *url* via ``curl_cffi`` with browser impersonation and return JSON.

        Falls back to FlareSolverr when ``curl_cffi`` also gets a 403.
        """
        self.logger.debug("curl_cffi GET (json) %s (impersonate=%s)", url, _CFFI_IMPERSONATE)
        headers = dict(DEFAULT_HEADERS)
        if extra_headers:
            headers.update(extra_headers)
        try:
            async with CffiSession() as s:
                resp = await s.get(
                    url,
                    headers=headers,
                    impersonate=_CFFI_IMPERSONATE,
                    timeout=30,
                )
                resp.raise_for_status()
                return _json.loads(resp.content)
        except Exception:
            if self.flaresolverr_url:
                text = await self._flaresolverr_fetch(url)
                return _json.loads(text)
            raise

    # ------------------------------------------------------------------
    # FlareSolverr fallback (external service for Cloudflare challenges)
    # ------------------------------------------------------------------

    async def _flaresolverr_fetch(self, url: str) -> str:
        """Request *url* through a running FlareSolverr instance.

        FlareSolverr uses a real browser with Xvfb to solve Cloudflare
        managed challenges.  Set ``flaresolverr_url`` in config to enable.
        """
        endpoint = self.flaresolverr_url
        self.logger.debug("FlareSolverr GET %s via %s", url, endpoint)
        payload = {
            "cmd": "request.get",
            "url": url,
            "maxTimeout": 60000,
        }
        async with aiohttp.ClientSession() as session:
            async with session.post(
                endpoint,
                json=payload,
                timeout=aiohttp.ClientTimeout(total=90),
            ) as resp:
                resp.raise_for_status()
                data = await resp.json()
        status = data.get("status", "")
        if status != "ok":
            msg = data.get("message", "unknown error")
            raise RuntimeError(f"FlareSolverr error: {msg}")
        solution = data.get("solution", {})
        body = solution.get("response", "")
        if not body:
            raise RuntimeError("FlareSolverr returned empty response")
        return body

    async def _post_json(
        self,
        session: aiohttp.ClientSession,
        url: str,
        payload: dict[str, Any],
    ) -> Any:
        """POST JSON and return parsed JSON response."""
        self.logger.debug("POST (json) %s", url)
        async with session.post(
            url, json=payload, timeout=aiohttp.ClientTimeout(total=30)
        ) as resp:
            resp.raise_for_status()
            return await resp.json(content_type=None)

    @staticmethod
    def _soup(html: str) -> BeautifulSoup:
        return BeautifulSoup(html, "lxml")

    def _enabled(self) -> bool:
        return self.source_config.get("enabled", True)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def scrape(self, keywords: list[str]) -> list[Listing]:
        """Entry-point called by the orchestrator.

        Returns an empty list if the source is disabled.
        """
        if not self._enabled():
            self.logger.info("Source %s is disabled - skipping.", self.name)
            return []

        self.logger.info("Scraping %s with keywords=%s …", self.name, keywords)
        try:
            listings = await self._do_scrape(keywords)
            self.logger.info("Source %s returned %d listing(s).", self.name, len(listings))
            return listings
        except Exception:
            self.logger.exception("Source %s failed.", self.name)
            return []

    # ------------------------------------------------------------------
    # Subclass contract
    # ------------------------------------------------------------------

    @abc.abstractmethod
    async def _do_scrape(self, keywords: list[str]) -> list[Listing]:
        """Perform the actual scraping.  Must be implemented by every source."""
        ...
