FROM python:3.12-slim

LABEL maintainer="Chisanan232 <chi10211201@cycu.org.tw>"
LABEL org.opencontainers.image.source="https://github.com/Chisanan232/Create-PR-Bot"
LABEL org.opencontainers.image.description="Create PR Bot - Automate pull request creation with AI-generated content"
LABEL org.opencontainers.image.licenses="MIT"

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    POETRY_VERSION=1.7.1 \
    POETRY_HOME="/opt/poetry" \
    POETRY_VIRTUALENVS_CREATE=false

# Install git and other dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    curl \
    bash \
    && rm -rf /var/lib/apt/lists/*

# Install Poetry
#RUN curl -sSL https://install.python-poetry.org | python3 -
#ENV PATH="$POETRY_HOME/bin:$PATH"
RUN pip install -U pip
RUN pip install -U poetry
RUN poetry --version

# Set working directory
WORKDIR /app

# Copy project files
COPY . /app/

# Install dependencies
RUN poetry install --no-interaction --without=dev
# # It already in a virtual runtime environment --- a Docker container, so it doesn't need to create another independent
# # virtual enviroment again in Docker virtual environment
RUN poetry config virtualenvs.create false

# Create a volume for configuration
VOLUME ["/config"]

# Copy entrypoint script
COPY scripts/docker/entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

# Mark repo as safe
RUN git config --global --add safe.directory /github/workspace

# Set the entrypoint
ENTRYPOINT ["/app/entrypoint.sh"]

# # For debug
#ENTRYPOINT ["tail", "-f", "/dev/null"]
