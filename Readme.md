# Version Checker

[![Travis](https://img.shields.io/travis/kmfarley11/version-checker/master.svg?logo=travis)](https://travis-ci.org/kmfarley11/version-checker)

Synchronize and track all hardcoded versions in a project!

## Install (non-devs)
```bash
sudo apt install python3 python3-pip
python3 -m pip install version_checker-0.1.5-py3-none-any.whl
version_checker -h
```

## Dev (devs-only)
```bash
sudo apt install python3 python3-venv python3-pip
python3 -m venv .venv
. .venv/bin/activate
pip install -e .[dev]
python3 -m build
pylint version_checker/
pytest
pytest --cov=version_checker.utils tests/ # --cov-report html && firefox htmlcov/index.html
bash integration-test.sh
```

## Use

### .bumpversion.cfg

This file is highly recommended to get the most out of this tool.
Without it you may get varied mileage from this as a git hook & when using bump2version.
Here's an example
```
[bumpversion]
current_version = 0.0.3

[bumpversion:file:Readme.md]
search = version_checker-{current_version}-py3-none-any.whl
replace = version_checker-{new_version}-py3-none-any.whl

[bumpversion:file:setup.cfg]
search = version = {current_version}
replace = version = {new_version}

[bumpversion:file:version.txt]

[bumpversion:file:kustomize/base/service.yaml]

[bumpversion:file:openapi-spec.json]
search = "version": "{current_version}"
replace = "version": "{new_version}"

[bumpversion:file:pom.xml]
search = <version>{current_version}</version> <!--this comment helps bumpversion find my (and only my) version!-->
replace = <version>{new_version}</version> <!--this comment helps bumpversion find my (and only my) version!-->
```

#### bump version cfg format
This format is driven by bump2version: https://github.com/c4urself/bump2version/blob/master/README.md
I cannot assert that search & replace are regex compatibile, I would strongly recommend you stick to the above format.
- `[bumpversion]`: top level of bumpversion cfg, this is the base for version synchronizing etc.
- `{current_version}`: the checker & bump2version dryly replace this value with that reported at the top of the cfg
- `{new_version}`: only used by bump2version and is replaced by the `part` update commanded (patch v minor v major)
- `[bumpversion:file:<file>]`: section declaring a hardcoded version is present in a particular file
- `search`: used by the checker and bumper to search for specific text other than the current_version
- `replace`: used by the bumper only. the raw text to replace the `search` text


### version_checker usage assuming a .bumpversion.cfg
```bash
# to run manually
version_checker -h

# to see an example .bumpversion.cfg
version_checker --example-config

# to install as pre-push git hook
version_checker -i pre-push

# add & commit your files, push should throw errors if versions not in sync/updated
# the errors should tell you to do something like the following
bump2version patch
bump2version --help
```

### environment variables
A few configurations can be modified by environment variables:

Environment Variable | Default | Description
------------ | ------------- | -------------
VERSION_BASE | origin/master | The base branch/commit to check versions against
VERSION_HEAD | HEAD | The current commit to check versions on
REPO_PATH | . | The path to the git repo
VERSION_FILE | .bumpversion.cfg | The config file with version configs to parse
VERSION_REGEX | `([0-9]+\.?){3}` | The version regex to search for, changes to this have not been tested much

