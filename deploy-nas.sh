#!/bin/bash
# NAS 首次部署脚本
# 使用方法: ssh WPY@192.168.31.148 < deploy-nas.sh
# 或者复制内容到 NAS 终端执行

set -e

echo "=== 开始部署 Weibull 平台 ==="

# 创建目录
mkdir -p /share/docker
cd /share/docker

# 克隆项目（如果不存在）
if [ ! -d "weibull" ]; then
    echo "正在克隆项目..."
    git clone https://github.com/NEUwpy/weibull.work.git weibull
fi

cd weibull

# 拉取最新代码
echo "正在拉取最新代码..."
git pull

# 启动容器
echo "正在构建并启动容器（首次约 5-10 分钟）..."
docker-compose up -d --build

# 等待启动
echo "等待服务启动..."
sleep 10

# 检查状态
echo ""
echo "=== 部署完成 ==="
echo ""
docker-compose ps
echo ""
echo "访问地址:"
echo "  前端: https://weibull.work"
echo "  后端: https://api.weibull.work/docs"
echo ""
echo "查看日志: docker-compose logs -f"
