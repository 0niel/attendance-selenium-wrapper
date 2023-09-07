FROM tiangolo/uvicorn-gunicorn-fastapi:python3.11


ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV DEBIAN_FRONTEND noninteractive

WORKDIR /app/

COPY . /app

RUN pip install -r requirements.txt

CMD ["celery", "-A", "worker.tasks", "worker", "-B", "-E", "--concurrency=2", "--time-limit=120"]