FROM ghcr.io/astral-sh/uv:python3.13-trixie-slim
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy
WORKDIR /app
COPY uv.lock pyproject.toml requirements.txt /app/
USER root
RUN uv sync --frozen --no-install-project --no-dev
COPY src /app
RUN uv sync --frozen --no-dev
ENV PATH="/app/.venv/bin:$PATH"
EXPOSE 8080
WORKDIR /app
CMD ["bash", "-c", "exec uv run src/main.py"]
