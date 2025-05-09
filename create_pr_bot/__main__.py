"""
Entry point for the Create PR Bot.

This module provides the command line interface for the Create PR Bot,
which automates the creation of pull requests with AI-generated content.
"""

import argparse
import logging
import sys

from create_pr_bot.ai_bot import AiModuleClient
from create_pr_bot.bot import CreatePrAIBot
from create_pr_bot.log import init_logger_config
from create_pr_bot.model import BotSettings, find_default_config_path
from create_pr_bot.project_management_tool import ProjectManagementToolType

# Configure logging
init_logger_config(level=logging.DEBUG)
logger = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Create PR Bot - Automate pull request creation with AI-generated content"
    )

    # Configuration file
    parser.add_argument(
        "--config",
        dest="config_file",
        help="Path to configuration file (default: .github/pr-creator.yaml or .github/pr-creator.yml in the repository)",
    )

    # Git settings
    parser.add_argument("--repo-path", help="Path to the git repository (default: current directory)")
    parser.add_argument("--base-branch", help="Name of the base branch to compare against (default: main)")
    parser.add_argument("--branch-name", help="Name of the branch to create PR from (default: current branch)")

    # GitHub settings
    parser.add_argument("--github-token", help="GitHub access token for API access")
    parser.add_argument("--github-repo", help="GitHub repository name in format 'owner/repo'")

    # AI settings
    parser.add_argument(
        "--ai-client-type",
        choices=[client.value for client in AiModuleClient],
        default=AiModuleClient.CLAUDE.value,
        help="Type of AI client to use",
    )
    parser.add_argument("--ai-api-key", help="API key for the AI service")

    # Project management tool settings
    parser.add_argument(
        "--pm-tool-type",
        choices=[pm.value for pm in ProjectManagementToolType],
        default=ProjectManagementToolType.CLICKUP.value,
        help="Type of project management tool to use",
    )
    parser.add_argument("--pm-tool-api-key", help="API key for the project management tool")

    return parser.parse_args()


def run_bot(settings: BotSettings) -> None:
    """Run the Create PR Bot with the provided settings."""
    try:
        logger.info("Initializing Create PR Bot...")

        # Create project management tool config
        pm_tool_config = settings.pm_tool if settings.pm_tool.tool_type else None

        # Initialize the bot
        bot = CreatePrAIBot(
            repo_path=settings.git.repo_path,
            base_branch=settings.git.base_branch,
            github_token=settings.github.token,
            github_repo=settings.github.repo,
            project_management_tool_type=settings.pm_tool.tool_type,
            project_management_tool_config=pm_tool_config,
            ai_client_type=settings.ai.client_type,
            ai_client_api_key=settings.ai.api_key,
        )

        # Run the bot
        logger.info("Running Create PR Bot...")
        result = bot.run(branch_name=settings.git.branch_name)

        if result:
            logger.info(f"Successfully created PR: {result.html_url}")
        else:
            logger.info("No PR was created. See logs for details.")

    except Exception as e:
        logger.error(f"Error running Create PR Bot: {str(e)}", exc_info=True)
        sys.exit(1)


def main() -> None:
    """Main entry point for the Create PR Bot."""
    # Parse command line arguments
    args = parse_args()

    # Check for default config file if not specified
    if not args.config_file:
        default_config_path = find_default_config_path(args.repo_path if args.repo_path else ".")
        if default_config_path:
            logger.info(f"Found default configuration file: {default_config_path}")

    # Load settings
    settings = BotSettings.from_args(args)

    # Run the bot
    run_bot(settings)


if __name__ == "__main__":
    main()
