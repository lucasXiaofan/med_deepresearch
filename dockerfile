FROM python:3.10-slim

# 安装 Xvfb (屏幕), x11vnc (传输画面), Fluxbox (窗口管理), Chrome
RUN apt-get update && apt-get install -y \
    xvfb \
    fluxbox \
    x11vnc \
    chromium \
    chromium-driver \
    && rm -rf /var/lib/apt/lists/*

# 设置屏幕参数
ENV DISPLAY=:99
ENV RESOLUTION=1280x960x16

# 暴露 VNC 端口 (5900是 VNC 默认端口)
EXPOSE 5900

WORKDIR /app

# 启动命令：
# 1. 启动虚拟屏幕 (Xvfb)
# 2. 启动窗口管理器 (fluxbox)
# 3. 启动 VNC 服务器 (x11vnc) -> 这就是你的“监控摄像头”
#    -forever: 断开连接后不关闭
#    -usepw: 使用密码 (可选，这里为了简单先不用)
#    -create: 自动创建连接
CMD ["sh", "-c", "Xvfb :99 -screen 0 ${RESOLUTION} & fluxbox & x11vnc -display :99 -nopw -listen localhost -xkb -nocache -forever & tail -f /dev/null"]