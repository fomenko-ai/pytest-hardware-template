FROM ghcr.io/astral-sh/uv:0.12.5-python3.14-trixie-slim

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

WORKDIR /app

ARG INSTALL_ALLURE=false

COPY pyproject.toml uv.lock README.md LICENSE ./
COPY src/ ./src/

RUN --mount=type=cache,target=/root/.cache/uv \
    if [ "$INSTALL_ALLURE" = "true" ]; then \
        uv sync --locked --no-install-project --group allure; \
    else \
        uv sync --locked --no-install-project; \
    fi

COPY . .

RUN --mount=type=cache,target=/root/.cache/uv \
    if [ "$INSTALL_ALLURE" = "true" ]; then \
        uv sync --locked --group allure; \
    else \
        uv sync --locked; \
    fi

CMD ["uv", "run", "pytest", "tests/unit", "tests/integration"]
