"""
Unit tests for the PullRequestAIAgent class.
"""

from typing import Any, Dict, Optional, cast
from unittest.mock import MagicMock, PropertyMock, call, mock_open, patch

import pytest
from github.PullRequest import PullRequest

from pull_request_ai_agent.ai_bot import AiModuleClient
from pull_request_ai_agent.ai_bot.gpt.client import GPTClient
from pull_request_ai_agent.bot import PullRequestAIAgent
from pull_request_ai_agent.git_hdlr import GitCodeConflictError, GitHandler
from pull_request_ai_agent.github_opt import GitHubOperations
from pull_request_ai_agent.model import ProjectManagementToolSettings
from pull_request_ai_agent.project_management_tool import ProjectManagementToolType
from pull_request_ai_agent.project_management_tool._base.model import BaseImmutableModel
from pull_request_ai_agent.project_management_tool.clickup.client import (
    ClickUpAPIClient,
)


class SpyAgent(PullRequestAIAgent):
    def __init__(
        self,
        repo_path: str = ".",
        base_branch: str = "main",
        github_token: Optional[str] = None,
        github_repo: Optional[str] = None,
        project_management_tool_type: Optional[ProjectManagementToolType] = None,
        project_management_tool_config: Optional[Dict[str, Any]] = None,
        ai_client_type: AiModuleClient = AiModuleClient.GPT,
        ai_client_api_key: Optional[str] = None,
    ):
        # Initialize attributes directly
        self.repo_path: str = repo_path
        self.base_branch: str = base_branch
        self.github_token: Optional[str] = github_token
        self.github_repo: Optional[str] = github_repo
        self.project_management_tool_type: Optional[ProjectManagementToolType] = project_management_tool_type
        self.project_management_tool_config: Optional[Dict[str, Any]] = project_management_tool_config
        self.ai_client_type: AiModuleClient = ai_client_type
        self.ai_client_api_key: Optional[str] = ai_client_api_key

        # Initialize components
        self.git_handler: Optional[GitHandler] = None  # type: ignore[assignment]
        self.github_operations: Optional[GitHubOperations] = None
        self.project_management_client: Optional[Any] = None
        self.ai_client: Optional[Any] = None  # type: ignore[assignment]


class TestPullRequestAIAgent:
    """Test cases for PullRequestAIAgent class."""

    @pytest.fixture
    def mock_git_handler(self) -> MagicMock:
        """Create a mock GitHandler for testing."""
        mock = MagicMock(spec=GitHandler)

        # Setup active branch
        mock._get_current_branch.return_value = "feature-branch"

        # Setup commit details
        mock_commit = {
            "hash": "1234567890abcdef1234567890abcdef12345678",
            "short_hash": "1234567",
            "author": {"name": "Test Author", "email": "test@example.com"},
            "committer": {"name": "Test Author", "email": "test@example.com"},
            "message": "Test commit message",
            "committed_date": 1620000000,
            "authored_date": 1620000000,
        }
        mock.get_branch_head_commit_details.return_value = mock_commit

        # Setup repo
        mock_repo = MagicMock()
        type(mock).repo = PropertyMock(return_value=mock_repo)

        # Setup is_branch_outdated
        mock.is_branch_outdated.return_value = False

        return mock

    @pytest.fixture
    def mock_github_operations(self) -> MagicMock:
        """Create a mock GitHubOperations for testing."""
        mock = MagicMock(spec=GitHubOperations)

        # Setup get_pull_request_by_branch
        mock.get_pull_request_by_branch.return_value = None

        # Setup create_pull_request
        mock_pr = MagicMock(spec=PullRequest)
        mock_pr.number = 123
        mock_pr.html_url = "https://github.com/owner/repo/pull/123"
        mock.create_pull_request.return_value = mock_pr

        return mock

    @pytest.fixture
    def mock_project_management_client(self) -> MagicMock:
        """Create a mock project management client for testing."""
        mock = MagicMock(spec=ClickUpAPIClient)

        # Setup get_ticket
        mock_ticket = MagicMock(spec=BaseImmutableModel)
        mock_ticket.id = "123456"
        mock_ticket.name = "Test ticket"
        mock_ticket.text_content = "Test ticket description"
        mock_ticket.description = None

        # Mock status as a nested object
        mock_status = MagicMock()
        mock_status.status = "In Progress"
        mock_status.color = "#4A90E2"
        mock_ticket.status = mock_status

        mock.get_ticket.return_value = mock_ticket

        return mock

    @pytest.fixture
    def mock_ai_client(self) -> MagicMock:
        """Create a mock AI client for testing."""
        mock = MagicMock(spec=GPTClient)

        # Setup get_content
        mock.get_content.return_value = """
        TITLE: Test PR title

        BODY:
        This is a test PR description.
        It includes multiple lines.
        """

        return mock

    @pytest.fixture
    def bot(
        self,
        mock_git_handler: MagicMock,
        mock_github_operations: MagicMock,
        mock_ai_client: MagicMock,
        mock_project_management_client: MagicMock,
    ) -> PullRequestAIAgent:
        """Create a PullRequestAIAgent instance with mocked dependencies."""
        with (
            patch("pull_request_ai_agent.bot.GitHandler", return_value=mock_git_handler),
            patch("pull_request_ai_agent.bot.GitHubOperations", return_value=mock_github_operations),
            patch.object(PullRequestAIAgent, "_initialize_ai_client", return_value=mock_ai_client),
            patch.object(
                PullRequestAIAgent, "_initialize_project_management_client", return_value=mock_project_management_client
            ),
        ):

            bot = PullRequestAIAgent(
                repo_path="/mock/repo",
                base_branch="main",
                github_token="mock-token",
                github_repo="owner/repo",
                project_management_tool_type=ProjectManagementToolType.CLICKUP,
                project_management_tool_config=ProjectManagementToolSettings(api_key="mock-api-key"),
                ai_client_type=AiModuleClient.GPT,
                ai_client_api_key="mock-api-key",
            )

            return bot

    def test_initialize_ai_client_gpt(self) -> None:
        """Test initialization of GPT AI client."""
        with patch("pull_request_ai_agent.bot.GPTClient") as mock_gpt_client:
            SpyAgent()._initialize_ai_client(AiModuleClient.GPT, "mock-api-key")
            mock_gpt_client.assert_called_once_with(api_key="mock-api-key")

    def test_initialize_ai_client_claude(self) -> None:
        """Test initialization of Claude AI client."""
        with patch("pull_request_ai_agent.bot.ClaudeClient") as mock_claude_client:
            SpyAgent()._initialize_ai_client(AiModuleClient.CLAUDE, "mock-api-key")
            mock_claude_client.assert_called_once_with(api_key="mock-api-key")

    def test_initialize_ai_client_gemini(self) -> None:
        """Test initialization of Gemini AI client."""
        with patch("pull_request_ai_agent.bot.GeminiClient") as mock_gemini_client:
            SpyAgent()._initialize_ai_client(AiModuleClient.GEMINI, "mock-api-key")
            mock_gemini_client.assert_called_once_with(api_key="mock-api-key")

    def test_initialize_ai_client_unsupported(self) -> None:
        """Test initialization with unsupported AI client type."""
        with pytest.raises(ValueError, match="Unsupported AI client type"):
            SpyAgent()._initialize_ai_client(cast(AiModuleClient, "unsupported"), "mock-api-key")

    def test_get_current_branch(self, bot: PullRequestAIAgent, mock_git_handler: MagicMock) -> None:
        """Test _get_current_branch method."""
        branch = bot._get_current_branch()
        mock_git_handler._get_current_branch.assert_called_once()
        assert branch == "feature-branch"

    def test_is_branch_outdated(self, bot: PullRequestAIAgent, mock_git_handler: MagicMock) -> None:
        """Test is_branch_outdated method."""
        result = bot.is_branch_outdated("test-branch")
        mock_git_handler.is_branch_outdated.assert_called_once_with("test-branch", "main")
        assert not result

    def test_is_branch_outdated_current_branch(self, bot: PullRequestAIAgent, mock_git_handler: MagicMock) -> None:
        """Test is_branch_outdated method with current branch."""
        result = bot.is_branch_outdated()
        mock_git_handler.is_branch_outdated.assert_called_once_with("feature-branch", "main")
        assert not result

    def test_is_pr_already_opened(self, bot: PullRequestAIAgent, mock_github_operations: MagicMock) -> None:
        """Test is_pr_already_opened method."""
        result = bot.is_pr_already_opened("test-branch")
        mock_github_operations.get_pull_request_by_branch.assert_called_once_with("test-branch")
        assert not result

    def test_is_pr_already_opened_exists(self, bot: PullRequestAIAgent, mock_github_operations: MagicMock) -> None:
        """Test is_pr_already_opened method when PR exists."""
        mock_pr = MagicMock(spec=PullRequest)
        mock_github_operations.get_pull_request_by_branch.return_value = mock_pr

        result = bot.is_pr_already_opened("test-branch")
        assert result

    def test_is_pr_already_opened_no_github_ops(self, bot: PullRequestAIAgent) -> None:
        """Test is_pr_already_opened method with no GitHub operations."""
        bot.github_operations = None
        result = bot.is_pr_already_opened("test-branch")
        assert not result

    def test_is_pr_already_opened_exception(self, bot: PullRequestAIAgent, mock_github_operations: MagicMock) -> None:
        """Test is_pr_already_opened method with exception."""
        mock_github_operations.get_pull_request_by_branch.side_effect = Exception("Test error")

        result = bot.is_pr_already_opened("test-branch")
        assert not result

    def test_fetch_and_merge_latest_from_base_branch(
        self, bot: PullRequestAIAgent, mock_git_handler: MagicMock
    ) -> None:
        """Test fetch_and_merge_latest_from_base_branch method."""
        mock_git_handler.fetch_and_merge_remote_branch.return_value = True

        result = bot.fetch_and_merge_latest_from_base_branch("test-branch")
        mock_git_handler.fetch_and_merge_remote_branch.assert_called_once_with("test-branch")
        assert result

    def test_fetch_and_merge_latest_from_base_branch_conflict(
        self, bot: PullRequestAIAgent, mock_git_handler: MagicMock
    ) -> None:
        """Test fetch_and_merge_latest_from_base_branch method with conflict."""
        mock_git_handler.fetch_and_merge_remote_branch.side_effect = GitCodeConflictError("Test conflict")

        with pytest.raises(GitCodeConflictError):
            bot.fetch_and_merge_latest_from_base_branch("test-branch")

    def test_get_branch_commits(self, bot: PullRequestAIAgent, mock_git_handler: MagicMock) -> None:
        """Test get_branch_commits method."""
        # Setup mock repo and commits
        mock_repo = mock_git_handler.repo

        # Create mock commit objects
        mock_commit1 = MagicMock()
        mock_commit1.hexsha = "abcdef1"
        mock_commit1.author.name = "Author 1"
        mock_commit1.author.email = "author1@example.com"
        mock_commit1.committer.name = "Committer 1"
        mock_commit1.committer.email = "committer1@example.com"
        mock_commit1.message = "Commit message 1"
        mock_commit1.committed_date = 1620000001
        mock_commit1.authored_date = 1620000001

        mock_commit2 = MagicMock()
        mock_commit2.hexsha = "abcdef2"
        mock_commit2.author.name = "Author 2"
        mock_commit2.author.email = "author2@example.com"
        mock_commit2.committer.name = "Committer 2"
        mock_commit2.committer.email = "committer2@example.com"
        mock_commit2.message = "Commit message 2"
        mock_commit2.committed_date = 1620000002
        mock_commit2.authored_date = 1620000002

        # Mock base commit
        mock_base_commit = MagicMock()
        mock_base_commit.hexsha = "base123"

        # Setup refs
        mock_feature_ref = MagicMock()
        mock_feature_ref.name = "test-branch"

        mock_base_ref = MagicMock()
        mock_base_ref.name = "main"

        # Set up repo.refs
        mock_repo.refs = [mock_feature_ref, mock_base_ref]

        # Setup merge_base
        mock_repo.merge_base.return_value = [mock_base_commit]

        # Setup iter_commits to return our mock commits
        mock_repo.iter_commits.return_value = [mock_commit1, mock_commit2, mock_base_commit]

        # Call get_branch_commits
        commits = bot.get_branch_commits("test-branch")

        # Verify calls
        mock_repo.merge_base.assert_called_once_with("test-branch", "main")
        mock_repo.iter_commits.assert_called_once_with("test-branch")

        # Verify returned commits (should exclude base commit)
        assert len(commits) == 2
        assert commits[0]["hash"] == "abcdef1"
        assert commits[1]["hash"] == "abcdef2"

    def test_get_branch_commits_no_commits(self, bot: PullRequestAIAgent, mock_git_handler: MagicMock) -> None:
        """Test get_branch_commits method with no commits."""
        mock_repo = mock_git_handler.repo

        # Setup refs
        mock_feature_ref = MagicMock()
        mock_feature_ref.name = "test-branch"

        mock_base_ref = MagicMock()
        mock_base_ref.name = "main"

        # Set up repo.refs
        mock_repo.refs = [mock_feature_ref, mock_base_ref]

        mock_repo.merge_base.return_value = []

        commits = bot.get_branch_commits("test-branch")

        # Verify merge_base was called with the correct arguments
        mock_repo.merge_base.assert_called_once_with("test-branch", "main")

        assert commits == []

    def test_get_branch_commits_feature_branch_not_found(
        self, bot: PullRequestAIAgent, mock_git_handler: MagicMock
    ) -> None:
        """Test get_branch_commits method when feature branch doesn't exist."""
        mock_repo = mock_git_handler.repo

        # Setup refs with only base branch
        mock_base_ref = MagicMock()
        mock_base_ref.name = "main"
        mock_repo.refs = [mock_base_ref]

        # Expect ValueError to be raised
        with pytest.raises(ValueError) as excinfo:
            bot.get_branch_commits("test-branch")

        # Verify error message contains branch name
        assert "Feature branch 'test-branch' not found" in str(excinfo.value)

    def test_get_branch_commits_base_branch_not_found(
        self, bot: PullRequestAIAgent, mock_git_handler: MagicMock
    ) -> None:
        """Test get_branch_commits method when base branch doesn't exist."""
        mock_repo = mock_git_handler.repo

        # Setup refs with only feature branch
        mock_feature_ref = MagicMock()
        mock_feature_ref.name = "test-branch"
        mock_repo.refs = [mock_feature_ref]

        # Expect ValueError to be raised
        with pytest.raises(ValueError) as excinfo:
            bot.get_branch_commits("test-branch")

        # Verify error message contains branch name
        assert "Base branch 'main' not found" in str(excinfo.value)

    @pytest.mark.parametrize(
        ("git_branch", "expected_ticket_id"),
        [
            # separate by slash */*
            ("#123/fix_bug", "#123"),
            ("PROJ-456/implement_feature", "PROJ-456"),
            ("CU-abc123/update-docs", "CU-abc123"),
            ("Task-789/refactor-code", "Task-789"),
            ("no-ticket/just-test", ""),
            # separate by underline *_*
            ("#123_fix_bug", "#123"),
            ("PROJ-456_implement_feature", "PROJ-456"),
            ("CU-abc123_update-docs", "CU-abc123"),
            ("Task-789_refactor-code", "Task-789"),
            ("no-ticket_just-test", ""),
        ],
    )
    def test_extract_ticket_id(self, bot: PullRequestAIAgent, git_branch: str, expected_ticket_id: str) -> None:
        """Test extract_ticket_id method."""
        # Create test commits with various ticket patterns
        ticket_id = bot.extract_ticket_id(git_branch)

        # Verify extracted ticket IDs
        assert ticket_id == expected_ticket_id

    def test_get_ticket_details(self, bot: PullRequestAIAgent, mock_project_management_client: MagicMock) -> None:
        """Test get_ticket_details method."""
        # Set up the project management tool client and type
        bot.project_management_client = mock_project_management_client
        bot.project_management_tool_type = ProjectManagementToolType.CLICKUP

        # Call get_ticket_details
        tickets = bot.get_ticket_details(["CU-123456", "CU-789012"])

        # Verify get_ticket was called with formatted ticket IDs
        assert mock_project_management_client.get_ticket.call_count >= 2

        # Check that get_ticket was called with the expected arguments (using any_order=True)
        # This is more robust than checking exact call sequence, as it ignores any __str__ calls
        mock_project_management_client.get_ticket.assert_any_call("123456")
        mock_project_management_client.get_ticket.assert_any_call("789012")

        # Verify returned tickets
        assert len(tickets) == 2
        assert tickets[0] is mock_project_management_client.get_ticket.return_value
        assert tickets[1] is mock_project_management_client.get_ticket.return_value

    def test_get_ticket_details_no_client(self, bot: PullRequestAIAgent) -> None:
        """Test get_ticket_details method with no project management client."""
        # Set project management client to None
        bot.project_management_client = None

        # Call get_ticket_details
        tickets = bot.get_ticket_details(["PROJ-123", "PROJ-456"])

        # Should return empty list
        assert tickets == []

    def test_get_ticket_details_client_exception(
        self, bot: PullRequestAIAgent, mock_project_management_client: MagicMock
    ) -> None:
        """Test get_ticket_details method with client exception."""
        # Set up the project management tool client and type
        bot.project_management_client = mock_project_management_client
        bot.project_management_tool_type = ProjectManagementToolType.JIRA

        # Mock get_ticket to raise exception
        mock_project_management_client.get_ticket.side_effect = Exception("API error")

        # Call get_ticket_details
        tickets = bot.get_ticket_details(["PROJ-123"])

        # Should return empty list
        assert tickets == []

    def test_get_ticket_details_missing_ticket(
        self, bot: PullRequestAIAgent, mock_project_management_client: MagicMock
    ) -> None:
        """Test get_ticket_details method with missing ticket."""
        # Set up the project management tool client and type
        bot.project_management_client = mock_project_management_client
        bot.project_management_tool_type = ProjectManagementToolType.CLICKUP

        # Mock get_ticket to return None for one ticket
        mock_project_management_client.get_ticket.side_effect = [None, MagicMock()]

        # Call get_ticket_details
        tickets = bot.get_ticket_details(["CU-123", "CU-456"])

        # Should only include the non-None ticket
        assert len(tickets) == 1

    def test_prepare_ai_prompt(self, bot: PullRequestAIAgent) -> None:
        """Test prepare_ai_prompt method."""
        # Mock commits and tickets
        commits = [
            {"short_hash": "abc123", "message": "Fix bug in login form", "author": "John Doe", "date": "2023-01-01"},
            {"short_hash": "def456", "message": "Add new feature", "author": "Jane Smith", "date": "2023-01-02"},
        ]

        # Create mock tickets with the new structure
        mock_ticket1 = MagicMock()
        mock_ticket2 = MagicMock()

        # Set up _extract_ticket_info to return structured ticket info
        with patch.object(bot, "_extract_ticket_info") as mock_extract_info:
            mock_extract_info.side_effect = [
                {
                    "id": "PROJ-123",
                    "title": "Fix login bug",
                    "description": "The login form has a bug that needs to be fixed",
                    "status": "In Progress",
                },
                {
                    "id": "PROJ-456",
                    "title": "Implement new feature",
                    "description": "Add a new feature to the application",
                    "status": "In Review",
                },
            ]

            # Call prepare_ai_prompt
            prompt_data = bot.prepare_ai_prompt(commits, [mock_ticket1, mock_ticket2])

            # Verify _extract_ticket_info was called
            assert mock_extract_info.call_count == 2
            mock_extract_info.assert_has_calls([call(mock_ticket1), call(mock_ticket2)])

        # Verify prompt_data is a PRPromptData object
        assert hasattr(prompt_data, "title")
        assert hasattr(prompt_data, "description")

    def test_prepare_ai_prompt_no_tickets(self, bot: PullRequestAIAgent) -> None:
        """Test prepare_ai_prompt method with no tickets."""
        # Mock commits
        commits = [
            {"short_hash": "abc123", "message": "Fix bug in login form", "author": "John Doe", "date": "2023-01-01"}
        ]

        # Call prepare_ai_prompt with empty tickets list
        prompt_data = bot.prepare_ai_prompt(commits, [])

        # Verify prompt_data is a PRPromptData object
        assert hasattr(prompt_data, "title")
        assert hasattr(prompt_data, "description")

    def test_prepare_ai_prompt_no_commits(self, bot: PullRequestAIAgent) -> None:
        """Test prepare_ai_prompt method with no commits."""
        # Create mock ticket
        mock_ticket = MagicMock()

        # Set up _extract_ticket_info to return structured ticket info
        with patch.object(bot, "_extract_ticket_info") as mock_extract_info:
            mock_extract_info.return_value = {
                "id": "PROJ-123",
                "title": "Fix login bug",
                "description": "The login form has a bug that needs to be fixed",
                "status": "In Progress",
            }

            # Call prepare_ai_prompt with empty commits list
            prompt_data = bot.prepare_ai_prompt([], [mock_ticket])

        # Verify prompt_data is a PRPromptData object
        assert hasattr(prompt_data, "title")
        assert hasattr(prompt_data, "description")

    def test_parse_ai_response_title(self, bot: PullRequestAIAgent) -> None:
        """Test _parse_ai_response_title method."""
        # Test with well-formatted response
        response = """
        TITLE: This is the PR title

        BODY:
        This is the PR body.
        It spans multiple lines.
        """

        title = bot._parse_ai_response_title(response)

        assert "This is the PR title" in title

    def test_parse_ai_response_body(self, bot: PullRequestAIAgent) -> None:
        """Test _parse_ai_response_body method."""
        response = """
        Here's the PR description:

        ```markdown
        ## _Target_

        * ### Task summary:
            This is the PR body.
            It spans multiple lines.

        * ### Task tickets:
            * Task ID: TEST-123
        ```
        """

        body = bot._parse_ai_response_body(response)

        assert "## _Target_" in body
        assert "This is the PR body." in body
        assert "Task ID: TEST-123" in body

    def test_parse_ai_response_body_no_markdown(self, bot: PullRequestAIAgent) -> None:
        """Test _parse_ai_response_body method with no markdown content."""
        response = """
        This is just some text without any formatting.
        """

        body = bot._parse_ai_response_body(response)

        # When no markdown is found, the method returns an empty string
        assert body == ""

    def test_create_pull_request(self, bot: PullRequestAIAgent, mock_github_operations: MagicMock) -> None:
        """Test create_pull_request method."""
        pr = bot.create_pull_request(title="Test PR", body="Test PR description", branch_name="feature-branch")

        # Verify create_pull_request was called
        mock_github_operations.create_pull_request.assert_called_once_with(
            title="Test PR", body="Test PR description", base_branch="main", head_branch="feature-branch"
        )

        # Verify returned PR
        assert pr is not None
        assert getattr(pr, "number", None) == 123
        assert getattr(pr, "html_url", None) == "https://github.com/owner/repo/pull/123"

    def test_create_pull_request_no_github_ops(self, bot: PullRequestAIAgent) -> None:
        """Test create_pull_request method with no GitHub operations."""
        bot.github_operations = None

        pr = bot.create_pull_request(title="Test PR", body="Test PR description")

        # Should return None
        assert pr is None

    def test_create_pull_request_exception(self, bot: PullRequestAIAgent, mock_github_operations: MagicMock) -> None:
        """Test create_pull_request method with exception."""
        mock_github_operations.create_pull_request.side_effect = Exception("Test error")

        pr = bot.create_pull_request(title="Test PR", body="Test PR description")

        # Should return None
        assert pr is None

    def test_run_outdated_pr_exists(self, bot: PullRequestAIAgent) -> None:
        """Test run method when branch is outdated and PR exists."""
        # Mock is_branch_outdated and is_pr_already_opened
        with (
            patch.object(bot, "is_branch_outdated", return_value=True),
            patch.object(bot, "is_pr_already_opened", return_value=True),
        ):

            # Call run
            result = bot.run()

            # Verify no PR was created
            assert result is None

    def test_run_outdated_no_pr(
        self,
        bot: PullRequestAIAgent,
        mock_git_handler: MagicMock,
        mock_ai_client: MagicMock,
        mock_github_operations: MagicMock,
    ) -> None:
        """Test run method when branch is outdated and no PR exists."""
        # Mock methods
        with (
            patch.object(bot, "is_branch_outdated", return_value=True),
            patch.object(bot, "is_pr_already_opened", return_value=False),
            patch.object(bot, "fetch_and_merge_latest_from_base_branch", return_value=True),
            patch.object(bot, "get_branch_commits", return_value=[{"message": "Test commit"}]),
            patch.object(bot, "extract_ticket_id", return_value=["PROJ-123"]),
            patch.object(bot, "get_ticket_details", return_value=[MagicMock()]),
            patch.object(bot, "prepare_ai_prompt", return_value=MagicMock()),
            patch.object(bot, "_parse_ai_response_title", return_value="Test title"),
            patch.object(bot, "_parse_ai_response_body", return_value="Test body"),
        ):

            # Call run
            result = bot.run()

            # Verify PR was created
            assert result is not None
            mock_github_operations.create_pull_request.assert_called_once()

    def test_run_up_to_date_no_pr(self, bot: PullRequestAIAgent, mock_github_operations: MagicMock) -> None:
        """Test run method when branch is up to date and no PR exists."""
        # Mock methods
        with (
            patch.object(bot, "is_branch_outdated", return_value=False),
            patch.object(bot, "is_pr_already_opened", return_value=False),
            patch.object(bot, "get_branch_commits", return_value=[{"message": "Test commit"}]),
            patch.object(bot, "extract_ticket_id", return_value=["PROJ-123"]),
            patch.object(bot, "get_ticket_details", return_value=[MagicMock()]),
            patch.object(bot, "prepare_ai_prompt", return_value=MagicMock()),
            patch.object(bot, "_parse_ai_response_title", return_value="Test title"),
            patch.object(bot, "_parse_ai_response_body", return_value="Test body"),
        ):

            # Call run
            result = bot.run()

            # Verify PR was created
            assert result is not None
            mock_github_operations.create_pull_request.assert_called_once()

    def test_run_merge_conflict(self, bot: PullRequestAIAgent) -> None:
        """Test run method with merge conflict."""
        # Mock methods
        with (
            patch.object(bot, "is_branch_outdated", return_value=True),
            patch.object(bot, "is_pr_already_opened", return_value=False),
            patch.object(
                bot, "fetch_and_merge_latest_from_base_branch", side_effect=GitCodeConflictError("Test conflict")
            ),
        ):

            # Call run
            result = bot.run()

            # Verify no PR was created
            assert result is None

    def test_run_no_commits(self, bot: PullRequestAIAgent) -> None:
        """Test run method with no commits."""
        # Mock methods
        with (
            patch.object(bot, "is_branch_outdated", return_value=False),
            patch.object(bot, "is_pr_already_opened", return_value=False),
            patch.object(bot, "get_branch_commits", return_value=[]),
        ):

            # Call run
            result = bot.run()

            # Verify no PR was created
            assert result is None

    def test_run_ai_failure(
        self, bot: PullRequestAIAgent, mock_ai_client: MagicMock, mock_github_operations: MagicMock
    ) -> None:
        """Test run method with AI failure."""
        # Mock AI client to raise exception
        mock_ai_client.get_content.side_effect = Exception("AI error")

        # Mock methods
        with (
            patch.object(bot, "is_branch_outdated", return_value=False),
            patch.object(bot, "is_pr_already_opened", return_value=False),
            patch.object(bot, "get_branch_commits", return_value=[{"message": "Test commit"}]),
            patch.object(bot, "extract_ticket_id", return_value=[]),
            patch.object(bot, "get_ticket_details", return_value=[]),
            patch.object(bot, "prepare_ai_prompt", return_value=MagicMock()),
        ):

            # Call run
            result = bot.run()

            # Verify PR was created with fallback content
            assert result is not None
            mock_github_operations.create_pull_request.assert_called_once()
            title, body, branch = (
                mock_github_operations.create_pull_request.call_args[1]["title"],
                mock_github_operations.create_pull_request.call_args[1]["body"],
                mock_github_operations.create_pull_request.call_args[1]["head_branch"],
            )
            assert title == f"Update {branch}"
            assert body == "Automated pull request."

    def test_initialize_project_management_client_clickup(self) -> None:
        """Test initialization of ClickUp project management client."""
        with patch("pull_request_ai_agent.bot.ClickUpAPIClient") as mock_clickup_client:
            config = ProjectManagementToolSettings(api_key="mock-api-token")
            client = SpyAgent()._initialize_project_management_client(ProjectManagementToolType.CLICKUP, config)
            mock_clickup_client.assert_called_once_with(api_token="mock-api-token")

    def test_initialize_project_management_client_jira(self) -> None:
        """Test initialization of Jira project management client."""
        with patch("pull_request_ai_agent.bot.JiraAPIClient") as mock_jira_client:
            config = ProjectManagementToolSettings(
                base_url="https://example.atlassian.net", username="test@example.com", api_key="mock-api-token"
            )
            client = SpyAgent()._initialize_project_management_client(ProjectManagementToolType.JIRA, config)
            mock_jira_client.assert_called_once_with(
                base_url="https://example.atlassian.net", email="test@example.com", api_token="mock-api-token"
            )

    @pytest.mark.parametrize(
        ("service_type", "config"),
        [
            (ProjectManagementToolType.CLICKUP, ProjectManagementToolSettings()),
            (
                ProjectManagementToolType.JIRA,
                ProjectManagementToolSettings(username="test@example.com", api_key="mock-token"),
            ),
            (
                ProjectManagementToolType.JIRA,
                ProjectManagementToolSettings(base_url="example.com", api_key="mock-token"),
            ),
            (
                ProjectManagementToolType.JIRA,
                ProjectManagementToolSettings(base_url="example.com", username="test@example.com"),
            ),
        ],
    )
    def test_initialize_project_management_client_missing_config(
        self, service_type: ProjectManagementToolType, config: ProjectManagementToolSettings
    ) -> None:
        # Test Jira with missing base_url
        with pytest.raises(ValueError, match="is required"):
            SpyAgent()._initialize_project_management_client(service_type, config)

    def test_initialize_project_management_client_unsupported(self) -> None:
        """Test initialization with unsupported project management tool type."""
        with pytest.raises(ValueError, match="Unsupported project management tool type"):
            SpyAgent()._initialize_project_management_client(
                cast(ProjectManagementToolType, "unsupported"), ProjectManagementToolSettings()
            )

    def test_format_ticket_id_clickup(self, bot: PullRequestAIAgent) -> None:
        """Test _format_ticket_id method for ClickUp tickets."""
        # Mock the project management tool type
        bot.project_management_tool_type = ProjectManagementToolType.CLICKUP

        # Test with CU- prefix
        ticket_id = bot._format_ticket_id("CU-abc123")
        assert ticket_id == "abc123"

        # Test without prefix
        ticket_id = bot._format_ticket_id("def456")
        assert ticket_id == "def456"

        # Test with whitespace
        ticket_id = bot._format_ticket_id(" CU-ghi789 ")
        assert ticket_id == "ghi789"

    def test_format_ticket_id_jira(self, bot: PullRequestAIAgent) -> None:
        """Test _format_ticket_id method for Jira tickets."""
        # Mock the project management tool type
        bot.project_management_tool_type = ProjectManagementToolType.JIRA

        # Test with standard Jira format
        ticket_id = bot._format_ticket_id("PROJ-123")
        assert ticket_id == "PROJ-123"

        # Test with whitespace
        ticket_id = bot._format_ticket_id(" TEST-456 ")
        assert ticket_id == "TEST-456"

    def test_format_ticket_id_none(self, bot: PullRequestAIAgent) -> None:
        """Test _format_ticket_id method with None input."""
        ticket_id = bot._format_ticket_id(cast(str, None))
        assert ticket_id is None

    def test_format_ticket_id_unknown_tool(self, bot: PullRequestAIAgent) -> None:
        """Test _format_ticket_id method with unknown tool type."""
        # Set project management tool type to None
        bot.project_management_tool_type = None

        ticket_id = bot._format_ticket_id("TICKET-123")
        assert ticket_id == "TICKET-123"

    def test_extract_ticket_info_clickup(self, bot: PullRequestAIAgent) -> None:
        """Test _extract_ticket_info method for ClickUp tickets."""
        # Mock the project management tool type
        bot.project_management_tool_type = ProjectManagementToolType.CLICKUP

        # Create a mock ClickUp ticket
        mock_ticket = MagicMock()
        mock_ticket.id = "123456"
        mock_ticket.name = "Test ClickUp ticket"
        mock_ticket.text_content = "Test ticket text content"
        mock_ticket.description = None

        # Mock status as a nested object
        mock_status = MagicMock()
        mock_status.status = "In Progress"
        mock_status.color = "#4A90E2"
        mock_ticket.status = mock_status

        # Extract ticket info
        ticket_info = bot._extract_ticket_info(mock_ticket)

        # Verify extracted info
        assert ticket_info["id"] == "123456"
        assert ticket_info["title"] == "Test ClickUp ticket"
        assert ticket_info["description"] == "Test ticket text content"
        assert ticket_info["status"] == "In Progress"

    def test_extract_ticket_info_clickup_with_description(self, bot: PullRequestAIAgent) -> None:
        """Test _extract_ticket_info method for ClickUp tickets with description instead of text_content."""
        # Mock the project management tool type
        bot.project_management_tool_type = ProjectManagementToolType.CLICKUP

        # Create a mock ClickUp ticket
        mock_ticket = MagicMock()
        mock_ticket.id = "123456"
        mock_ticket.name = "Test ClickUp ticket"
        mock_ticket.text_content = None
        mock_ticket.description = "Test ticket description"

        # Extract ticket info
        ticket_info = bot._extract_ticket_info(mock_ticket)

        # Verify extracted info
        assert ticket_info["description"] == "Test ticket description"

    def test_extract_ticket_info_jira(self, bot: PullRequestAIAgent) -> None:
        """Test _extract_ticket_info method for Jira tickets."""
        # Mock the project management tool type
        bot.project_management_tool_type = ProjectManagementToolType.JIRA

        # Create a mock Jira ticket
        mock_ticket = MagicMock()
        mock_ticket.id = "PROJ-123"
        mock_ticket.title = "Test Jira ticket"
        mock_ticket.description = "Test Jira description"
        mock_ticket.status = "In Review"

        # Extract ticket info
        ticket_info = bot._extract_ticket_info(mock_ticket)

        # Verify extracted info
        assert ticket_info["id"] == "PROJ-123"
        assert ticket_info["title"] == "Test Jira ticket"
        assert ticket_info["description"] == "Test Jira description"
        assert ticket_info["status"] == "In Review"

    def test_extract_ticket_info_unknown_tool(self, bot: PullRequestAIAgent) -> None:
        """Test _extract_ticket_info method with unknown tool type."""
        # Set project management tool type to None
        bot.project_management_tool_type = None

        # Create a mock ticket with various attributes
        mock_ticket = MagicMock()
        mock_ticket.id = "TICKET-123"
        mock_ticket.name = "Test ticket name"
        mock_ticket.title = "Test ticket title"
        mock_ticket.description = "Test description"
        mock_ticket.status = "Open"

        # Extract ticket info
        ticket_info = bot._extract_ticket_info(mock_ticket)

        # Verify extracted info - should use generic fallback
        assert ticket_info["id"] == "TICKET-123"
        assert ticket_info["title"] == "Test ticket title"  # Should prefer title over name
        assert ticket_info["description"] == "Test description"
        assert ticket_info["status"] == "Open"

    def test_prepare_ai_prompt_with_prompt_templates(self, bot: PullRequestAIAgent) -> None:
        """Test prepare_ai_prompt method using prompt templates."""
        # Mock commits and tickets
        commits = [
            {"short_hash": "abc123", "message": "Fix bug in login form", "author": "John Doe", "date": "2023-01-01"},
            {"short_hash": "def456", "message": "Add new feature", "author": "Jane Smith", "date": "2023-01-02"},
        ]

        # Create mock tickets
        mock_ticket1 = MagicMock()
        mock_ticket2 = MagicMock()

        # Mock prepare_pr_prompt_data
        mock_prompt_data = MagicMock()
        mock_prompt_data.title = "Test title prompt"

        with patch("pull_request_ai_agent.bot.prepare_pr_prompt_data", return_value=mock_prompt_data) as mock_prepare:
            # Set up _extract_ticket_info to return structured ticket info
            with patch.object(bot, "_extract_ticket_info") as mock_extract_info:
                mock_extract_info.side_effect = [
                    {
                        "id": "PROJ-123",
                        "title": "Fix login bug",
                        "description": "The login form has a bug that needs to be fixed",
                        "status": "In Progress",
                    },
                    {
                        "id": "PROJ-456",
                        "title": "Implement new feature",
                        "description": "Add a new feature to the application",
                        "status": "In Review",
                    },
                ]

                # Call prepare_ai_prompt
                prompt_data = bot.prepare_ai_prompt(commits, [mock_ticket1, mock_ticket2])

                # Verify _extract_ticket_info was called
                assert mock_extract_info.call_count == 2

                # Verify prepare_pr_prompt_data was called with the right arguments
                mock_prepare.assert_called_once()
                call_args = mock_prepare.call_args[1]
                assert len(call_args["task_tickets_details"]) == 2
                assert call_args["task_tickets_details"][0]["id"] == "PROJ-123"
                assert call_args["task_tickets_details"][1]["id"] == "PROJ-456"
                assert len(call_args["commits"]) == 2
                assert call_args["commits"][0]["short_hash"] == "abc123"
                assert call_args["commits"][1]["short_hash"] == "def456"

                # Verify the returned prompt_data is the same as mock_prompt_data
                assert prompt_data is mock_prompt_data

    def test_prepare_ai_prompt_template_not_found(self, bot: PullRequestAIAgent) -> None:
        """Test prepare_ai_prompt method when prompt template is not found."""
        # Mock commits and tickets
        commits = [{"short_hash": "abc123", "message": "Fix bug in login form"}]

        # Create mock ticket
        mock_ticket = MagicMock()

        # Mock prepare_pr_prompt_data to raise FileNotFoundError
        with patch("pull_request_ai_agent.bot.prepare_pr_prompt_data", side_effect=FileNotFoundError("Test error")):
            # Set up _extract_ticket_info to return structured ticket info
            with patch.object(bot, "_extract_ticket_info") as mock_extract_info:
                mock_extract_info.return_value = {
                    "id": "PROJ-123",
                    "title": "Fix login bug",
                    "description": "The login form has a bug that needs to be fixed",
                    "status": "In Progress",
                }

                # Call prepare_ai_prompt should raise FileNotFoundError
                with pytest.raises(FileNotFoundError):
                    bot.prepare_ai_prompt(commits, [mock_ticket])

    def test_prepare_ai_prompt_fallback(self, bot: PullRequestAIAgent) -> None:
        """Test prepare_ai_prompt method falling back to default prompt on error."""
        # Mock commits and tickets
        commits = [{"short_hash": "abc123", "message": "Fix bug in login form"}]

        # Create mock ticket
        mock_ticket = MagicMock()

        # Mock prepare_pr_prompt_data to raise a generic Exception
        with patch("pull_request_ai_agent.bot.prepare_pr_prompt_data", side_effect=Exception("Test error")):
            # Set up _extract_ticket_info to return structured ticket info
            with patch.object(bot, "_extract_ticket_info") as mock_extract_info:
                mock_extract_info.return_value = {
                    "id": "PROJ-123",
                    "title": "Fix login bug",
                    "description": "The login form has a bug that needs to be fixed",
                    "status": "In Progress",
                }

                # Call prepare_ai_prompt
                prompt_data = bot.prepare_ai_prompt(commits, [mock_ticket])

                # Verify the fallback prompt was returned
                assert hasattr(prompt_data, "title")
                assert hasattr(prompt_data, "description")
                assert "I need you to generate a pull request title and description" in prompt_data.description
                assert "abc123 - Fix bug in login form" in prompt_data.description
                assert "PROJ-123: Fix login bug" in prompt_data.description
                assert "Description: The login form has a bug that needs to be fixed" in prompt_data.description
                assert "Status: In Progress" in prompt_data.description

    def test_prepare_ai_prompt_invalid_commits(self, bot: PullRequestAIAgent) -> None:
        """Test prepare_ai_prompt method with invalid commits."""
        # Mock commits without required fields
        commits = [
            {"hash": "abc123", "author": "John Doe"},  # Missing short_hash and message
        ]

        # Create mock ticket
        mock_ticket = MagicMock()

        # Mock prepare_pr_prompt_data
        mock_prompt_data = MagicMock()
        mock_prompt_data.title = "Test title prompt"

        with patch("pull_request_ai_agent.bot.prepare_pr_prompt_data", return_value=mock_prompt_data) as mock_prepare:
            # Set up _extract_ticket_info to return structured ticket info
            with patch.object(bot, "_extract_ticket_info") as mock_extract_info:
                mock_extract_info.return_value = {
                    "id": "PROJ-123",
                    "title": "Fix login bug",
                    "description": "The login form has a bug that needs to be fixed",
                    "status": "In Progress",
                }

                # Call prepare_ai_prompt
                prompt_data = bot.prepare_ai_prompt(commits, [mock_ticket])

                # Verify prepare_pr_prompt_data was called with empty commits list
                mock_prepare.assert_called_once()
                call_args = mock_prepare.call_args[1]
                assert len(call_args["commits"]) == 0

                # Verify the returned prompt_data is the same as mock_prompt_data
                assert prompt_data is mock_prompt_data

    def test_prepare_ai_prompt_with_pr_template(self, bot: PullRequestAIAgent) -> None:
        """Test prepare_ai_prompt method with PR template."""
        # Mock commits and tickets
        commits = [{"short_hash": "abc123", "message": "Fix bug in login form"}]

        # Create mock ticket
        mock_ticket = MagicMock()

        # Mock prepare_pr_prompt_data
        mock_prompt_data = MagicMock()
        mock_prompt_data.title = "Test title prompt with PR template"

        with patch("pull_request_ai_agent.bot.prepare_pr_prompt_data", return_value=mock_prompt_data) as mock_prepare:
            # Set up _extract_ticket_info to return structured ticket info
            with patch.object(bot, "_extract_ticket_info") as mock_extract_info:
                mock_extract_info.return_value = {
                    "id": "PROJ-123",
                    "title": "Fix login bug",
                    "description": "The login form has a bug that needs to be fixed",
                    "status": "In Progress",
                }

                # Call prepare_ai_prompt
                prompt_data = bot.prepare_ai_prompt(commits, [mock_ticket])

                # Verify prepare_pr_prompt_data was called with project_root
                mock_prepare.assert_called_once()
                call_args = mock_prepare.call_args[1]
                assert "project_root" in call_args
                assert call_args["project_root"] == bot.repo_path

                # Verify the returned prompt_data is the same as mock_prompt_data
                assert prompt_data is mock_prompt_data

    def test_prepare_ai_prompt_fallback_with_pr_template(self, bot: PullRequestAIAgent) -> None:
        """Test prepare_ai_prompt fallback with PR template."""
        # Mock commits and tickets
        commits = [{"short_hash": "abc123", "message": "Fix bug in login form"}]

        # Create mock ticket
        mock_ticket = MagicMock()

        # Mock PR template file
        mock_pr_template = "## PR Template\n* Task ID: \n* Description: "

        # Mock prepare_pr_prompt_data to raise Exception
        with patch("pull_request_ai_agent.bot.prepare_pr_prompt_data", side_effect=Exception("Test error")):
            # Set up _extract_ticket_info to return structured ticket info
            with patch.object(bot, "_extract_ticket_info") as mock_extract_info:
                mock_extract_info.return_value = {
                    "id": "PROJ-123",
                    "title": "Fix login bug",
                    "description": "The login form has a bug that needs to be fixed",
                    "status": "In Progress",
                }

                # Mock Path.exists and open for PR template
                with patch("pathlib.Path.exists", return_value=True):
                    with patch("builtins.open", mock_open(read_data=mock_pr_template)):
                        # Call prepare_ai_prompt
                        prompt_data = bot.prepare_ai_prompt(commits, [mock_ticket])

                        # Verify the fallback prompt includes PR template
                        assert hasattr(prompt_data, "title")
                        assert hasattr(prompt_data, "description")
                        assert "Pull Request Template" in prompt_data.description
                        assert mock_pr_template in prompt_data.description
