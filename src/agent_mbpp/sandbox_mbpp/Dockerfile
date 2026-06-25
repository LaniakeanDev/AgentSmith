FROM python:3.13-slim

ENV PYTHONUNBUFFERED=1
ENV VIRTUAL_ENV=/app/.venv
ENV PATH="$VIRTUAL_ENV/bin:$PATH"

RUN pip install uv

WORKDIR /app

COPY pyproject.toml uv.lock* ./

# meaning of --frozen:
# no changes are made to the lock file during the sync process
# uv.lock already in sync with pyproject.toml
RUN mkdir sandbox && \
    uv sync --frozen

COPY . ./sandbox_mbpp

CMD ["uv", "run", "python", "-m", "sandbox_mbpp"]