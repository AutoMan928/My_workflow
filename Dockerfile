FROM python:3.11-slim

WORKDIR /app

# 先用空 app/ 安装依赖，利用 Docker layer 缓存
COPY pyproject.toml .
RUN mkdir -p app && pip install --no-cache-dir -e . && rm -rf app

# 复制应用代码（依赖层已缓存，只有代码变动时重建此层）
COPY app/ app/
COPY config.yaml .

# 数据目录
RUN mkdir -p data

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips=*"]
