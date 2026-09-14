FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

COPY pyproject.toml ./
COPY garleak_api ./garleak_api
RUN pip install .

COPY alembic.ini ./
COPY alembic ./alembic

RUN useradd --create-home --uid 10001 garleak
USER garleak

EXPOSE 8000
CMD ["uvicorn", "--factory", "garleak_api.main:create_app", "--host", "0.0.0.0", "--port", "8000"]
