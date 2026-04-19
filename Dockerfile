FROM python:3.11-slim

WORKDIR /app

COPY . /app

RUN pip install --no-cache-dir streamlit requests

EXPOSE 8080

CMD ["streamlit", "run", "app.py", "--server.address=0.0.0.0", "--server.port=8080", "--server.headless=true", "--browser.gatherUsageStats=false", "--server.enableCORS=false", "--server.enableXsrfProtection=false"]
