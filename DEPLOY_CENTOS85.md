# CentOS 8.5 一键安装与迁移

Warehouse Agent 推荐在 CentOS 8.5 上通过 Podman 运行。脚本会自动完成：

1. 检查 CentOS 8.x。
2. 检查 `dnf`；如果官方 CentOS 8 源因 EOL 失效，则备份 repo 并切换到 CentOS Vault 8.5.2111。
3. 安装 Git、curl、Podman。
4. 克隆或更新 `https://github.com/NJgaoyang/warehouse-agent.git`。
5. 首次自动从 `.env.example` 创建 `.env`，已有 `.env` 不覆盖。
6. 创建 `data/source`、`data/workspaces`、`data/releases`。
7. 构建 Python 3.12 容器镜像。
8. 使用 SELinux `:Z` 挂载 `data`，避免 `Permission denied: data/source`。
9. 启动容器并设置 `--restart=always`。
10. firewalld 运行时自动放行 8000/tcp。
11. 调用 `/api/health` 做启动健康检查。

## 新 VM 最简单的方式

如果系统已经有 curl：

```bash
curl -fsSL https://raw.githubusercontent.com/NJgaoyang/warehouse-agent/main/install-centos85.sh | sudo bash
```

如果你已经 clone 了仓库：

```bash
git clone https://github.com/NJgaoyang/warehouse-agent.git
cd warehouse-agent
sudo bash install-centos85.sh install
```

默认安装目录：

```text
/opt/apps/warehouse-agent
```

默认端口：

```text
8000
```

启动成功后访问：

```text
http://<VM-IP>:8000/docs
```

## 日常命令

脚本可重复使用：

```bash
sudo bash /opt/apps/warehouse-agent/install-centos85.sh status
sudo bash /opt/apps/warehouse-agent/install-centos85.sh logs
sudo bash /opt/apps/warehouse-agent/install-centos85.sh stop
sudo bash /opt/apps/warehouse-agent/install-centos85.sh start
sudo bash /opt/apps/warehouse-agent/install-centos85.sh restart
sudo bash /opt/apps/warehouse-agent/install-centos85.sh update
```

`update` 会执行：

```text
git pull -> podman build -> 删除旧容器 -> 启动新容器 -> 健康检查
```

不会删除：

```text
.env
data/source
data/workspaces
data/releases
data/warehouse_agent.db
```

## 修改真实环境配置

首次安装使用仓库 `.env.example`，默认是 Mock 外部服务模式。项目启动成功后编辑：

```bash
vi /opt/apps/warehouse-agent/.env
```

真实连接 DolphinScheduler / StarRocks 时，将：

```env
APP_MOCK_EXTERNAL=true
```

改成：

```env
APP_MOCK_EXTERNAL=false
```

然后：

```bash
sudo bash /opt/apps/warehouse-agent/install-centos85.sh restart
```

注意：如果修改了 Python 代码或 requirements，请使用 `update`（会重新构建镜像），而不是仅执行 `restart`。

## 自定义安装目录或端口

```bash
sudo WAREHOUSE_AGENT_INSTALL_DIR=/data/apps/warehouse-agent \
     WAREHOUSE_AGENT_PORT=18000 \
     bash install-centos85.sh install
```

或者通过远程脚本：

```bash
curl -fsSL https://raw.githubusercontent.com/NJgaoyang/warehouse-agent/main/install-centos85.sh \
  | sudo WAREHOUSE_AGENT_PORT=18000 bash
```

## 排查

查看状态：

```bash
podman ps -a
```

查看日志：

```bash
podman logs -f warehouse-agent
```

检查 SELinux：

```bash
getenforce
ls -ldZ /opt/apps/warehouse-agent/data
```

检查健康接口：

```bash
curl http://127.0.0.1:8000/api/health
```
