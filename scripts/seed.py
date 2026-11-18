"""File the demo issues on a forge.

    python scripts/seed.py --forge github --repo OWNER/NAME [--base-url URL] [--dry-run] [FILE ...]
    python scripts/seed.py --forge gitlab --repo GROUP/NAME --base-url URL [--dry-run] [FILE ...]

Each issue is a Markdown file, `demo/issues/NN-slug.md` by default, whose
front matter gives its title and labels and whose rest is the issue's body:

    ---
    title: A total of an hour or more prints the hour again in its minutes, as 1h 90m
    labels: [bug]
    ---
    ## Problem / why
    ...

The token comes from the environment (GITHUB_TOKEN, else GH_TOKEN) and is
sent only to the forge named. `--base-url` is the forge's API address: the
default is github.com's; a GitHub Enterprise Server is `https://HOST/api/v3`.

For `--forge gitlab` the token comes from GITLAB_TOKEN, and `--base-url` is
required: the instance's web address or its API address (`.../api/v4`), path
prefix included (`https://HOST/gitlab`). The project may be nested in groups
(`group/subgroup/name`); it is URL-encoded once in the API's paths. A CA
bundle for an instance whose certificate a test CA signed is named in
GITLAB_CA_BUNDLE (optional). The demo issues make no blocked-by link on
GitLab: a Community Edition instance refuses one, and each issue carries its
blockers as a `Blocked by #N` line in its body, which both forges read.
Nothing is filed on a repository other than the one `.agent/manifest.yaml`
names, since the engine works on that one.

Each filed body ends with a hidden marker naming its file
(`<!-- demo-seed: NN-slug.md -->`). An issue the repository already has,
open or closed, found by that marker or, for one filed before the marker, by
its title, is not filed again, so a second run files nothing twice; the
labels it lacks are added to it. The forge's listing can trail a filing by
seconds, so after filing the script waits until the listing shows every issue
it filed, and fails, saying so, when it does not: a run that returned sooner
could be followed by a second that filed both again.

Labels missing from the repository are created first, and an
issue the forge left without a label asked for is an error: the forge drops
labels silently for a token without push access. Label names are compared
without regard to case, as the forge compares them.

Standard library only, so it runs before anything is installed. `--forge` is
an argument from the start: another forge is a new backend beside these.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import ssl
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MANIFEST = ROOT / ".agent" / "manifest.yaml"
ISSUES = ROOT / "demo" / "issues"
ISSUE_FILES = "[0-9][0-9]-*.md"
MARKER = "<!-- demo-seed: {name} -->"
MARKER_PATTERN = re.compile(r"<!-- demo-seed: (?P<name>[^\s>]+) -->")
# How long, and how often, the listing is read after a filing for it to show
# what was filed; the tests shorten both.
SETTLE_SECONDS = 60.0
SETTLE_INTERVAL = 2.0
TOKEN_VARIABLES = ("GITHUB_TOKEN", "GH_TOKEN")
GITLAB_TOKEN_VARIABLES = ("GITLAB_TOKEN",)
GITLAB_CA_VARIABLE = "GITLAB_CA_BUNDLE"


class SeedError(Exception):
    """Something that stops the seeding, said in one line."""


class _RefuseRedirects(urllib.request.HTTPRedirectHandler):
    """urllib follows a redirect and sends its headers on, the token among
    them; a forge that redirects is given the wrong address, so it is refused."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise SeedError("the forge redirected: give its https address")


def _open(request: urllib.request.Request, context: ssl.SSLContext | None = None):
    """Open the request with an opener that never follows a redirect."""
    opener = urllib.request.build_opener(
        _RefuseRedirects, urllib.request.HTTPSHandler(context=context)
    )
    try:
        return opener.open(request, timeout=30)
    except urllib.error.HTTPError:
        raise
    except urllib.error.URLError as exc:
        where = urllib.parse.urlsplit(request.full_url)
        raise SeedError(
            f"the forge at {where.scheme}://{where.netloc} could not be reached: {exc.reason}"
        ) from None


@dataclass(frozen=True)
class Issue:
    source: Path
    title: str
    labels: tuple[str, ...]
    body: str

    @property
    def marker(self) -> str:
        return MARKER.format(name=self.source.name)

    @property
    def filed_body(self) -> str:
        """The body as it is filed: the file's, then the hidden marker."""
        return f"{self.body.rstrip()}\n\n{self.marker}\n"


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


@dataclass
class Existing:
    """The issues a repository already has."""

    by_title: dict[str, dict] = field(default_factory=dict)
    by_file: dict[str, dict] = field(default_factory=dict)

    def of(self, issue: Issue) -> dict | None:
        """The issue filed for this file: by its marker, else by its title."""
        return self.by_file.get(issue.source.name) or self.by_title.get(issue.title)


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
        with _open(request) as response:
            text = response.read().decode("utf-8")
        try:
            return json.loads(text) if text else None
        except json.JSONDecodeError:
            raise SeedError(f"the forge's answer to {method} {path} is not JSON") from None

    def existing_issues(self) -> Existing:
        """Every issue the repository has, open or closed, by title and by
        the file its marker names; pull requests, which the forge lists among
        the issues, are left out."""
        found = Existing()
        page = 1
        while True:
            batch = self._call("GET", f"/issues?state=all&per_page=100&page={page}")
            for item in batch:
                if "pull_request" in item:
                    continue
                found.by_title.setdefault(item["title"], item)
                marked = MARKER_PATTERN.search(item.get("body") or "")
                if marked:
                    found.by_file.setdefault(marked["name"], item)
            if len(batch) < 100:
                return found
            page += 1

    def settle(self, issues: list[Issue], numbers: dict[str, int]) -> None:
        """Wait until the listing shows each issue just filed (its file name
        to its number); SeedError when it does not within SETTLE_SECONDS."""
        deadline = time.monotonic() + SETTLE_SECONDS
        while True:
            listed = self.existing_issues()
            missing = [
                name
                for name, number in numbers.items()
                if (listed.by_file.get(name) or {}).get("number") != number
            ]
            if not missing:
                return
            if time.monotonic() >= deadline:
                raise SeedError(
                    f"the forge's listing does not show {', '.join(missing)} after "
                    f"{SETTLE_SECONDS:g} seconds: wait before running this again, or the "
                    "issues are filed twice"
                )
            time.sleep(SETTLE_INTERVAL)

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
            {"title": issue.title, "body": issue.filed_body, "labels": list(issue.labels)},
        )
        _require_labels(issue, created.get("labels", []), f"#{created['number']} was filed")
        return created["number"], created["html_url"]

    def label_issue(self, issue: Issue, existing: dict) -> bool:
        """Add to an issue filed earlier the labels it lacks; True when it lacked any."""
        missing = _missing(issue.labels, existing.get("labels", []))
        if not missing:
            return False
        number = existing["number"]
        labels = self._call("POST", f"/issues/{number}/labels", {"labels": missing})
        _require_labels(issue, labels, f"#{number} is still")
        return True


class GitLab:
    """GitLab's REST API (v4), on gitlab.com or a self-managed instance.

    Written against the replies captured from GitLab CE 19.5.3: an issue is
    addressed by its `iid`, its `labels` are names, its `description` may be
    null, and a label that exists is refused with 409. A listing is read by
    `page` until a page is short (the `Link` header's `next` is the same
    walk; no listing's headers were captured).
    """

    token_variables = GITLAB_TOKEN_VARIABLES
    settle = GitHub.settle  # the same wait on the listing: it needs only existing_issues

    def __init__(self, repo: str, token: str, base_url: str | None):
        if not re.fullmatch(r"[A-Za-z0-9_.-]+(/[A-Za-z0-9_.-]+)+", repo):
            raise SeedError(f"--repo is GROUP/NAME (groups may nest), got {repo!r}")
        if not base_url:
            raise SeedError("--base-url is required for gitlab: the instance's web address")
        self.repo = repo
        self.token = token
        base = base_url.rstrip("/")
        if not base.endswith("/api/v4"):
            base += "/api/v4"
        # The project path is encoded once, `/` as `%2F`, and sent as encoded.
        self.project = f"{base}/projects/{urllib.parse.quote(repo, safe='')}"
        self._labels: list[str] | None = None
        bundle = os.environ.get(GITLAB_CA_VARIABLE)
        try:
            self._context = ssl.create_default_context(cafile=bundle) if bundle else None
        except (OSError, ssl.SSLError) as exc:
            raise SeedError(f"{GITLAB_CA_VARIABLE} cannot be read as a CA bundle: {exc}") from None

    def _call(self, method: str, path: str, payload: dict | None = None):
        data = None if payload is None else json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(
            f"{self.project}{path}",
            data=data,
            method=method,
            headers={
                "Accept": "application/json",
                "PRIVATE-TOKEN": self.token,
                "Content-Type": "application/json",
                "User-Agent": "durasum-demo-seed",
            },
        )
        try:
            with _open(request, self._context) as response:
                text = response.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            variable = self.token_variables[0]
            if exc.code == 401:
                raise SeedError(
                    f"GitLab refused the token in {variable} (401 Unauthorized): "
                    "it is revoked, expired or not for this instance"
                ) from None
            if exc.code == 403:
                raise SeedError(
                    f"GitLab refused the token in {variable} for this project (403 Forbidden): "
                    "it needs the `api` scope and the Developer role or more"
                ) from None
            if exc.code == 404:
                raise SeedError(
                    f"GitLab has no project {self.repo}, or the token in {variable} cannot "
                    "see it (404 Not Found)"
                ) from None
            raise
        try:
            return json.loads(text) if text else None
        except json.JSONDecodeError:
            raise SeedError(f"the forge's answer to {method} {path} is not JSON") from None

    def _pages(self, path: str):
        page = 1
        while True:
            joiner = "&" if "?" in path else "?"
            batch = self._call("GET", f"{path}{joiner}per_page=100&page={page}")
            yield from batch
            if len(batch) < 100:
                return
            page += 1

    @staticmethod
    def _normalized(item: dict) -> dict:
        """An issue as the rest of the script reads it: GitHub's keys."""
        return {
            "number": item["iid"],
            "title": item["title"],
            "body": item.get("description") or "",
            "html_url": item["web_url"],
            "labels": [{"name": name} for name in item.get("labels", [])],
        }

    def existing_issues(self) -> Existing:
        """Every issue the project has, open or closed, by title and by the
        file its marker names."""
        found = Existing()
        for raw in self._pages("/issues?state=all&scope=all"):
            item = self._normalized(raw)
            found.by_title.setdefault(item["title"], item)
            marked = MARKER_PATTERN.search(item["body"])
            if marked:
                found.by_file.setdefault(marked["name"], item)
        return found

    def ensure_label(self, name: str) -> bool:
        """Create the label unless the project (or a group above it) has it;
        True when created. Names are compared without regard to case: the
        forge refuses a second label that differs only in case."""
        if self._labels is None:
            self._labels = [label["name"] for label in self._pages("/labels")]
        if name.casefold() in {have.casefold() for have in self._labels}:
            return False
        try:
            self._call("POST", "/labels", {"name": name, "color": "#ededed"})
        except urllib.error.HTTPError as exc:
            if exc.code != 409:  # 409 "Label already exists": present after all
                raise
            return False
        self._labels.append(name)
        return True

    def file_issue(self, issue: Issue) -> tuple[int, str]:
        """File the issue; its number (iid) and address."""
        created = self._call(
            "POST",
            "/issues",
            {
                "title": issue.title,
                "description": issue.filed_body,
                "labels": ",".join(issue.labels),
            },
        )
        item = self._normalized(created)
        _require_labels(issue, item["labels"], f"#{item['number']} was filed")
        return item["number"], item["html_url"]

    def label_issue(self, issue: Issue, existing: dict) -> bool:
        """Add to an issue filed earlier the labels it lacks; True when it lacked any."""
        missing = _missing(issue.labels, existing.get("labels", []))
        if not missing:
            return False
        number = existing["number"]
        updated = self._call("PUT", f"/issues/{number}", {"add_labels": ",".join(missing)})
        _require_labels(issue, self._normalized(updated)["labels"], f"#{number} is still")
        return True


def _missing(wanted: tuple[str, ...], labels: list[dict]) -> list[str]:
    """The wanted label names not among the labels the forge returned."""
    have = {label["name"].casefold() for label in labels}
    return [name for name in wanted if name.casefold() not in have]


def _require_labels(issue: Issue, labels: list[dict], what: str) -> None:
    dropped = _missing(issue.labels, labels)
    if dropped:
        raise SeedError(
            f"{what} without {', '.join(sorted(dropped))}: "
            "the token cannot set labels on this repository"
        )


FORGES = {"github": GitHub, "gitlab": GitLab}


def _arguments(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="File the demo issues on a forge.")
    parser.add_argument("--forge", required=True, choices=sorted(FORGES))
    parser.add_argument("--repo", required=True, help="OWNER/NAME (GitLab: GROUP/.../NAME)")
    parser.add_argument(
        "--base-url",
        help="github: the API (default api.github.com); gitlab: the instance's web or API "
        "address, path prefix included",
    )
    parser.add_argument("--dry-run", action="store_true", help="say what would be filed")
    parser.add_argument("files", nargs="*", type=Path, help=f"default: demo/issues/{ISSUE_FILES}")
    return parser.parse_args(argv)


def _manifest_repo() -> str | None:
    if not MANIFEST.is_file():
        return None
    match = re.search(r"^repo:\s*(\S+)", MANIFEST.read_text(encoding="utf-8"), re.MULTILINE)
    return _unquote(match.group(1)) if match else None


def main(argv: list[str] | None = None) -> int:
    args = _arguments(argv)
    try:
        files = args.files or sorted(ISSUES.glob(ISSUE_FILES))
        if not files:
            raise SeedError(f"no issue files in {ISSUES}")
        issues = [parse_issue(path) for path in files]
        manifest_repo = _manifest_repo()
        if manifest_repo is not None and manifest_repo != args.repo:
            mismatch = (
                f".agent/manifest.yaml names {manifest_repo}, not {args.repo}, and the engine "
                f"works on the repository its manifest names: set `repo: {args.repo}` there "
                "and commit it first (README, 'Resetting a demo')"
            )
            if not args.dry_run:
                raise SeedError(mismatch)
            print(f"note: {mismatch}", file=sys.stderr)
        if args.dry_run:
            for issue in issues:
                labels = ", ".join(issue.labels) or "no labels"
                print(f"would file  {issue.title}  ({labels})  from {issue.source.name}")
            return 0
        variables = GITLAB_TOKEN_VARIABLES if args.forge == "gitlab" else TOKEN_VARIABLES
        token = next((os.environ[name] for name in variables if os.environ.get(name)), "")
        if not token:
            raise SeedError(f"no token: set {' or '.join(variables)}")
        base_url = args.base_url
        if base_url is None and args.forge == "github":
            base_url = "https://api.github.com"
        forge = FORGES[args.forge](args.repo, token, base_url)
        existing = forge.existing_issues()
        for name in sorted({label for issue in issues for label in issue.labels}):
            if forge.ensure_label(name):
                print(f"created label  {name}")
        filed: dict[str, int] = {}
        for issue in issues:
            found = existing.of(issue)
            if found is None:
                number, url = forge.file_issue(issue)
                filed[issue.source.name] = number
                print(f"filed #{number}  {issue.title}  {url}")
            elif forge.label_issue(issue, found):
                print(f"labelled #{found['number']}  {issue.title}")
            else:
                print(f"exists     {issue.title}  (#{found['number']}, not filed again)")
        if filed:
            forge.settle(issues, filed)
    except SeedError as exc:
        print(f"seed: {exc}", file=sys.stderr)
        return 1
    except urllib.error.HTTPError as exc:
        print(
            f"seed: the forge answered {exc.code} {exc.reason} for {exc.filename}", file=sys.stderr
        )
        return 1
    except TimeoutError:
        print("seed: the forge did not answer in time", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
