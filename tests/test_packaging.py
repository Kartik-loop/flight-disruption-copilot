"""Guard the deployment manifest against the self-reference rejected by Cloud's installer."""

import tomllib
from pathlib import Path


def test_all_extra_is_explicit_union():
    """Keep local all-extras installation useful without a circular package dependency."""
    project = tomllib.loads(Path("pyproject.toml").read_text())["project"]
    extras = project["optional-dependencies"]
    expected = {dep for name, deps in extras.items() if name != "all" for dep in deps}
    assert set(extras["all"]) == expected
    assert not any(project["name"] in dep for dep in extras["all"])
