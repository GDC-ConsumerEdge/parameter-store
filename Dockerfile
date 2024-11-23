# Copyright 2021 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

# Use the official Python docker container, slim version, running Debian
FROM python:3.13.0-slim-bookworm@sha256:450bb2ed2919f9a476c54c19884e200f473d89c2b2d458f07a03ee463026dcb8 as base

# define virtual environment
ENV VIRTUAL_ENV=/opt/venv

FROM base as builder

# Create a virtual environment
RUN python3 -m venv $VIRTUAL_ENV

# Activate the virtual environment
ENV PATH="$VIRTUAL_ENV/bin:$PATH"

# Install dependencies.
COPY requirements.* ./
RUN pip install --require-hashes -r requirements.txt
#ENV PYTHONPATH="/usr/local/lib/python3.13/site-packages:${PYTHONPATH}"

# Copy your source code
COPY manage.py /app/
COPY parameter_store /app/parameter_store
COPY auto_api /app/auto_api

# Set working directory
WORKDIR /app

# Collect static files. This will generate a folder named `staticfiles` in working directory
RUN python3 manage.py collectstatic --noinput

FROM base

# Copy the virtual environment from the builder stage
COPY --from=builder $VIRTUAL_ENV $VIRTUAL_ENV

# Copy collected static files
COPY --from=builder /app /app

# Activate the virtual environment
ENV PATH="$VIRTUAL_ENV/bin:$PATH"

# Set working directory
WORKDIR /app

# show python logs as they occur
ENV PYTHONUNBUFFERED=0

# explicitly set a fallback log level in case no log level is defined by Kubernetes
ENV LOG_LEVEL info

# default port of django admin site
ENV DJANGO_PORT=8080
EXPOSE ${DJANGO_PORT}

RUN chmod 777 /app && chmod 666 /app/*
RUN chmod 777 /tmp

# Start server using gunicorn
# CMD cat /app/logging.conf && echo $PORT && echo $LOG_LEVEL && gunicorn -b :$PORT --threads 2 --log-config /app/logging.conf --log-level=$LOG_LEVEL "api:create_app()"
CMD ["sh", "-c", "gunicorn parameter_store.wsgi:application --bind :${DJANGO_PORT}"]