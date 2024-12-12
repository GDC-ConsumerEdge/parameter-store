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
FROM python:3.12-alpine
# Set working directory
WORKDIR /app
# Copy your source code
COPY . .

# Install dependencies.
# Collect static files. This will generate a folder named `staticfiles` in working directory
RUN pip3 install -r requirements.txt --require-hashes --no-cache-dir && \
    python3 manage.py collectstatic --noinput

# show python logs as they occur
ENV PYTHONUNBUFFERED=0

# explicitly set a fallback log level in case no log level is defined by Kubernetes
ENV LOG_LEVEL info

# default port of django admin site
ENV DJANGO_PORT=8080
EXPOSE ${DJANGO_PORT}

# Start server using gunicorn
# CMD cat /app/logging.conf && echo $PORT && echo $LOG_LEVEL && gunicorn -b :$PORT --threads 2 --log-config /app/logging.conf --log-level=$LOG_LEVEL "api:create_app()"
CMD ["sh", "-c", "gunicorn parameter_store.wsgi:application --workers 5 --worker-class sync --bind :${DJANGO_PORT}"]
