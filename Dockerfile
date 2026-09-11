FROM ghcr.io/astral-sh/uv:0.12.5-python3.14-trixie-slim

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

WORKDIR /app

ARG INSTALL_ALLURE=false
ARG INSTALL_REPORTPORTAL=false

COPY pyproject.toml uv.lock README.md LICENSE ./
COPY src/ ./src/

RUN --mount=type=cache,target=/root/.cache/uv \
    set --; \
    if [ "$INSTALL_ALLURE" = "true" ]; then set -- "$@" --group allure; fi; \
    if [ "$INSTALL_REPORTPORTAL" = "true" ]; then set -- "$@" --group reportportal; fi; \
    uv sync --locked --no-install-project "$@"

COPY . .

RUN --mount=type=cache,target=/root/.cache/uv \
    set --; \
    if [ "$INSTALL_ALLURE" = "true" ]; then set -- "$@" --group allure; fi; \
    if [ "$INSTALL_REPORTPORTAL" = "true" ]; then set -- "$@" --group reportportal; fi; \
    uv sync --locked "$@"

CMD ["uv", "run", "pytest", "tests/unit", "tests/integration"]
