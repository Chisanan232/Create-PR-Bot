import os
import re
from typing import List, Optional

from git import Repo
from github import Github
from github.PullRequest import PullRequest


class NotFoundTargetGitBranch(RuntimeError):
    def __init__(self, branch: str, current_all_branches: List[str]):
        self._target_branch = branch
        self._current_all_branches = current_all_branches

    def __str__(self):
        return f"Cannot find the target git branch *{self._target_branch}*. Current all branches: {self._current_all_branches}."


REPO: Optional[Repo] = None
GITHUB: Optional[Github] = None


def init_git() -> None:
    global REPO
    REPO = Repo("./")


def get_all_branch() -> List[str]:
    return [ref.name for ref in REPO.refs]  # type: ignore[union-attr]


def expect_branch_name() -> str:
    return os.environ["TEST_BRANCH"]


def search_branch(name: str, all_branch: List[str]) -> str:
    for branch in all_branch:
        if re.search(re.escape(name), str(branch), re.IGNORECASE):
            return branch.replace("origin/", "")
    raise NotFoundTargetGitBranch(name, all_branch)


def delete_remote_branch(name: str) -> None:
    REPO.git.push("origin", "--delete", name)  # type: ignore[union-attr]


def init_github() -> None:
    global GITHUB
    GITHUB = Github(os.environ["GITHUB_TOKEN"])


def search_github_repo_pr(head_branch: str) -> PullRequest:
    assert GITHUB
    prs = GITHUB.get_repo(os.environ["GITHUB_REPOSITORY"]).get_pulls(
        state="open",
        base=os.environ["GITHUB_BASE_REF"] or "master",
        head=head_branch,
    )
    one_page = prs.get_page(0)
    assert one_page
    print(f"[DEBUG] one_page {one_page}.")
    target_pr = list(filter(lambda p: p.head.ref == head_branch, one_page))
    print(f"[DEBUG] target_pr {target_pr}.")
    assert target_pr
    return target_pr[0]


def delete_github_repo_pr(pr: PullRequest) -> None:
    pr.edit(state="closed")
    print(f"Pull request #{pr.number} closed successfully.")


def run() -> None:
    init_git()
    all_branch = get_all_branch()
    e2e_test_branch = search_branch(name=expect_branch_name(), all_branch=all_branch)
    print(f"[DEBUG] Target branch: {e2e_test_branch}")

    init_github()
    pr = search_github_repo_pr(e2e_test_branch)
    try:
        delete_github_repo_pr(pr)
    except Exception as e:
        raise e
    finally:
        delete_remote_branch(e2e_test_branch)


if __name__ == "__main__":
    run()
