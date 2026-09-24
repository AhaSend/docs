#!/usr/bin/env python3
"""Check published MDX, navigation, and CLI example names without executing examples."""
import argparse
from dataclasses import dataclass
import json
from pathlib import Path
import re
import sys
import unicodedata

from tree_sitter import Language, Parser
import tree_sitter_bash
import yaml

# User-directed exception: preserve this verified historical page byte for byte.
# No other SMTP or MDX page is exempt. Snippets are reusable content, not pages.
EXCLUDED_PAGES = {"smtp/delphi.mdx"}
BANNED_STRINGS = (
    "createTransporter", "ahasend-message-retention", "ahasend-message-data-retention",
    "POST /v2/send", "All code examples in this documentation are tested",
)
FENCE = re.compile(r"^\s*(`{3,}|~{3,})(.*)$")
HEADING = re.compile(r"^\s*(#{1,6})\s+(.+?)\s*#*\s*$")


@dataclass
class Finding:
    rule: str
    path: str
    line: int
    message: str

    def __str__(self):
        return f"{self.path}:{self.line}: {self.rule}: {self.message}"


def split_page(text):
    match = re.match(r"^---\r?\n(.*?)\r?\n---(?:\r?\n|$)(.*)", text, re.S)
    if not match:
        return {}, text, 1
    metadata = yaml.safe_load(match[1]) or {}
    if not isinstance(metadata, dict):
        raise ValueError("Frontmatter must be a YAML mapping")
    return metadata, match[2], text[:match.start(2)].count("\n") + 1


def body_parts(body, first_line=1):
    """Yield prose lines and entire fences, including indented MDX component fences."""
    opening, content, language, start = None, [], "", first_line
    for number, line in enumerate(body.splitlines(), first_line):
        match = FENCE.match(line)
        if opening:
            if match and match[1][0] == opening[0] and len(match[1]) >= len(opening) and not match[2].strip():
                yield "fence", start, language, "\n".join(content)
                opening, content = None, []
            else:
                content.append(line)
        elif match:
            opening, start = match[1], number
            language = match[2].strip().split(maxsplit=1)[0] if match[2].strip() else ""
        else:
            yield "prose", number, "", line
    if opening:
        yield "unclosed-fence", start, language, "\n".join(content)


def navigation_pages(value):
    pages = set()
    if isinstance(value, dict):
        for key, child in value.items():
            if key == "pages" and isinstance(child, list):
                pages.update(item.removesuffix(".mdx").strip("/") for item in child if isinstance(item, str))
            pages.update(navigation_pages(child))
    elif isinstance(value, list):
        for child in value:
            pages.update(navigation_pages(child))
    return pages


def shell_commands(source):
    """Use the shell syntax tree, including substitutions, functions and pipelines."""
    # GitHub expressions are filled before the shell runs; they are opaque values here.
    source = re.sub(r"\$\{\{.*?\}\}", "GITHUB_EXPRESSION", source, flags=re.S)
    # Usage placeholders are values, not shell input/output redirections.
    source = re.sub(r"(?<!\S)<([a-z][\w-]*)>(?=\s|$)", r"PLACEHOLDER_\1", source)
    tree = Parser(Language(tree_sitter_bash.language())).parse(source.encode())
    if tree.root_node.has_error:
        raise ValueError("Invalid shell syntax; cannot reliably check CLI names")

    def visit(node):
        if node.type == "command":
            name = node.child_by_field_name("name")
            if name and name.text.decode() in ("ahasend", "ahasend.exe", "./ahasend", "./ahasend.exe"):
                words = []
                for part in node.named_children:
                    if part == name or part.type in ("variable_assignment", "file_redirect", "heredoc_redirect"):
                        continue
                    # Keep an argument containing spaces or substitutions as one value.
                    value = part.text.decode().replace("\\\n", "")
                    if value.startswith(("'", '"')) and value.endswith(value[0]):
                        value = value[1:-1]
                    words.append(value)
                yield node.start_point.row, words
        for child in node.named_children:
            yield from visit(child)

    yield from visit(tree.root_node)


def yaml_runs(value):
    if isinstance(value, dict):
        for key, child in value.items():
            if key == "run" and isinstance(child, str):
                yield child
            else:
                yield from yaml_runs(child)
    elif isinstance(value, list):
        for child in value:
            yield from yaml_runs(child)


def cli_problems(words, commands):
    path, used_flags = [], []
    index = 0
    while index < len(words):
        word = words[index]
        current = commands[" ".join(path)]
        if word == "--":
            break
        if word.startswith("-"):
            flag = word.split("=", 1)[0]
            used_flags.append(flag)
            takes_value = current["flags"].get(flag)
            if takes_value is None:
                # Cobra accepts local flags before the subcommand too.
                takes_value = any(info["flags"].get(flag) for key, info in commands.items()
                                  if key.startswith(" ".join(path)))
            if takes_value and "=" not in word:
                index += 1
        elif word in ("[command]", "[subcommand]", "[flags]"):
            pass  # Literal usage notation, not a command or flag name.
        elif word in current["children"]:
            path.append(word)
        elif current["children"]:
            yield "cli-command", f"Unknown command: ahasend {' '.join([*path, word])}"
            return
        index += 1
    current = commands[" ".join(path)]
    for flag in used_flags:
        if flag not in current["flags"]:
            yield "cli-flag", f"Unknown flag {flag} for ahasend {' '.join(path)}"


def load_commands(release, contacts):
    snapshot = json.loads(release.read_text())
    if snapshot["source"].get("version") != "v0.2.0":
        raise ValueError("CLI command source must be the pinned v0.2.0 release")
    commands = snapshot["commands"]
    exception = json.loads(contacts.read_text())
    if exception["source"].get("commit") != "7a47882b56f766ce0cf9a82c447d9319664d5ef4":
        raise ValueError("Unexpected Contacts exception source")
    for path, info in exception["commands"].items():
        if path != "contacts" and not path.startswith("contacts "):
            raise ValueError("Development exception may only contain Contacts commands")
        if path in commands:
            raise ValueError("Contacts is in the release: remove the development exception")
        commands[path] = info
    commands[""]["children"].append("contacts")
    return commands


def lint(root, commands):
    findings, titles, descriptions = [], {}, {}
    config = json.loads((root / "docs.json").read_text())
    navigated = navigation_pages(config["navigation"])

    def add(rule, path, line, message):
        findings.append(Finding(rule, path, line, message))

    for file in sorted(root.rglob("*.mdx")):
        relative = file.relative_to(root)
        if any(part.startswith(".") or part == "node_modules" for part in relative.parts):
            continue
        path = relative.as_posix()
        if path in EXCLUDED_PAGES:
            continue
        snippet = relative.parts[0] == "snippets"
        text = file.read_text()
        try:
            metadata, body, first_line = split_page(text)
        except (ValueError, yaml.YAMLError) as error:
            add("frontmatter", path, 1, str(error))
            continue
        if not snippet:
            for name, seen, minimum, maximum in (("title", titles, 1, 50), ("description", descriptions, 120, 160)):
                value = metadata.get(name)
                if not isinstance(value, str) or not value.strip():
                    add("frontmatter", path, 1, f"Missing {name}")
                    continue
                if not minimum <= len(value) <= maximum:
                    add(name + "-length", path, 1, f"{name} has {len(value)} characters; expected {minimum}–{maximum}")
                normalized = value.casefold().strip()
                if normalized in seen:
                    add(name + "-duplicate", path, 1, f"Same {name} as {seen[normalized]}")
                seen[normalized] = path
            if relative.with_suffix("").as_posix() not in navigated:
                add("navigation", path, 1, "Page is missing from docs.json navigation")
        for banned in BANNED_STRINGS:
            for match in re.finditer(re.escape(banned), text, re.I):
                add("banned-string", path, text[:match.start()].count("\n") + 1, f"Old example string: {banned}")
        previous_heading = 1
        for kind, number, language, content in body_parts(body, first_line):
            if kind != "prose":
                if not language:
                    add("fence-language", path, number, "Code fence needs a language tag")
                if kind == "unclosed-fence":
                    add("fence-close", path, number, "Code fence is not closed")
            else:
                heading = HEADING.match(content)
                html_heading = re.search(r"<h([1-6])(?:\s[^>]*)?>(.*?)</h\1>", content, re.I)
                if heading or html_heading:
                    level = len(heading[1]) if heading else int(html_heading[1])
                    label = heading[2] if heading else html_heading[2]
                    if level == 1:
                        add("body-h1", path, number, "The page title is the only H1")
                    elif level > previous_heading + 1:
                        add("heading-level", path, number, f"Heading skips from H{previous_heading} to H{level}")
                    previous_heading = level
                    if "**" in label or "__" in label or any(unicodedata.category(c) == "So" for c in label):
                        add("heading-style", path, number, "Headings cannot contain bold markup or emoji")
            if relative.parts[0] != "cli":
                continue
            sources = []
            if kind == "prose":
                sources = re.findall(r"`(ahasend(?: [^`]+)?)`", content)
            elif language in ("bash", "sh", "shell"):
                sources = [content]
            elif language in ("yaml", "yml"):
                try:
                    sources = list(yaml_runs(yaml.safe_load(content)))
                except yaml.YAMLError as error:
                    add("cli-parse", path, number, str(error))
            elif language in ("text", "powershell", "batch", "console"):
                # Check literal invocations, not output trees, download paths or prose.
                joined = re.sub(r"[`^]\\?\n\s*", " ", content)
                sources = [line.strip() for line in joined.splitlines()
                           if re.match(r"^\s*(?:\./)?ahasend(?:\.exe)?(?:\s|$)", line)]
            for source in sources:
                if not re.search(r"\bahasend\b", source):
                    continue
                try:
                    for offset, words in shell_commands(source):
                        for rule, message in cli_problems(words, commands):
                            add(rule, path, number + offset, message)
                except ValueError as error:
                    add("cli-parse", path, number, f"Cannot check CLI example: {error}")
    return findings


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--cli-reference", type=Path, required=True)
    args = parser.parse_args()
    commands = load_commands(args.cli_reference, Path(__file__).parent / "contacts-cli-exception.json")
    findings = lint(args.root.resolve(), commands)
    for finding in findings:
        print(finding)
    if findings:
        print(f"{len(findings)} documentation check(s) failed")
        return 1
    print("Documentation checks passed (Delphi excluded; CLI names checked, examples not executed)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
