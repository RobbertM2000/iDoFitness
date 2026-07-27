FROM python:3.13-slim

WORKDIR /app

# psycopg2-binary ships prebuilt wheels for slim images, but libpq5 is still
# needed at runtime, and gcc/libpq-dev cover the rare case pip falls back
# to a source build.
RUN apt-get update && apt-get install -y --no-install-recommends \
        libpq-dev gcc \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# App source (backend/ contents — see docker-compose.yml build context)
COPY . .

COPY docker-entrypoint.sh /app/docker-entrypoint.sh
RUN chmod +x /app/docker-entrypoint.sh

EXPOSE 5000

ENTRYPOINT ["/app/docker-entrypoint.sh"]
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "3", "--access-logfile", "-", "wsgi:app"]
