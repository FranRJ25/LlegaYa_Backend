FROM python:3.12-slim

WORKDIR /app

# Driver ODBC 18 de Microsoft para SQL Server (instrucciones oficiales Debian/Ubuntu)
RUN apt-get update && apt-get install -y --no-install-recommends \
        curl gnupg2 ca-certificates apt-transport-https gcc g++ unixodbc-dev \
    && curl -sSL https://packages.microsoft.com/keys/microsoft.asc | gpg --dearmor -o /usr/share/keyrings/microsoft-prod.gpg \
    && curl -sSL https://packages.microsoft.com/config/debian/12/prod.list -o /etc/apt/sources.list.d/mssql-release.list \
    && apt-get update \
    && ACCEPT_EULA=Y apt-get install -y --no-install-recommends msodbcsql18 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p /app/data && chmod +x entrypoint.sh

EXPOSE 8004

ENTRYPOINT ["./entrypoint.sh"]
