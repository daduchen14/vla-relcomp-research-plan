#!/usr/bin/env python3
"""Verify one downloaded H2 file by exact size and SHA-256."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--path", type=Path, required=True)
    parser.add_argument("--bytes", type=int, required=True)
    parser.add_argument("--sha256", required=True)
    args = parser.parse_args()
    try:
        root = args.root.expanduser().resolve()
        path = args.path.expanduser().resolve()
        if root in {Path("/"), Path.home().resolve()} or len(root.parts) < 3:
            raise ValueError(f"unsafe verification root: {root}")
        if root != path and root not in path.parents:
            raise ValueError("file escapes verification root")
        if not path.is_file() or path.is_symlink():
            raise ValueError("path must be an existing regular non-symlink file")
        if args.bytes < 0 or len(args.sha256) != 64 or any(character not in "0123456789abcdef" for character in args.sha256):
            raise ValueError("invalid expected size or lowercase SHA-256")
        size = path.stat().st_size
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if (size, digest) != (args.bytes, args.sha256):
            raise ValueError(f"file lock mismatch: expected {args.bytes}/{args.sha256}, observed {size}/{digest}")
        payload = {"status": "passed", "path": str(path), "bytes": size, "sha256": digest}
    except ValueError as exc:
        print(json.dumps({"status": "rejected", "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
