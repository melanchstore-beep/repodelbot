FROM python:3.11-slim

WORKDIR /app

# Dependencias primero (aprovecha cache de Docker)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Código
COPY . .

# Render enruta tráfico a este puerto (coincide con el default del dashboard)
EXPOSE 10000

CMD ["python", "bot.py"]
