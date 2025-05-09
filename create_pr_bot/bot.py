"""
CreatePrAIBot - A bot that helps developers create pull requests with AI-generated content.
"""

import logging
import re
import traceback
from typing import Any, Dict, List, Optional, Tuple

from github.PullRequest import PullRequest

from .ai_bot import AiModuleClient
from .ai_bot._base.client import BaseAIClient
from .ai_bot.claude.client import ClaudeClient
from .ai_bot.gemini.client import GeminiClient
from .ai_bot.gpt.client import GPTClient
from .ai_bot.prompts.model import prepare_pr_prompt_data
from .git_hdlr import GitCodeConflictError, GitHandler
from .github_opt import GitHubOperations
from .model import ProjectManagementToolSettings
from .project_management_tool import ProjectManagementToolType
from .project_management_tool._base.client import BaseProjectManagementAPIClient
from .project_management_tool._base.model import BaseImmutableModel
from .project_management_tool.clickup.client import ClickUpAPIClient
from .project_management_tool.jira.client import JiraAPIClient

logger = logging.getLogger(__name__)


class CreatePrAIBot:
    """
    A bot that automates creation of pull requests with AI-generated content
    based on git commits and task tickets information.
    """

    # AI client types
    AI_CLIENT_GPT = AiModuleClient.GPT
    AI_CLIENT_CLAUDE = AiModuleClient.CLAUDE
    AI_CLIENT_GEMINI = AiModuleClient.GEMINI

    # Project management tool types
    PM_TOOL_CLICKUP = ProjectManagementToolType.CLICKUP
    PM_TOOL_JIRA = ProjectManagementToolType.JIRA

    def __init__(
        self,
        repo_path: str = ".",
        base_branch: str = "main",
        github_token: Optional[str] = None,
        github_repo: Optional[str] = None,
        project_management_tool_type: Optional[ProjectManagementToolType] = None,
        project_management_tool_config: Optional[ProjectManagementToolSettings] = None,
        ai_client_type: AiModuleClient = AI_CLIENT_GPT,
        ai_client_api_key: Optional[str] = None,
    ):
        """
        Initialize the CreatePrAIBot.

        Args:
            repo_path: Path to the git repository. Defaults to current directory.
            base_branch: Name of the base branch to compare against. Defaults to "main".
            github_token: GitHub access token for API access.
            github_repo: GitHub repository name in format 'owner/repo'.
            project_management_tool_type: Type of project management tool to use.
            project_management_tool_config: Configuration for the project management tool.
            ai_client_type: Type of AI client to use (gpt, claude, gemini).
            ai_client_api_key: API key for the AI service.
        """
        self.repo_path = repo_path
        self.base_branch = base_branch
        self.git_handler = GitHandler(repo_path)

        # Initialize GitHub operations if token and repo are provided
        self.github_operations = None
        if github_token and github_repo:
            self.github_operations = GitHubOperations(github_token, github_repo)

        # Initialize project management client based on type
        self.project_management_client = None
        self.project_management_tool_type = project_management_tool_type
        if project_management_tool_type and project_management_tool_config:
            self.project_management_client = self._initialize_project_management_client(
                project_management_tool_type, project_management_tool_config
            )

        # Initialize AI client based on type
        self.ai_client = self._initialize_ai_client(ai_client_type, ai_client_api_key)

    def _initialize_project_management_client(
        self, tool_type: ProjectManagementToolType, config: ProjectManagementToolSettings
    ) -> Optional[BaseProjectManagementAPIClient]:
        """
        Initialize the project management client based on the specified type.

        Args:
            tool_type: Type of project management tool
            config: Configuration for the project management tool

        Returns:
            Initialized project management client or None if initialization fails

        Raises:
            ValueError: If the tool type is not supported or required config is missing
        """
        if tool_type == self.PM_TOOL_CLICKUP:
            if not config.api_key:
                raise ValueError("ClickUp API token is required")
            return ClickUpAPIClient(api_token=config.api_key)
        elif tool_type == self.PM_TOOL_JIRA:
            required_keys = ["base_url", "username", "api_key"]
            for key in required_keys:
                if getattr(config, key) is None:
                    raise ValueError(f"Jira {key} is required")
            return JiraAPIClient(base_url=config.base_url, email=config.username, api_token=config.api_key)
        else:
            raise ValueError(f"Unsupported project management tool type: {tool_type}")

    def _initialize_ai_client(self, client_type: AiModuleClient, api_key: Optional[str] = None) -> BaseAIClient:
        """
        Initialize the AI client based on the specified type.

        Args:
            client_type: Type of AI client (gpt, claude, gemini)
            api_key: API key for the AI service

        Returns:
            Initialized AI client

        Raises:
            ValueError: If the client type is not supported
        """
        if client_type == self.AI_CLIENT_GPT:
            return GPTClient(api_key=api_key)
        elif client_type == self.AI_CLIENT_CLAUDE:
            return ClaudeClient(api_key=api_key)
        elif client_type == self.AI_CLIENT_GEMINI:
            return GeminiClient(api_key=api_key)
        else:
            raise ValueError(f"Unsupported AI client type: {client_type}")

    def _get_current_branch(self) -> str:
        """
        Get the name of the current git branch.

        Returns:
            Name of the current branch
        """
        return self.git_handler._get_current_branch()

    def is_branch_outdated(self, branch_name: Optional[str] = None) -> bool:
        """
        Check if the branch is outdated compared to the base branch.

        Args:
            branch_name: Name of the branch to check. If None, uses the current branch.

        Returns:
            True if the branch is outdated, False otherwise
        """
        if not branch_name:
            branch_name = self._get_current_branch()

        return self.git_handler.is_branch_outdated(branch_name, self.base_branch)

    def is_pr_already_opened(self, branch_name: Optional[str] = None) -> bool:
        """
        Check if a pull request is already opened for the branch.

        Args:
            branch_name: Name of the branch to check. If None, uses the current branch.

        Returns:
            True if a PR exists, False otherwise
        """
        if not branch_name:
            branch_name = self._get_current_branch()

        if not self.github_operations:
            logger.warning("GitHub operations not configured. Cannot check if PR exists.")
            return False

        try:
            pr = self.github_operations.get_pull_request_by_branch(branch_name)
            return pr is not None
        except Exception as e:
            logger.error(f"Error checking if PR exists: {str(e)}")
            return False

    def fetch_and_merge_latest_from_base_branch(self, branch_name: Optional[str] = None) -> bool:
        """
        Fetch and merge the latest changes from the remote base branch.

        Args:
            branch_name: Name of the branch to update. If None, uses the current branch.

        Returns:
            True if update was successful, False otherwise

        Raises:
            GitCodeConflictError: If there is a merge conflict
        """
        if not branch_name:
            branch_name = self._get_current_branch()

        try:
            return self.git_handler.fetch_and_merge_remote_branch(branch_name)
        except GitCodeConflictError as e:
            logger.error(f"Merge conflict detected: {str(e)}")
            raise

    def get_branch_commits(self, branch_name: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get all commits in the branch that are not in the base branch.

        Args:
            branch_name: Name of the branch to get commits from. If None, uses the current branch.

        Returns:
            List of commit details

        Raises:
            ValueError: If the feature branch or base branch cannot be found
        """
        if not branch_name:
            branch_name = self._get_current_branch()

        # Get the commits between the base branch and the current branch
        repo = self.git_handler.repo

        try:
            # Check if branches exist using repo.refs
            refs = {ref.name: ref for ref in repo.refs}

            # Try different possible reference formats
            feature_ref_options = [
                branch_name,
                f"refs/heads/{branch_name}",
                f"origin/{branch_name}",
                f"refs/remotes/origin/{branch_name}",
            ]

            base_ref_options = [
                self.base_branch,
                f"refs/heads/{self.base_branch}",
                f"origin/{self.base_branch}",
                f"refs/remotes/origin/{self.base_branch}",
            ]

            # Find valid references using filter
            feature_branch_ref = next(filter(lambda ref: ref in refs, feature_ref_options), None)
            base_branch_ref = next(filter(lambda ref: ref in refs, base_ref_options), None)

            # If we couldn't find valid references, raise an error
            if not feature_branch_ref:
                error_msg = f"Feature branch '{branch_name}' not found. Available references: {list(refs.keys())}"
                logger.error(error_msg)
                raise ValueError(error_msg)

            if not base_branch_ref:
                error_msg = f"Base branch '{self.base_branch}' not found. Available references: {list(refs.keys())}"
                logger.error(error_msg)
                raise ValueError(error_msg)

            # Get the merge base between the branches
            merge_base = repo.merge_base(feature_branch_ref, base_branch_ref)
            if not merge_base:
                return []

            # Get all commits from merge base to head of branch
            base_commit = merge_base[0]
            commits = []

            # Iterate through commits in reverse chronological order
            for commit in repo.iter_commits(f"{branch_name}"):
                # Stop when we reach the merge base
                if commit.hexsha == base_commit.hexsha:
                    break

                commits.append(
                    {
                        "hash": commit.hexsha,
                        "short_hash": commit.hexsha[:7],
                        "author": {"name": commit.author.name, "email": commit.author.email},
                        "committer": {"name": commit.committer.name, "email": commit.committer.email},
                        "message": commit.message.strip(),
                        "committed_date": commit.committed_date,
                        "authored_date": commit.authored_date,
                    }
                )

            return commits
        except ValueError:
            # Re-raise ValueError exceptions (our custom errors)
            raise
        except Exception as e:
            logger.error(f"Error getting branch commits: {str(e)}")
            traceback.print_exc()
            return []

    def extract_ticket_ids(self, commits: List[Dict[str, Any]]) -> List[str]:
        """
        Extract ticket IDs from commit messages.

        Args:
            commits: List of commit details

        Returns:
            List of unique ticket IDs
        """
        ticket_ids = set()

        # Common patterns for ticket IDs in commit messages
        # Adjust patterns based on your project's conventions
        patterns = [
            r"#(\d+)",  # GitHub issue format: #123
            r"([A-Z]+-\d+)",  # Jira format: PROJ-123
            r"CU-([a-z0-9]+)",  # ClickUp format: CU-abc123
            r"Task-(\d+)",  # Generic task format: Task-123
        ]

        for commit in commits:
            message = commit["message"]

            for pattern in patterns:
                matches = re.findall(pattern, message)
                ticket_ids.update(matches)

        return list(ticket_ids)

    def get_ticket_details(self, ticket_ids: List[str]) -> List[BaseImmutableModel]:
        """
        Get details for each ticket ID from the project management system.

        Args:
            ticket_ids: List of ticket IDs to get details for

        Returns:
            List of ticket details as BaseImmutableModel objects
        """
        if not self.project_management_client:
            logger.warning("Project management client not configured. Cannot get ticket details.")
            return []

        if not ticket_ids:
            logger.info("No ticket IDs provided. Skipping ticket details retrieval.")
            return []

        ticket_details = []

        for ticket_id in ticket_ids:
            try:
                # Format ticket ID based on project management tool type
                formatted_ticket_id = self._format_ticket_id(ticket_id)
                if not formatted_ticket_id:
                    logger.warning(f"Could not format ticket ID: {ticket_id}")
                    continue

                logger.info(f"Fetching details for ticket: {formatted_ticket_id}")
                ticket = self.project_management_client.get_ticket(formatted_ticket_id)

                if ticket:
                    logger.info(f"Successfully retrieved ticket: {formatted_ticket_id}")
                    ticket_details.append(ticket)
                else:
                    logger.warning(f"No ticket found with ID: {formatted_ticket_id}")
            except Exception as e:
                logger.error(f"Error getting details for ticket {ticket_id}: {str(e)}")

        return ticket_details

    def _format_ticket_id(self, ticket_id: str) -> Optional[str]:
        """
        Format the ticket ID based on the project management tool type.

        Args:
            ticket_id: Raw ticket ID from commit message

        Returns:
            Formatted ticket ID or None if formatting fails
        """
        if not ticket_id:
            return None

        # Remove any leading/trailing whitespace
        ticket_id = ticket_id.strip()

        if self.project_management_tool_type == self.PM_TOOL_CLICKUP:
            # For ClickUp, if the ID starts with "CU-", remove it
            if ticket_id.startswith("CU-"):
                return ticket_id[3:]
            return ticket_id
        elif self.project_management_tool_type == self.PM_TOOL_JIRA:
            # For Jira, the ID format is typically PROJECT-123
            return ticket_id
        else:
            # For unknown tool types, return as is
            return ticket_id

    def prepare_ai_prompt(self, commits: List[Dict[str, Any]], ticket_details: List[BaseImmutableModel]) -> str:
        """
        Prepare a prompt for the AI to generate a PR title and body.

        Args:
            commits: List of commit details
            ticket_details: List of ticket details as BaseImmutableModel objects

        Returns:
            Formatted prompt string
        """
        # Extract ticket information
        ticket_info_list = []
        for ticket in ticket_details:
            ticket_info = self._extract_ticket_info(ticket)
            ticket_info_list.append(ticket_info)

        # Ensure commits have required fields
        formatted_commits = []
        for commit in commits:
            if "short_hash" in commit and "message" in commit:
                formatted_commits.append({"short_hash": commit["short_hash"], "message": commit["message"]})

        try:
            # Process prompt templates
            prompt_data = prepare_pr_prompt_data(
                task_tickets_details=ticket_info_list, commits=formatted_commits, project_root=self.repo_path
            )

            # For now, we'll just use the title prompt
            # In the future, we could use both title and description separately
            return prompt_data.title

        except FileNotFoundError as e:
            logger.error(f"Failed to load prompt template: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Error preparing AI prompt: {str(e)}")

            # Fallback to a simple prompt
            prompt = (
                "I need you to generate a pull request title and description based on the following information:\n\n"
            )

            # Add commit information
            prompt += "## Commits\n"
            for i, commit in enumerate(commits, 1):
                prompt += f"{i}. {commit.get('short_hash', '')} - {commit.get('message', '')}\n"

            prompt += "\n"

            # Add ticket information
            if ticket_info_list:
                prompt += "## Related Tickets\n"
                for i, ticket_info in enumerate(ticket_info_list, 1):
                    prompt += f"{i}. {ticket_info.get('id', '')}: {ticket_info.get('title', '')}\n"
                    if ticket_info.get("description"):
                        # Truncate long descriptions
                        short_desc = (
                            ticket_info["description"][:200] + "..."
                            if len(ticket_info["description"]) > 200
                            else ticket_info["description"]
                        )
                        prompt += f"   Description: {short_desc}\n"

                    # Add status if available
                    if ticket_info.get("status"):
                        prompt += f"   Status: {ticket_info['status']}\n"

                prompt += "\n"

            # Add PR template if available
            try:
                from pathlib import Path

                pr_template_path = Path(self.repo_path) / ".github" / "PULL_REQUEST_TEMPLATE.md"
                if pr_template_path.exists():
                    with open(pr_template_path, "r", encoding="utf-8") as file:
                        pr_template = file.read()
                    prompt += f"## Pull Request Template\n{pr_template}\n\n"
            except Exception as e:
                # Ignore errors when trying to read PR template in fallback mode
                logger.error(f"Error setting pull request template into AI prompt: {str(e)}")

            return prompt

    def _extract_ticket_info(self, ticket: BaseImmutableModel) -> Dict[str, str]:
        """
        Extract relevant information from a ticket based on its type.

        Args:
            ticket: Ticket object as a BaseImmutableModel

        Returns:
            Dictionary with standardized ticket information
        """
        ticket_info = {"id": "", "title": "", "description": "", "status": ""}

        # Handle different ticket types
        if self.project_management_tool_type == self.PM_TOOL_CLICKUP:
            # For ClickUp tickets
            ticket_info["id"] = getattr(ticket, "id", "")
            ticket_info["title"] = getattr(ticket, "name", "")

            # Use text_content if available, otherwise use description
            description = getattr(ticket, "text_content", None)
            if not description:
                description = getattr(ticket, "description", "")
            ticket_info["description"] = description or ""

            # Get status if available
            status = getattr(ticket, "status", None)
            if status:
                ticket_info["status"] = getattr(status, "status", "")

        elif self.project_management_tool_type == self.PM_TOOL_JIRA:
            # For Jira tickets
            ticket_info["id"] = getattr(ticket, "id", "")
            ticket_info["title"] = getattr(ticket, "title", "")
            ticket_info["description"] = getattr(ticket, "description", "")
            ticket_info["status"] = getattr(ticket, "status", "")
        else:
            # Generic fallback for unknown ticket types
            # Try to extract common attributes
            for field in ["id", "title", "name", "description", "status"]:
                value = getattr(ticket, field, None)
                if value and isinstance(value, str):
                    if field == "name" and not ticket_info["title"]:
                        ticket_info["title"] = value
                    else:
                        ticket_info[field] = value

        return ticket_info

    def parse_ai_response(self, response: str) -> Tuple[str, str]:
        """
        Parse the AI-generated response into a PR title and body.

        Args:
            response: Raw response from the AI

        Returns:
            Tuple of (title, body)
        """
        # Extract title and body from the response
        title_match = re.search(r"TITLE:\s*(.*?)(?:\n|$)", response)
        title = title_match.group(1).strip() if title_match else "Automated Pull Request"

        body_match = re.search(r"BODY:\s*(.*)", response, re.DOTALL)
        body = body_match.group(1).strip() if body_match else response

        return title, body

    def create_pull_request(self, title: str, body: str, branch_name: Optional[str] = None) -> Optional[PullRequest]:
        """
        Create a pull request from the branch to the base branch.

        Args:
            title: Title of the pull request
            body: Body/description of the pull request
            branch_name: Name of the branch to create PR from. If None, uses the current branch.

        Returns:
            Created PullRequest object or None if creation failed
        """
        if not branch_name:
            branch_name = self._get_current_branch()

        if not self.github_operations:
            logger.error("GitHub operations not configured. Cannot create PR.")
            return None

        try:
            # Create the pull request
            pr = self.github_operations.create_pull_request(
                title=title, body=body, base_branch=self.base_branch, head_branch=branch_name
            )

            logger.info(f"Created pull request #{pr.number}: {pr.html_url}")
            return pr
        except Exception as e:
            logger.error(f"Error creating pull request: {str(e)}")
            return None

    def run(self, branch_name: Optional[str] = None) -> Optional[PullRequest]:
        """
        Run the PR creation workflow.

        Args:
            branch_name: Name of the branch to create PR from. If None, uses the current branch.

        Returns:
            Created PullRequest object or None if no PR was created
        """
        if not branch_name:
            branch_name = self._get_current_branch()

        logger.info(f"Running CreatePrAIBot for branch: {branch_name}")

        # Step 1: Check if branch is outdated
        is_outdated = self.is_branch_outdated(branch_name)
        logger.info(f"Branch is outdated: {is_outdated}")

        # Step 2: Check if PR already exists
        pr_exists = self.is_pr_already_opened(branch_name)
        logger.info(f"PR already exists: {pr_exists}")

        if is_outdated and pr_exists:
            # Step 3: If branch is up-to-date and PR exists, do nothing
            logger.info("Branch is outdated and PR already exists. Nothing to do.")
            return None
        else:
            # Step 4: If PR doesn't exist, create PR
            if not pr_exists:
                # If branch is outdated, update
                if is_outdated:
                    # Step 4-1: Update the branch
                    try:
                        logger.info("Updating branch...")
                        self.fetch_and_merge_latest_from_base_branch(branch_name)
                    except GitCodeConflictError:
                        logger.error("Merge conflicts detected. Cannot proceed.")
                        return None

                # Step 4-2: Get branch commits
                logger.info("Getting branch commits...")
                commits = self.get_branch_commits(branch_name)
                if not commits:
                    logger.warning("No commits found in branch. Cannot create PR.")
                    return None

                # Step 4-3: Get ticket details
                logger.info("Extracting ticket IDs from commits...")
                ticket_ids = self.extract_ticket_ids(commits)

                logger.info(f"Found ticket IDs: {ticket_ids}")
                ticket_details = self.get_ticket_details(ticket_ids)

                # Step 4-4: Prepare AI prompt
                logger.info("Preparing AI prompt...")
                prompt = self.prepare_ai_prompt(commits, ticket_details)

                # Step 4-5: Ask AI to generate PR content
                logger.info("Asking AI to generate PR content...")
                try:
                    ai_response = self.ai_client.get_content(prompt)
                    title, body = self.parse_ai_response(ai_response)
                except Exception as e:
                    logger.error(f"Error generating PR content with AI: {str(e)}")
                    # Fall back to basic PR content if AI fails
                    title = f"Update {branch_name}"
                    body = "Automated pull request."

                # Step 4-6: Create the pull request
                logger.info("Creating pull request...")
                return self.create_pull_request(title, body, branch_name)

            return None
