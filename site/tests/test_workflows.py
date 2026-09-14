# SPDX-License-Identifier: AGPL-3.0-or-later
"""Security and wiring of the workflows, labels and code owners. Issue text is untrusted,
so no workflow may interpolate it into a shell line."""

import re
import shutil
import subprocess

import pytest
import yaml

from garleak_intake import labels as L

from .intake_support import FORMS, REPO

WF = REPO / ".github" / "workflows"
INTAKE = sorted(WF.glob("intake*.yml"))
UNTRUSTED = re.compile(
    r"\$\{\{[^}]*\b(github\.event\.(issue|comment|label|review|discussion|pages|commits|head_commit)"
    r"|github\.event\.pull_request\.(title|body|head\.ref|head\.label)|github\.head_ref|inputs\.)[^}]*\}\}")


def load(path):
    data = yaml.safe_load(path.read_text())
    return data, data.get("on", data.get(True))


def steps(data):
    for job in data["jobs"].values():
        for step in job.get("steps", []):
            yield job, step


@pytest.mark.parametrize("path", sorted(WF.glob("*.yml")), ids=lambda p: p.name)
def test_no_untrusted_field_reaches_a_shell(path):
    data, _ = load(path)
    for _, step in steps(data):
        assert not UNTRUSTED.search(step.get("run", "")), (path.name, step.get("name"))


@pytest.mark.parametrize("path", INTAKE, ids=lambda p: p.name)
def test_intake_workflows_put_no_expression_in_a_shell_line(path):
    data, _ = load(path)
    for _, step in steps(data):
        assert "${{" not in step.get("run", ""), (path.name, step.get("name"))


def test_no_pull_request_target_anywhere():
    for path in WF.glob("*.yml"):
        _, on = load(path)
        assert "pull_request_target" not in (on if isinstance(on, dict) else {}), path.name
        assert "pull_request_target" not in path.read_text(), path.name


@pytest.mark.parametrize("path", INTAKE, ids=lambda p: p.name)
def test_least_privilege(path):
    data, _ = load(path)
    assert data["permissions"] == {}
    for job in data["jobs"].values():
        assert isinstance(job.get("permissions"), dict) and job["permissions"], path.name
        assert "id-token" not in job["permissions"] and "pages" not in job["permissions"]


def test_secrets_reach_only_the_orcid_step():
    for path in WF.glob("intake*.yml"):
        data, _ = load(path)
        for job, step in steps(data):
            env = " ".join(str(v) for v in (step.get("env") or {}).values())
            if "secrets." in env:
                assert step["name"] == "Read the public ORCID record", step["name"]
                assert "garleak-intake orcid-lookup" in step["run"] and "process" not in step["run"]
        assert "secrets." not in str(data.get("env", "")) and all("secrets." not in str(j.get("env", ""))
                                                                  for j in data["jobs"].values())


def test_actions_are_pinned():
    for path in WF.glob("*.yml"):
        data, _ = load(path)
        for _, step in steps(data):
            if "uses" in step:
                assert re.fullmatch(r"[\w.-]+/[\w.-]+@v\d+(\.\d+){0,2}", step["uses"]), step["uses"]


def test_intake_runs_once_at_a_time_per_issue():
    data, on = load(WF / "intake.yml")
    assert "github.event.issue.number" in data["concurrency"]["group"]
    assert data["concurrency"]["cancel-in-progress"] is False
    assert set(on) == {"issues", "issue_comment", "workflow_dispatch"}
    assert on["issues"]["types"] == ["opened", "edited", "labeled"]
    checkout = next(s for _, s in steps(data) if s.get("uses", "").startswith("actions/checkout"))
    assert checkout["with"]["persist-credentials"] is False
    assert "default_branch" in checkout["with"]["ref"]


def test_site_workflow_can_be_dispatched_for_a_redeploy():
    _, on = load(WF / "site.yml")
    assert "workflow_dispatch" in on


def test_labels_cover_everything_the_bot_writes():
    defined = {x["name"] for x in L.load_file()}
    assert L.emitted() <= defined
    for form in FORMS.values():
        assert set(form.labels) <= defined
    assert len(L.tsv().splitlines()) == len(defined)


def test_codeowners():
    text = (REPO / ".github" / "CODEOWNERS").read_text()
    rules = [ln.split() for ln in text.splitlines() if ln.strip() and not ln.startswith("#")]
    owners = {r[0]: r[1:] for r in rules}
    assert owners["/archive/papers/"] == ["@garleak-org/moderators"]
    assert owners["/archive/accounts/"] == ["@garleak-org/moderators"]
    assert owners["/archive/papers/*/verifications/"] == [] and owners["/archive/papers/*/signals/"] == []
    assert "/archive/scratches/" not in owners  # scratches merge on the automated checks


@pytest.mark.skipif(shutil.which("actionlint") is None, reason="actionlint is not installed")
def test_actionlint():
    r = subprocess.run(["actionlint", *map(str, sorted(WF.glob("*.yml")))], capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
