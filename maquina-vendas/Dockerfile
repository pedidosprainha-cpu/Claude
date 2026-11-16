FROM python:3.13-slim
WORKDIR /app
RUN pip install --no-cache-dir "fastapi>=0.115" "uvicorn>=0.30" "anthropic>=2.9"
COPY maquina maquina
COPY web web
# O banco de dados fica neste volume: sem ele, tudo some quando o servidor reinicia.
ENV MAQUINA_DADOS=/dados
VOLUME /dados
EXPOSE 8000
CMD ["uvicorn", "maquina.api:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers"]
