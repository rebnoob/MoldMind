FROM python:3.11-slim

WORKDIR /app

# System deps for OpenCascade and numpy
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libgl1-mesa-glx \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

COPY apps/api/requirements.txt ./requirements.txt
COPY services/geometry/requirements.txt ./requirements-geometry.txt
COPY services/dfm/requirements.txt ./requirements-dfm.txt

RUN pip install --no-cache-dir -r requirements.txt \
    -r requirements-geometry.txt \
    -r requirements-dfm.txt

COPY apps/api/src ./src
COPY services ./services

ENV PYTHONPATH=/app:/app/services

CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]
