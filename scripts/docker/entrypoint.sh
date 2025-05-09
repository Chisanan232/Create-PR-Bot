#!/bin/bash

git config --global --add safe.directory /github/workspace

# Build command arguments based on environment variables
ARGS=""

# Add config file if provided
if [ ! -z "$CREATE_PR_BOT_CONFIG_FILE" ]; then
  ARGS="$ARGS --config $CREATE_PR_BOT_CONFIG_FILE"
fi

# Add git settings if provided
if [ ! -z "$CREATE_PR_BOT_GIT_REPO_PATH" ]; then
  ARGS="$ARGS --repo-path $CREATE_PR_BOT_GIT_REPO_PATH"
fi

if [ ! -z "$CREATE_PR_BOT_GIT_BASE_BRANCH" ]; then
  ARGS="$ARGS --base-branch $CREATE_PR_BOT_GIT_BASE_BRANCH"
fi

if [ ! -z "$CREATE_PR_BOT_GIT_BRANCH_NAME" ]; then
  ARGS="$ARGS --branch-name $CREATE_PR_BOT_GIT_BRANCH_NAME"
fi

# Add GitHub settings if provided
if [ ! -z "$CREATE_PR_BOT_GITHUB_TOKEN" ]; then
  ARGS="$ARGS --github-token $CREATE_PR_BOT_GITHUB_TOKEN"
fi

if [ ! -z "$CREATE_PR_BOT_GITHUB_REPO" ]; then
  ARGS="$ARGS --github-repo $CREATE_PR_BOT_GITHUB_REPO"
fi

# Add AI settings if provided
if [ ! -z "$CREATE_PR_BOT_AI_CLIENT_TYPE" ]; then
  ARGS="$ARGS --ai-client-type $CREATE_PR_BOT_AI_CLIENT_TYPE"
fi

if [ ! -z "$CREATE_PR_BOT_AI_API_KEY" ]; then
  ARGS="$ARGS --ai-api-key $CREATE_PR_BOT_AI_API_KEY"
fi

# Add PM tool settings if provided
if [ ! -z "$CREATE_PR_BOT_PM_TOOL_TYPE" ]; then
  ARGS="$ARGS --pm-tool-type $CREATE_PR_BOT_PM_TOOL_TYPE"
fi

if [ ! -z "$CREATE_PR_BOT_PM_TOOL_API_KEY" ]; then
  ARGS="$ARGS --pm-tool-api-key $CREATE_PR_BOT_PM_TOOL_API_KEY"
fi

# Run the bot with the constructed arguments
# Note: Other PM tool settings (organization_id, project_id, base_url, username)
# will be picked up from environment variables by BotSettings.from_env()
poetry run create-pr-bot $ARGS
