FROM python:3.11-slim

WORKDIR /app

# 先复制依赖文件，利用 Docker layer 缓存
COPY pyproject.toml .
RUN pip install --no-cache-dir -e . || true

# 复制应用代码
COPY app/ app/
COPY config.yaml .

# 数据目录
RUN mkdir -p data

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips=*"]
