'''
version_checker constants

Defaults and globals to be used by version checker software
'''
import os


# tries to find .bumpversion.cfg first to load globals, then uses args
CONFIG_FILE = os.getenv('VERSION_CONFIG_FILE', '.bumpversion.cfg')

REPO_PATH = os.getenv('REPO_PATH', '.')
BASE = os.getenv('VERSION_BASE', 'origin/master')
CURRENT = os.getenv('VERSION_CURRENT', 'HEAD')
VERSION_FILE = os.getenv('VERSION_FILE', CONFIG_FILE)
VERSION_REGEX = os.getenv('VERSION_REGEX', r'([0-9]+\.?){3}')
FILES = []
FILE_REGEXES = []

LOG_NAME = '(version_checker)'

# bash color help for flair
NO_COLOR = "\033[0m"
GREEN = "\033[0;92m"
RED = "\033[0;91m"
_red = lambda s: f'{RED}{s}{NO_COLOR}'
_grn = lambda s: f'{GREEN}{s}{NO_COLOR}'
OK = _grn('ok')
ERROR = _red('error')

# long / help text
EXAMPLE_CONFIG = '''
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
'''
