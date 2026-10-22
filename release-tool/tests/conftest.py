import shutil
from pathlib import Path

import pytest

from release_tool.cli import main

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def repo(tmp_path):
    """Copy a fixture repo layout into a temp dir and return its path."""

    def _copy(name):
        dest = tmp_path / name
        shutil.copytree(FIXTURES / name, dest)
        return dest

    return _copy


@pytest.fixture
def run(capsys):
    """Run the CLI and return (exit_code, stdout, stderr)."""

    def _run(*args):
        code = main([str(a) for a in args])
        out, err = capsys.readouterr()
        return code, out, err

    return _run


def edit_config(repo_dir, mutate):
    """Load the fixture's release-config.yml, apply `mutate(dict)`, write it back."""
    import yaml

    path = repo_dir / ".github" / "release-config.yml"
    data = yaml.safe_load(path.read_text())
    mutate(data)
    path.write_text(yaml.safe_dump(data))
