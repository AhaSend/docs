# AhaSend Documentation

Documentation site for AhaSend, a developer-first transactional email service. This repository contains the Mintlify docs for AhaSend's REST APIs, SMTP relay, CLI, webhooks, domains, security features, and integration guides.

## Check a change

Every pull request runs `.github/workflows/docs-checks.yml`. Run the same checks locally with Python 3.12+, Node.js 22.17.1, and Go 1.26.1+:

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -r scripts/requirements.txt
npm install --global mint@4.2.315
go install github.com/AhaSend/ahasend-cli@v0.2.0
DOCS_CHECK_DIR=$(mktemp -d)
python scripts/capture_cli.py --binary "$(go env GOPATH)/bin/ahasend-cli" --output "$DOCS_CHECK_DIR/ahasend-cli.json"
python scripts/docs_lint.py --cli-reference "$DOCS_CHECK_DIR/ahasend-cli.json"
curl --fail --location --user-agent 'Mozilla/5.0' https://mintlify.com/docs.json --output "$DOCS_CHECK_DIR/mintlify-schema.json"
python scripts/validate_schema.py --schema "$DOCS_CHECK_DIR/mintlify-schema.json"
mint validate
mint broken-links
python scripts/test_docs_checks.py --cli-reference "$DOCS_CHECK_DIR/ahasend-cli.json" --mint mint
```

The checks cover page metadata, duplicate titles and descriptions, navigation, headings, code fence languages, known broken example strings, and CLI command and flag names. The test script creates disposable source copies and proves each rule rejects a bad change. It never changes the original pages.

`smtp/delphi.mdx` is the sole page exception, at the owner's request. Preserve it byte for byte. Files in `snippets/` are shared content and need no page metadata or navigation entry; their headings and code fences are still checked.

The CLI check reads real help from release **v0.2.0**, installed from its Go module with a checked module checksum. Help runs with an empty temporary home directory. It checks names only: it does not run examples, contact the API, or validate argument values. Changed executable examples still need their separate execution checks.

Contacts is a narrow temporary exception because its API and CLI release checks are deferred. `scripts/contacts-cli-exception.json` contains only Contacts names from development commit `7a47882b56f766ce0cf9a82c447d9319664d5ef4`. It records the supplied binary's SHA-256 and its `vcs.modified=true` build status; the Contacts source at that commit was checked and has no local changes. Unknown Contacts commands and flags still fail. To inspect or regenerate that list from the same supplied build:

```bash
python scripts/capture_cli.py --binary /path/to/development/ahasend --contacts-only --output scripts/contacts-cli-exception.json
```

When a compatible release ships, update the pinned version and module checksum in the collector, workflow and README, remove the Contacts exception from `load_commands`, and delete its JSON file. Run the deferred Contacts API and CLI execution checks before publishing those pages.

Every spec-driven page has a short frontmatter description and a full description in the MDX body. When upstream specs change, compare each changed operation or event description with its body copy and update it by hand. Keep access rules and restrictions. The current `suppression.created` body uses the corrected cause-based durations from the webhook owner page; its upstream spec correction is tracked in `plans/seo-audit/STAGE_2_SPEC_HANDOFF.md`.
