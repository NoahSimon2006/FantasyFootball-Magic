"""The web app's copy of the OpenAPI schema must match the API that serves it.

web/src/lib/api/openapi.json is generated from this app and is what the web app's
TypeScript types are generated from. If a route or schema changes without regenerating
it, every pytest can pass while the frontend still expects the old shape.
"""

from pathlib import Path

from app.export_openapi import WEB_OPENAPI_PATH, main, render_openapi_json

REGENERATE = """
web/src/lib/api/openapi.json no longer matches the API. Regenerate it and the TypeScript types:
  1. in api/:  uv run python -m app.export_openapi
  2. in web/:  npm run gen:api
"""


def test_committed_openapi_json_matches_the_api() -> None:
    # newline="" keeps "\r\n" as-is, so the comparison is against the exact committed text.
    committed = (
        WEB_OPENAPI_PATH.read_text(encoding="utf-8", newline="")
        if WEB_OPENAPI_PATH.exists()
        else ""
    )

    assert committed == render_openapi_json(), REGENERATE


def test_exporter_writes_exactly_what_the_contract_test_expects(tmp_path: Path) -> None:
    # Guarantees the command in REGENERATE actually fixes the test above, on every OS:
    # same text, UTF-8, "\n" newlines even on Windows.
    output = tmp_path / "openapi.json"

    main([str(output)])

    assert output.read_bytes() == render_openapi_json().encode("utf-8")
