FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Install system dependencies for GIS
RUN apt-get update \
    && apt-get install --yes --no-install-recommends \
        binutils \
        gdal-bin \
        libgdal-dev \
        libgeos-dev \
        libproj-dev \
        gdal-data \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Run as an unprivileged user. staticfiles/ is created here so the shared
# named volume mounted on it inherits this ownership.
RUN useradd --create-home --uid 1000 app \
    && mkdir -p /app/staticfiles \
    && chown -R app:app /app

COPY --chown=app:app . .

USER app

EXPOSE 8000
ENTRYPOINT ["/app/entrypoint.sh"]
CMD ["gunicorn", "ai_datacenter_map.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "3", "--access-logfile", "-"]
