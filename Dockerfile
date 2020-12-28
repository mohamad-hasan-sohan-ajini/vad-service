FROM python:3.8-slim

RUN apt update && \
    apt upgrade -y && \
    apt install -y ffmpeg libsndfile1 libsndfile1-dev gcc git

COPY . /app

WORKDIR /app

RUN cd /app && \
    pip install -r requirements.txt

CMD uvicorn app.app:app --host 0.0.0.0
