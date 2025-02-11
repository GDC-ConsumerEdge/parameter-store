FROM python:3.12-alpine

# Set working directoryx
WORKDIR /app
# Copy your source code
COPY . .

# Install dependencies.
# Collect static files. This will generate a folder named `staticfiles` in working directory
RUN pip3 install -r requirements.txt --require-hashes --no-cache-dir && \
    python3 manage.py collectstatic --noinput

# show python logs as they occur
ENV PYTHONUNBUFFERED 0

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
CMD ["sh", "-c", "gunicorn parameter_store.asgi:application --workers ${NUM_WORKERS} -k uvicorn.workers.UvicornWorker --preload --bind :${DJANGO_PORT}"]