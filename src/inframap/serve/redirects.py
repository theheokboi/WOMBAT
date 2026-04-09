from __future__ import annotations

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import RedirectResponse


def register_ui_redirects(app: FastAPI) -> None:
    @app.get("/", include_in_schema=False)
    def root_redirect() -> RedirectResponse:
        return RedirectResponse(url="/ui/", status_code=307)

    @app.get("/ar", include_in_schema=False)
    @app.get("/ar/", include_in_schema=False)
    def argentina_redirect() -> RedirectResponse:
        return RedirectResponse(url="/ui/?country=AR", status_code=307)

    @app.get("/demo", include_in_schema=False)
    @app.get("/demo/", include_in_schema=False)
    def demo_redirect() -> RedirectResponse:
        return RedirectResponse(url="/ui/?country=DEMO", status_code=307)

    @app.get("/k-rings", include_in_schema=False)
    @app.get("/k-rings/", include_in_schema=False)
    def k_rings_redirect(request: Request) -> RedirectResponse:
        query = request.url.query
        suffix = f"?{query}" if query else ""
        return RedirectResponse(url=f"/ui/k-rings.html{suffix}", status_code=307)

    @app.get("/{country_code}", include_in_schema=False)
    @app.get("/{country_code}/", include_in_schema=False)
    def country_redirect(country_code: str) -> RedirectResponse:
        code = country_code.strip().upper()
        if len(code) != 2 or not code.isalpha() or code in {"UI", "V1"}:
            raise HTTPException(status_code=404, detail="Not Found")
        return RedirectResponse(url=f"/ui/?country={code}", status_code=307)
