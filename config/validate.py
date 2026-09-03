"""Side-effect-free command-line validator for the candidate configuration."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .loader import load_config


def main() -> int:
    parser = argparse.ArgumentParser(description="Valider la configuration Skull sans initialiser le matériel")
    parser.add_argument("path", type=Path)
    args = parser.parse_args()
    config, provenance = load_config(args.path, environ={})
    print(json.dumps(config.redacted_dict(include_provenance=provenance), ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
