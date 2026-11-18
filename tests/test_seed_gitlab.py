"""scripts/seed.py --forge gitlab against a fake GitLab on this machine.

The fake answers as GitLab CE 19.5.3 did when its replies were captured (the
engine's `docs/evaluation/gitlab-ce-facts.md`, facts 1, 4, 6 and 7): an issue
is read and written by its `iid`, its `labels` are names, an issue made with
no description has a null one, a label that exists is a 409 with
`{"message": "Label already exists"}`, a refused token is a 401 with
`{"message": "401 Unauthorized"}`, and a project that is missing is a 404.
Shapes that were not captured are written from GitLab's API documentation and
marked `DOCS` where they are served: `labels` on a create as a comma-joined
string, `add_labels` on an edit, `GET .../labels` and `GET .../issues`
listed by `per_page` and `page` (the listings' headers were not captured), and
a group label showing in the project's label list.
"""

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
TOKEN = "glpat-planted-token-0123456789"

_spec = importlib.util.spec_from_file_location("seed_for_gitlab", ROOT / "scripts" / "seed.py")
seed = importlib.util.module_from_spec(_spec)
sys.modules["seed_for_gitlab"] = seed
_spec.loader.exec_module(seed)


class FakeGitLab:
    """Just enough of GitLab's REST API for seed.py, recording every request.

    `prefix` is the path the instance is served under; `project` the path of
    the one project it has, as a person writes it."""

    def __init__(self, project="demo/seeded", prefix="", labels=(), titles=()):
        self.project = project
        self.encoded = urllib.parse.quote(project, safe="")
        self.prefix = prefix
        self.labels = list(labels)
        self.issues = []
        for iid, title in enumerate(titles, start=1):
            self.issues.append(self._issue(iid, title, None, []))
        self.token = TOKEN
        self.lag = 0  # list reads an issue just filed stays out of the listing for
        self.reads = 0
        self.requests = []

    def _issue(self, iid, title, description, labels):
        return {
            "iid": iid,
            "title": title,
            "description": description,
            "labels": labels,
            "state": "opened",
            "web_url": f"http://forge.test/{self.project}/-/work_items/{iid}",
        }

    def filed(self):
        return [b for m, p, _, b in self.requests if m == "POST" and p.endswith("/issues")]

    def handle(self, method, raw_path, headers, body):
        """The raw path is kept: whether `%2F` was sent once is the test."""
        self.requests.append((method, raw_path, headers, body))
        if headers.get("PRIVATE-TOKEN") != self.token:
            return 401, {"message": "401 Unauthorized"}
        address = urllib.parse.urlsplit(raw_path)
        base = f"{self.prefix}/api/v4/projects/{self.encoded}"
        if not address.path.startswith(base):
            return 404, {"message": "404 Not Found"}
        route = address.path[len(base) :]
        query = urllib.parse.parse_qs(address.query)
        if method == "GET" and route == "/labels":  # DOCS: pages by per_page and page
            return 200, self._page(query, [{"id": n, "name": x} for n, x in enumerate(self.labels)])
        if method == "POST" and route == "/labels":
            if any(have.casefold() == body["name"].casefold() for have in self.labels):
                return 409, {"message": "Label already exists"}
            self.labels.append(body["name"])
            return 201, {"name": body["name"], "color": body["color"], "is_project_label": True}
        if method == "GET" and route == "/issues":  # DOCS: pages by per_page and page
            self.reads += 1
            listed = [i for i in self.issues if i.get("listed_from", 0) <= self.reads]
            return 200, self._page(query, listed)
        if method == "POST" and route == "/issues":
            if "title" not in body:
                return 400, {"error": "title is missing"}
            names = [n for n in body.get("labels", "").split(",") if n]  # DOCS: a string
            iid = len(self.issues) + 1
            issue = self._issue(iid, body["title"], body.get("description"), self._known(names))
            issue["listed_from"] = self.reads + 1 + self.lag
            self.issues.append(issue)
            return 201, issue
        found = re.fullmatch(r"/issues/(\d+)", route)
        if method == "PUT" and found:  # DOCS: add_labels is a comma-joined string
            issue = next(i for i in self.issues if i["iid"] == int(found[1]))
            issue["labels"] += self._known(body["add_labels"].split(","))
            return 200, issue
        return 404, {"message": "404 Not Found"}

    def _known(self, names):
        """A label GitLab was given that the project lacks it creates (the
        Issues API says so); the label then exists."""
        have = {x.casefold(): x for x in self.labels}
        out = []
        for name in names:
            if name.casefold() not in have:
                self.labels.append(name)
                have[name.casefold()] = name
            out.append(have[name.casefold()])
        return out

    @staticmethod
    def _page(query, rows):
        per_page = int(query["per_page"][0])
        page = int(query["page"][0])
        return rows[(page - 1) * per_page : page * per_page]


def _serve(state):
    class Handler(BaseHTTPRequestHandler):
        def _answer(self):
            length = int(self.headers.get("Content-Length") or 0)
            body = json.loads(self.rfile.read(length)) if length else None
            status, answer = state.handle(
                self.command, self.path, {k.upper(): v for k, v in self.headers.items()}, body
            )
            payload = json.dumps(answer).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        do_GET = do_POST = do_PUT = _answer

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    server.state = state
    threading.Thread(
        target=server.serve_forever, kwargs={"poll_interval": 0.01}, daemon=True
    ).start()
    return server


@pytest.fixture
def make_forge():
    servers = []

    def make(**kwargs):
        server = _serve(FakeGitLab(**kwargs))
        servers.append(server)
        return server

    yield make
    for server in servers:
        server.shutdown()
        server.server_close()


@pytest.fixture
def forge(make_forge):
    return make_forge()


@pytest.fixture(autouse=True)
def manifest(tmp_path, monkeypatch):
    path = tmp_path / "manifest.yaml"
    path.write_text('repo: "demo/seeded"\n', encoding="utf-8")
    monkeypatch.setattr(seed, "MANIFEST", path)
    monkeypatch.setattr(seed, "SETTLE_INTERVAL", 0, raising=False)
    monkeypatch.delenv("GITLAB_CA_BUNDLE", raising=False)
    return path


def _address(server, prefix=""):
    return f"http://127.0.0.1:{server.server_address[1]}{prefix}"


def _run(server, monkeypatch, *extra, repo=None, prefix="", token=TOKEN, set_manifest=True):
    monkeypatch.setenv("GITLAB_TOKEN", token)
    repo = repo or server.state.project
    if repo != "demo/seeded" and set_manifest:
        seed.MANIFEST.write_text(f'repo: "{repo}"\n', encoding="utf-8")
    return seed.main(
        ["--forge", "gitlab", "--repo", repo, "--base-url", _address(server, prefix), *extra]
    )


def _as_written(path):
    text = path.read_text(encoding="utf-8")
    _, front, body = text.split("---\n", 2)
    title = re.search(r"^title: (.*)$", front, re.MULTILINE).group(1)
    labels = re.search(r"^labels: \[(.*)\]$", front, re.MULTILINE).group(1)
    return {
        "title": title,
        "labels": [name.strip() for name in labels.split(",") if name.strip()],
        "body": body.lstrip("\n"),
    }


def _marked(path):
    return f"{_as_written(path)['body'].rstrip()}\n\n<!-- demo-seed: {path.name} -->\n"


def test_every_issue_file_is_filed_with_its_title_body_and_labels(forge, monkeypatch):
    assert _run(forge, monkeypatch) == 0

    assert forge.state.filed() == [
        {
            "title": _as_written(path)["title"],
            "description": _marked(path),
            "labels": ",".join(_as_written(path)["labels"]),
        }
        for path in ISSUE_FILES
    ]
    assert all(issue["labels"] for issue in forge.state.filed())
    assert [i["labels"] for i in forge.state.issues] == [
        _as_written(path)["labels"] for path in ISSUE_FILES
    ]


def test_the_token_is_sent_in_the_private_token_header(forge, monkeypatch):
    _run(forge, monkeypatch)

    assert {headers["PRIVATE-TOKEN"] for _, _, headers, _ in forge.state.requests} == {TOKEN}


def test_no_blocked_by_link_is_made(forge, monkeypatch):
    # Fact 10: a Community Edition instance refuses blocks / is_blocked_by links.
    _run(forge, monkeypatch)

    assert not [r for r in forge.state.requests if "/links" in r[1]]


def test_a_second_run_files_nothing(forge, monkeypatch, capsys):
    _run(forge, monkeypatch)
    capsys.readouterr()

    assert _run(forge, monkeypatch) == 0

    assert len(forge.state.filed()) == len(ISSUE_FILES)
    out = capsys.readouterr().out
    assert out.count("not filed again") == len(ISSUE_FILES)
    assert "filed #" not in out


def test_a_second_run_files_nothing_while_the_listing_trails_the_filing(forge, monkeypatch):
    forge.state.lag = 3

    assert _run(forge, monkeypatch) == 0
    assert _run(forge, monkeypatch) == 0

    assert len(forge.state.filed()) == len(ISSUE_FILES)


def test_a_listing_that_never_shows_the_filing_is_an_error(forge, monkeypatch, capsys):
    forge.state.lag = 10**6
    monkeypatch.setattr(seed, "SETTLE_SECONDS", 0, raising=False)

    assert _run(forge, monkeypatch) == 1

    assert "does not show" in capsys.readouterr().err


def test_an_issue_is_found_by_its_marker_when_its_title_was_edited(forge, monkeypatch):
    path = ISSUE_FILES[0]
    forge.state.issues = [
        forge.state._issue(
            5, "A title a person changed", _marked(path), _as_written(path)["labels"]
        )
    ]

    assert _run(forge, monkeypatch) == 0

    assert [i["title"] for i in forge.state.filed()] == [
        _as_written(p)["title"] for p in ISSUE_FILES[1:]
    ]


def test_an_issue_the_project_has_by_title_and_a_null_description_is_not_filed_again(
    make_forge, monkeypatch
):
    # Fact 1: an issue made with no description reads `description: null`.
    forge = make_forge(titles=[_as_written(ISSUE_FILES[0])["title"]])

    assert _run(forge, monkeypatch) == 0

    assert [i["title"] for i in forge.state.filed()] == [
        _as_written(p)["title"] for p in ISSUE_FILES[1:]
    ]


def test_titles_are_read_past_the_first_page(make_forge, monkeypatch):
    forge = make_forge(titles=[f"older {n}" for n in range(1, 151)])
    forge.state.issues[120]["title"] = _as_written(ISSUE_FILES[0])["title"]

    assert _run(forge, monkeypatch) == 0

    assert [i["title"] for i in forge.state.filed()] == [
        _as_written(p)["title"] for p in ISSUE_FILES[1:]
    ]


def test_missing_labels_are_created_before_the_issues(forge, monkeypatch):
    _run(forge, monkeypatch)

    wanted = {label for path in ISSUE_FILES for label in _as_written(path)["labels"]}
    assert set(forge.state.labels) == wanted
    posts = [(i, r[1]) for i, r in enumerate(forge.state.requests) if r[0] == "POST"]
    created = [i for i, p in posts if p.endswith("/labels")]
    first_issue = min(i for i, p in posts if p.endswith("/issues"))
    assert created and max(created) < first_issue
    assert all(r[3]["color"] for r in forge.state.requests if r[0] == "POST" and "labels" in r[1])


def test_a_label_the_project_has_in_another_case_is_not_created_again(make_forge, monkeypatch):
    # Fact 4: creating a label that exists is a 409; the project spells it in its own case.
    wanted = sorted({label for path in ISSUE_FILES for label in _as_written(path)["labels"]})
    forge = make_forge(labels=[name.upper() for name in wanted])

    assert _run(forge, monkeypatch) == 0

    assert not [r for r in forge.state.requests if r[0] == "POST" and r[1].endswith("/labels")]
    assert len(forge.state.filed()) == len(ISSUE_FILES)


def test_a_rerun_adds_the_labels_an_earlier_run_could_not(make_forge, monkeypatch):
    path = ISSUE_FILES[0]
    forge = make_forge()
    forge.state.issues = [forge.state._issue(1, _as_written(path)["title"], _marked(path), [])]

    assert _run(forge, monkeypatch) == 0

    puts = [r for r in forge.state.requests if r[0] == "PUT"]
    assert [r[3]["add_labels"] for r in puts] == [",".join(_as_written(path)["labels"])]
    assert forge.state.issues[0]["labels"] == _as_written(path)["labels"]


def test_labels_the_forge_dropped_are_an_error(forge, monkeypatch, capsys):
    original = forge.state._known
    forge.state._known = lambda names: []
    try:
        assert _run(forge, monkeypatch) == 1
    finally:
        forge.state._known = original

    assert "without" in capsys.readouterr().err


def test_a_base_url_with_a_path_prefix_is_served_under_it(make_forge, monkeypatch):
    forge = make_forge(prefix="/gitlab")

    assert _run(forge, monkeypatch, prefix="/gitlab") == 0

    assert len(forge.state.filed()) == len(ISSUE_FILES)
    assert all(r[1].startswith("/gitlab/api/v4/projects/") for r in forge.state.requests)


def test_a_base_url_may_be_the_api_address_itself(make_forge, monkeypatch):
    forge = make_forge(prefix="/gitlab")

    assert _run(forge, monkeypatch, prefix="/gitlab/api/v4/") == 0

    assert len(forge.state.filed()) == len(ISSUE_FILES)
    assert not any("/api/v4/api/v4" in r[1] for r in forge.state.requests)


def test_a_nested_project_path_is_encoded_once(make_forge, monkeypatch):
    forge = make_forge(project="demo/sub/pilot-demo")

    assert _run(forge, monkeypatch) == 0

    assert len(forge.state.filed()) == len(ISSUE_FILES)
    for _, path, _, _ in forge.state.requests:
        assert "/projects/demo%2Fsub%2Fpilot-demo/" in path
        assert "%25" not in path


def test_a_project_the_manifest_does_not_name_is_refused(forge, monkeypatch, capsys):
    seed.MANIFEST.write_text('repo: "someone/else"\n', encoding="utf-8")

    assert _run(forge, monkeypatch, set_manifest=False) == 1

    assert "someone/else" in capsys.readouterr().err
    assert forge.state.requests == []


def test_a_refused_token_is_named_in_the_error_and_never_printed(forge, monkeypatch, capsys):
    refused = "glpat-refused-token-9876543210"

    assert _run(forge, monkeypatch, token=refused) == 1

    seen = capsys.readouterr()
    assert "GITLAB_TOKEN" in seen.err
    assert "401" in seen.err
    assert refused not in seen.out + seen.err
    assert forge.state.filed() == []


def test_the_token_never_appears_in_any_output(forge, monkeypatch, capsys):
    _run(forge, monkeypatch)
    _run(forge, monkeypatch)

    seen = capsys.readouterr()
    assert TOKEN not in seen.out + seen.err


def test_a_project_the_instance_does_not_have_is_named(make_forge, monkeypatch, capsys):
    forge = make_forge(project="demo/other")
    seed.MANIFEST.write_text('repo: "demo/seeded"\n', encoding="utf-8")

    assert _run(forge, monkeypatch, repo="demo/seeded", set_manifest=False) == 1

    assert "demo/seeded" in capsys.readouterr().err


def test_no_token_files_nothing(forge, monkeypatch, capsys):
    monkeypatch.delenv("GITLAB_TOKEN", raising=False)
    monkeypatch.setenv("GITHUB_TOKEN", "a-github-token")

    code = seed.main(["--forge", "gitlab", "--repo", "demo/seeded", "--base-url", _address(forge)])

    assert code == 1
    assert "GITLAB_TOKEN" in capsys.readouterr().err
    assert forge.state.requests == []


def test_gitlab_needs_a_base_url(monkeypatch, capsys):
    monkeypatch.setenv("GITLAB_TOKEN", TOKEN)

    assert seed.main(["--forge", "gitlab", "--repo", "demo/seeded"]) == 1

    assert "--base-url" in capsys.readouterr().err


def test_a_ca_bundle_that_cannot_be_read_is_an_error(forge, monkeypatch, capsys, tmp_path):
    monkeypatch.setenv("GITLAB_CA_BUNDLE", str(tmp_path / "missing.pem"))

    assert _run(forge, monkeypatch) == 1

    assert "GITLAB_CA_BUNDLE" in capsys.readouterr().err
    assert forge.state.requests == []


def test_a_dry_run_sends_nothing(forge, monkeypatch, capsys):
    assert _run(forge, monkeypatch, "--dry-run") == 0

    assert capsys.readouterr().out.count("would file") == len(ISSUE_FILES)
    assert forge.state.requests == []
