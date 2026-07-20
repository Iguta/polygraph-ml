from __future__ import annotations

import json
from pathlib import Path

from polygraphml.api.main import app


def main() -> None:
    destination = Path("packages/contracts/openapi.json")
    destination.parent.mkdir(parents=True, exist_ok=True)
    rendered = json.dumps(app.openapi(), indent=2, sort_keys=True) + "\n"
    if destination.exists() and destination.read_text() == rendered:
        return
    destination.write_text(rendered)


if __name__ == "__main__":
    main()
