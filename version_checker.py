#!.venv/bin/python
'''
Version Helper
Python utility designed to facilitate version file checks & updates
    ln -s $(pwd)/version_checker.py $(pwd)/.git/hooks/pre-push
'''

import argparse
import git
import logging
import re
import sys


# globals & default configs
REPO = git.Repo('.')

logging.basicConfig(stream=sys.stdout, level=logging.INFO)
LOG = logging.getLogger('(versioner)')

BASE = 'origin/master'
CURRENT = 'HEAD'
VERSION_FILE = 'version.txt'
VERSION_REGEX = r'([0-9]+\.?){3}'
FILES = ['openapi-spec.json', 'kustomize/base/service.yaml']
FILE_REGEXES = [rf'"version":\s"{VERSION_REGEX}"', VERSION_REGEX]

# bash color help for flair
NO_COLOR = "\033[0m"
GREEN = "\033[0;92m"
RED = "\033[0;91m"
_red = lambda s: f'{RED}{s}{NO_COLOR}'
_grn = lambda s: f'{GREEN}{s}{NO_COLOR}'
OK = _grn('ok')
ERROR = _red('error')


# helpers
def _commit_file(fcommit, fpath):
    '''Helper (shorthand) to extract file contents at a specific commit'''
    return (fcommit.tree / fpath).data_stream.read().decode()


def _ok(msg):
    '''Helper to print out an ok message'''
    LOG.info(f'{msg}... {OK}')


def _error(msg):
    '''Helper to print out an error message and exit (1)'''
    LOG.error(f'{msg}... {ERROR}')
    LOG.error('Run with "--log-level debug" for more detail')
    LOG.error('''
        Otherwise, try bumping your versions i.e.
            git checkout origin/master -- version.txt
            bump2version patch version.txt openapi-spec.json kustomize/base/service.yaml --current-version $(cat version.txt) --allow-dirty
    ''')
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

    base_commit = REPO.commit(base)
    current_commit = REPO.commit(current)

    # files that were modified
    base_commit = REPO.commit(base)
    current_commit = REPO.commit(current)
    diffs = list(base_commit.diff(current_commit).iter_change_type('M'))

    # filter the changes for the base version file, empty list if not found
    version_file_diff = list(filter(lambda d: d.a_path == version_file, diffs))
    if version_file_diff:
        _ok(f'{version_file} change detected')
    else:
        _error(f'{version_file} change not detected')

    # attempt to parse out new & old version from inputted version_file
    try:
        old_file = _commit_file(base_commit, version_file)
        old = re.search(version_regex, old_file).group(0)

        new_file = _commit_file(current_commit, version_file)
        new = re.search(version_regex, new_file).group(0)
    except AttributeError as e:
        LOG.error(e)
        _error(f'could not find {version_regex} in {version_file}')
    
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

    errs = []
    for f, r in zip(files, file_regexes):
        matches = re.search(r, _commit_file(current_commit, f))
        if not matches or new not in matches.group(0):
            errs.append(f'{f} needs to match {version_file}!')
        elif matches:
            LOG.debug(f'{f}: {matches.group(0)}')
        else:
            LOG.debug(f'{f}: {matches}')
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

    _error('arbitrary exit 1 till we are done testing')


if __name__ == '__main__':
    main()

