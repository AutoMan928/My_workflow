#!/bin/bash
# 首次部署时在阿里云服务器上执行一次
# 用法: bash server-init.sh

set -e

REPO_URL="https://github.com/AutoMan928/My_workflow.git"
DEPLOY_DIR="/opt/news-platform"

echo "=== 检查 Docker ==="
if ! command -v docker &> /dev/null; then
    apt-get update -q
    apt-get install -y docker.io
    systemctl start docker
    systemctl enable docker
    echo "Docker 已安装"
else
    echo "Docker 已存在: $(docker --version)"
fi

if ! docker compose version &> /dev/null; then
    apt-get install -y docker-compose-plugin
    echo "docker compose plugin 已安装"
fi

echo ""
echo "=== 克隆仓库 ==="
if [ -d "$DEPLOY_DIR/.git" ]; then
    echo "仓库已存在，跳过克隆"
else
    git clone "$REPO_URL" "$DEPLOY_DIR"
    echo "克隆完成"
fi

echo ""
echo "=== 创建数据目录 ==="
mkdir -p "$DEPLOY_DIR/data"
chmod 755 "$DEPLOY_DIR/data"

echo ""
echo "=== 完成 ==="
echo "下一步（手动操作）："
echo "  1. cd $DEPLOY_DIR"
echo "  2. cp .env.example .env && nano .env   # 填写真实 key"
echo "  3. docker compose up -d --build        # 首次启动"
echo "  4. 配置 Nginx + SSL（参考 deploy/nginx.conf）"
