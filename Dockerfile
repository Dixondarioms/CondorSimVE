FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /app/backend

COPY backend/requirements.txt ./
RUN pip install -r requirements.txt

# la interfaz se sirve desde ../frontend (mapas, relieve y librerias ya estan incluidos: funciona sin internet)
COPY backend/ /app/backend/
COPY frontend/ /app/frontend/

EXPOSE 8000
# Cree el primer instructor una vez:  docker compose run --rm app python -m app.crear_usuario <usuario> --rol instructor
CMD ["python", "-m", "app.servidor", "--host", "0.0.0.0", "--port", "8000"]
