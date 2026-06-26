# 백엔드 단일 이미지 — api / worker(loop) / bot 이 같은 이미지를 명령만 바꿔 실행한다.
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY app ./app

EXPOSE 8000

# 기본 명령은 API 서버. worker/bot은 compose에서 command로 덮어쓴다.
CMD ["uvicorn", "app.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
