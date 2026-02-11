"""prompt_anywhere.host.main

Local Agent Host daemon.

Goal: keep model backends warm and provide a stable localhost API for the UI.

Run:
  python -m prompt_anywhere.host
  # or: prompt-anywhere-host
"""

from __future__ import annotations

import os

import uvicorn

from prompt_anywhere.host.api import create_app


def main() -> None:
    host = os.environ.get("PROMPT_ANYWHERE_HOST", "127.0.0.1")
    port = int(os.environ.get("PROMPT_ANYWHERE_PORT", "17123"))

    app = create_app()
    uvicorn.run(app, host=host, port=port, log_level="info")


if __name__ == "__main__":
    main()
