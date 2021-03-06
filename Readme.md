# Version Checker

[![Travis](https://img.shields.io/travis/kmfarley11/version-checker/main.svg?logo=travis)](https://travis-ci.com/kmfarley11/version-checker)
[![codecov](https://codecov.io/gh/kmfarley11/version-checker/branch/main/graph/badge.svg?token=IG1MO377GJ)](https://codecov.io/gh/kmfarley11/version-checker)

Synchronize and track all hardcoded versions in a project!

## User install
```bash
sudo apt install python3 python3-pip
python3 -m pip install version_checker-0.2.2-alpha.2-py3-none-any.whl
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

## Usage
See [version_checker/Readme.md] for usage details.
