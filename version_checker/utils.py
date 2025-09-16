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

import semver
from git.exc import BadName

from version_checker.constants import LOG_NAME, CONFIG_FILE, OK, ERROR, BASES_IF_NONE


LOG = logging.getLogger(LOG_NAME)


# utility functions
def get_base_commit(repo, base_input):
    '''Obtain the base commit to check against

    Uses an inputted GitPython repo object (git.Repo) to retrieve the base commit

    If base_input is None, attempts the possibilities listed in BASE_IF_NONE
        (origin/main & origin/master)

    Returns GitPython commit object if successful, errors if invalid
    '''
    if not repo:
        return _error('Invalid GitPython repo provided!')

    if base_input:
        return repo.commit(base_input)

    LOG.info('No VERSION_BASE provided, trying: %s', ', '.join(BASES_IF_NONE))
    for possible_base in BASES_IF_NONE:
        try:
            base_commit = repo.commit(possible_base)
            LOG.info('Using %s', possible_base)
            return base_commit
        except BadName:
            LOG.warning('%s not detected', possible_base)
    return _error('No VERSION_BASE provided, and default bases not valid!')


def compare_versions(old_version_str, new_version_str, abort=False):
    '''Helper to compare two version strings via semver-python

    Positional arguments
    old_version_str     -- raw string of old version to compare against
    new_version_str     -- raw string of new version to compare

    Keyword arguments
    abort               -- boolean indicating whether to sys.exit(1) in case of errors

    Returns boolean indicating success. May sys.exit(1) if abort is set to True
    '''
    old_version, new_version = None, None
    try:
        if not old_version_str:
            LOG.warning('Old version empty, assuming brand new version')
        else:
            old_version = semver.VersionInfo.parse(old_version_str)
        new_version = semver.VersionInfo.parse(new_version_str)
    except ValueError as _exc:
        LOG.warning('One or more of the version files was un-parsable:', exc_info=_exc)

    # verify the change is productive
    LOG.info('\tOld version = %s', old_version)
    LOG.info('\tNew version = %s', new_version)

    if new_version is None:
        _error('New version not detected!', abort=abort)
        return False

    if old_version is None:
        _ok('Old version not detected, assuming first commit with new version')
        return True

    if old_version < new_version:
        _ok('New version larger than old')
        return True

    _error('New version needs to be greater than old! See semver.org', abort=abort)
    return False


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
    LOG.debug(
        '%s, %s, %s, %s', str(base_commit), str(current_commit), str(files), str(file_regexes))

    if not files or not file_regexes:
        return _error('No files or regexes provided!', abort=True)

    version_file = files.pop(0)
    version_regex = file_regexes.pop(0)

    cwd_repo_path = os.path.relpath(os.getcwd(), current_commit.repo.working_tree_dir)
    LOG.info('Checking for changes within path %s/', cwd_repo_path)

    scoped_diff = base_commit.diff(current_commit, cwd_repo_path)
    if len(scoped_diff) == 0:
        _ok('No changes detected between current commit and base commit')
        return True

    old, new = _parse_versions_from_version_file(
        base_commit, current_commit, version_file, version_regex)

    compare_versions(old, new, abort=True)

    if len(files) == 0:
        LOG.warning('No extra file checking inputted, only verfied %s', version_file)

    file_regexes = _resolve_files_to_regexes_mismatch(files, file_regexes, version_regex)

    error_detected = False
    LOG.debug('Checking %s against regexes %s', str(files), str(file_regexes))
    for _f, _r in zip(files, file_regexes):
        file_version = search_commit_file(current_commit, _f, _r, abort=False)
        if new not in file_version:
            _error(f'\t{_f} needs to match {version_file}!', abort=False)
            error_detected = True
        else:
            LOG.debug('\t%s: %s', _f, file_version)
    if error_detected:
        return _error('Not all files are correct', abort=True)

    _ok('All files matched the correct version')
    return True


def do_update(version_part, options='--allow-dirty'):
    '''Enact version updates for local files

    Just calls out to bump2version, relies on a .bumpversion.cfg
    '''
    cmd = f'bump2version {version_part} {options}'
    LOG.info("Attempting command: '%s'", cmd)
    LOG.info(subprocess.check_output(cmd, shell=True).decode())


def install_hook(hook):
    '''Symlink version_checker as a git-hook

    Verifies it has been installed & symlinks the binpath to a githook
    '''
    LOG.info('verifying version_checker is installed...!')

    prog_path = shutil.which('version_checker')
    if not prog_path:
        _error('Issue getting version_checker bin path, is it installed?!', use_long_text=False)
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
        LOG.warning('Invalid bumpversion config detected %s skipping cfg parse...', cfg_file)
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
    LOG.debug('Toplevel (bumpversion) dict: %s', str(replace_dict))

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
                # the key is probably current_version, we need to make it {current_version}...
                fregex = fregex.replace('{' + str(_k) + '}', _v)
        file_regexes.append(fregex)
        LOG.debug('Added %s for %s', fregex, _f)

    # make files relative to cwd if .bumpversion.cfg is not in cwd
    config_dirs = os.path.dirname(cfg_file)
    files = [os.path.join(config_dirs, f) if config_dirs else f for f in files]

    LOG.info('Successfully parsed %s', cfg_file)
    return files, file_regexes


def search_commit_file(git_commit, fpath, search_regex, abort=True):
    '''Search a file in a source tree for some regex pattern

    Returns search text or empty string
    '''
    try:
        commit_file = _get_commit_file(git_commit, fpath)
        return _search_or_error(search_regex, commit_file, abort=abort)
    except KeyError:
        _error(f'File {fpath} not found in the provided commit ({str(git_commit)})!', abort=abort)
    except AttributeError:
        _error(f'Provided commit ({str(git_commit)}) is not valid!', abort=abort)
    return ''


# (protected) helpers

def _parse_versions_from_version_file(base_commit, current_commit, version_file, version_regex):
    '''Helper to parse out old & new versions from the base & current commits
    
    Returns old, new version strings'''
    if not _has_commit_file(current_commit, version_file):
        _error(
            f"File {version_file} not found in current commit ({str(current_commit)})!",
            abort=True,
        )

    if not _has_commit_file(base_commit, version_file):
        LOG.warning(
            "File %s not found in base commit (%s), assuming new file...",
            version_file,
            str(base_commit),
        )
        new = search_commit_file(current_commit, version_file, version_regex)
        return "", new

    # attempt to parse out new & old version from inputted version_file
    _ok(f'Parsed versions from {version_file} for base commit and current commit')
    old = search_commit_file(base_commit, version_file, version_regex, abort=True)
    new = search_commit_file(current_commit, version_file, version_regex, abort=True)
    return old, new

def _resolve_files_to_regexes_mismatch(files, file_regexes, default_regex):
    '''Helper to resolve mismatches between files & file_regexes lengths

    Returns updated file_regexes list'''
    resolved_file_regexes = file_regexes
    if len(file_regexes) < len(files):
        LOG.warning(
            'Inputted file regexes didnt match file list size, '
            'defaulting to %s for remaining files', default_regex)
        missing_regexes_count = len(files) - len(file_regexes)
        missing_regexes = [default_regex] * missing_regexes_count
        resolved_file_regexes = file_regexes + missing_regexes
    elif len(file_regexes) > len(files):
        LOG.warning(
            'Inputted file regexes didnt match file list size, '
            'ignoring extra regexes')
        resolved_file_regexes = file_regexes[:len(files)]
    return resolved_file_regexes


def _get_commit_file(fcommit, fpath):
    '''Helper (shorthand) to extract file contents at a specific commit'''
    return (fcommit.tree / fpath).data_stream.read().decode()

def _has_commit_file(fcommit, fpath):
    '''Helper (shorthand) to check if a file exists at a specific commit'''
    try:
        fcommit.tree.join(fpath)
        return True
    except KeyError:
        return False

def _search_or_error(regex_str, to_search_str, abort=True):
    '''Helper to do a regex search and return matches, exits program on error'''
    retval = ''
    result = re.search(regex_str, to_search_str)
    LOG.debug('Inputted: "%s"', to_search_str)
    LOG.debug('Search txt: "%s"', regex_str)
    if result:
        retval = result.group(0)
    elif regex_str in to_search_str:
        LOG.debug('Regex parse failed, but raw string compare succeeded for "%s"', regex_str)
        retval = regex_str
    else:
        _error(f'Could not find "{regex_str}" in inputted string', abort=abort)
    return retval


def _ok(msg):
    '''Helper to print out an ok message'''
    LOG.info('%s... %s', msg, OK)


def _error(msg, abort=True, use_long_text=True):
    '''Helper to print out an error message and exit (1)

    Generically returns empty string, if not aborting via sys.exit...
    '''
    LOG.error('%s... %s', msg, ERROR)
    if abort:
        LOG.error('Run "version_checker --log-level debug" for more detail')
        if use_long_text:
            LOG.error('''
                Otherwise, try bumping your versions i.e.
                    bump2version patch --help
                    bump2version patch --allow-dirty
                    bump2version patch --commit

                Note: this checker will only succeed if the latest commit contains updated versions
                To bypass it as a hook try using --no-verify but this is NOT preferred...

                If your files are out-of sync, it is recommended to revert the files per the base
                Then the bump2version program can update them all synchronously
            ''')
        sys.exit(1)
    return ''
