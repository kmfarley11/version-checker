'''
version_checker constants

Defaults and globals to be used by version checker software
'''
import os


# tries to find .bumpversion.cfg first to load globals, then uses args
CONFIG_FILE = os.getenv('VERSION_CONFIG_FILE', '.bumpversion.cfg')

REPO_PATH = os.getenv('REPO_PATH', '.')
BASE = os.getenv('VERSION_BASE', None)
BASES_IF_NONE = ['origin/main', 'origin/master']
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

# long / help text & version-checker specific info
EXAMPLE_CONFIG = ''
LIB_LOC = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
with open(os.path.join(LIB_LOC, '.bumpversion.cfg'), 'r') as _f:
    EXAMPLE_CONFIG = _f.read()

README_CONTENTS = ''
with open(os.path.join(LIB_LOC, 'Readme.md'), 'r') as _f:
    README_CONTENTS = _f.read()
