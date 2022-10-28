#!.venv/bin/python
r'''
Version Checker Utility: 0.2.2-beta.12
Python utility designed to facilitate version file checks & updates.
Assumes git and prefers bump2version.
Sync files containing raw version text, and verify they get bumped from a git base location.

Usage:
    version_checker.py -h
    version_checker.py -e
    version_checker.py --readme
    version_checker.py -l debug
    VERSION_BASE=origin/non-main version_checker
    version_checker.py -v version.txt -r '([0-9]+\.?){3}'
    version_checker.py -v version.txt -r '([0-9]+\.?){3}?(\-([a-z]+)\.(\d+))'
    version_checker.py -v version.txt -f openapi-spec.json --file-regexes 'version.: \d\.\d\.\d'

Can be used as a simple dev script, or a git-hook:
    version_checker -i pre-push

To make full-use of this tool, create a .bumpversion.cfg!
    see github.com/c4urself/bump2version
'''

import argparse
import logging
import os
import sys

import git

from version_checker.constants import LOG_NAME, CONFIG_FILE, BASE, CURRENT, REPO_PATH, FILES, \
                                      VERSION_FILE, VERSION_REGEX, FILE_REGEXES, EXAMPLE_CONFIG, \
                                      README_CONTENTS
from version_checker.utils import get_base_commit, do_check, do_update, install_hook, \
                                  get_bumpversion_config


logging.basicConfig(stream=sys.stdout, level=logging.INFO)
LOG = logging.getLogger(LOG_NAME)


def _get_repo(repo_path=REPO_PATH):
    '''Helper to verify a repo and return the git.Repo object'''
    try:
        return git.Repo(repo_path)
    except git.exc.InvalidGitRepositoryError:
        LOG.critical('This utility must be run from the root of a git repository!')
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


# main method
def main():
    '''Main function for version check/update stuff.'''
    # Note: a meld of RawTextHelpFormatter + ArgumentDefaultsHelpFormatter seems appropriate
    arg_parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawTextHelpFormatter)

    # verify the runlocation has a git repo
    repo = _get_repo(REPO_PATH)

    # prior to argument parsing etc., attempt to parse bumpversion config
    files, file_regexes = FILES, FILE_REGEXES
    if os.path.exists(CONFIG_FILE) and os.path.isfile(CONFIG_FILE):
        files, file_regexes = get_bumpversion_config(cfg_file=CONFIG_FILE)
    else:
        LOG.warning('bumpversion configs not found, skipping...')

    _a = arg_parser.add_argument

    _a('--example-config', '-e', action='store_true',
       help='Print an example .bumpversion.cfg to stdout')
    _a('--readme', action='store_true',
       help='Print the repository Readme to stdout')
    _a('--version', action='store_true',
       help='Print the version of the version_checker utility itself to stdout')

    _a('--install-hook', '-i', choices=['pre-push'], default=None,
       help='Install version_checker as a git hook (works best with .bumpconfig.cfg)')
    _a('--update', '-u', choices=['major', 'minor', 'patch'], default=None,
       help='Update versions via bump2version, assumes .bumpconfig.cfg')
    _a('--log-level', '-l', choices=['info', 'debug', 'warning', 'error'], default='info',
       help='Set the log level for the application')

    _a('--base', '-b', type=str, default=BASE,
       help='Branch in version control to check against. Tries origin/main & origin/master if None')
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

    if args.version:
        LOG.info('Version Checker Utility: 0.2.2-beta.12')

    elif args.example_config:
        LOG.info('Here is an example config you could tailor, then paste into '
                 '.bumpversion.cfg: \n%s', EXAMPLE_CONFIG)

    elif args.readme:
        LOG.info('\n%s', README_CONTENTS)

    elif args.install_hook:
        install_hook(args.install_hook)

    elif args.update:
        do_update(args.update)

    else:
        # for brevity & pylint, package version file & regex with others, pop later...
        files = [args.version_file] + args.files
        file_regexes = [args.version_regex] + args.file_regexes
        base_commit = get_base_commit(repo, args.base)
        do_check(base_commit, repo.commit(args.current), files, file_regexes)


if __name__ == '__main__':
    main()
