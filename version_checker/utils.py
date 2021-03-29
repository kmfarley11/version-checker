'''
Utils for the version checker to work its magic

Contains common public-exposed functions for cli to use etc.
'''
import configparser
import logging
import os
import re
import shutil
import subprocess
import sys

from version_checker.constants import LOG_NAME, CONFIG_FILE, OK, ERROR


LOG = logging.getLogger(LOG_NAME)


# utility functions
def do_check(base_commit, current_commit, files, file_regexes):
    '''Checking functionality

    Verified the current file versions have been incremented from the base branch

    Positional arguments
    base_commit     -- GitPython commit object for base hash to check against
    current_commit  -- GitPython commit object for current hash to check
    files           -- list of file paths with hardcoded versions ([0] = file to synchronize)
    file_regexes    -- list of regexes to check against relative file (in files)

    Returns True if check succeeded
    '''
    LOG.debug(f'{base_commit}, {current_commit}, {files}, {file_regexes}')

    if not files or not file_regexes:
        return _error('No files or regexes provided!')

    version_file = files.pop(0)
    version_regex = file_regexes.pop(0)

    # filter the changelist for the base version file, empty list if not found
    version_file_diff = list(
        filter(
            lambda d: d.b_path == version_file,
            base_commit.diff(current_commit).iter_change_type('M')))
    new, old = '', ''

    if version_file not in base_commit.tree and version_file in current_commit.tree:
        LOG.warning(f'{version_file} not found in base ({base_commit}), assuming new file...')
        new = search_commit_file(current_commit, version_file, version_regex)
    elif not version_file_diff:
        return _error(f'{version_file} change not detected')
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
        return _error('new version smaller than old')

    if len(files) == 0:
        LOG.warning(f'No extra file checking inputted, only verfied {version_file}')
        return True

    # verify any other inputted files match the version_file's contents
    if len(file_regexes) != len(files):
        LOG.warning(
            f'Inputted file regexes didnt match file list size, '
            f'defaulting to {version_regex}')
        file_regexes = [version_regex] * len(files)

    error_detected = False
    LOG.debug(f'checking {files} against regexes {file_regexes}')
    for _f, _r in zip(files, file_regexes):
        file_version = search_commit_file(current_commit, _f, _r, abort=False)
        if new not in file_version:
            _error(f'\t{_f} needs to match {version_file}!', abort=False)
            error_detected = True
        else:
            LOG.debug(f'\t{_f}: {file_version}')
    if error_detected:
        return _error('not all files are correct')

    _ok('all files matched the correct version')
    return True


def do_update(version_part, options='--allow-dirty'):
    '''Enact version updates for local files

    Just calls out to bump2version, relies on a .bumpversion.cfg
    '''
    cmd = f'bump2version {version_part} {options}'
    LOG.info(f"attempting command: '{cmd}'")
    LOG.info(_bash(cmd))


def install_hook(hook):
    '''Symlink version_checker as a git-hook

    Verifies it has been installed & symlinks the binpath to a githook
    '''
    LOG.info('verifying version_checker is installed...!')

    prog_path = shutil.which('version_checker')
    if not prog_path:
        _error('issue getting version_checker bin path, is it installed?!', use_long_text=False)
        return

    hook_path = os.path.abspath(os.path.join('.', '.git', 'hooks', hook))
    if os.path.exists(hook_path) or os.path.islink(hook_path):
        _error(f'Git hook "{hook_path}" already exists!\n\tRemove the existing hook '
                'and re-try if further action is desired.', use_long_text=False)
    else:
        os.symlink(prog_path, hook_path)
        _ok(f'"{prog_path}", installed to "{hook_path}"')


def get_bumpversion_config(cfg_file=CONFIG_FILE):
    '''Helper to parse bumpversion configurations

    returns file, file regexes, and current version to be checked
    '''
    def _warn_invalid():
        # generator to shorthand warn the user of an invalid config
        LOG.warning(f'invalid bumpversion config detected {cfg_file} skipping cfg parse...')
        LOG.warning('version_checker --example-config')
        LOG.warning('or see github.com/c4urself/bump2version for more details')
        return [], []

    cfg = configparser.ConfigParser()

    try:
        cfg.read(cfg_file)
    except configparser.MissingSectionHeaderError:
        return _warn_invalid()

    if not cfg.has_section('bumpversion') or not cfg.has_option('bumpversion', 'current_version'):
        return _warn_invalid()

    current_version = cfg.get('bumpversion', 'current_version')
    toplevel_options = cfg.options('bumpversion')
    replace_dict = {o: cfg.get('bumpversion', o) for o in toplevel_options}
    LOG.debug(f'toplevel (bumpversion) dict: {replace_dict}')

    file_regexes = []
    files = [s.split(':')[-1] for s in cfg.sections() if ':file:' in s]
    for _f in files:
        fregex = current_version
        section = f'bumpversion:file:{_f}'
        # we only update if a search option is provided
        if cfg.has_option(section, 'search'):
            fregex = cfg.get(section, 'search')
            # this'd be easier if bump2version used interpolation but they dont...
            #   so we need to replace any {keys} at the bumpversion level with the values provided
            for _k, _v in replace_dict.items():
                fregex = fregex.replace('{%s}' % _k, _v)
        file_regexes.append(fregex)
        LOG.debug(f'Added {fregex} for {_f}')

    LOG.info(f'Successfully parsed {cfg_file}')
    return files, file_regexes


def search_commit_file(git_commit, fpath, search_regex, abort=True):
    '''Search a file in a source tree for some regex pattern

    Returns search text or empty string
    '''
    try:
        commit_file = _get_commit_file(git_commit, fpath)
        return _search_or_error(search_regex, commit_file, abort=abort)
    except KeyError:
        _error(f'file {fpath} not found in the provided git.Commit {git_commit}', abort=abort)
    except AttributeError:
        _error(f'provided git.Commit {git_commit} is not valid!', abort=abort)
    return ''


# (protected) helpers
def _bash(cmd):
    '''Helper to run quick bash command and return its shell output'''
    return subprocess.check_output(cmd, shell=True).decode()


def _get_commit_file(fcommit, fpath):
    '''Helper (shorthand) to extract file contents at a specific commit'''
    return (fcommit.tree / fpath).data_stream.read().decode()


def _search_or_error(regex_str, to_search_str, abort=True):
    '''Helper to do a regex search and return matches, exits program on error'''
    retval = ''
    result = re.search(regex_str, to_search_str)
    LOG.debug(f'inputted: "{to_search_str}"')
    LOG.debug(f'search txt: "{regex_str}"')
    if result:
        retval = result.group(0)
    elif regex_str in to_search_str:
        LOG.debug(f'regex parse failed, but raw string compare succeeded for "{regex_str}"')
        retval = regex_str
    else:
        _error(f'could not find "{regex_str}" in inputted string', abort=abort)
    return retval


def _ok(msg):
    '''Helper to print out an ok message'''
    LOG.info(f'{msg}... {OK}')


def _error(msg, abort=True, use_long_text=True):
    '''Helper to print out an error message and exit (1)

    Generically returns empty string, if not aborting via sys.exit...
    '''
    LOG.error(f'{msg}... {ERROR}')
    if abort:
        LOG.error('Run with "--log-level debug" for more detail')
        if use_long_text:
            LOG.error('''
                Otherwise, try bumping your versions i.e.
                    bump2version patch --allow-dirty
                    bump2version patch --help

                Note: this checker will only succeed if the latest commit contains updated versions
                To bypass it as a hook try using --no-verify but this is NOT preferred...

                If your files are out-of sync, it is recommended to revert the files per the base
                Then the bump2version program can update them all synchronously
            ''')
        sys.exit(1)
    return ''
