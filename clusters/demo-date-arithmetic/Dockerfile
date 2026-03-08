FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY runtime/ runtime/
COPY config/ config/
CMD ["python", "-m", "runtime.cli", "run-agent"]
