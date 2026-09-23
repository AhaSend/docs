#!/usr/bin/env python3
"""Prove each lint rule fails on a disposable copy; also run a real broken-link check."""
import argparse
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

from docs_lint import BANNED_STRINGS, split_page
import yaml


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cli-reference", type=Path, required=True)
    parser.add_argument("--mint", required=True)
    parser.add_argument("--results", type=Path)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    results = []
    with tempfile.TemporaryDirectory(prefix="ahasend-docs-tests-") as directory:
        copy = Path(directory)
        for source in root.rglob("*"):
            relative = source.relative_to(root)
            if any(part in (".git", ".venv", "node_modules", "__pycache__", "plans") for part in relative.parts):
                continue
            if source.is_file() and source.suffix in (".mdx", ".json", ".yaml", ".svg", ".png"):
                target = copy / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, target)
        command = [sys.executable, str(root / "scripts/docs_lint.py"), "--root", str(copy),
                   "--cli-reference", str(args.cli_reference.resolve())]

        def run(name, expected=None):
            result = subprocess.run(command, text=True, capture_output=True)
            output = result.stdout + result.stderr
            passed = (result.returncode == 0 if expected is None else
                      result.returncode != 0 and f": {expected}:" in output)
            results.append({"test": name, "expected_rule": expected, "passed": passed,
                            "exit_code": result.returncode, "output": output})
            print(f"{'PASS' if passed else 'FAIL'} {name}")
            if not passed:
                raise AssertionError(output)

        page = copy / "index.mdx"
        original = page.read_text()
        metadata, body, _ = split_page(original)

        def frontmatter(name, field, value, rule):
            changed = dict(metadata)
            if value is None:
                del changed[field]
            else:
                changed[field] = value
            page.write_text("---\n" + yaml.safe_dump(changed, sort_keys=False) + "---\n" + body)
            run(name, rule)
            page.write_text(original)

        def append(name, addition, rule, target=page):
            previous = target.read_text()
            target.write_text(previous + "\n" + addition + "\n")
            run(name, rule)
            target.write_text(previous)

        run("unchanged copy")
        frontmatter("missing title", "title", None, "frontmatter")
        frontmatter("missing description", "description", None, "frontmatter")
        frontmatter("title over 50 characters", "title", "T" * 51, "title-length")
        other, _, _ = split_page((copy / "quickstart.mdx").read_text())
        frontmatter("duplicate title", "title", other["title"], "title-duplicate")
        frontmatter("short description", "description", "Too short.", "description-length")
        frontmatter("long description", "description", "D" * 161, "description-length")
        frontmatter("duplicate description", "description", other["description"], "description-duplicate")
        page.write_text(body)
        run("missing frontmatter", "frontmatter")
        page.write_text(original)
        append("body H1", "# Another title", "body-h1")
        append("HTML body H1", "<h1>Another title</h1>", "body-h1")
        append("heading skips a level", "## Section\n\n#### Skipped H3", "heading-level")
        append("bold heading", "## **Bold heading**", "heading-style")
        append("emoji heading", "## 🚀 Heading", "heading-style")
        append("untagged backtick fence", "```\nplain text\n```", "fence-language")
        append("untagged tilde fence", "~~~\nplain text\n~~~", "fence-language")
        orphan = copy / "orphan.mdx"
        orphan.write_text(original)
        run("page missing from navigation", "navigation")
        orphan.unlink()
        for banned in BANNED_STRINGS:
            append("banned " + banned, banned, "banned-string")
        cli = copy / "cli/commands/messages.mdx"
        append("released sub-account API key alias", "```bash\nahasend subaccounts apikeys list SUBACCOUNT_ID --limit 1\n```", None, cli)
        append("unknown flag through released alias", "```bash\nahasend subaccounts apikeys list SUBACCOUNT_ID --made-up-flag\n```", "cli-flag", cli)
        append("unknown root CLI command", "```bash\nahasend nonexistent\n```", "cli-command", cli)
        append("unknown CLI subcommand", "```bash\nahasend messages nonexistent\n```", "cli-command", cli)
        append("unknown CLI flag", "```bash\nahasend messages send --made-up-flag value\n```", "cli-flag", cli)
        append("unknown flag after continuation", "```bash\nahasend messages send \\\n  --made-up-flag value\n```", "cli-flag", cli)
        append("unknown command in substitution", "```bash\nRESULT=$(ahasend messages nonexistent)\n```", "cli-command", cli)
        append("unknown flag in function", "```bash\nnotify() { ahasend messages send --made-up-flag; }\n```", "cli-flag", cli)
        append("unknown flag in YAML run", "```yaml\nsteps:\n  - run: |\n      ahasend messages send --made-up-flag\n```", "cli-flag", cli)
        append("unknown Contacts command", "```bash\nahasend contacts nonexistent\n```", "cli-command", cli)
        append("unknown Contacts flag", "```bash\nahasend contacts list --made-up-flag\n```", "cli-flag", cli)
        append("valid shell comments, strings and substitutions", """```bash
# A shell comment is not a body H1. ahasend nonexistent is only a comment.
RESULT=$(ahasend messages list --limit 1)
send_test() {
  ahasend messages send \
    --subject '--a-string-value' --text 'ahasend nonexistent' --sandbox
}
cat <<'EOF'
ahasend nonexistent --made-up-flag
EOF
```""", None, cli)
        # The exact user exception is checked on a copy, never on the real page.
        delphi = copy / "smtp/delphi.mdx"
        delphi.write_text("# Existing historical page\n```\ncreateTransporter\n```\n")
        run("Delphi remains the only explicit page exception")
        shutil.copy2(root / "smtp/delphi.mdx", delphi)
        broken_path = "__missing_docs_check_fixture__"
        page.write_text(original + f"\n[Broken test link](/{broken_path})\n")
        result = subprocess.run([args.mint, "broken-links"], cwd=copy,
                                text=True, capture_output=True)
        output = result.stdout + result.stderr
        passed = result.returncode != 0 and broken_path in output
        results.append({"test": "Mintlify broken link", "passed": passed,
                        "exit_code": result.returncode, "output": output})
        print(f"{'PASS' if passed else 'FAIL'} Mintlify broken link")
        if not passed:
            raise AssertionError("mint broken-links must fail and name the missing target:\n" + output)
    if args.results:
        args.results.write_text(json.dumps(results, indent=2) + "\n")
    print(f"All {len(results)} checks passed; original source was not changed")


if __name__ == "__main__":
    main()
