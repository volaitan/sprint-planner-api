FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app

# Run as a non-root user, with a writable folder for the SQLite database
RUN useradd --create-home appuser && mkdir -p /app/data && chown appuser:appuser /app/data
USER appuser
ENV DATABASE_URL=sqlite:////app/data/sprint_planner.db

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
