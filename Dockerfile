FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY merger.py ./merger.py

ENTRYPOINT ["python", "/app/merger.py"]
