"""File the demo issues on a forge.

    python scripts/seed.py --forge github --repo OWNER/NAME [--base-url URL] [--dry-run] [FILE ...]

Each issue is a Markdown file, `demo/issues/NN-slug.md` by default, whose
front matter gives its title and labels and whose rest is the issue's body:

    ---
    title: A total of an hour or more prints its minutes twice
    labels: [bug]
    ---
    ## Problem / why
    ...

The token comes from the environment (GITHUB_TOKEN, else GH_TOKEN) and is
sent only to the forge named. `--base-url` is the forge's API address: the
default is github.com's; a GitHub Enterprise Server is `https://HOST/api/v3`.
An issue whose title the repository already has, open or closed, is skipped,
so a second run files nothing twice. Labels missing from the repository are
created first, and an issue the forge filed without every label asked for is
an error: the forge drops labels silently for a token without push access.

Standard library only, so it runs before anything is installed. `--forge` is
an argument from the start: another forge is a new backend beside GitHub's.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ISSUES = ROOT / "demo" / "issues"
ISSUE_FILES = "[0-9][0-9]-*.md"
TOKEN_VARIABLES = ("GITHUB_TOKEN", "GH_TOKEN")


class SeedError(Exception):
    """Something that stops the seeding, said in one line."""


@dataclass(frozen=True)
class Issue:
    source: Path
    title: str
    labels: tuple[str, ...]
    body: str


def parse_issue(path: Path) -> Issue:
    """Read one issue file: front matter with `title` and `labels`, then the body.

    The front matter is a strict subset of YAML: `title: text` and
    `labels: [a, b]`, each once, nothing else.
    """
    text = path.read_text(encoding="utf-8").replace("\r\n", "\n")
    match = re.match(r"---\n(?P<front>.*?)\n---\n(?P<body>.*)\Z", text, re.DOTALL)
    if match is None:
        raise SeedError(f"{path.name}: no front matter between `---` lines")
    fields: dict[str, str] = {}
    for line in match["front"].splitlines():
        key, sep, value = line.partition(":")
        key = key.strip()
        if not sep or key not in ("title", "labels") or key in fields:
            raise SeedError(f"{path.name}: front matter line not understood: {line!r}")
        fields[key] = value.strip()
    if not fields.get("title"):
        raise SeedError(f"{path.name}: front matter has no title")
    if "labels" not in fields:
        raise SeedError(f"{path.name}: front matter has no labels (write `labels: []` for none)")
    labels = fields["labels"]
    if not (labels.startswith("[") and labels.endswith("]")):
        raise SeedError(f"{path.name}: labels are a list in brackets, got {labels!r}")
    names = tuple(_unquote(name) for name in labels[1:-1].split(",") if name.strip())
    body = match["body"].lstrip("\n")
    if not body.strip():
        raise SeedError(f"{path.name}: the issue has no body")
    return Issue(source=path, title=_unquote(fields["title"]), labels=names, body=body)


def _unquote(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
        return value[1:-1]
    return value


class GitHub:
    """GitHub's REST API, on github.com or a GitHub Enterprise Server."""

    def __init__(self, repo: str, token: str, base_url: str = "https://api.github.com"):
        if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repo):
            raise SeedError(f"--repo is OWNER/NAME, got {repo!r}")
        self.repo = repo
        self.token = token
        self.base_url = base_url.rstrip("/")

    def _call(self, method: str, path: str, payload: dict | None = None):
        data = None if payload is None else json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(
            f"{self.base_url}/repos/{self.repo}{path}",
            data=data,
            method=method,
            headers={
                "Accept": "application/vnd.github+json",
                "Authorization": f"Bearer {self.token}",
                "Content-Type": "application/json",
                "User-Agent": "durasum-demo-seed",
                "X-GitHub-Api-Version": "2022-11-28",
            },
        )
        with urllib.request.urlopen(request, timeout=30) as response:
            text = response.read().decode("utf-8")
        return json.loads(text) if text else None

    def existing_titles(self) -> set[str]:
        """Every issue title the repository has, open or closed."""
        titles: set[str] = set()
        page = 1
        while True:
            batch = self._call("GET", f"/issues?state=all&per_page=100&page={page}")
            titles.update(item["title"] for item in batch if "pull_request" not in item)
            if len(batch) < 100:
                return titles
            page += 1

    def ensure_label(self, name: str) -> bool:
        """Create the label unless the repository has it; True when created."""
        try:
            self._call("GET", f"/labels/{urllib.parse.quote(name, safe='')}")
            return False
        except urllib.error.HTTPError as exc:
            if exc.code != 404:
                raise
        self._call("POST", "/labels", {"name": name, "color": "ededed"})
        return True

    def file_issue(self, issue: Issue) -> tuple[int, str]:
        """File the issue; its number and address."""
        created = self._call(
            "POST",
            "/issues",
            {"title": issue.title, "body": issue.body, "labels": list(issue.labels)},
        )
        dropped = set(issue.labels) - {label["name"] for label in created.get("labels", [])}
        if dropped:
            raise SeedError(
                f"#{created['number']} was filed without {', '.join(sorted(dropped))}: "
                "the token cannot set labels on this repository"
            )
        return created["number"], created["html_url"]


FORGES = {"github": GitHub}


def _arguments(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="File the demo issues on a forge.")
    parser.add_argument("--forge", required=True, choices=sorted(FORGES))
    parser.add_argument("--repo", required=True, help="OWNER/NAME of the repository to seed")
    parser.add_argument("--base-url", default="https://api.github.com", help="the forge's API")
    parser.add_argument("--dry-run", action="store_true", help="say what would be filed")
    parser.add_argument("files", nargs="*", type=Path, help=f"default: demo/issues/{ISSUE_FILES}")
    return parser.parse_args(argv)


def _manifest_repo() -> str | None:
    manifest = ROOT / ".agent" / "manifest.yaml"
    if not manifest.is_file():
        return None
    match = re.search(r"^repo:\s*(\S+)", manifest.read_text(encoding="utf-8"), re.MULTILINE)
    return match.group(1) if match else None


def main(argv: list[str] | None = None) -> int:
    args = _arguments(argv)
    try:
        files = args.files or sorted(ISSUES.glob(ISSUE_FILES))
        if not files:
            raise SeedError(f"no issue files in {ISSUES}")
        issues = [parse_issue(path) for path in files]
        manifest_repo = _manifest_repo()
        if manifest_repo is not None and manifest_repo != args.repo:
            print(
                f"note: .agent/manifest.yaml names {manifest_repo}, not {args.repo}; "
                "the engine works on the repository its manifest names",
                file=sys.stderr,
            )
        if args.dry_run:
            for issue in issues:
                labels = ", ".join(issue.labels) or "no labels"
                print(f"would file  {issue.title}  ({labels})  from {issue.source.name}")
            return 0
        token = next((os.environ[name] for name in TOKEN_VARIABLES if os.environ.get(name)), "")
        if not token:
            raise SeedError(f"no token: set {' or '.join(TOKEN_VARIABLES)}")
        forge = FORGES[args.forge](args.repo, token, args.base_url)
        existing = forge.existing_titles()
        for name in sorted({label for issue in issues for label in issue.labels}):
            if forge.ensure_label(name):
                print(f"created label  {name}")
        for issue in issues:
            if issue.title in existing:
                print(f"exists     {issue.title}")
                continue
            number, url = forge.file_issue(issue)
            print(f"filed #{number}  {issue.title}  {url}")
    except SeedError as exc:
        print(f"seed: {exc}", file=sys.stderr)
        return 1
    except urllib.error.HTTPError as exc:
        print(
            f"seed: the forge answered {exc.code} {exc.reason} for {exc.filename}", file=sys.stderr
        )
        return 1
    except urllib.error.URLError as exc:
        print(f"seed: the forge could not be reached: {exc.reason}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
