FROM python:3.11-slim

WORKDIR /app

COPY pyproject.toml README.md LICENSE ./
COPY src ./src

RUN pip install --no-cache-dir --upgrade pip \
  && pip install --no-cache-dir .

EXPOSE 8080

CMD ["swsynth", "serve", "--db", "/app/data/workspace.db", "--host", "0.0.0.0", "--port", "8080"]
