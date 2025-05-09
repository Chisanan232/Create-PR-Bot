"""
Git Handler module for PR creation bot.
This module provides functionality for common git operations.
"""

import logging
import re
from typing import Any, Dict, Optional

import git
from git.exc import GitCommandError


class GitCodeConflictError(Exception):
    """Custom exception raised when a git merge operation results in code conflicts."""


class GitHandler:
    """Class to handle Git operations."""

    def __init__(self, repo_path: str = "."):
        """
        Initialize the GitHandler with the path to the git repository.

        Args:
            repo_path: Path to the git repository. Defaults to current directory.
        """
        self.repo = git.Repo(repo_path)

    def _get_current_branch(self) -> str:
        """
        Get the name of the current git branch.

        Returns:
            The name of the current branch as a string.
        """
        return self.repo.active_branch.name

    def get_branch_head_commit_details(self, branch_name: Optional[str] = None) -> Dict[str, Any]:
        """
        Get details of the head commit for a specific branch.

        Args:
            branch_name: Name of the branch. If None, uses the current branch.

        Returns:
            Dictionary containing commit details like hash, author, message, etc.
        """
        if branch_name is None:
            branch_name = self._get_current_branch()

        try:
            branches = list(filter(lambda head: head.name == branch_name, self.repo.heads))
            if not branches:
                raise KeyError(
                    f"Cannot get the git branch '{branch_name}' from repository head list '{[h.name for h in self.repo.heads]}'."
                )
            branch = branches[0]
            logging.debug(f"branch: {branch}")
            logging.debug(f"type of branch: {type(branch)}")
            commit = branch.commit

            return {
                "hash": commit.hexsha,
                "short_hash": commit.hexsha[:7],
                "author": {"name": commit.author.name, "email": commit.author.email},
                "committer": {"name": commit.committer.name, "email": commit.committer.email},
                "message": commit.message.strip(),
                "committed_date": commit.committed_date,
                "authored_date": commit.authored_date,
            }
        except (IndexError, KeyError):
            raise ValueError(f"Branch '{branch_name}' not found")

    def get_remote_branch_head_commit_details(self, branch_name: str, remote_name: str = "origin") -> Dict[str, Any]:
        """
        Get details of the head commit for a remote branch.

        Args:
            branch_name: Name of the remote branch.
            remote_name: Name of the remote. Defaults to "origin".

        Returns:
            Dictionary containing commit details of the remote branch head.
        """
        try:
            # Fetch latest from remote
            print(f"[DEBUG] self.repo.remotes: {self.repo.remotes}")
            self.repo.remotes[remote_name].fetch()

            # Get the remote reference
            remote_ref = f"{remote_name}/{branch_name}"
            try:
                print(f"[DEBUG] self.repo.refs: {self.repo.refs}")
                remote_commit = self.repo.refs[remote_ref].commit
            except (IndexError, KeyError):
                raise ValueError(f"Remote branch '{remote_ref}' not found")

            return {
                "hash": remote_commit.hexsha,
                "short_hash": remote_commit.hexsha[:7],
                "author": {"name": remote_commit.author.name, "email": remote_commit.author.email},
                "committer": {"name": remote_commit.committer.name, "email": remote_commit.committer.email},
                "message": remote_commit.message.strip(),
                "committed_date": remote_commit.committed_date,
                "authored_date": remote_commit.authored_date,
            }
        except (IndexError, KeyError):
            raise ValueError(f"Remote '{remote_name}' not found")

    def is_branch_outdated(
        self, branch_name: Optional[str] = None, base_branch: str = "main", remote_name: str = "origin"
    ) -> bool:
        """
        Check if the local branch is outdated compared to the remote base branch.

        Args:
            branch_name: Name of the local branch to check. If None, uses the current branch.
            base_branch: Name of the base branch to compare against. Defaults to "main".
            remote_name: Name of the remote. Defaults to "origin".

        Returns:
            True if the local branch is outdated, False otherwise.
        """
        if branch_name is None:
            branch_name = self._get_current_branch()

        # Get the local branch head commit
        local_commit_details = self.get_branch_head_commit_details(branch_name)
        local_commit_hash = local_commit_details["hash"]

        # Get the remote base branch head commit
        remote_commit_details = self.get_remote_branch_head_commit_details(base_branch, remote_name)
        remote_commit_hash = remote_commit_details["hash"]

        # Find the merge base (common ancestor)
        merge_base = self.repo.merge_base(local_commit_hash, remote_commit_hash)

        # If the merge base is the same as the remote commit, then remote is behind (not outdated)
        # If the merge base is the same as the local commit, then local is behind (outdated)
        # Otherwise, they have diverged from a common point

        if not merge_base:
            # No common ancestor, consider outdated
            return True

        if merge_base[0].hexsha == local_commit_hash:
            # Local branch is behind remote
            return True

        return False

    def fetch_and_merge_remote_branch(
        self, branch_name: Optional[str] = None, remote_branch: Optional[str] = None, remote_name: str = "origin"
    ) -> bool:
        """
        Fetch and merge the remote branch into the local branch.

        Args:
            branch_name: Name of the local branch to merge into. If None, uses the current branch.
            remote_branch: Name of the remote branch to fetch and merge from. If None, uses the same name as local branch.
            remote_name: Name of the remote. Defaults to "origin".

        Returns:
            True if the merge was successful, False if no merge was needed.

        Raises:
            GitCodeConflictError: If there is a conflict during the merge operation.
            ValueError: If the branch is not found.
        """
        if branch_name is None:
            branch_name = self._get_current_branch()

        if remote_branch is None:
            remote_branch = branch_name

        # Ensure we're on the correct branch
        current_branch = self._get_current_branch()
        if current_branch != branch_name:
            self.repo.git.checkout(branch_name)

        # Fetch the latest from remote
        self.repo.remotes[remote_name].fetch()

        remote_ref = f"{remote_name}/{remote_branch}"

        try:
            # Check if merge is necessary
            merge_base = self.repo.merge_base(f"refs/heads/{branch_name}", f"refs/remotes/{remote_ref}")

            # Get the specific branch
            branches = list(filter(lambda head: head.name == branch_name, self.repo.heads))
            if not branches:
                raise KeyError(
                    f"Cannot get the git branch '{branch_name}' from repository head list '{[h.name for h in self.repo.heads]}'."
                )
            branch = branches[0]

            if merge_base and merge_base[0].hexsha == branch.commit.hexsha:
                # Local branch is directly behind remote, we can fast-forward
                try:
                    self.repo.git.merge(remote_ref, ff_only=True)
                    return True
                except GitCommandError:
                    # Cannot fast-forward, need to do a real merge
                    # print(f"[DEBUG in force self.repo.git.merge GitCommandError] e: {e}")
                    pass

            # Try to merge
            try:
                self.repo.git.merge(remote_ref)
                return True
            except GitCommandError as e:
                # Check if the error is due to conflicts
                search_conflict = re.search(r"CONFLICT", str(e), re.IGNORECASE)
                search_merge_fail = re.search(r"Automatic merge failed", str(e), re.IGNORECASE)
                if search_conflict or search_merge_fail:
                    # NOTE: It seems like doesn't need to do the step of command line "git merge --abort" when facing
                    # git code conflict with git Python SDK. Just note it and observe the usage state.
                    # Abort the merge
                    # self.repo.git.merge("--abort")
                    raise GitCodeConflictError(f"Merge conflicts detected between {branch_name} and {remote_ref}")
                raise  # Re-raise the original exception if not a conflict error

        except (IndexError, KeyError) as e:
            print(f"[DEBUG in IndexError, KeyError] e: {e}")
            raise ValueError(f"Branch '{branch_name}' or remote branch '{remote_ref}' not found")

        return False  # No merge was needed

    def push_branch_to_remote(
        self, branch_name: Optional[str] = None, remote_name: str = "origin", force: bool = False
    ) -> bool:
        """
        Push the local branch to the remote repository.

        Args:
            branch_name: Name of the local branch to push. If None, uses the current branch.
            remote_name: Name of the remote. Defaults to "origin".
            force: If True, force push the branch. Use with caution. Defaults to False.

        Returns:
            True if the push was successful.

        Raises:
            GitCommandError: If there's an error during the push operation.
            ValueError: If the branch is not found.
        """
        if branch_name is None:
            branch_name = self._get_current_branch()

        try:
            # Ensure the branch exists
            print(f"[DEBUG] self.repo.heads: {self.repo.heads}")
            if branch_name not in [b.name for b in self.repo.heads]:
                raise ValueError(f"Branch '{branch_name}' not found")

            # Push to remote
            if force:
                self.repo.git.push(remote_name, branch_name, force=True)
            else:
                self.repo.git.push(remote_name, branch_name)

            return True

        except GitCommandError as e:
            if "rejected" in str(e) and "non-fast-forward" in str(e):
                raise GitCommandError(
                    "Push rejected: Remote has changes you don't have locally. Use force=True to override or fetch and merge first."
                )
            raise e
