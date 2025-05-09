import argparse
import logging
import os
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Dict, Optional, Union

import yaml

from create_pr_bot.ai_bot import AiModuleClient
from create_pr_bot.project_management_tool import ProjectManagementToolType

logger = logging.getLogger(__name__)


class EnvVarPrefix(Enum):
    """Enum for environment variable prefixes."""

    CREATE_PR_BOT = "CREATE_PR_BOT"


def load_yaml_config(config_path: Union[str, Path]) -> Dict[str, Any]:
    """
    Load configuration from a YAML file.

    Args:
        config_path: Path to the YAML configuration file

    Returns:
        Dictionary containing the configuration

    Raises:
        FileNotFoundError: If the configuration file does not exist
        yaml.YAMLError: If the configuration file is not valid YAML
    """
    config_path = Path(config_path)
    if not config_path.exists():
        raise FileNotFoundError(f"Configuration file not found: {config_path}")

    try:
        with open(config_path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)

        if config is None:
            # Empty file or only comments
            return {}

        if not isinstance(config, dict):
            raise ValueError(f"Invalid configuration format in {config_path}. Expected a dictionary.")

        return config
    except yaml.YAMLError as e:
        logger.error(f"Error parsing YAML configuration file {config_path}: {str(e)}")
        raise


def find_default_config_path(repo_path: Union[str, Path] = ".") -> Optional[Path]:
    """
    Find the default configuration file path.

    Args:
        repo_path: Path to the git repository

    Returns:
        Path to the configuration file or None if not found
    """
    repo_path = Path(repo_path)
    default_config_path = repo_path / ".github" / "pr-creator.yaml"

    if default_config_path.exists():
        return default_config_path

    # Also check for .yml extension
    alt_config_path = repo_path / ".github" / "pr-creator.yml"
    if alt_config_path.exists():
        return alt_config_path

    return None


@dataclass
class ProjectManagementToolSettings:
    """Settings for project management tool."""

    tool_type: Optional[ProjectManagementToolType] = None
    api_key: Optional[str] = None
    organization_id: Optional[str] = None
    project_id: Optional[str] = None
    base_url: Optional[str] = None
    username: Optional[str] = None

    @classmethod
    def from_env(cls) -> "ProjectManagementToolSettings":
        """Load settings from environment variables."""
        prefix = f"{EnvVarPrefix.CREATE_PR_BOT.value}_PM_TOOL"

        # Get tool type
        tool_type_str = os.environ.get(f"{prefix}_TYPE")
        tool_type = None
        if tool_type_str:
            try:
                tool_type = ProjectManagementToolType(tool_type_str.lower())
            except ValueError:
                logger.warning(f"Invalid project management tool type: {tool_type_str}")

        return cls(
            tool_type=tool_type,
            api_key=os.environ.get(f"{prefix}_API_KEY"),
            organization_id=os.environ.get(f"{prefix}_ORGANIZATION_ID"),
            project_id=os.environ.get(f"{prefix}_PROJECT_ID"),
            base_url=os.environ.get(f"{prefix}_BASE_URL"),
            username=os.environ.get(f"{prefix}_USERNAME"),
        )

    @classmethod
    def serialize(cls, config: Dict[str, Any]) -> "ProjectManagementToolSettings":
        """
        Load settings from a configuration dictionary.

        Args:
            config: Dictionary containing the configuration

        Returns:
            ProjectManagementToolSettings object
        """
        if not config:
            return cls()

        pm_config = config.get("project_management_tool", {})

        # Get tool type
        tool_type_str = pm_config.get("type")
        tool_type = None
        if tool_type_str:
            try:
                tool_type = ProjectManagementToolType(tool_type_str.lower())
            except ValueError:
                logger.warning(f"Invalid project management tool type: {tool_type_str}")

        return cls(
            tool_type=tool_type,
            api_key=pm_config.get("api_key"),
            organization_id=pm_config.get("organization_id"),
            project_id=pm_config.get("project_id"),
            base_url=pm_config.get("base_url"),
            username=pm_config.get("username"),
        )


@dataclass
class AISettings:
    """Settings for AI client."""

    client_type: AiModuleClient = AiModuleClient.GPT
    api_key: Optional[str] = None

    @classmethod
    def from_env(cls) -> "AISettings":
        """Load settings from environment variables."""
        prefix = f"{EnvVarPrefix.CREATE_PR_BOT.value}_AI"

        # Get client type
        client_type_str = os.environ.get(f"{prefix}_CLIENT_TYPE", AiModuleClient.GPT.value)
        client_type = AiModuleClient.GPT  # Default to GPT

        try:
            client_type = AiModuleClient(client_type_str.lower())
        except ValueError:
            logger.warning(f"Invalid AI client type: {client_type_str}. Using default: {client_type.value}")

        return cls(
            client_type=client_type,
            api_key=os.environ.get(f"{prefix}_API_KEY"),
        )

    @classmethod
    def serialize(cls, config: Dict[str, Any]) -> "AISettings":
        """
        Load settings from a configuration dictionary.

        Args:
            config: Dictionary containing the configuration

        Returns:
            AISettings object
        """
        if not config:
            return cls()

        ai_config = config.get("ai", {})

        # Get client type
        client_type_str = ai_config.get("client_type", AiModuleClient.GPT.value)
        client_type = AiModuleClient.GPT  # Default to GPT

        if client_type_str:
            try:
                client_type = AiModuleClient(client_type_str.lower())
            except ValueError:
                logger.warning(f"Invalid AI client type: {client_type_str}. Using default: {client_type.value}")

        return cls(
            client_type=client_type,
            api_key=ai_config.get("api_key"),
        )


@dataclass
class GitHubSettings:
    """Settings for GitHub operations."""

    token: Optional[str] = None
    repo: Optional[str] = None

    @classmethod
    def from_env(cls) -> "GitHubSettings":
        """Load settings from environment variables."""
        prefix = f"{EnvVarPrefix.CREATE_PR_BOT.value}_GITHUB"

        # Try both specific and generic GitHub token env vars
        token = os.environ.get(f"{prefix}_TOKEN") or os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")

        return cls(
            token=token,
            repo=os.environ.get(f"{prefix}_REPO"),
        )

    @classmethod
    def serialize(cls, config: Dict[str, Any]) -> "GitHubSettings":
        """
        Load settings from a configuration dictionary.

        Args:
            config: Dictionary containing the configuration

        Returns:
            GitHubSettings object
        """
        if not config:
            return cls()

        github_config = config.get("github", {})

        return cls(
            token=github_config.get("token"),
            repo=github_config.get("repo"),
        )


@dataclass
class GitSettings:
    """Settings for Git operations."""

    repo_path: str = "."
    base_branch: str = "main"
    branch_name: Optional[str] = None

    @classmethod
    def from_env(cls) -> "GitSettings":
        """Load settings from environment variables."""
        prefix = f"{EnvVarPrefix.CREATE_PR_BOT.value}_GIT"

        return cls(
            repo_path=os.environ.get(f"{prefix}_REPO_PATH", "."),
            base_branch=os.environ.get(f"{prefix}_BASE_BRANCH", "main"),
            branch_name=os.environ.get(f"{prefix}_BRANCH_NAME"),
        )

    @classmethod
    def serialize(cls, config: Dict[str, Any]) -> "GitSettings":
        """
        Load settings from a configuration dictionary.

        Args:
            config: Dictionary containing the configuration

        Returns:
            GitSettings object
        """
        if not config:
            return cls()

        git_config = config.get("git", {})

        return cls(
            repo_path=git_config.get("repo_path", "."),
            base_branch=git_config.get("base_branch", "main"),
            branch_name=git_config.get("branch_name"),
        )


@dataclass
class BotSettings:
    """Settings for the Create PR Bot."""

    git: GitSettings
    github: GitHubSettings
    ai: AISettings
    pm_tool: ProjectManagementToolSettings

    @classmethod
    def from_env(cls) -> "BotSettings":
        """Load settings from environment variables."""
        return cls(
            git=GitSettings.from_env(),
            github=GitHubSettings.from_env(),
            ai=AISettings.from_env(),
            pm_tool=ProjectManagementToolSettings.from_env(),
        )

    @classmethod
    def from_config_file(cls, config_path: Union[str, Path]) -> "BotSettings":
        """
        Load settings from a configuration file.

        Args:
            config_path: Path to the configuration file

        Returns:
            BotSettings object
        """
        config = load_yaml_config(config_path)
        return cls.serialize(config)

    @classmethod
    def serialize(cls, config: Dict[str, Any]) -> "BotSettings":
        """
        Load settings from a configuration dictionary.

        Args:
            config: Dictionary containing the configuration

        Returns:
            BotSettings object
        """
        return cls(
            git=GitSettings.serialize(config),
            github=GitHubSettings.serialize(config),
            ai=AISettings.serialize(config),
            pm_tool=ProjectManagementToolSettings.serialize(config),
        )

    @classmethod
    def from_args(cls, args: argparse.Namespace) -> "BotSettings":
        """Load settings from command line arguments."""
        # Start with environment variables
        settings = cls.from_env()

        # Override with config file if provided
        if hasattr(args, "config_file") and args.config_file:
            config_settings = cls.from_config_file(args.config_file)

            # Merge settings
            settings.git = config_settings.git
            settings.github = config_settings.github
            settings.ai = config_settings.ai
            settings.pm_tool = config_settings.pm_tool
        else:
            # Try to find default config file
            default_config_path = find_default_config_path(
                args.repo_path if hasattr(args, "repo_path") and args.repo_path else "."
            )
            if default_config_path:
                logger.info(f"Using default configuration file: {default_config_path}")
                config_settings = cls.from_config_file(default_config_path)

                # Merge settings
                settings.git = config_settings.git
                settings.github = config_settings.github
                settings.ai = config_settings.ai
                settings.pm_tool = config_settings.pm_tool

        # Override with command line arguments if provided
        if hasattr(args, "repo_path") and args.repo_path:
            settings.git.repo_path = args.repo_path

        if hasattr(args, "base_branch") and args.base_branch:
            settings.git.base_branch = args.base_branch

        if hasattr(args, "branch_name") and args.branch_name:
            settings.git.branch_name = args.branch_name

        if hasattr(args, "github_token") and args.github_token:
            settings.github.token = args.github_token

        if hasattr(args, "github_repo") and args.github_repo:
            settings.github.repo = args.github_repo

        if hasattr(args, "ai_client_type") and args.ai_client_type:
            settings.ai.client_type = AiModuleClient(args.ai_client_type.lower())

        if hasattr(args, "ai_api_key") and args.ai_api_key:
            settings.ai.api_key = args.ai_api_key

        if hasattr(args, "pm_tool_type") and args.pm_tool_type:
            settings.pm_tool.tool_type = ProjectManagementToolType(args.pm_tool_type.lower())

        if hasattr(args, "pm_tool_api_key") and args.pm_tool_api_key:
            settings.pm_tool.api_key = args.pm_tool_api_key

        return settings
