"""Production entrypoint — reads PORT from the environment (no shell expansion)."""

from __future__ import annotations

import os
import sys


def main() -> None:
    port = int(os.environ.get("PORT", "8000"))
    print(f"starting uvicorn on 0.0.0.0:{port}", flush=True)
    try:
        import uvicorn
    except Exception as exc:  # pragma: no cover
        print(f"failed to import uvicorn: {exc}", file=sys.stderr, flush=True)
        raise
    uvicorn.run("app.main:app", host="0.0.0.0", port=port, log_level="info")


if __name__ == "__main__":
    main()
