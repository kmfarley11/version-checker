#!.venv/bin/python
r'''
Version Helper
Python utility designed to facilitate version file checks & updates.
Assumes git and prefers bump2version.
Sync files containing raw version text, and verify they get bumped from a git base location.

Usage:
    version_checker.py -h
    version_checker.py -l debug
    version_checker.py -v version.txt -r '([0-9]+\.?){3}'
    version_checker.py -v version.txt -f openapi-spec.json --file-regexes 'version.: \d\.\d\.\d'

Can be used as a simple dev script, or a git-hook:
    version_checker -i pre-push

To make full-use of this tool, create a .bumpversion.cfg or setup.cfg!
    see github.com/c4urself/bump2version
'''

import argparse
import configparser
import logging
import os
import re
import subprocess
import sys

import git


# globals & default configs
logging.basicConfig(stream=sys.stdout, level=logging.INFO)
LOG = logging.getLogger('(version_checker)')

try:
    REPO = git.Repo('.')
except git.exc.InvalidGitRepositoryError:
    LOG.critical('This utility must be run from the root of a git repository!')
    sys.exit(1)

# tries to find .bumpversion.cfg first to load globals, then tries setup.cfg, then uses args
CONFIG_FILE = os.getenv('VERSION_CONFIG_FILE', '.bumpversion.cfg')
CONFIG_FILE_ALT = os.getenv('VERSION_CONFIG_FILE_ALT', 'setup.cfg')

BASE = 'origin/master'
CURRENT = 'HEAD'
VERSION_FILE = CONFIG_FILE
VERSION_REGEX = r'([0-9]+\.?){3}'
FILES = []
FILE_REGEXES = []

# bash color help for flair
NO_COLOR = "\033[0m"
GREEN = "\033[0;92m"
RED = "\033[0;91m"
_red = lambda s: f'{RED}{s}{NO_COLOR}'
_grn = lambda s: f'{GREEN}{s}{NO_COLOR}'
OK = _grn('ok')
ERROR = _red('error')


# (protected) helpers
def _bash(cmd):
    '''Helper to run quick bash command and return its shell output'''
    return subprocess.check_output(cmd, shell=True).decode()


def _get_commit_file(fcommit, fpath):
    '''Helper (shorthand) to extract file contents at a specific commit'''
    return (fcommit.tree / fpath).data_stream.read().decode()


def _ok(msg):
    '''Helper to print out an ok message'''
    LOG.info(f'{msg}... {OK}')


def _error(msg, abort=True):
    '''Helper to print out an error message and exit (1)'''
    LOG.error(f'{msg}... {ERROR}')
    if abort:
        LOG.error('Run with "--log-level debug" for more detail')
        LOG.error('''
            Otherwise, try bumping your versions i.e.
                bump2version patch --allow-dirty
                bump2version patch --commit
                bump2version patch version.txt \\
                    --allow-dirty --no-configured-files --current-version 0.0.1
            Note: this checker will only succeed if the latest commit contains updated versions
            To bypass it as a hook try using --no-verify but this is NOT preferred...
        ''')
        sys.exit(1)


def _log_name_to_level(name):
    '''Helper to convert inputted log'''
    lvl = -1
    if name.lower() == 'debug':
        lvl = logging.DEBUG
    elif name.lower() == 'info':
        lvl = logging.INFO
    elif name.lower() == 'warning':
        lvl = logging.WARNING
    elif name.lower() == 'error':
        lvl = logging.ERROR
    else:
        raise NotImplementedError(f'log level {name} not found')
    return lvl


def _search_or_error(regex_str, to_search_str, abort=True):
    '''Helper to do a regex search and return matches, exits program on error'''
    result = re.search(regex_str, to_search_str)
    if result:
        return result.group(0)
    LOG.debug(f'inputted: "{to_search_str}"')
    _error(f'could not find {regex_str} in inputted string', abort=abort)
    return ''


# utility functions
def get_bumpversion_config(cfg_file):
    '''Helper to parse bumpversion configurations

    returns file and file regexes to be checked, used to globals prior to argparse
    '''
    with open(cfg_file, 'r') as _f:
        cfg_raw = _f.read()

    cfg = configparser.ConfigParser()
    cfg.read_string(cfg_raw)

    if not cfg.has_section('bumpversion') or not cfg.has_option('bumpversion', 'current_version'):
        LOG.warning(f'invalid bumpversion config detected {cfg_file}')
        LOG.warning('see github.com/c4urself/bump2version for more details, skipping cfg parse...')
        return [], []

    file_regexes = []
    files = [s.split(':')[-1] for s in cfg.sections() if ':file:' in s]
    for _f in files:
        fregex = VERSION_REGEX
        section = f'bumpversion:file:{_f}'
        if cfg.has_option(section, 'search'):
            fregex = cfg.get(section, 'search').replace('{current_version}', VERSION_REGEX)
        file_regexes.append(fregex)

    LOG.info(f'Successfully parsed {cfg_file}')
    return files, file_regexes


def search_commit_file(git_commit, fpath, search_regex, abort=True):
    '''Search a file in a source tree for some regex pattern

    Accepts GitPython commit object, filepath, and regex to search for (and bool to abort or not)
    Returns search text or empty string
    '''
    if fpath in git_commit.tree:
        commit_file = _get_commit_file(git_commit, fpath)
        return _search_or_error(search_regex, commit_file, abort=abort)

    _error(f'file {fpath} not found in the provided git.Commit {git_commit}', abort=abort)
    return ''


# temporary disable some pylint to reduce globals and decouple from argparse itself
#pylint: disable=too-many-arguments
def do_check(base, current, version_file, version_regex, files, file_regexes):
    '''Checking functionality

    verify the local versions have been incremented from the base branch
    '''
    LOG.debug(f'{base}, {current}, {version_file}, {version_regex}, {files}')
    LOG.debug(f'{file_regexes}')

    # get the files that were modified
    base_commit = REPO.commit(base)
    current_commit = REPO.commit(current)

    # filter the changelist for the base version file, empty list if not found
    version_file_diff = list(
        filter(
            lambda d: d.b_path == version_file,
            base_commit.diff(current_commit).iter_change_type('M')))
    new, old = '', ''

    if version_file not in base_commit.tree and version_file in current_commit.tree:
        LOG.warning(f'{version_file} not found in base ({base}), assuming new file...')
        new = search_commit_file(current_commit, version_file, version_regex)
    elif not version_file_diff:
        _error(f'{version_file} change not detected')
    else:
        # attempt to parse out new & old version from inputted version_file
        _ok(f'{version_file} change detected')
        old = search_commit_file(base_commit, version_file, version_regex)
        new = search_commit_file(current_commit, version_file, version_regex)

    # verify the change is productive
    LOG.info(f'\told version = {old}')
    LOG.info(f'\tnew version = {new}')
    if old < new:
        _ok('new version larger than old')
    else:
        _error('new version smaller than old')

    if len(files) == 0:
        LOG.warning(f'No extra file checking inputted, only verfied {version_file}')
        return

    # verify any other inputted files match the version_file's contents
    if len(file_regexes) != len(files):
        LOG.warning(
            f'Inputted file regexes didnt match file list size, '
            f'defaulting to {version_regex}')
        file_regexes = [version_regex] * len(files)

    error_detected = False
    for _f, _r in zip(files, file_regexes):
        file_version = search_commit_file(current_commit, _f, _r, abort=False)
        if new not in file_version:
            _error(f'\t{_f} needs to match {version_file}!', abort=False)
            error_detected = True
        else:
            LOG.debug(f'\t{_f}: {file_version}')
    if error_detected:
        _error('not all files are correct')

    _ok('all files matched the correct version')
#pylint: enable=too-many-arguments


def do_update(part, options='--allow-dirty'):
    '''Enact version updates for local files

    Just calls out to bump2version, relies on a .bumpversion.cfg or setup.cfg
    '''
    cmd = f'bump2version {part} {options}'
    LOG.info(f"attempting command: '{cmd}'")
    LOG.info(_bash(cmd))


def install_hook(hook):
    '''Symlink this program as a git-hook'''
    hook_path = os.path.abspath(os.path.join('.', '.git', 'hooks', hook))
    prog_path = os.path.abspath(__file__)
    if not os.path.exists(prog_path):
        _error(f'Symlink source source "{prog_path}" not found!')
    elif os.path.exists(hook_path) or os.path.islink(hook_path):
        LOG.error(f'Git hook "{hook_path}" already exists!')
        LOG.error('Remove the existing hook and re-try if further action is desired.')
        sys.exit(1)
    else:
        os.symlink(prog_path, hook_path)
        _ok(f'"{prog_path}", installed to "{hook_path}"')


# main method
def main():
    '''Main function for version check/update stuff.'''
    # Note: a meld of RawTextHelpFormatter + ArgumentDefaultsHelpFormatter seems appropriate
    arg_parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawTextHelpFormatter)

    # prior to argument parsing etc., attempt to parse bumpversion config
    files, file_regexes = FILES, FILE_REGEXES
    if os.path.exists(CONFIG_FILE) and os.path.isfile(CONFIG_FILE):
        files, file_regexes = get_bumpversion_config(CONFIG_FILE)
    elif os.path.exists(CONFIG_FILE_ALT) and os.path.isfile(CONFIG_FILE_ALT):
        files, file_regexes = get_bumpversion_config(CONFIG_FILE_ALT)
    else:
        LOG.warning('bumpversion configs not found, skipping...')

    _a = arg_parser.add_argument
    _a('--install-hook', '-i', choices=['pre-push'], default=None,
        help='Install version_checker as a git hook (works best with .bumpconfig.cfg)')
    _a('--update', '-u', choices=['major', 'minor', 'patch'], default=None,
        help='Update versions via bump2version, assumes .bumpconfig.cfg or setup.cfg')
    _a('--log-level', '-l', choices=['info', 'debug', 'warning', 'error'], default='info',
        help='Set the log level for the application')

    _a('--base', '-b', type=str, default=BASE,
        help='Branch in version control to check against')
    _a('--current', '-c', type=str, default=CURRENT,
        help='Git tag/branch/hash to verify')
    _a('--version-file', '-v', type=str, default=VERSION_FILE,
        help='File to base all version checks against')
    _a('--version-regex', '-r', type=str, default=VERSION_REGEX,
        help='Regex to extract version out of version file')

    _a('--files', '-f', nargs='+', default=files,
        help='Files to check version number')
    _a('--file-regexes', nargs='+', default=file_regexes,
        help='List of regex for inputted files when checking for version #')

    _a('hookargs', nargs=argparse.REMAINDER,
        help='Positional args which a git hook may provide, we ignore these')

    args = arg_parser.parse_args()

    LOG.setLevel(_log_name_to_level(args.log_level))
    LOG.debug(args)

    if args.install_hook:
        install_hook(args.install_hook)

    elif args.update:
        do_update(args.update)

    else:
        do_check(
            args.base, args.current, args.version_file, args.version_regex,
            args.files, args.file_regexes)


if __name__ == '__main__':
    main()