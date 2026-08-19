FROM mcr.microsoft.com/devcontainers/python:1-3.12

RUN apt-get update \
    && apt-get install -y --no-install-recommends ripgrep git curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:0.8.15 /uv /uvx /usr/local/bin/

RUN curl --proto '=https' --tlsv1.2 -sSf https://just.systems/install.sh \
    | bash -s -- --to /usr/local/bin
