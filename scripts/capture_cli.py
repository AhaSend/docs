#!/usr/bin/env python3
"""Collect names from real Cobra help without running examples or reading profiles."""
import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile


def capture(binary):
    commands = {}
    # Isolated HOME prevents any access to a contributor's real CLI profile.
    with tempfile.TemporaryDirectory(prefix="ahasend-help-") as home:
        env = dict(os.environ, HOME=home, XDG_CONFIG_HOME=home, NO_COLOR="1")

        def visit(path):
            result = subprocess.run([binary, *path, "--help"], env=env,
                                    text=True, capture_output=True, check=True)
            flags, children, aliases, section = {}, [], [], None
            for line in result.stdout.splitlines():
                if line and not line.startswith(" "):
                    section = line
                if section == "Available Commands:":
                    match = re.match(r"^  ([\w-]+)\s+", line)
                    if match:
                        children.append(match[1])
                if section == "Aliases:" and line.startswith(" "):
                    aliases.extend(name.strip() for name in line.split(",")
                                   if name.strip() and (not path or name.strip() != path[-1]))
                if section in ("Flags:", "Global Flags:"):
                    match = re.match(r"^\s+(?:-([\w]),\s+)?(--[\w-]+)(.*?)\s{2,}\S", line)
                    if match:
                        takes_value = bool(match[3].strip())
                        flags[match[2]] = takes_value
                        if match[1]:
                            flags["-" + match[1]] = takes_value
            commands[" ".join(path)] = {"flags": flags, "children": children}
            for child in tuple(children):
                child_path = (*path, child)
                child_aliases = visit(child_path)
                canonical = " ".join(child_path)
                descendants = [(key, value) for key, value in commands.items()
                               if key == canonical or key.startswith(canonical + " ")]
                for alias in child_aliases:
                    children.append(alias)
                    alias_path = " ".join((*path, alias))
                    for key, value in descendants:
                        commands[alias_path + key[len(canonical):]] = value
            return aliases

        visit(())
    return commands


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--binary", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    binary = str(Path(args.binary).resolve())
    build = subprocess.run(["go", "version", "-m", binary], capture_output=True,
                           text=True, check=True).stdout
    module = re.search(r"\bmod\s+github.com/AhaSend/ahasend-cli\s+(\S+)\s+(\S+)", build)
    if not module or module[1] != "v0.2.0" or module[2] != "h1:Kj87jOuqApnhYuisUuCUvoDcDlYW/aLIrHsjsB/a7ds=":
        raise SystemExit("Expected go install github.com/AhaSend/ahasend-cli@v0.2.0 with the recorded module checksum")
    source = {"module": "github.com/AhaSend/ahasend-cli", "version": module[1], "checksum": module[2]}
    commands = capture(binary)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps({"source": source, "commands": commands}, indent=2) + "\n")
    print(f"Collected {len(commands)} command paths from {binary}; names only, no examples executed")


if __name__ == "__main__":
    main()
