FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p /app/data && chmod +x entrypoint.sh

EXPOSE 8005

ENTRYPOINT ["./entrypoint.sh"]
