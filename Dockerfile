FROM python:3.11-slim
RUN apt-get update && apt-get install -y --no-install-recommends gcc && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app/       ./app/
COPY templates/ ./templates/
COPY static/    ./static/
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
EXPOSE 5000
CMD ["gunicorn","app.main:app","--bind","0.0.0.0:5000","--workers","2","--timeout","120","--log-level","info"]
