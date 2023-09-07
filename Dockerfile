FROM tiangolo/uvicorn-gunicorn-fastapi:python3.11

RUN apt-get update && apt-get install -y libgl1-mesa-dev

RUN apt-get install -y libglib2.0-0 libnss3 libgconf-2-4 libfontconfig1

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV DEBIAN_FRONTEND noninteractive

WORKDIR /app/

COPY . /app

RUN pip install -r requirements.txt

EXPOSE $PORT

ENV APP_MODULE="app.main:app"