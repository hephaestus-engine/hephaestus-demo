"""The demo issues name in backticks only files their change may touch.

Before a run, the engine reads an issue's expected scope from the paths its
body names in backticks, and floors the model by that scope. A file the change
must not touch, named that way, would send a plain fix to the strongest model.
A path cited with its line, such as `src/durasum/fmt.py:14`, is a citation and
not part of the scope.
"""

import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
ISSUES = sorted((ROOT / "demo" / "issues").rglob("[0-9][0-9]-*.md"))
# The pattern the engine reads an issue's expected scope with.
NAMED = re.compile(r"`([A-Za-z0-9_./-]+\.[A-Za-z0-9]{1,5})`")


def _floored():
    """Every path a model floor in the manifest names."""
    manifest = (ROOT / ".agent" / "manifest.yaml").read_text(encoding="utf-8")
    lists = re.findall(r"^\s+paths:\s*(\[.*\])\s*$", manifest, re.MULTILINE)
    return {path for found in lists for path in json.loads(found)}


def test_the_manifest_has_a_floor_to_check_against():
    assert "src/durasum/store.py" in _floored()


@pytest.mark.parametrize("issue", ISSUES, ids=lambda path: path.name)
def test_an_issue_names_files_that_exist_and_carry_no_floor(issue):
    named = NAMED.findall(issue.read_text(encoding="utf-8"))

    assert named
    assert [path for path in named if not (ROOT / path).is_file()] == []
    assert [path for path in named if path in _floored()] == []
