# Install
```bash
pip install base-version-checker
```

# Usage

## .bumpversion.cfg

This file is highly recommended to get the most out of this tool.
Without it you may get varied mileage from this as a git hook & when using bump2version.
Here's a simplified example. Use `version_checker -e` ([bumpversion_cfg_example.txt]) for more details
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

### bump version cfg format
This format is driven by bump2version: https://github.com/c4urself/bump2version/blob/master/README.md
I cannot assert that search & replace are regex compatibile, I would strongly recommend you stick to the above format.
- `[bumpversion]`: top level of bumpversion cfg, this is the base for version synchronizing etc.
- `{current_version}`: the checker & bump2version dryly replace this value with that reported at the top of the cfg
- `{new_version}`: only used by bump2version and is replaced by the `part` update commanded (patch v minor v major)
- `[bumpversion:file:<file>]`: section declaring a hardcoded version is present in a particular file
- `search`: used by the checker and bumper to search for specific text other than the current_version
- `replace`: used by the bumper only. the raw text to replace the `search` text


## version_checker usage assuming a .bumpversion.cfg
```bash
# to run manually
version_checker -h
VERSION_BASE=origin/non-main-branch version_checker

# to see an example .bumpversion.cfg
version_checker --example-config

# to install as pre-push git hook
version_checker -i pre-push

# add & commit your files, push should throw errors if versions not in sync/updated
# the errors should tell you to do something like the following
bump2version patch
bump2version --help
```

## environment variables
A few configurations can be modified by environment variables:

Environment Variable | Default | Description
------------ | ------------- | -------------
VERSION_BASE | origin/main or origin/master | The base branch/commit to check versions against
VERSION_HEAD | HEAD | The current commit to check versions on
REPO_PATH | . | The path to the git repo
VERSION_FILE | .bumpversion.cfg | The config file with version configs to parse
VERSION_REGEX | `([0-9]+\.?){3}?(\-([a-z]+)\.(\d+))` | The version regex to search for, _changes to this have not been tested much_
