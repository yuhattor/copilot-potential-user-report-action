FROM python:3.9-slim-buster
WORKDIR /app
COPY requirements.txt /app
RUN pip install --no-cache-dir -r requirements.txt

COPY . /app
ENTRYPOINT ["/app/entrypoint.sh"]