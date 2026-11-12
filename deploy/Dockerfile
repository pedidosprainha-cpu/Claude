FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 FXI_DATA_DIR=/data
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY fxintel fxintel
COPY backend backend
COPY dashboard dashboard
COPY config config
COPY reports reports
RUN useradd -m fxi && mkdir -p /data && chown -R fxi /data /app/reports /app/config
USER fxi
EXPOSE 8000
HEALTHCHECK --interval=60s --timeout=10s --start-period=60s CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://localhost:8000/api/v1/health',timeout=8).status==200 else 1)"
CMD ["python", "-m", "fxintel", "serve", "--host", "0.0.0.0", "--port", "8000"]
