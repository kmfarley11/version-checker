#!.venv/bin/python
r'''
Version Helper
Python utility designed to facilitate version file checks & updates.
Assumes git and prefers bump2version.
Sync files containing raw version text, and verify they get bumped from a git base location.

Usage:
    ./version_checker.py -h
    ./version_checker.py -l debug
    ./version_checker.py -v version.txt -r '([0-9]+\.?){3}'
    ./version_checker.py -v version.txt -f openapi-spec.json --file-regexes 'version.: \d\.\d\.\d'

Can be used as a simple dev script, or a git-hook:
    ln -s $(pwd)/version_checker.py $(pwd)/.git/hooks/pre-push

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
REPO = git.Repo('.')

logging.basicConfig(stream=sys.stdout, level=logging.INFO)
LOG = logging.getLogger('(version_checker)')

# TODO: package it... make sure works with setup.cfg?

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


# helpers
def _load_bumpversion_config(cfg_file):
    '''Helper to parse bumpversion configurations, overrides globals prior to argparse'''
    if not os.path.exists(cfg_file) or not os.path.isfile(cfg_file):
        LOG.warning(f'bumpversion config {cfg_file} not found, skipping...')
        return False

    with open(cfg_file, 'r') as _f:
        cfg_raw = _f.read()

    cfg = configparser.ConfigParser()
    cfg.read_string(cfg_raw)

    if not cfg.has_section('bumpversion') or not cfg.has_option('bumpversion', 'current_version'):
        LOG.warning(f'invalid bumpversion config detected {cfg_file}')
        LOG.warning('see github.com/c4urself/bump2version for more details, skipping cfg parse...')
        return False

    global FILE_REGEXES
    global FILES
    FILES = [s.split(':')[-1] for s in cfg.sections() if ':file:' in s]
    for _f in FILES:
        fregex = VERSION_REGEX
        section = f'bumpversion:file:{_f}'
        if cfg.has_option(section, 'search'):
            fregex = cfg.get(section, 'search').replace('{current_version}', VERSION_REGEX)
        FILE_REGEXES.append(fregex)

    LOG.info(f'Successfully parsed {cfg_file}')
    return True


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
                .venv/bin/bump2version patch --allow-dirty
                .venv/bin/bump2version patch --commit
                .venv/bin/bump2version patch version.txt \\
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
def do_check(base, current, version_file, version_regex, files, file_regexes):
    '''Checking functionality

    verify the local versions have been incremented from the base branch
    '''
    LOG.debug(f'{base}, {current}, {version_file}, {version_regex}, {files}')
    LOG.debug(f'{file_regexes}')

    # get the files that were modified
    base_commit = REPO.commit(base)
    current_commit = REPO.commit(current)
    diffs = list(base_commit.diff(current_commit).iter_change_type('M'))

    # filter the changes for the base version file, empty list if not found
    version_file_diff = list(filter(lambda d: d.b_path == version_file, diffs))
    new, old = '', ''

    if version_file not in base_commit.tree and version_file in current_commit.tree:
        LOG.warning(f'{version_file} not found in base ({base}), assuming new file...')
        new = _search_or_error(version_regex, _get_commit_file(current_commit, version_file))
    elif not version_file_diff:
        _error(f'{version_file} change not detected')
    else:
        # attempt to parse out new & old version from inputted version_file
        _ok(f'{version_file} change detected')
        old_file = _get_commit_file(base_commit, version_file)
        old = _search_or_error(version_regex, old_file)

        new_file = _get_commit_file(current_commit, version_file)
        new = _search_or_error(version_regex, new_file)

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
        matches = re.search(_r, _get_commit_file(current_commit, _f))
        if not matches or new not in matches.group(0):
            _error(f'\t{_f} needs to match {version_file}!', abort=False)
            error_detected = True
        elif matches:
            LOG.debug(f'\t{_f}: {matches.group(0)}')
        else:
            LOG.debug(f'\t{_f}: {matches}')
    if error_detected:
        _error('not all files are correct')

    _ok('all files matched the correct version')


def do_update(part, options='--allow-dirty'):
    '''Enact version updates for local files

    Just calls out to bump2version, relies on a .bumpversion.cfg or setup.cfg
    '''
    cmd = f'.venv/bin/bump2version {part} {options}'
    LOG.info(f"attempting command: '{cmd}'")
    LOG.info(_bash(cmd))


# main method
def main():
    '''Main function for version check/update stuff.'''
    # Note: a meld of RawTextHelpFormatter + ArgumentDefaultsHelpFormatter seems appropriate
    arg_parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawTextHelpFormatter)

    # prior to argument parsing etc., attempt to parse bumpversion config
    if not _load_bumpversion_config(CONFIG_FILE):
        _load_bumpversion_config(CONFIG_FILE_ALT)

    _a = arg_parser.add_argument
    _a('--update', '-u', choices=['major', 'minor', 'patch'], default=None,
        help='Update versions via bump2version, assumes .bumpconfig.cfg or setup.cfg')
    _a('--log-level', '-l', choices=['info', 'debug', 'warning', 'error'],
        default='info', help='Set the log level for the application')

    _a('--base', '-b', type=str, default=BASE,
        help='Branch in version control to check against')
    _a('--current', '-c', type=str, default=CURRENT,
        help='Git tag/branch/hash to verify')
    _a('--version-file', '-v', type=str, default=VERSION_FILE,
        help='File to base all version checks against')
    _a('--version-regex', '-r', type=str, default=VERSION_REGEX,
        help='Regex to extract version out of version file')

    _a('--files', '-f', nargs='+', default=FILES,
        help='Files to check version number')
    _a('--file-regexes', nargs='+', default=FILE_REGEXES,
        help='List of regex for inputted files when checking for version #')

    _a('hookargs', nargs=argparse.REMAINDER,
        help='Positional args which a git hook may provide, we ignore these')

    args = arg_parser.parse_args()

    LOG.setLevel(_log_name_to_level(args.log_level))
    LOG.debug(args)

    if not args.update:
        do_check(
            args.base, args.current, args.version_file, args.version_regex,
            args.files, args.file_regexes)
    else:
        do_update(args.update)


if __name__ == '__main__':
    main()
