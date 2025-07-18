FROM python:3.12-slim
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Set working directoryx
WORKDIR /app

# Install dependencies.
# Collect static files. This will generate a folder named `staticfiles` in working directory
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --frozen --no-install-project --verbose

 # Copy your source code
COPY . .

# Sync the project
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --frozen --verbose

# explicitly set a fallback log level in case no log level is defined by Kubernetes
ENV DJANGO_LOG_LEVEL INFO

# default port of django admin site
ENV DJANGO_PORT 8080
EXPOSE ${DJANGO_PORT}

# Set a default value for the number of workers; this is a semi-sane number, but should be something like 2 per CPU
ARG DEFAULT_NUM_WORKERS=4

# Expose the environment variable to be used at runtime
ENV NUM_WORKERS=${DEFAULT_NUM_WORKERS}

# Start server using gunicorn
# CMD cat /app/logging.conf && echo $PORT && echo $LOG_LEVEL && gunicorn -b :$PORT --threads 2 --log-config /app/logging.conf --log-level=$LOG_LEVEL "api:create_app()"
#CMD ["sh", "-c", "gunicorn parameter_store.asgi:application --workers ${NUM_WORKERS} -k uvicorn.workers.UvicornWorker --preload --bind :${DJANGO_PORT}"]
CMD ["sh", "-c", "uv run gunicorn parameter_store.asgi:application --workers ${NUM_WORKERS} -k uvicorn.workers.UvicornWorker --preload --bind :${DJANGO_PORT}"]
