# SPDX-License-Identifier: Apache-2.0
"""HTTP layer: the PWA, its share target and a small JSON API."""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import parse_qs, quote

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import __version__
from .assets import page
from .config import Settings, load_settings
from .cookies import PLATFORMS, CookieError, netscape
from .cookies import remove as remove_cookies
from .cookies import save as save_cookies
from .cookies import source as cookie_source
from .jobs import STORAGE_FAILED, JobStore, Runner, StorageError, default_runner
from .urls import UrlError, target_from_shared

# Login page texts, "du" as in all own Azentrius apps. Buttons are verb plus object.
LOGIN_TEXT = {
    "de": {
        "title": "Gerät anmelden",
        "desc": "Sharewerk fragt den Zugangs-Token einmal pro Gerät ab.",
        "label": "Zugangs-Token",
        "help": "Der Wert von SHAREWERK_AUTH_TOKEN aus der .env-Datei des Servers.",
        "error": "Der Token stimmt nicht. Gib den Wert von SHAREWERK_AUTH_TOKEN ein.",
        "submit": "Gerät anmelden",
        "source": "Quellcode",
    },
    "en": {
        "title": "Sign in this device",
        "desc": "Sharewerk asks for the access token once per device.",
        "label": "Access token",
        "help": "The value of SHAREWERK_AUTH_TOKEN from the server's .env file.",
        "error": "The token does not match. Enter the value of SHAREWERK_AUTH_TOKEN.",
        "submit": "Sign in device",
        "source": "Source code",
    },
}

STATIC = Path(__file__).parent / "static"
COOKIE = "sharewerk_session"
CLIENT_HEADER = "x-sharewerk-client"
MAX_COOKIE_UPLOAD = 512 * 1024
PUBLIC_PATHS = {"/healthz", "/login", "/manifest.webmanifest", "/sw.js", "/favicon.ico"}
CSP = (
    "default-src 'self'; img-src 'self' blob: data:; media-src 'self' blob:; style-src 'self'; "
    "script-src 'self'; connect-src 'self'; manifest-src 'self'; worker-src 'self'; "
    "frame-ancestors 'none'; base-uri 'none'; form-action 'self'"
)

log = logging.getLogger("sharewerk")


class JobRequest(BaseModel):
    text: str | None = None
    url: str | None = None
    title: str | None = None
    force: bool = False


def session_value(token: str) -> str:
    return hmac.new(token.encode(), b"sharewerk-session-v1", hashlib.sha256).hexdigest()


def safe_next(value: str | None) -> str:
    if not value or not value.startswith("/") or value.startswith(("//", "/\\")):
        return "/"
    return value


def create_app(settings: Settings | None = None, runner: Runner | None = None) -> FastAPI:
    settings = settings or load_settings()
    store = JobStore(settings, runner or default_runner)

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        store.start()
        log.info(
            "Sharewerk ready (auth=%s, transcription=%s, cookies=%s)",
            settings.auth_mode,
            settings.whisper_model if settings.transcription_enabled else "off",
            ",".join(p for p in PLATFORMS if cookie_source(settings, p)) or "none",
        )
        yield
        store.stop()

    app = FastAPI(title="Sharewerk", docs_url=None, redoc_url=None, openapi_url=None, lifespan=lifespan)
    app.state.store = store
    app.state.settings = settings

    # ------------------------------------------------------------- middleware
    def authorised(request: Request) -> bool:
        if settings.auth_mode == "none":
            return True
        expected = session_value(settings.auth_token)
        cookie = request.cookies.get(COOKIE, "")
        if cookie and hmac.compare_digest(cookie, expected):
            return True
        header = request.headers.get("authorization", "")
        if header.lower().startswith("bearer "):
            return hmac.compare_digest(header[7:].strip(), settings.auth_token)
        return False

    @app.middleware("http")
    async def guard(request: Request, call_next):
        path = request.url.path
        public = path in PUBLIC_PATHS or path.startswith("/static/")
        if not public and not authorised(request):
            if path.startswith("/api/"):
                response: Response = JSONResponse({"error": "unauthorised"}, status_code=401)
            else:
                target = path + (f"?{request.url.query}" if request.url.query else "")
                response = RedirectResponse(f"/login?next={quote(target, safe='')}", status_code=303)
        else:
            response = await call_next(request)
        response.headers.setdefault("Content-Security-Policy", CSP)
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("Permissions-Policy", "web-share=(self)")
        return response

    # ------------------------------------------------------------------ pages
    index_html = page("index.html")  # script and stylesheet URLs carry their content hash

    def index() -> HTMLResponse:
        return HTMLResponse(index_html, headers={"Cache-Control": "no-cache"})

    app.get("/", include_in_schema=False)(index)
    app.get("/share", include_in_schema=False)(index)

    @app.get("/manifest.webmanifest", include_in_schema=False)
    def manifest() -> FileResponse:
        return FileResponse(STATIC / "manifest.webmanifest", media_type="application/manifest+json")

    @app.get("/sw.js", include_in_schema=False)
    def service_worker() -> FileResponse:
        return FileResponse(STATIC / "sw.js", media_type="text/javascript", headers={"Cache-Control": "no-cache"})

    @app.get("/favicon.ico", include_in_schema=False)
    def favicon() -> FileResponse:
        return FileResponse(STATIC / "icons" / "icon-192.png", media_type="image/png")

    @app.get("/healthz", include_in_schema=False)
    def healthz() -> Response:
        # 503 when jobs cannot be processed: the worker stopped, or job states cannot be saved.
        # The cookie state never fails the check (Facebook works without cookies); a monitor
        # can watch for "cookies":"expired" on its own. "cookies" is Instagram's state, as before
        # there were cookies per platform; "cookie_states" has every platform.
        problem = store.problem()
        body: dict = {"ok": not problem}
        if problem:
            body["problem"] = problem
        body["cookies"] = store.cookie_state("instagram")
        body["cookie_states"] = {p: store.cookie_state(p) for p in PLATFORMS}
        return JSONResponse(body, status_code=503 if problem else 200)

    @app.get("/login", include_in_schema=False)
    def login_page(request: Request, error: str = "") -> Response:
        if settings.auth_mode == "none" or authorised(request):
            return RedirectResponse(safe_next(request.query_params.get("next")), status_code=303)
        lang = "de" if request.headers.get("accept-language", "").lower().startswith("de") else "en"
        values = {
            **LOGIN_TEXT[lang],
            "lang": lang,
            "next": safe_next(request.query_params.get("next")),
            "version": __version__,
            "host": request.headers.get("host", ""),
            "error_hidden": "" if error else "hidden",
            "invalid": 'aria-invalid="true"' if error else "",
        }
        html = page("login.html")
        for key, value in values.items():
            safe = value if key in {"error_hidden", "invalid"} else _escape(value)
            html = html.replace("{{" + key + "}}", safe)
        return HTMLResponse(html, headers={"Cache-Control": "no-store"})

    @app.post("/login", include_in_schema=False)
    async def login(request: Request) -> Response:
        form = parse_qs((await request.body()).decode("utf-8", "replace"))
        token = (form.get("token") or [""])[0].strip()
        nxt = safe_next((form.get("next") or ["/"])[0])
        if settings.auth_mode == "none":
            return RedirectResponse(nxt, status_code=303)
        if not hmac.compare_digest(token, settings.auth_token):
            return RedirectResponse(f"/login?error=1&next={quote(nxt, safe='')}", status_code=303)
        response = RedirectResponse(nxt, status_code=303)
        response.set_cookie(
            COOKIE, session_value(settings.auth_token), max_age=400 * 24 * 3600,
            httponly=True, secure=settings.cookie_secure, samesite="lax", path="/",
        )
        return response

    @app.post("/logout", include_in_schema=False)
    def logout() -> Response:
        response = RedirectResponse("/login", status_code=303)
        response.delete_cookie(COOKIE, path="/")
        return response

    # -------------------------------------------------------------------- api
    @app.get("/api/config")
    def api_config() -> dict:
        return {
            "version": __version__,
            "auth_mode": settings.auth_mode,
            "transcription": settings.transcription_enabled,
            "cookies": any(cookie_source(settings, p) for p in PLATFORMS),
            "retention_hours": settings.retention_hours,
            "max_share_files": 10,
        }

    @app.post("/api/jobs")
    def create_job(body: JobRequest) -> dict:
        try:
            target = target_from_shared(body.url, body.text, body.title, allowed_hosts=settings.allowed_hosts)
        except UrlError as exc:
            raise HTTPException(status_code=422, detail={"code": exc.code, "message": str(exc)}) from exc
        try:
            job = store.submit(target, force=body.force)
        except StorageError as exc:
            raise HTTPException(status_code=503, detail={"code": STORAGE_FAILED, "message": str(exc)}) from exc
        return job_view(job)

    @app.get("/api/jobs")
    def list_jobs() -> list[dict]:
        return [
            {"id": j.id, "url": j.url, "platform": j.platform, "status": j.status,
             "author": (j.result or {}).get("meta", {}).get("author", ""), "created": j.created}
            for j in store.recent()
        ]

    @app.get("/api/jobs/{job_id}")
    def get_job(job_id: str) -> dict:
        job = store.get(job_id)
        if not job:
            raise HTTPException(status_code=404, detail={"code": "job_not_found"})
        return job_view(job)

    @app.delete("/api/jobs/{job_id}")
    def delete_job(job_id: str) -> dict:
        try:
            refused = store.delete(job_id)
        except StorageError as exc:
            raise HTTPException(status_code=503, detail={"code": STORAGE_FAILED, "message": str(exc)}) from exc
        if refused:
            raise HTTPException(status_code=404 if refused == "job_not_found" else 409, detail={"code": refused})
        return {"deleted": job_id}

    @app.get("/api/jobs/{job_id}/files/{name}")
    def get_file(job_id: str, name: str) -> FileResponse:
        job = store.get(job_id)
        found = store.file_path(job, name) if job else None
        if not found:
            raise HTTPException(status_code=404, detail={"code": "file_not_found"})
        path, meta = found
        return FileResponse(
            path, media_type=meta["type"], filename=meta["name"], content_disposition_type="inline",
            headers={"Cache-Control": "private, max-age=86400"},
        )

    # ---------------------------------------------------- cookies (browser extension)
    # Only the extension sends cookies. Its requests carry CLIENT_HEADER: a web page cannot add a
    # custom header to a request to another site without a CORS preflight, which this app never
    # allows, so no other site can plant cookies here through a logged-in browser.
    def cookie_view(platform: str) -> dict:
        found = cookie_source(settings, platform)
        updated = None
        if found:
            try:
                updated = found[0].stat().st_mtime
            except OSError:
                found = None
        return {
            "state": store.cookie_state(platform),
            "source": found[1] if found else "",
            "updated": updated,
        }

    def check_cookie_request(request: Request, platform: str) -> None:
        if request.headers.get(CLIENT_HEADER, "") != "extension":
            raise HTTPException(status_code=403, detail={"code": "client_header_missing"})
        if platform not in PLATFORMS:
            raise HTTPException(status_code=404, detail={"code": "platform_unknown"})

    @app.get("/api/cookies")
    def list_cookies() -> dict:
        return {"platforms": {p: cookie_view(p) for p in PLATFORMS}}

    @app.put("/api/cookies/{platform}")
    async def put_cookies(platform: str, request: Request) -> dict:
        check_cookie_request(request, platform)
        too_large = HTTPException(status_code=413, detail={"code": "cookies_too_large"})
        length = request.headers.get("content-length", "0")
        if not length.isdigit() or int(length) > MAX_COOKIE_UPLOAD:
            raise too_large
        raw = await request.body()
        if len(raw) > MAX_COOKIE_UPLOAD:  # sent without a (true) Content-Length
            raise too_large
        try:
            data = json.loads(raw)
        except (ValueError, RecursionError):  # RecursionError: nested a few thousand levels deep
            data = None
        try:
            text = netscape(platform, data.get("cookies") if isinstance(data, dict) else None)
        except CookieError as exc:  # the message names domains or cookie names, never values
            raise HTTPException(status_code=422, detail={"code": exc.code, "message": str(exc)}) from exc
        try:
            save_cookies(settings, platform, text)
        except OSError as exc:
            log.error("cannot save the cookies of %s: %s", platform, exc)
            raise HTTPException(status_code=503, detail={"code": STORAGE_FAILED}) from exc
        log.info("cookies of %s received from the browser extension", platform)
        return {"platform": platform, **cookie_view(platform)}

    @app.delete("/api/cookies/{platform}")
    def delete_cookies(platform: str, request: Request) -> dict:
        check_cookie_request(request, platform)
        try:
            removed = remove_cookies(settings, platform)
        except OSError as exc:
            log.error("cannot delete the cookies of %s: %s", platform, exc)
            raise HTTPException(status_code=503, detail={"code": STORAGE_FAILED}) from exc
        if not removed:
            raise HTTPException(status_code=404, detail={"code": "cookies_not_found"})
        log.info("cookies of %s deleted by the browser extension", platform)
        return {"platform": platform, **cookie_view(platform)}

    def job_view(job) -> dict:
        data = job.public()
        data["queue_position"] = store.queue_position(job.id)
        if data["result"]:
            for meta in data["result"]["files"].values():
                meta.pop("path", None)
        return data

    app.mount("/static", StaticFiles(directory=STATIC), name="static")
    return app


def _escape(value: str) -> str:
    return (
        value.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")
    )


def run() -> None:  # pragma: no cover - container entry point
    import uvicorn

    logging.basicConfig(
        level=os.environ.get("SHAREWERK_LOG_LEVEL", "INFO").upper(),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    uvicorn.run(
        create_app(),
        host=os.environ.get("SHAREWERK_HOST", "0.0.0.0"),
        port=int(os.environ.get("SHAREWERK_PORT", "8080")),
        proxy_headers=True,
        forwarded_allow_ips=os.environ.get("SHAREWERK_FORWARDED_ALLOW_IPS", "*"),
        log_level="warning",
    )


if __name__ == "__main__":  # pragma: no cover
    run()
