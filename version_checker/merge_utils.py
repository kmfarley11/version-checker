'''
Utils for version checker merge conflict resolution

Contains common public-exposed functions for cli to use etc.
'''
from dataclasses import dataclass
import logging
import os
import re

from git import Commit, Repo

from version_checker.constants import CONFLICT_RE, LOG_NAME, MergeStrategy
from version_checker.utils import (
    CheckerPath,
    error,
    ok,
    parse_versions_from_version_file,
    compare_versions,
)


LOG = logging.getLogger(LOG_NAME)


@dataclass
class VersionFile:
    """Dataclass for storing file path and corresponding regexes for current and incoming commits"""
    path: CheckerPath
    current_regex: str
    incoming_regex: str


@dataclass
class MergeConflict:
    """Dataclass for merge conflict information with utilities for resolving them"""
    start_index: int
    end_index: int
    start_line: str
    end_line: str
    current: str
    incoming: str
    text: str

    @classmethod
    def from_regex_match(cls, match: re.Match[str]) -> "MergeConflict":
        """Generate MergeConflict from regex match (see constants.py)"""
        return MergeConflict(
            start_index=match.start(),
            end_index=match.end(),
            start_line=match.group("start"),
            end_line=match.group("end"),
            current=match.group("current"),
            incoming=match.group("incoming"),
            text=match.group(0),
        )

    def get_merge_result(self, merge_strategy: MergeStrategy = None) -> str:
        """Get simple merge result given a merge strategy"""
        return self._get_merge_result(
            self.current, self.incoming, self.text, merge_strategy
        )

    def get_split_merge_result(
        self, merge_splits: list[tuple[str, str]], merge_strategy: MergeStrategy = None
    ) -> str:
        """Get merge result given a merge strategy and a list text sections (current and incoming) 
        from within the merge conflict that may split the merge conflict into multiple conflicts"""
        result = ""
        current = self.current
        incoming = self.incoming
        for current_split, incoming_split in merge_splits:
            try:
                current_parsed, current = current.split(current_split, 1)
                incoming_parsed, incoming = incoming.split(incoming_split, 1)
            except ValueError:
                LOG.warning("Unable to find given text within given merge conflict" \
                " - skipping conflict resolution")
                return self.text
            if (
                self._is_invalid_line(current_parsed)
                or self._is_invalid_line(incoming_parsed)
                or self._is_invalid_line(current_split)
                or self._is_invalid_line(incoming_split)
            ):
                LOG.warning("Given text does not break up merge conflict into complete lines" \
                " - skipping conflict resolution")
                return self.text

            result += self._create_conflict_text(current_parsed, incoming_parsed)
            result += self._get_merge_result(
                current_split,
                incoming_split,
                self._create_conflict_text(current_split, incoming_split),
                merge_strategy,
            )
        result += self._create_conflict_text(current, incoming)

        return result

    def apply_merge(self, file_text: str, merge_result: str) -> str:
        """Apply a merge result to file text (given start/end indices of the original merge 
        conflict)"""
        LOG.debug("Applying merge resolution, replacing:\n%swith:\n%s", self.text, merge_result)
        return (
            file_text[: self.start_index] + merge_result + file_text[self.end_index :]
        )

    def _create_conflict_text(self, current: str, incoming: str) -> str:
        """Create a new merge conflict section"""
        if current == "" and incoming == "":
            return ""
        return self.start_line + current + "=======\n" + incoming + self.end_line

    def _get_merge_result(
        self,
        current: str,
        incoming: str,
        default: str,
        merge_strategy: MergeStrategy = None,
    ) -> str:
        """Get the result of a merge conflict given current/incoming text"""
        if merge_strategy == MergeStrategy.CURRENT:
            return current
        if merge_strategy == MergeStrategy.INCOMING:
            return incoming
        if merge_strategy == MergeStrategy.BOTH:
            return current + incoming
        if merge_strategy == MergeStrategy.NEITHER:
            return ""
        return default

    def _is_invalid_line(self, text: str) -> bool:
        """Does this text end on a newline"""
        return text != "" and not text.endswith("\n")


def do_merge(
    current_commit: Commit,
    files: list[CheckerPath],
    file_regexes: list[str],
    merge_strategy: MergeStrategy,
):
    """Apply merge strategy for version conflicts given a list of files/version regexes"""
    LOG.debug(
        '%s, %s, %s, %s', str(current_commit), str(files), str(file_regexes), merge_strategy.value)

    repo = current_commit.repo

    conflicted_files = set(repo.index.unmerged_blobs().keys())
    if len(conflicted_files) == 0:
        ok("No merge conflicts detected")
        return

    if not files or not file_regexes:
        error('No files or regexes provided!', abort=True)
        return

    incoming_commit = repo.commit(repo.git.rev_parse("--verify", "MERGE_HEAD"))

    incoming_version, current_version = parse_versions_from_version_file(
        incoming_commit, current_commit, files[0].repo_path, file_regexes[0]
    )

    if merge_strategy in {MergeStrategy.HIGHER, MergeStrategy.LOWER}:
        is_current_bigger = compare_versions(incoming_version, current_version)
        should_merge_current = (
            is_current_bigger and merge_strategy == MergeStrategy.HIGHER
        ) or (not is_current_bigger and merge_strategy == MergeStrategy.LOWER)
        merge_strategy = (
            MergeStrategy.CURRENT if should_merge_current else MergeStrategy.INCOMING
        )
    LOG.info('Resolving version conflicts using "%s" merge strategy', merge_strategy.value)

    conflicted_version_files = [
        VersionFile(
            file,
            file_regex,
            file_regex.replace(current_version, incoming_version, 1),
        )
        for file, file_regex in zip(files, file_regexes)
        if file.repo_path in conflicted_files
    ]
    LOG.debug('Resolving the following version file conflicts: %s', conflicted_version_files)

    for version_file in conflicted_version_files:
        resolve_version_conflicts(version_file, merge_strategy, repo)

    ok("Resolved all version merge conflicts that could be auto-resolved." \
    " Verify changes for errors or failed resolutions before committing")

    return


def resolve_version_conflicts(
    version_file: VersionFile, merge_strategy: MergeStrategy, repo: Repo
):
    """Resolve version conflicts for a specific version file

    FTODO: Doesn't yet auto-resolve conflicts caused by deleted/added version files
    """
    if not os.path.exists(version_file.path) or not os.path.isfile(version_file.path):
        error(f"Version file {version_file.path} does not exist", abort=False)
        return

    LOG.info("Resolving conflicts for version file: %s", version_file)

    with open(version_file.path, "r", encoding="utf-8") as file:
        file_text = file.read()

    conflicts = parse_merge_conflicts(file_text)
    for conflict in reversed(conflicts):
        version_conflict_lines = parse_version_conflict_lines(version_file, conflict)
        if len(version_conflict_lines) > 0:
            merge_result = conflict.get_split_merge_result(
                version_conflict_lines, merge_strategy
            )
            file_text = conflict.apply_merge(file_text, merge_result)

    with open(version_file.path, "w", encoding="utf-8") as file:
        file.write(file_text)

    conflicts = parse_merge_conflicts(file_text)
    if not conflicts:
        LOG.debug(
            "All conflicts resolved for version file %s - adding to merge commit",
            version_file.path,
        )
        repo.git.restore("--staged", version_file.path.repo_path)
        repo.index.add([version_file.path.repo_path])


def parse_merge_conflicts(file_text: str) -> list[MergeConflict]:
    """Parse all merge conflicts in file"""
    return [
        MergeConflict.from_regex_match(match)
        for match in CONFLICT_RE.finditer(file_text)
    ]


def parse_version_conflict_lines(
    version_file: VersionFile, conflict: MergeConflict
) -> list[tuple[str, str]]:
    """Parse version conflict lines from a merge conflict"""
    current_version_lines = [
        line
        for line in conflict.current.splitlines(keepends=True)
        if is_regex_match(version_file.current_regex, line)
    ]
    incoming__version_lines = [
        line
        for line in conflict.incoming.splitlines(keepends=True)
        if is_regex_match(version_file.incoming_regex, line)
    ]

    if len(current_version_lines) != len(incoming__version_lines):
        LOG.warning("Found different number of version matches in merge conflict for current" \
        " commit vs incoming commit. Defaulting to smaller length." \
        " Verify changes before committing.")

    return list(zip(current_version_lines, incoming__version_lines))


def is_regex_match(regex_str: str, search_str: str) -> bool:
    """Checks if a given regex string matches (or is within) a given search string"""
    return re.search(regex_str, search_str) or regex_str in search_str
