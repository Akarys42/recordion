FROM python:3.10-slim

EXPOSE 80

ENV PIP_NO_CACHE_DIR=false \
    POETRY_VIRTUALENVS_CREATE=false \
    MAX_WORKERS=3

RUN pip install -U poetry

ARG git_sha="development"
ENV GIT_SHA=$git_sha

CMD ["uvicorn", "recordion.app:app", "--host", "0.0.0.0", "--port", "80"]

WORKDIR /recordion

COPY pyproject.toml poetry.lock ./
RUN poetry install --no-dev

COPY . .
