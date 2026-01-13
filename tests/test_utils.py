"""
def test_get_base_commit_handles_valid_input_value():
    fake_repo = mock.Mock()
    fake_repo.commit.return_value = 'expect_me'
    fake_base = 'origin/idk'
    retval = vc_utils.get_base_commit(fake_repo, fake_base)
    assert retval == 'expect_me'
    fake_repo.commit.assert_called_once_with(fake_base)
Pytests for the public functions of the version_checker code
"""

import os
import mock
import pytest

import git

import version_checker.utils as vc_utils
import version_checker.constants as _constants
from version_checker import __version__ as _vc_version


# region test vars
# test file for probing different configs
NOTFOUND_CFG_FILE = "tests/notfound.txt"
MALFORMATTED_CFG_FILE = "tests/bad_config_malformatted.txt"
NOSECTIONS_CFG_FILE = "tests/bad_config_sections.txt"
EMPTY_CFG_FILE = "tests/ok_config_empty.txt"
VALID_CFG_FILE = ".bumpversion.cfg"

# based on this repos valid cfg, list the files we expect to use
#   and whether to expect them to default (True) or have a custom search (False)
KNOWN_FILE_DEFAULTS = {
    "Readme.md": False,
    "setup.cfg": False,
    "version_checker/__init__.py": True,
    "version_checker/cli.py": False,
    "version_checker/examples/.env": False,
    "version_checker/examples/version.txt": True,
    "version_checker/examples/kustomize/base/service.yaml": True,
    "version_checker/examples/openapi-spec.json": False,
    "version_checker/examples/pom.xml": False,
}

BAD_VERSION = "0.0.0"


class DiffStub(list):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.iter_change_type = mock.MagicMock()


def create_mock_tree(in_files: str) -> tuple[git.Tree, git.Blob]:
    """Our source uses the join op to verify and extract file from the git tree

    We need those methods to resolve in our test code for it to work as expected
    """
    fake_tree = mock.MagicMock(spec=git.Tree)
    fake_tree.in_files = in_files
    fake_blob = mock.MagicMock(spec=git.Blob)

    def _fake_tree_join(in_file: str):
        if in_file in fake_tree.in_files:
            fake_blob.b_path = in_file
            return fake_blob
        raise KeyError

    fake_tree.join = _fake_tree_join
    fake_tree.__truediv__ = _fake_tree_join
    return fake_tree, fake_blob


# endregion


# region CheckerPath tests

def test_checker_path():
    path = vc_utils.CheckerPath("./", "version_checker/__init__.py")

    assert path.repo_root_path == os.path.abspath("./")
    assert path.abs_path == os.path.abspath("version_checker/__init__.py")
    assert path.cwd_path == "version_checker/__init__.py"
    assert path.repo_path == "version_checker/__init__.py"

# endregion


# region get_base_commit tests
def test_get_base_commit_errors_for_bad_repo(mocker):
    patched_sys = mocker.patch.object(vc_utils, "sys")
    fake_repo = None
    fake_base = None
    retval = vc_utils.get_base_commit(fake_repo, fake_base)
    assert not retval
    patched_sys.exit.assert_called_once_with(1)


def test_get_base_commit_handles_valid_input_value():
    fake_repo = mock.Mock()
    fake_repo.commit.return_value = "expect_me"
    fake_base = "origin/idk"
    retval = vc_utils.get_base_commit(fake_repo, fake_base)
    assert retval == "expect_me"
    fake_repo.commit.assert_called_once_with(fake_base)


def test_get_base_commit_attempts_defaults_if_None():
    fake_repo = mock.Mock()
    fake_repo.commit.return_value = "expect_me"
    fake_base = None
    retval = vc_utils.get_base_commit(fake_repo, fake_base)
    assert retval == "expect_me"
    fake_repo.commit.assert_called_once_with(_constants.BASES_IF_NONE[0])


def test_get_base_commit_errors_for_no_valid_base(mocker):
    patched_sys = mocker.patch.object(vc_utils, "sys")
    fake_repo = mock.Mock()
    num_bases = len(_constants.BASES_IF_NONE)
    fake_repo.commit.side_effect = [git.exc.BadName("dne")] * num_bases
    fake_base = None
    retval = vc_utils.get_base_commit(fake_repo, fake_base)
    assert not retval
    fake_repo.commit.assert_has_calls(
        list(map(lambda b: mock.call(b), _constants.BASES_IF_NONE))
    )
    patched_sys.exit.assert_called_once_with(1)


# endregion


# region get_bumpversion_config tests
def test_get_bumpversion_config_handles_invalid_config():
    test_cfg_file = MALFORMATTED_CFG_FILE
    files, regexes = vc_utils.get_bumpversion_config(test_cfg_file)
    assert not files
    assert not regexes


def test_get_bumpversion_config_handles_no_bumpversion_settings():
    test_cfg_file = NOSECTIONS_CFG_FILE
    files, regexes = vc_utils.get_bumpversion_config(test_cfg_file)
    assert not files
    assert not regexes


def test_get_bumpversion_config_returns_nothing_if_no_files_detected():
    test_cfg_file = EMPTY_CFG_FILE
    files, regexes = vc_utils.get_bumpversion_config(test_cfg_file)
    assert not files
    assert not regexes

def test_get_bumpversion_config_returns_nothing_if_config_is_not_found():
    test_cfg_file = NOTFOUND_CFG_FILE
    files, regexes = vc_utils.get_bumpversion_config(test_cfg_file)
    assert not files
    assert not regexes

def test_get_bumpversion_config_handles_valid_config():
    test_cfg_file = vc_utils.CheckerPath(".", VALID_CFG_FILE)
    files, regexes = vc_utils.get_bumpversion_config(test_cfg_file)

    # verify we have files & regexes & match overall expected list size
    assert len(files) == len(KNOWN_FILE_DEFAULTS)
    assert len(regexes) == len(KNOWN_FILE_DEFAULTS)

    # verify all files are accounted for, and the ones without 'search' are defaulted
    for f, r in zip(files, regexes):
        f_str = str(f)
        assert f_str in KNOWN_FILE_DEFAULTS.keys()
        if KNOWN_FILE_DEFAULTS[f_str]:
            assert r == _vc_version
        else:
            assert r != _vc_version

def test_get_bumpversion_config_handles_valid_commit_config(mocker):
    test_cfg_file = vc_utils.CheckerPath(".", VALID_CFG_FILE)

    commit_mock = mock.MagicMock(spec=git.Commit)
    patched__has = mocker.patch.object(vc_utils, "_has_commit_file")
    patched__has.return_value = True
    patched__get = mocker.patch.object(vc_utils, "_get_commit_file")
    with open(test_cfg_file, "r", encoding="utf-8") as f:
        cfg_content = f.read()
    patched__get.return_value = cfg_content

    files, regexes = vc_utils.get_bumpversion_config(test_cfg_file, commit=commit_mock)

    # verify we have files & regexes & match overall expected list size
    assert len(files) == len(KNOWN_FILE_DEFAULTS)
    assert len(regexes) == len(KNOWN_FILE_DEFAULTS)

    # verify all files are accounted for, and the ones without 'search' are defaulted
    for f, r in zip(files, regexes):
        f_str = str(f)
        assert f_str in KNOWN_FILE_DEFAULTS.keys()
        if KNOWN_FILE_DEFAULTS[f_str]:
            assert r == _vc_version
        else:
            assert r != _vc_version

# endregion


# region search_commit_file tests
def test_search_commit_file_handles_invalid_file(mocker):
    # note __truediv__ -> '/' operator
    commit_mock = mock.MagicMock(spec=git.Commit)
    commit_mock.tree.__truediv__.side_effect = KeyError("file not found")

    patched_err = mocker.patch.object(vc_utils, "error")

    ret = vc_utils.search_commit_file(
        commit_mock, "fakefile", "fakesearch", abort=False
    )
    assert not ret
    patched_err.assert_called_once()


def test_search_commit_file_handles_invalid_commit(mocker):
    patched_err = mocker.patch.object(vc_utils, "error")

    # wrong type, will raise attribute error
    ret = vc_utils.search_commit_file(
        "fakecommit", "fakefile", "fakesearch", abort=False
    )
    assert not ret
    patched_err.assert_called_once()


def test_search_commit_file_handles_text_not_found(mocker):
    patched_err = mocker.patch.object(vc_utils, "error")
    patched__get = mocker.patch.object(vc_utils, "_get_commit_file")
    patched__get.return_value = "arbitrary text"

    # '_' represents dont care (patched out...)
    ret = vc_utils.search_commit_file("_", "_", "bad search text", abort=False)
    assert not ret
    patched_err.assert_called_once()


def test_search_commit_file_handles_regex_fail_but_rawtext_match(mocker):
    patched_err = mocker.patch.object(vc_utils, "error")
    patched__get = mocker.patch.object(vc_utils, "_get_commit_file")
    patched__get.return_value = "some content... no regex here[0-9]asdf!..."

    # '_' represents dont care (patched out...)
    ret = vc_utils.search_commit_file("_", "_", "no regex here[0-9]", abort=False)
    assert ret == "no regex here[0-9]"
    patched_err.assert_not_called()


def test_search_commit_file_handles_regex_success(mocker):
    patched_err = mocker.patch.object(vc_utils, "error")
    patched__get = mocker.patch.object(vc_utils, "_get_commit_file")
    patched__get.return_value = "some content... regex me here123!..."

    # '_' represents dont care (patched out...)
    ret = vc_utils.search_commit_file("_", "_", r"regex[\w\s]*[0-9]{3}", abort=False)
    assert ret == "regex me here123"
    patched_err.assert_not_called()


# endregion


# region install_hook tests
def test_install_hook_handles_vc_not_installed(mocker):
    patched_shutil = mocker.patch.object(vc_utils, "shutil")
    patched_shutil.which.return_value = ""

    patched_os = mocker.patch.object(vc_utils, "os")
    patched_err = mocker.patch.object(vc_utils, "error")

    vc_utils.install_hook("pre-push")

    patched_err.assert_called_once()
    patched_os.symlink.assert_not_called()


def test_install_hook_handles_hook_already_exists(mocker):
    patched_shutil = mocker.patch.object(vc_utils, "shutil")
    patched_err = mocker.patch.object(vc_utils, "error")
    patched_os = mocker.patch.object(vc_utils, "os")

    patched_os.path.islink.return_value = True

    vc_utils.install_hook("pre-push")

    patched_err.assert_called_once()
    patched_os.symlink.assert_not_called()


def test_install_hook_creates_link_if_dne(mocker):
    patched_shutil = mocker.patch.object(vc_utils, "shutil")
    patched_err = mocker.patch.object(vc_utils, "error")
    patched_os = mocker.patch.object(vc_utils, "os")

    patched_os.path.islink.return_value = False
    patched_os.path.exists.return_value = False

    vc_utils.install_hook("pre-push")

    patched_err.assert_not_called()
    patched_os.symlink.assert_called_once()


# endregion


# region do_update tests
def test_do_update_calls_bump2version(mocker):
    patched_sp = mocker.patch.object(vc_utils, "subprocess")
    vc_utils.do_update("minor")
    patched_sp.check_output.assert_called_once_with(
        "bump2version minor --allow-dirty", shell=True
    )


# endregion


# region do_check tests (coupled with compare_versions tests)
#   Note: not doing fully strict input validation, maybe eventually but the docstring
#   is pretty explicit about using GitPython
def test_do_check_handles_empty_file_list(mocker):
    patched_sys = mocker.patch.object(vc_utils, "sys")
    base_commit_mock = mock.MagicMock(spec=git.Commit)
    current_commit_mock = mock.MagicMock(spec=git.Commit)
    files = []
    file_regexes = ["0.0.1"]

    assert not vc_utils.do_check(
        base_commit_mock, current_commit_mock, files, file_regexes
    )
    patched_sys.exit.assert_called_once_with(1)


def test_do_check_handles_empty_file_regex_list(mocker):
    patched_sys = mocker.patch.object(vc_utils, "sys")
    base_commit_mock = mock.MagicMock(spec=git.Commit)
    current_commit_mock = mock.MagicMock(spec=git.Commit)
    files = ["version.txt"]
    file_regexes = []

    assert not vc_utils.do_check(
        base_commit_mock, current_commit_mock, files, file_regexes
    )
    patched_sys.exit.assert_called_once_with(1)


def test_do_check_handles_file_not_changed(mocker):
    patched_sys = mocker.patch.object(vc_utils, "sys")
    patched_ok = mocker.patch.object(vc_utils, "ok")
    base_commit_mock = mock.MagicMock(spec=git.Commit)
    current_commit_mock = mock.MagicMock(spec=git.Commit)
    files = ["version.txt"]
    file_regexes = ["0.0.1"]

    base_commit_mock.tree = ""
    base_commit_mock.diff.iter_change_type.return_value = ""

    assert vc_utils.do_check(base_commit_mock, current_commit_mock, files, file_regexes)
    patched_ok.assert_called_once()
    patched_sys.exit.assert_not_called()


def test_do_check_handles_file_changed_but_no_version_change(mocker):
    patched_sys = mocker.patch.object(vc_utils, "sys")
    patched_sys.exit.side_effect = RuntimeError("sys.exit called")
    base_commit_mock = mock.MagicMock(spec=git.Commit)
    current_commit_mock = mock.MagicMock(spec=git.Commit)
    blob_mock = mock.MagicMock(spec=git.Blob)
    blob_mock.b_path = "file.txt"

    old_ver = _vc_version
    new_ver = _vc_version

    patched_search = mocker.patch.object(vc_utils, "search_commit_file")
    patched_search.side_effect = [old_ver, new_ver]

    files = [vc_utils.CheckerPath(".", "version.txt")]
    file_regexes = [_vc_version]

    fake_tree, blob_mock = create_mock_tree(["version.txt"])
    base_commit_mock.tree = fake_tree
    current_commit_mock.tree = fake_tree

    diff_stub = DiffStub([blob_mock])
    base_commit_mock.diff.return_value = diff_stub
    diff_stub.iter_change_type.return_value = [blob_mock]

    with pytest.raises(RuntimeError, match="sys.exit called"):
        vc_utils.do_check(base_commit_mock, current_commit_mock, files, file_regexes)

    patched_sys.exit.assert_called_once_with(1)


def test_do_check_handles_release_and_build_number_addition(mocker):
    # DISCLAIMER: see semver.org for more details on versioning
    #   0.0.0-rc.0 < 0.0.0
    #   0.0.0 < 0.0.1-rc.0
    patched_sys = mocker.patch.object(vc_utils, "sys")
    base_commit_mock = mock.MagicMock(spec=git.Commit)
    current_commit_mock = mock.MagicMock(spec=git.Commit)
    blob_mock = mock.MagicMock(spec=git.Blob)
    blob_mock.b_path = "version.txt"

    old_ver = "0.0.0"
    new_ver = "0.0.1-alpha.0"

    patched_ok = mocker.patch.object(vc_utils, "ok")
    patched_search = mocker.patch.object(vc_utils, "search_commit_file")
    patched_search.side_effect = [old_ver, new_ver]

    files = ["version.txt"]
    file_regexes = [old_ver, old_ver]

    base_commit_mock.tree = ["version.txt"]
    current_commit_mock.tree = ["version.txt"]
    base_commit_mock.diff().iter_change_type.return_value = [blob_mock]

    assert vc_utils.do_check(base_commit_mock, current_commit_mock, files, file_regexes)
    patched_ok.assert_called()
    patched_sys.exit.assert_not_called()


def test_do_check_detects_other_file_mismatch(mocker):
    patched_sys = mocker.patch.object(vc_utils, "sys")
    patched_sys.exit.side_effect = RuntimeError("sys.exit called")
    base_commit_mock = mock.MagicMock(spec=git.Commit)
    current_commit_mock = mock.MagicMock(spec=git.Commit)
    blob_mock = mock.MagicMock(spec=git.Blob)
    blob_mock.b_path = "version.txt"

    old_ver = "0.0.1"
    new_ver = "0.0.2"
    other_file_ver = old_ver

    patched_search = mocker.patch.object(vc_utils, "search_commit_file")
    patched_search.side_effect = [old_ver, new_ver, other_file_ver]

    files = [vc_utils.CheckerPath(".", "version.txt"), vc_utils.CheckerPath(".", "some_other_file.txt")]
    file_regexes = [_vc_version, _vc_version]

    patched_log = mocker.patch.object(vc_utils, "LOG")

    fake_tree, blob_mock = create_mock_tree(["version.txt"])
    base_commit_mock.tree = fake_tree
    current_commit_mock.tree = fake_tree

    diff_stub = DiffStub([blob_mock])
    base_commit_mock.diff.return_value = diff_stub
    diff_stub.iter_change_type.return_value = [blob_mock]

    with pytest.raises(RuntimeError, match="sys.exit called"):
        vc_utils.do_check(base_commit_mock, current_commit_mock, files, file_regexes)

    patched_sys.exit.assert_called_once_with(1)
    patched_log.error.assert_called()
    assert "needs to match" in patched_log.error.call_args_list[0].args[1]


def test_do_check_verifies_all_version_changes(mocker):
    patched_sys = mocker.patch.object(vc_utils, "sys")
    base_commit_mock = mock.MagicMock(spec=git.Commit)
    current_commit_mock = mock.MagicMock(spec=git.Commit)
    blob_mock = mock.MagicMock(spec=git.Blob)
    blob_mock.b_path = "version.txt"

    old_ver = "0.0.1"
    new_ver = "0.0.2"
    other_file_ver = new_ver
    other_file_ver2 = new_ver

    patched_ok = mocker.patch.object(vc_utils, "ok")
    patched_search = mocker.patch.object(vc_utils, "search_commit_file")
    patched_search.side_effect = [old_ver, new_ver, other_file_ver, other_file_ver2]

    files = [vc_utils.CheckerPath(".", "version.txt"), vc_utils.CheckerPath(".", "some_other_file.txt"), vc_utils.CheckerPath(".", "some_other_file2.txt")]
    file_regexes = [_vc_version, _vc_version, _vc_version]

    fake_tree, blob_mock = create_mock_tree(["version.txt"])
    base_commit_mock.tree = fake_tree
    current_commit_mock.tree = fake_tree

    diff_stub = DiffStub([blob_mock])
    base_commit_mock.diff.return_value = diff_stub
    diff_stub.iter_change_type.return_value = [blob_mock]

    assert vc_utils.do_check(base_commit_mock, current_commit_mock, files, file_regexes)
    patched_sys.exit.assert_not_called()
    patched_ok.assert_called()


def test_do_check_handles_new_file(mocker):
    patched_sys = mocker.patch.object(vc_utils, "sys")
    base_commit_mock = mock.MagicMock(spec=git.Commit)
    current_commit_mock = mock.MagicMock(spec=git.Commit)

    old_ver = "0.0.1"
    new_ver = "0.0.2"

    patched_ok = mocker.patch.object(vc_utils, "ok")
    patched_search = mocker.patch.object(vc_utils, "search_commit_file")
    patched_search.side_effect = [old_ver, new_ver]

    files = [vc_utils.CheckerPath(".", "version.txt")]
    file_regexes = [_vc_version, _vc_version]

    fake_current_tree, fake_blob = create_mock_tree(["version.txt"])
    base_commit_mock.tree, _ = create_mock_tree([])
    current_commit_mock.tree = fake_current_tree

    diff_stub = DiffStub([fake_blob])
    base_commit_mock.diff.return_value = diff_stub
    diff_stub.iter_change_type.return_value = [fake_blob]

    assert vc_utils.do_check(base_commit_mock, current_commit_mock, files, file_regexes)
    patched_ok.assert_called()
    patched_sys.exit.assert_not_called()


def test_do_check_errors_for_file_not_in_current_tree(mocker):
    patched_sys = mocker.patch.object(vc_utils, "sys")
    base_commit_mock = mock.MagicMock(spec=git.Commit)
    current_commit_mock = mock.MagicMock(spec=git.Commit)

    old_ver = "0.0.1"
    new_ver = "0.0.2"

    patched_search = mocker.patch.object(vc_utils, "search_commit_file")
    patched_search.side_effect = [old_ver, new_ver]

    patched_log = mocker.patch.object(vc_utils, "LOG")

    files = [vc_utils.CheckerPath(".", "file-should-not-be-found-version.txt")]
    file_regexes = [_vc_version, _vc_version]

    fake_tree, fake_blob = create_mock_tree(["version.txt"])
    base_commit_mock.tree = fake_tree
    current_commit_mock.tree = fake_tree

    diff_stub = DiffStub([fake_blob])
    base_commit_mock.diff.return_value = diff_stub
    diff_stub.iter_change_type.return_value = [fake_blob]

    assert vc_utils.do_check(base_commit_mock, current_commit_mock, files, file_regexes)
    patched_log.error.assert_called()
    patched_sys.exit.assert_called_once_with(1)


def test_do_check_handles_bad_new_version(mocker):
    patched_sys = mocker.patch.object(vc_utils, "sys")
    patched_sys.exit.side_effect = RuntimeError("sys.exit called")
    base_commit_mock = mock.MagicMock(spec=git.Commit)
    current_commit_mock = mock.MagicMock(spec=git.Commit)

    new_ver = (
        "completely invalid version string should get caught, logged, and return false"
    )

    patched_log = mocker.patch.object(vc_utils, "LOG")
    patched_ok = mocker.patch.object(vc_utils, "ok")
    patched_search = mocker.patch.object(vc_utils, "search_commit_file")
    patched_search.side_effect = [new_ver]

    files = [vc_utils.CheckerPath(".", "version.txt")]
    file_regexes = [_vc_version]

    fake_current_tree, fake_blob = create_mock_tree(["version.txt"])
    base_commit_mock.tree, _ = create_mock_tree([])
    current_commit_mock.tree = fake_current_tree

    diff_stub = DiffStub([fake_blob])
    base_commit_mock.diff.return_value = diff_stub
    diff_stub.iter_change_type.return_value = [fake_blob]

    with pytest.raises(RuntimeError, match="sys.exit called"):
        vc_utils.do_check(base_commit_mock, current_commit_mock, files, file_regexes)
    patched_ok.assert_not_called()
    patched_sys.exit.assert_called_once_with(1)
    patched_log.error.assert_called()
    assert patched_log.error.call_args_list[0].args[1] == "New version not detected!"


def test_do_check_handles_new_version_less_than_old_version(mocker):
    patched_sys = mocker.patch.object(vc_utils, "sys")
    patched_sys.exit.side_effect = RuntimeError("sys.exit called")
    base_commit_mock = mock.MagicMock(spec=git.Commit)
    current_commit_mock = mock.MagicMock(spec=git.Commit)
    blob_mock = mock.MagicMock(spec=git.Blob)
    blob_mock.b_path = "version.txt"

    old_ver = "0.0.2"
    new_ver = "0.0.1"

    patched_log = mocker.patch.object(vc_utils, "LOG")
    patched_search = mocker.patch.object(vc_utils, "search_commit_file")
    patched_search.side_effect = [old_ver, new_ver]

    files = [vc_utils.CheckerPath(".", "version.txt")]
    file_regexes = [_vc_version]

    fake_tree, blob_mock = create_mock_tree(["version.txt"])
    base_commit_mock.tree = fake_tree
    current_commit_mock.tree = fake_tree

    diff_stub = DiffStub([blob_mock])
    base_commit_mock.diff.return_value = diff_stub
    diff_stub.iter_change_type.return_value = [blob_mock]

    with pytest.raises(RuntimeError, match="sys.exit called"):
        vc_utils.do_check(base_commit_mock, current_commit_mock, files, file_regexes)

    patched_sys.exit.assert_called_once_with(1)
    patched_log.error.assert_called()
    assert (
        patched_log.error.call_args_list[0].args[1]
        == "New version needs to be greater than old! See semver.org"
    )


def test_compare_versions_returns_false_for_invalid_new_version(mocker):
    patched_err = mocker.patch.object(vc_utils, "error")
    old_ver = "0.0.1"
    new_ver = "not a version"
    assert not vc_utils.compare_versions(old_ver, new_ver, abort=False)
    patched_err.assert_called_once_with("New version not detected!", abort=False)


def test_compare_versions_returns_false_for_new_version_less_than_old(mocker):
    patched_err = mocker.patch.object(vc_utils, "error")
    old_ver = "0.0.2"
    new_ver = "0.0.1"
    assert not vc_utils.compare_versions(old_ver, new_ver, abort=False)
    patched_err.assert_called_once_with(
        "New version needs to be greater than old! See semver.org", abort=False
    )


# endregion


# region resolve_files_to_regexes_mismatch tests
# same, fewer files, fewer regexes


def test_resolve_files_to_regexes_mismatch_returns_original_regexes_if_file_count_matches():
    original_regexes = ["abc", "def"]
    resolved_regexes = vc_utils.resolve_files_to_regexes_mismatch(
        ["123", "456"], original_regexes, "ghi"
    )

    assert resolved_regexes == original_regexes


def test_resolve_files_to_regexes_mismatch_returns_appended_default_regex_if_file_count_larger():
    original_regexes = ["abc"]
    resolved_regexes = vc_utils.resolve_files_to_regexes_mismatch(
        ["123", "456"], original_regexes, "ghi"
    )

    assert resolved_regexes == ["abc", "ghi"]


def test_resolve_files_to_regexes_mismatch_returns_truncated_regexes_if_file_count_smaller():
    original_regexes = ["abc", "def"]
    resolved_regexes = vc_utils.resolve_files_to_regexes_mismatch(
        ["123"], original_regexes, "ghi"
    )

    assert resolved_regexes == ["abc"]


# endregion
