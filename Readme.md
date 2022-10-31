# (Base) Version Checker

[![PyPI version](https://badge.fury.io/py/base-version-checker.svg)](https://badge.fury.io/py/base-version-checker)
[![Travis](https://img.shields.io/travis/kmfarley11/version-checker/main.svg?logo=travis)](https://travis-ci.com/kmfarley11/version-checker)
[![codecov](https://codecov.io/gh/kmfarley11/version-checker/branch/main/graph/badge.svg?token=IG1MO377GJ)](https://codecov.io/gh/kmfarley11/version-checker)

Synchronize and track all hardcoded versions in a project!
Versions specified in .bumpversion.cfg are compared to those hosted in a baseline such as `origin/main`...

## User install
```bash
sudo apt install python3 python3-pip
python3 -m pip install version_checker-0.2.3-py3-none-any.whl
version_checker -h
```

## Dev install
```bash
sudo apt install python3 python3-venv python3-pip
python3 -m venv .venv
. .venv/bin/activate
pip install -e .[dev]
python3 -m build
pylint version_checker/
pytest
pytest --cov=version_checker.utils tests/ # --cov-report html && firefox htmlcov/index.html
# or `coverage run && coverage html`
bash integration-test.sh
```

### Creating a new pypi release
New pypi releases are triggered by tags:
```bash
git checkout main
bump2version <major|minor|patch|pre|build> --commit --tag
git push
git push --tags
```

## Usage
See [version_checker/Readme.md](version_checker/Readme.md) for usage details.
