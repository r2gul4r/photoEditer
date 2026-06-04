from __future__ import annotations

import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = PROJECT_ROOT / "apps" / "backend"
sys.path.insert(0, str(BACKEND_ROOT))

from app.services.lut_style_index import save_lut_style_index  # noqa: E402


def main() -> int:
    index = save_lut_style_index()
    print(f"profileCount={index['profileCount']}")
    print(f"groupCount={index['groupCount']}")
    print(f"uniqueHashCount={index['duplicates']['uniqueHashCount']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
