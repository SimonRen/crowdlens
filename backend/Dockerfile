FROM python:3.11-slim-bookworm AS builder

RUN apt-get update && \
    apt-get install -y --no-install-recommends build-essential gcc g++ python3-dev && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir --prefix=/install -r /tmp/requirements.txt

FROM python:3.11-slim-bookworm

ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 ORT_LOG_LEVEL=ERROR

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        libglib2.0-0 libgl1 libsm6 libxext6 libxrender1 ffmpeg wget unzip curl && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

COPY --from=builder /install /usr/local

# Pre-download YOLO model (into WORKDIR so detector finds it)
ADD https://github.com/ultralytics/assets/releases/download/v8.4.0/yolo26n.pt /app/yolo26n.pt

# Pre-download CLIP model
RUN python -c "from transformers import CLIPModel, CLIPProcessor; \
    CLIPModel.from_pretrained('openai/clip-vit-base-patch32'); \
    CLIPProcessor.from_pretrained('openai/clip-vit-base-patch32')"

WORKDIR /app
COPY . .

EXPOSE 8000
CMD ["python", "main.py"]
