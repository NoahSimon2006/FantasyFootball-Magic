"""Write the API's OpenAPI schema to the file the web app generates its TypeScript types from.

Run from api/:   uv run python -m app.export_openapi [output_path]
then from web/:  npm run gen:api
"""

import argparse
import json
from pathlib import Path

from app.main import app

# Resolved from this file rather than the working directory, so the default (and the
# contract test that reads it) points at the right file wherever the command runs from.
REPO_ROOT = Path(__file__).resolve().parents[2]
WEB_OPENAPI_PATH = REPO_ROOT / "web" / "src" / "lib" / "api" / "openapi.json"


def render_openapi_json() -> str:
    """Return the schema exactly as it is committed for the web app.

    Sorted keys and a fixed indent make the text deterministic, so the committed file
    (and its git diff) changes only when the API itself changes.
    """
    return json.dumps(app.openapi(), indent=2, sort_keys=True) + "\n"


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        prog="python -m app.export_openapi",
        description="Write the API's OpenAPI schema as JSON for the web app's generated types.",
    )
    parser.add_argument(
        "output_path",
        nargs="?",
        type=Path,
        default=WEB_OPENAPI_PATH,
        help="where to write the schema (default: ../web/src/lib/api/openapi.json)",
    )
    output_path: Path = parser.parse_args(argv).output_path

    # newline="\n": in text mode Windows would otherwise write "\r\n", and the file's bytes
    # would differ from what macOS, Linux, and the contract test produce.
    output_path.write_text(render_openapi_json(), encoding="utf-8", newline="\n")
    print(f"Wrote {output_path}")


if __name__ == "__main__":
    main()
