"""
Unit tests for the entry point module.
"""

import sys
from unittest.mock import MagicMock, patch

from create_pr_bot.__main__ import main, parse_args, run_bot
from create_pr_bot.ai_bot import AiModuleClient
from create_pr_bot.project_management_tool import ProjectManagementToolType


class TestParseArgs:
    """Tests for the parse_args function."""

    def test_parse_args_empty(self):
        """Test parsing empty command line arguments."""
        with patch.object(sys, "argv", ["create_pr_bot"]):
            args = parse_args()
            assert args.repo_path is None
            assert args.base_branch is None
            assert args.branch_name is None
            assert args.github_token is None
            assert args.github_repo is None
            assert args.ai_client_type == AiModuleClient.CLAUDE.value
            assert args.ai_api_key is None
            assert args.pm_tool_type == ProjectManagementToolType.CLICKUP.value
            assert args.pm_tool_api_key is None

    def test_parse_args_with_values(self):
        """Test parsing command line arguments with values."""
        test_args = [
            "create_pr_bot",
            "--repo-path",
            "/path/to/repo",
            "--base-branch",
            "master",
            "--branch-name",
            "feature/test",
            "--github-token",
            "test-token",
            "--github-repo",
            "owner/repo",
            "--ai-client-type",
            "claude",
            "--ai-api-key",
            "test-ai-key",
            "--pm-tool-type",
            "jira",
            "--pm-tool-api-key",
            "test-pm-key",
        ]

        with patch.object(sys, "argv", test_args):
            args = parse_args()
            assert args.repo_path == "/path/to/repo"
            assert args.base_branch == "master"
            assert args.branch_name == "feature/test"
            assert args.github_token == "test-token"
            assert args.github_repo == "owner/repo"
            assert args.ai_client_type == "claude"
            assert args.ai_api_key == "test-ai-key"
            assert args.pm_tool_type == "jira"
            assert args.pm_tool_api_key == "test-pm-key"


class TestRunBot:
    """Tests for the run_bot function."""

    def test_run_bot_success(self):
        """Test running the bot successfully."""
        # Create mock settings
        mock_settings = MagicMock()
        mock_settings.git.repo_path = "/path/to/repo"
        mock_settings.git.base_branch = "main"
        mock_settings.git.branch_name = "feature/test"
        mock_settings.github.token = "test-token"
        mock_settings.github.repo = "owner/repo"
        mock_settings.ai.client_type = AiModuleClient.GPT
        mock_settings.ai.api_key = "test-ai-key"
        mock_settings.pm_tool.tool_type = ProjectManagementToolType.CLICKUP

        # Create mock bot and PR result
        mock_bot = MagicMock()
        mock_pr = MagicMock()
        mock_pr.html_url = "https://github.com/owner/repo/pull/1"
        mock_bot.run.return_value = mock_pr

        with patch("create_pr_bot.__main__.CreatePrAIBot", return_value=mock_bot) as mock_create_bot:
            with patch("logging.Logger.info") as mock_info:
                run_bot(mock_settings)

                # Verify bot was created with correct settings
                mock_create_bot.assert_called_once_with(
                    repo_path="/path/to/repo",
                    base_branch="main",
                    github_token="test-token",
                    github_repo="owner/repo",
                    project_management_tool_type=ProjectManagementToolType.CLICKUP,
                    project_management_tool_config=mock_settings.pm_tool,
                    ai_client_type=AiModuleClient.GPT,
                    ai_client_api_key="test-ai-key",
                )

                # Verify bot.run was called with correct branch name
                mock_bot.run.assert_called_once_with(branch_name="feature/test")

                # Verify success message was logged
                mock_info.assert_any_call(f"Successfully created PR: {mock_pr.html_url}")

    def test_run_bot_no_pr_created(self):
        """Test running the bot with no PR created."""
        # Create mock settings
        mock_settings = MagicMock()

        # Create mock bot that returns None (no PR created)
        mock_bot = MagicMock()
        mock_bot.run.return_value = None

        with patch("create_pr_bot.__main__.CreatePrAIBot", return_value=mock_bot):
            with patch("logging.Logger.info") as mock_info:
                run_bot(mock_settings)

                # Verify info message was logged
                mock_info.assert_any_call("No PR was created. See logs for details.")

    def test_run_bot_exception(self):
        """Test running the bot with an exception."""
        # Create mock settings
        mock_settings = MagicMock()

        # Create mock bot that raises an exception
        mock_bot = MagicMock()
        mock_bot.run.side_effect = Exception("Test error")

        with patch("create_pr_bot.__main__.CreatePrAIBot", return_value=mock_bot):
            with patch("logging.Logger.error") as mock_error:
                with patch("sys.exit") as mock_exit:
                    run_bot(mock_settings)

                    # Verify error was logged
                    mock_error.assert_called_once()
                    assert "Test error" in mock_error.call_args[0][0]

                    # Verify sys.exit was called with code 1
                    mock_exit.assert_called_once_with(1)


class TestMain:
    """Tests for the main function."""

    def test_main(self):
        """Test the main function."""
        mock_args = MagicMock()
        mock_settings = MagicMock()

        with patch("create_pr_bot.__main__.parse_args", return_value=mock_args) as mock_parse_args:
            with patch("create_pr_bot.__main__.BotSettings.from_args", return_value=mock_settings) as mock_from_args:
                with patch("create_pr_bot.__main__.run_bot") as mock_run_bot:
                    main()

                    # Verify functions were called in the correct order
                    mock_parse_args.assert_called_once()
                    mock_from_args.assert_called_once_with(mock_args)
                    mock_run_bot.assert_called_once_with(mock_settings)
