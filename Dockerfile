# Use Python 3.12
FROM python:3.12-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# Set work directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    supervisor \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

# Copy project files
COPY . /app/

# Supervisor config to run both Django + Celery
COPY supervisord.conf /etc/supervisor/conf.d/supervisord.conf

# Collect static files
RUN python manage.py collectstatic --noinput

# Run supervisord
CMD ["/usr/bin/supervisord"]
