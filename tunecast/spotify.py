"""A thin async Spotify Web API client (accounts for the February 2026 changes)."""

import asyncio
import base64
import json
import logging
import secrets
import time
import webbrowser
from pathlib import Path
from typing import Any
from urllib.parse import urlencode, urlparse

import httpx
from aiohttp import web

from .i18n import t

log = logging.getLogger(__name__)

AUTH_URL = "https://accounts.spotify.com/authorize"
TOKEN_URL = "https://accounts.spotify.com/api/token"
API = "https://api.spotify.com/v1"
SCOPES = " ".join(
    [
        "user-read-playback-state",
        "user-modify-playback-state",
        "user-read-currently-playing",
        "playlist-read-private",
        "playlist-read-collaborative",
        "user-library-read",
    ]
)

def done_html() -> str:
    return (
        '<!doctype html><meta charset="utf-8"><title>TuneCast</title>'
        '<body style="font-family:system-ui;background:#121212;color:#fff;display:grid;place-items:center;height:100vh;margin:0">'
        f'<div style="text-align:center"><div style="font-size:64px">🎧</div><h2>{t("login.page_title")}</h2>'
        f'<p style="color:#b3b3b3">{t("login.page_text")}</p></div></body>'
    )


class SpotifyError(Exception):
    def __init__(self, status: int, message: str, reason: str = ""):
        super().__init__(f"{status}: {message}")
        self.status = status
        self.message = message
        self.reason = reason


class NoActiveDevice(SpotifyError):
    pass


class PremiumRequired(SpotifyError):
    pass


class Spotify:
    def __init__(self, client_id: str, client_secret: str, redirect_uri: str, token_path: Path):
        self.client_id = client_id
        self.client_secret = client_secret
        self.redirect_uri = redirect_uri
        self.token_path = token_path
        self._token: dict[str, Any] | None = None
        self._http = httpx.AsyncClient(timeout=httpx.Timeout(15))
        self._refresh_lock = asyncio.Lock()

    async def close(self) -> None:
        await self._http.aclose()

    # ---------- sign-in ----------

    async def ensure_auth(self) -> None:
        if self.token_path.exists():
            try:
                self._token = json.loads(self.token_path.read_text("utf-8"))
                await self._access_token()
                return
            except Exception as exc:  # the token is broken or revoked
                log.warning("Could not refresh the Spotify token (%s), signing in again", exc)
        await self._authorize()

    async def _authorize(self) -> None:
        url = urlparse(self.redirect_uri)
        host, port, path = url.hostname or "127.0.0.1", url.port or 80, url.path or "/"
        state = secrets.token_urlsafe(16)
        result: asyncio.Future[str] = asyncio.get_running_loop().create_future()

        async def callback(request: web.Request) -> web.Response:
            if request.query.get("state") != state:
                return web.Response(text="Invalid state", status=400)
            if "error" in request.query:
                if not result.done():
                    result.set_exception(RuntimeError(f"Spotify declined the sign-in: {request.query['error']}"))
                return web.Response(text=t("login.denied"), status=400)
            if not result.done():
                result.set_result(request.query["code"])
            return web.Response(text=done_html(), content_type="text/html")

        app = web.Application()
        app.router.add_get(path, callback)
        runner = web.AppRunner(app)
        await runner.setup()
        await web.TCPSite(runner, host, port).start()

        auth_url = AUTH_URL + "?" + urlencode(
            {
                "client_id": self.client_id,
                "response_type": "code",
                "redirect_uri": self.redirect_uri,
                "scope": SCOPES,
                "state": state,
            }
        )
        print("\n" + t("login.open") + "\n" + auth_url + "\n", flush=True)
        webbrowser.open(auth_url)
        try:
            code = await result
        finally:
            await runner.cleanup()

        await self._fetch_token(
            {"grant_type": "authorization_code", "code": code, "redirect_uri": self.redirect_uri}
        )
        log.info("Spotify: signed in")

    async def _fetch_token(self, data: dict[str, str]) -> None:
        basic = base64.b64encode(f"{self.client_id}:{self.client_secret}".encode()).decode()
        resp = await self._http.post(TOKEN_URL, data=data, headers={"Authorization": f"Basic {basic}"})
        if resp.status_code != 200:
            raise SpotifyError(resp.status_code, resp.text)
        token = resp.json()
        if "refresh_token" not in token and self._token:
            token["refresh_token"] = self._token.get("refresh_token")
        token["expires_at"] = time.time() + token.get("expires_in", 3600) - 60
        self._token = token
        self.token_path.parent.mkdir(parents=True, exist_ok=True)
        self.token_path.write_text(json.dumps(token), "utf-8")

    async def _access_token(self, force: bool = False) -> str:
        assert self._token is not None, "call ensure_auth() first"
        async with self._refresh_lock:
            if force or time.time() >= self._token.get("expires_at", 0):
                await self._fetch_token(
                    {"grant_type": "refresh_token", "refresh_token": self._token["refresh_token"]}
                )
            return self._token["access_token"]

    # ---------- requests ----------

    async def _req(
        self, method: str, path: str, *, params: dict | None = None, body: Any = None, _retry: int = 2
    ) -> Any:
        token = await self._access_token()
        kwargs: dict[str, Any] = {"params": params, "headers": {"Authorization": f"Bearer {token}"}}
        if body is not None:
            kwargs["json"] = body
        elif method != "GET":
            kwargs["content"] = b""  # Spotify requires Content-Length even without a body
        try:
            resp = await self._http.request(method, API + path, **kwargs)
        except httpx.TransportError as exc:
            raise SpotifyError(0, f"no connection to Spotify ({exc.__class__.__name__})") from exc

        if resp.status_code == 401 and _retry:
            await self._access_token(force=True)
            return await self._req(method, path, params=params, body=body, _retry=_retry - 1)
        if resp.status_code == 429 and _retry:
            await asyncio.sleep(min(float(resp.headers.get("Retry-After", 1)), 10))
            return await self._req(method, path, params=params, body=body, _retry=_retry - 1)
        if resp.status_code >= 400:
            raise self._error(resp)
        if resp.status_code == 204 or not resp.content:
            return None
        try:
            return resp.json()
        except ValueError:
            return None

    @staticmethod
    def _error(resp: httpx.Response) -> SpotifyError:
        try:
            err = resp.json().get("error", {})
            if isinstance(err, str):
                err = {"message": err}
        except ValueError:
            err = {}
        message = err.get("message") or resp.text or resp.reason_phrase
        reason = err.get("reason", "")
        if reason == "NO_ACTIVE_DEVICE" or (resp.status_code == 404 and "device" in message.lower()):
            return NoActiveDevice(resp.status_code, message, reason)
        if reason == "PREMIUM_REQUIRED":
            return PremiumRequired(resp.status_code, message, reason)
        return SpotifyError(resp.status_code, message, reason)

    # ---------- data ----------

    async def me(self) -> dict:
        return await self._req("GET", "/me")

    async def playback(self) -> dict | None:
        return await self._req("GET", "/me/player", params={"additional_types": "track,episode"})

    async def devices(self) -> list[dict]:
        data = await self._req("GET", "/me/player/devices")
        return (data or {}).get("devices", [])

    async def queue(self) -> dict:
        return await self._req("GET", "/me/player/queue") or {}

    async def search_tracks(self, query: str, offset: int = 0, limit: int = 10) -> dict:
        # Since 2026, limit is at most 10 for development-mode apps
        data = await self._req(
            "GET", "/search", params={"q": query, "type": "track", "limit": limit, "offset": offset}
        )
        return (data or {}).get("tracks", {})

    async def my_playlists(self, offset: int = 0, limit: int = 8) -> dict:
        return await self._req("GET", "/me/playlists", params={"limit": limit, "offset": offset}) or {}

    async def playlist(self, playlist_id: str) -> dict:
        return await self._req("GET", f"/playlists/{playlist_id}")

    async def album(self, album_id: str) -> dict:
        return await self._req("GET", f"/albums/{album_id}")

    async def artist(self, artist_id: str) -> dict:
        return await self._req("GET", f"/artists/{artist_id}")

    async def track(self, track_id: str) -> dict:
        return await self._req("GET", f"/tracks/{track_id}")

    async def liked_tracks(self, limit: int = 50) -> list[dict]:
        data = await self._req("GET", "/me/tracks", params={"limit": limit})
        return [entry["track"] for entry in (data or {}).get("items", []) if entry.get("track")]

    # ---------- playback control ----------

    async def play(
        self,
        *,
        context_uri: str | None = None,
        uris: list[str] | None = None,
        offset: int | None = None,
        device_id: str | None = None,
    ) -> None:
        body: dict[str, Any] = {}
        if context_uri:
            body["context_uri"] = context_uri
        if uris:
            body["uris"] = uris
        if offset is not None:
            body["offset"] = {"position": offset}
        params = {"device_id": device_id} if device_id else None
        await self._req("PUT", "/me/player/play", params=params, body=body or None)

    async def pause(self) -> None:
        await self._req("PUT", "/me/player/pause")

    async def next(self) -> None:
        await self._req("POST", "/me/player/next")

    async def previous(self) -> None:
        await self._req("POST", "/me/player/previous")

    async def shuffle(self, state: bool) -> None:
        await self._req("PUT", "/me/player/shuffle", params={"state": "true" if state else "false"})

    async def repeat(self, state: str) -> None:
        await self._req("PUT", "/me/player/repeat", params={"state": state})

    async def volume(self, percent: int) -> None:
        await self._req("PUT", "/me/player/volume", params={"volume_percent": max(0, min(100, percent))})

    async def add_to_queue(self, uri: str) -> None:
        await self._req("POST", "/me/player/queue", params={"uri": uri})

    async def transfer(self, device_id: str, play: bool = True) -> None:
        await self._req("PUT", "/me/player", body={"device_ids": [device_id], "play": play})
