FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app/backend

COPY backend/pyproject.toml ./pyproject.toml
COPY backend/medgraph_api ./medgraph_api

RUN pip install --no-cache-dir -e .

COPY backend ./

EXPOSE 8000

CMD ["uvicorn", "medgraph_api.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
