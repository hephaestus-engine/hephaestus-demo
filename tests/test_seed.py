"""scripts/seed.py against a fake forge on this machine: what it files is
exactly what the issue files say."""

import importlib.util
import json
import re
import sys
import threading
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
ISSUE_FILES = sorted((ROOT / "demo" / "issues").glob("[0-9][0-9]-*.md"))

# scripts/ is not a package: the script is loaded from its file, and registered
# first, as an import would, so its dataclasses can find their module.
_spec = importlib.util.spec_from_file_location("seed", ROOT / "scripts" / "seed.py")
seed = importlib.util.module_from_spec(_spec)
sys.modules["seed"] = seed
_spec.loader.exec_module(seed)


class FakeGitHub:
    """Just enough of GitHub's REST API for seed.py, recording every request."""

    def __init__(self, titles=(), labels=(), drop_labels=False):
        self.issues = [{"number": n, "title": t} for n, t in enumerate(titles, start=1)]
        self.labels = set(labels)
        self.drop_labels = drop_labels
        self.requests = []

    def filed(self):
        return [
            body
            for method, path, _, body in self.requests
            if (method, path) == ("POST", "/repos/demo/seeded/issues")
        ]

    def handle(self, method, path, headers, body):
        self.requests.append((method, path, headers, body))
        address = urllib.parse.urlsplit(path)
        route = urllib.parse.unquote(address.path)
        if method == "GET" and route == "/repos/demo/seeded/issues":
            page = int(urllib.parse.parse_qs(address.query)["page"][0])
            return 200, self.issues[(page - 1) * 100 : page * 100]
        if method == "GET" and route.startswith("/repos/demo/seeded/labels/"):
            name = route.removeprefix("/repos/demo/seeded/labels/")
            return (200, {"name": name}) if name in self.labels else (404, {})
        if method == "POST" and route == "/repos/demo/seeded/labels":
            self.labels.add(body["name"])
            return 201, body
        if method == "POST" and route == "/repos/demo/seeded/issues":
            number = len(self.issues) + 1
            self.issues.append({"number": number, "title": body["title"]})
            labels = [] if self.drop_labels else [{"name": n} for n in body.get("labels", [])]
            return 201, {"number": number, "html_url": f"http://forge/{number}", "labels": labels}
        return 404, {}


@pytest.fixture
def forge():
    state = FakeGitHub()

    class Handler(BaseHTTPRequestHandler):
        def _answer(self):
            length = int(self.headers.get("Content-Length") or 0)
            body = json.loads(self.rfile.read(length)) if length else None
            status, answer = server.state.handle(self.command, self.path, dict(self.headers), body)
            payload = json.dumps(answer).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        do_GET = do_POST = _answer

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    server.state = state
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield server
    finally:
        server.shutdown()
        server.server_close()


def _run(server, monkeypatch, *extra):
    monkeypatch.delenv("GH_TOKEN", raising=False)
    monkeypatch.setenv("GITHUB_TOKEN", "test-token")
    url = f"http://127.0.0.1:{server.server_address[1]}"
    return seed.main(["--forge", "github", "--repo", "demo/seeded", "--base-url", url, *extra])


def _as_written(path):
    """A file's title, labels and body, read here without seed.py's parser."""
    text = path.read_text(encoding="utf-8")
    _, front, body = text.split("---\n", 2)
    title = re.search(r"^title: (.*)$", front, re.MULTILINE).group(1)
    labels = re.search(r"^labels: \[(.*)\]$", front, re.MULTILINE).group(1)
    return {
        "title": title,
        "labels": [name.strip() for name in labels.split(",") if name.strip()],
        "body": body.lstrip("\n"),
    }


def test_there_are_issue_files_to_seed():
    assert [path.name[:3] for path in ISSUE_FILES] == ["01-", "02-"]


def test_every_issue_file_is_filed_exactly_as_written(forge, monkeypatch):
    assert _run(forge, monkeypatch) == 0

    assert forge.state.filed() == [_as_written(path) for path in ISSUE_FILES]
    assert all(issue["labels"] for issue in forge.state.filed())


def test_the_token_is_sent_to_the_forge(forge, monkeypatch):
    _run(forge, monkeypatch)

    assert {headers["Authorization"] for _, _, headers, _ in forge.state.requests} == {
        "Bearer test-token"
    }


def test_missing_labels_are_created_before_the_issues(forge, monkeypatch):
    _run(forge, monkeypatch)

    wanted = {label for path in ISSUE_FILES for label in _as_written(path)["labels"]}
    assert forge.state.labels == wanted
    first_issue = next(
        i
        for i, r in enumerate(forge.state.requests)
        if r[:2] == ("POST", "/repos/demo/seeded/issues")
    )
    created = [
        i
        for i, r in enumerate(forge.state.requests)
        if r[:2] == ("POST", "/repos/demo/seeded/labels")
    ]
    assert created and max(created) < first_issue


def test_a_title_the_repository_has_is_not_filed_twice(forge, monkeypatch):
    forge.state.issues = [{"number": 7, "title": _as_written(ISSUE_FILES[0])["title"]}]

    assert _run(forge, monkeypatch) == 0

    assert [issue["title"] for issue in forge.state.filed()] == [
        _as_written(path)["title"] for path in ISSUE_FILES[1:]
    ]


def test_titles_are_read_past_the_first_page(forge, monkeypatch):
    forge.state.issues = [{"number": n, "title": f"older {n}"} for n in range(1, 151)]
    forge.state.issues[120]["title"] = _as_written(ISSUE_FILES[0])["title"]

    assert _run(forge, monkeypatch) == 0

    assert [issue["title"] for issue in forge.state.filed()] == [
        _as_written(path)["title"] for path in ISSUE_FILES[1:]
    ]


def test_a_second_run_files_nothing(forge, monkeypatch):
    _run(forge, monkeypatch)
    _run(forge, monkeypatch)

    assert len(forge.state.filed()) == len(ISSUE_FILES)


def test_labels_the_forge_dropped_are_an_error(forge, monkeypatch, capsys):
    forge.state.drop_labels = True

    assert _run(forge, monkeypatch) == 1

    assert "was filed without" in capsys.readouterr().err


def test_no_token_files_nothing(forge, monkeypatch, capsys):
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    monkeypatch.delenv("GH_TOKEN", raising=False)
    url = f"http://127.0.0.1:{forge.server_address[1]}"

    assert seed.main(["--forge", "github", "--repo", "demo/seeded", "--base-url", url]) == 1

    assert forge.state.requests == []
    assert "no token" in capsys.readouterr().err


def test_a_dry_run_sends_nothing(forge, monkeypatch, capsys):
    assert _run(forge, monkeypatch, "--dry-run") == 0

    assert forge.state.requests == []
    assert capsys.readouterr().out.count("would file") == len(ISSUE_FILES)


@pytest.mark.parametrize(
    ("text", "complaint"),
    [
        ("# no front matter\n", "no front matter"),
        ("---\nlabels: [bug]\n---\nbody\n", "no title"),
        ("---\ntitle: T\n---\nbody\n", "no labels"),
        ("---\ntitle: T\nlabels: bug\n---\nbody\n", "a list in brackets"),
        ("---\ntitle: T\nlabels: []\nmilestone: M\n---\nbody\n", "not understood"),
        ("---\ntitle: T\nlabels: []\n---\n\n", "no body"),
    ],
)
def test_a_malformed_issue_file_is_refused(tmp_path, text, complaint):
    path = tmp_path / "01-bad.md"
    path.write_text(text, encoding="utf-8")

    with pytest.raises(seed.SeedError, match=complaint):
        seed.parse_issue(path)


def test_quoted_values_and_several_labels_are_read(tmp_path):
    path = tmp_path / "01-ok.md"
    path.write_text(
        '---\ntitle: "A: B"\nlabels: [bug, "good first issue"]\n---\nbody\n', encoding="utf-8"
    )

    issue = seed.parse_issue(path)

    assert (issue.title, issue.labels, issue.body) == (
        "A: B",
        ("bug", "good first issue"),
        "body\n",
    )
