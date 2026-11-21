FROM python:3.12-slim

WORKDIR /app
COPY . /app

ENV PYTHONUNBUFFERED=1
ENV GRUIA_HOST=0.0.0.0
ENV GRUIA_PORT=8787

EXPOSE 8787
RUN python3 cli.py init

CMD ["python3", "run.py"]
