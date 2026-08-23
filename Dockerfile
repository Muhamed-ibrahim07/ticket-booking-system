FROM python:3.11-slim
WORKDIR /app

# system deps
RUN apt-get update && apt-get install -y gcc libpq-dev build-essential && rm -rf /var/lib/apt/lists/*

# copy only requirements first for caching
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# copy app
COPY . /app

ENV FLASK_APP=run.py
ENV PYTHONUNBUFFERED=1

EXPOSE 5000

CMD ["gunicorn", "-k", "eventlet", "-w", "1", "run:app", "-b", "0.0.0.0:5000"]
