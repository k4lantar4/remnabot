"""Fork version and upstream update check.

The fork is built on upstream release 4.2.0 plus selective cherry-picks, so the version the
cabinet shows must name our own release (``4.2.0+rookari.N``), and the update check must not
compare it with upstream's releases by default — every upstream release would read as
"update available" although we never merge them wholesale.
"""

import re
from pathlib import Path

from packaging import version

from app.config import Settings
from app.services.version_service import VersionService


FORK_VERSION = re.compile(r'^\d+\.\d+\.\d+\+rookari\.\d+$')


def test_current_version_is_the_fork_release():
    current = VersionService._get_current_version(VersionService.__new__(VersionService))

    assert FORK_VERSION.match(current), current
    assert version.parse(current).local.startswith('rookari.')


def test_docker_image_version_matches_pyproject():
    current = VersionService._get_current_version(VersionService.__new__(VersionService))
    dockerfile = (Path(__file__).resolve().parents[2] / 'Dockerfile').read_text()

    assert f'ARG VERSION="v{current}"' in dockerfile


def test_upstream_update_check_is_off_by_default():
    assert Settings.model_fields['VERSION_CHECK_ENABLED'].default is False
