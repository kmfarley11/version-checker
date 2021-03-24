#!.venv/bin/python
'''
Version Helper
Python utility designed to facilitate version file checks & updates
    ln -s $(pwd)/version_checker.py $(pwd)/.git/hooks/pre-push
'''

import argparse
import logging
import re
import subprocess
import sys


# globals & default configs
logging.basicConfig(stream=sys.stdout, level=logging.INFO)
LOG = logging.getLogger('(versioner)')

BASE = 'origin/master'
CURRENT = 'HEAD'
VERSION_FILE = 'version.txt'
VERSION_REGEX = r'([0-9]+\.?){3}'
FILES = ['openapi-spec.json', 'kustomize/base/service.yaml']
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
def _bash(cmd):
    '''Helper to run quick bash command and return its shell output'''
    return subprocess.check_output(cmd, shell=True).decode()


def _ok(msg):
    '''Helper to print out an ok message'''
    LOG.info(f'{msg}... {OK}')


def _error(msg):
    '''Helper to print out an error message and exit (1)'''
    LOG.error(f'{msg}... {ERROR}')
    sys.exit(1)


def _log_name_to_level(name):
    '''Helper to convert inputted log'''
    if name.lower() == 'debug':
        return logging.DEBUG
    elif name.lower() == 'info':
        return logging.INFO
    elif name.lower() == 'warning':
        return logging.WARNING
    elif name.lower() == 'error':
        return logging.ERROR
    else:
        raise NotImplementedError(f'log level {name} not found')


# utility functions
def do_check(base, current, version_file, version_regex, files, file_regexes):
    '''Checking functionality

    verify the local version has been incremented from the base branch
    '''
    LOG.debug(f'{base}, {current}, {version_file}, {version_regex}, {files}')
    LOG.debug(f'{file_regexes}')

    changelist = _bash(f'git diff --name-only {base}..{current}')

    if version_file in changelist:
        _ok(f'{version_file} change detected')
    else:
        _error(f'{version_file} change not detected')

    changes = _bash(f'git diff {base}..{current} -- {version_file}')
    LOG.debug(changes)

    try:
        # [1:] cuts of prefix +/- from git
        old = re.search(fr'\-{version_regex}', changes).group(0)[1:]
        new = re.search(fr'\+{version_regex}', changes).group(0)[1:]
        LOG.info(f'\told version = {old}')
        LOG.info(f'\tnew version = {new}')
    except Exception:
        # TODO catch specific regex/access errors only...
        _error(f'could not find {version_regex} in {version_file}')

    if old < new:
        _ok('new version larger than old')
    else:
        _error('new version smaller than old')

    if len(file_regexes) != len(files):
        LOG.warning(
            f'Inputted file regexes didnt match file list size, '
            f'defaulting to {version_regex}')
        file_regexes = [version_regex] * len(files)

    errs = []
    for f in files: # f, r in zip(files, file_regexes)
        contents = _bash(f'git show {current}:{f}')
        if old in contents or new not in contents:
            errs.append(f'{f} needs to match {version_file}!')
    if errs:
        err_txt = '\n\t'.join(errs)
        _error(f'not all files are correct\n\t{err_txt}')
    else:
        _ok('all files matched the correct version')


def do_update():
    '''Updating functionality

    enact version updates for local files
    '''
    raise NotImplementedError('Updates not available yet')


# main method
def main():
    '''Main function for version check/update stuff.'''
    arg_parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawTextHelpFormatter)

    # this is useful as a command line utility with all the inputs
    #   but if many files with unique regexes it'd get cluttered real fast
    #   consider configargparse to allow some config options instead of cli?
    # for now, defaulting to global vars prolly works, maybe default to env?
    _a = arg_parser.add_argument
    _a('--do-update', '-u', action='store_true',
        help='Update (increment) the patch version for the repo')
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

    if not args.do_update:
        do_check(
            args.base, args.current, args.version_file, args.version_regex,
            args.files, args.file_regexes)
    else:
        do_update()


if __name__ == '__main__':
    main()

