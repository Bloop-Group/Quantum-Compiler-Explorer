FROM python:3.12-slim

WORKDIR /srv/backend
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY data ./data
COPY app ./app

RUN useradd --create-home --shell /bin/false qce
USER qce

EXPOSE 8000
HEALTHCHECK --interval=15s --timeout=3s --retries=3 CMD python3 -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/v1/health')"
CMD ["gunicorn", "app.main:app", "-w", "4", "-k", "uvicorn.workers.UvicornWorker", "--bind", "0.0.0.0:8000"]
