#!/usr/bin/env python3
"""Validate docs.json against the public Mintlify schema supplied by the caller."""
import argparse
import hashlib
import json
from pathlib import Path

import jsonschema

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--schema", type=Path, required=True)
parser.add_argument("--config", type=Path, default=Path("docs.json"))
args = parser.parse_args()
schema_bytes = args.schema.read_bytes()
jsonschema.validate(json.loads(args.config.read_text()), json.loads(schema_bytes),
                    format_checker=jsonschema.FormatChecker())
print(f"{args.config} passes the public Mintlify schema (SHA-256 {hashlib.sha256(schema_bytes).hexdigest()})")
