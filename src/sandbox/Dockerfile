FROM python:3.13-slim

ENV PYTHONUNBUFFERED=1
ENV VIRTUAL_ENV=/sandbox/.venv
ENV PATH="$VIRTUAL_ENV/bin:$PATH"

RUN pip install uv

WORKDIR /sandbox

COPY pyproject.toml uv.lock* ./

# no changes are made to the lock file during the sync process
# uv.lock already in sync with pyproject.toml
RUN uv sync --frozen

COPY . .

CMD ["uv", "run", "python", "sandbox_worker.py"]