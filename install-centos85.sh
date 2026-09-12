#!/usr/bin/env bash
set -Eeuo pipefail

ACTION="${1:-install}"
REPO_URL="${WAREHOUSE_AGENT_REPO_URL:-https://github.com/NJgaoyang/warehouse-agent.git}"
BRANCH="${WAREHOUSE_AGENT_BRANCH:-main}"
INSTALL_DIR="${WAREHOUSE_AGENT_INSTALL_DIR:-/opt/apps/warehouse-agent}"
IMAGE_NAME="${WAREHOUSE_AGENT_IMAGE:-warehouse-agent:latest}"
CONTAINER_NAME="${WAREHOUSE_AGENT_CONTAINER:-warehouse-agent}"
PORT="${WAREHOUSE_AGENT_PORT:-8000}"
VAULT_VERSION="${WAREHOUSE_AGENT_CENTOS_VAULT_VERSION:-8.5.2111}"

log()  { printf '\033[1;32m[warehouse-agent]\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m[warehouse-agent][WARN]\033[0m %s\n' "$*" >&2; }
die()  { printf '\033[1;31m[warehouse-agent][ERROR]\033[0m %s\n' "$*" >&2; exit 1; }

require_root() {
  [[ "${EUID}" -eq 0 ]] || die "请使用 root 执行：sudo bash install-centos85.sh ${ACTION}"
}

check_os() {
  [[ -f /etc/os-release ]] || die "无法识别操作系统。"
  # shellcheck disable=SC1091
  source /etc/os-release
  if [[ "${ID:-}" != "centos" || "${VERSION_ID:-}" != 8* ]]; then
    warn "当前系统为 ${PRETTY_NAME:-unknown}。脚本按 CentOS 8.x 编写，将继续尝试执行。"
  else
    log "检测到 ${PRETTY_NAME}."
  fi
}

switch_centos8_to_vault() {
  local repo_glob=(/etc/yum.repos.d/CentOS-Linux-*.repo)
  if [[ ! -e "${repo_glob[0]}" ]]; then
    die "dnf 不可用，且没有找到 CentOS-Linux-*.repo。若使用公司内部 yum 源，请先修复内部源后重试。"
  fi

  local backup="/etc/yum.repos.d/backup-warehouse-agent-$(date +%Y%m%d%H%M%S)"
  mkdir -p "$backup"
  cp -a /etc/yum.repos.d/CentOS-Linux-*.repo "$backup"/
  log "已备份原 CentOS repo 到 $backup"

  local f
  for f in /etc/yum.repos.d/CentOS-Linux-*.repo; do
    sed -ri 's|^[[:space:]]*mirrorlist=|#mirrorlist=|g' "$f"
    sed -ri "s|^#?[[:space:]]*baseurl=http://mirror\\.centos\\.org/\\\$contentdir/\\\$releasever|baseurl=https://vault.centos.org/${VAULT_VERSION}|g" "$f"
    sed -ri "s|^#?[[:space:]]*baseurl=https://mirror\\.centos\\.org/\\\$contentdir/\\\$releasever|baseurl=https://vault.centos.org/${VAULT_VERSION}|g" "$f"
  done

  dnf clean all
  dnf -y makecache || die "切换 CentOS Vault 后 dnf 仍不可用，请检查 VM 网络/DNS 或公司 yum 源。"
}

ensure_packages() {
  command -v dnf >/dev/null 2>&1 || die "没有找到 dnf，本脚本需要 CentOS/RHEL 8 系统。"

  if ! dnf -q makecache >/tmp/warehouse-agent-dnf.log 2>&1; then
    warn "dnf makecache 失败。CentOS 8 已 EOL，将仅在检测到官方 CentOS-Linux repo 时自动切换到 Vault ${VAULT_VERSION}."
    switch_centos8_to_vault
  fi

  log "安装/确认 git、curl、podman..."
  dnf install -y git curl ca-certificates podman
  command -v git >/dev/null 2>&1 || die "git 安装失败。"
  command -v podman >/dev/null 2>&1 || die "podman 安装失败。"

  if systemctl list-unit-files 2>/dev/null | grep -q '^podman-restart.service'; then
    systemctl enable podman-restart.service >/dev/null 2>&1 || true
  fi
}

sync_source() {
  mkdir -p "$(dirname "$INSTALL_DIR")"

  if [[ -d "$INSTALL_DIR/.git" ]]; then
    log "更新现有代码：$INSTALL_DIR"
    git -C "$INSTALL_DIR" fetch origin "$BRANCH"
    git -C "$INSTALL_DIR" checkout "$BRANCH"
    git -C "$INSTALL_DIR" pull --ff-only origin "$BRANCH" || \
      die "git pull 失败。请检查本地是否有未提交修改。"
  elif [[ -e "$INSTALL_DIR" ]] && [[ -n "$(ls -A "$INSTALL_DIR" 2>/dev/null || true)" ]]; then
    die "$INSTALL_DIR 已存在但不是 Git 仓库，请先备份或移走该目录。"
  else
    rm -rf "$INSTALL_DIR"
    log "克隆 $REPO_URL -> $INSTALL_DIR"
    git clone --branch "$BRANCH" "$REPO_URL" "$INSTALL_DIR"
  fi
}

prepare_files() {
  cd "$INSTALL_DIR"

  if [[ ! -f .env ]]; then
    cp .env.example .env
    log "已从 .env.example 创建 .env（默认 Mock 模式）。"
  else
    log "保留现有 .env 配置。"
  fi

  mkdir -p data/source data/workspaces data/releases
  chmod 0755 data data/source data/workspaces data/releases

  if command -v getenforce >/dev/null 2>&1; then
    log "SELinux: $(getenforce). 容器挂载将使用 :Z 自动设置标签。"
  fi
}

build_image() {
  cd "$INSTALL_DIR"
  log "构建镜像 $IMAGE_NAME ..."
  podman build -t "$IMAGE_NAME" .
}

container_exists() {
  podman container exists "$CONTAINER_NAME" >/dev/null 2>&1
}

run_container() {
  cd "$INSTALL_DIR"
  if container_exists; then
    log "停止并删除旧容器 $CONTAINER_NAME ..."
    podman stop "$CONTAINER_NAME" >/dev/null 2>&1 || true
    podman rm "$CONTAINER_NAME" >/dev/null 2>&1 || true
  fi

  log "启动 $CONTAINER_NAME，宿主端口 $PORT -> 容器 8000 ..."
  podman run -d \
    --name "$CONTAINER_NAME" \
    --restart=always \
    -p "${PORT}:8000" \
    --env-file "$INSTALL_DIR/.env" \
    -v "$INSTALL_DIR/data:/app/data:Z" \
    "$IMAGE_NAME" >/dev/null
}

open_firewall() {
  if command -v firewall-cmd >/dev/null 2>&1 && systemctl is-active --quiet firewalld; then
    log "放行 firewalld 端口 ${PORT}/tcp ..."
    firewall-cmd --permanent --add-port="${PORT}/tcp" >/dev/null
    firewall-cmd --reload >/dev/null
  fi
}

wait_for_health() {
  log "等待服务健康检查 ..."
  local i
  for i in $(seq 1 30); do
    if curl -fsS "http://127.0.0.1:${PORT}/api/health" >/tmp/warehouse-agent-health.json 2>/dev/null; then
      local ip
      ip="$(hostname -I 2>/dev/null | awk '{print $1}')"
      log "服务启动成功。"
      printf '\n  Health: http://127.0.0.1:%s/api/health\n' "$PORT"
      printf '  Swagger: http://%s:%s/docs\n' "${ip:-<VM-IP>}" "$PORT"
      printf '  Project: %s\n\n' "$INSTALL_DIR"
      return 0
    fi
    sleep 2
  done

  warn "健康检查失败，最近容器日志如下："
  podman logs --tail 120 "$CONTAINER_NAME" || true
  die "Warehouse Agent 未能正常启动。"
}

start_existing() {
  if container_exists; then
    podman start "$CONTAINER_NAME" >/dev/null
    open_firewall
    wait_for_health
  elif podman image exists "$IMAGE_NAME" >/dev/null 2>&1 && [[ -d "$INSTALL_DIR" ]]; then
    prepare_files
    run_container
    open_firewall
    wait_for_health
  else
    warn "没有现成容器或镜像，将执行完整安装。"
    full_install
  fi
}

stop_service() {
  if container_exists; then
    podman stop "$CONTAINER_NAME"
  else
    warn "容器 $CONTAINER_NAME 不存在。"
  fi
}

show_status() {
  podman ps -a --filter "name=^${CONTAINER_NAME}$"
  printf '\n'
  if [[ -d "$INSTALL_DIR" ]]; then
    printf 'Install dir: %s\n' "$INSTALL_DIR"
  fi
}

show_logs() {
  container_exists || die "容器 $CONTAINER_NAME 不存在。"
  podman logs -f --tail 200 "$CONTAINER_NAME"
}

full_install() {
  check_os
  ensure_packages
  sync_source
  prepare_files
  build_image
  run_container
  open_firewall
  wait_for_health
}

update_service() {
  check_os
  ensure_packages
  sync_source
  prepare_files
  build_image
  run_container
  open_firewall
  wait_for_health
}

require_root

case "$ACTION" in
  install)
    full_install
    ;;
  update)
    update_service
    ;;
  start)
    start_existing
    ;;
  stop)
    stop_service
    ;;
  restart)
    [[ -d "$INSTALL_DIR" ]] || die "项目目录不存在，请先执行 install。"
    prepare_files
    run_container
    open_firewall
    wait_for_health
    ;;
  status)
    show_status
    ;;
  logs)
    show_logs
    ;;
  *)
    cat <<USAGE
用法：
  bash install-centos85.sh install   # 首次安装（默认）
  bash install-centos85.sh update    # git pull + 重建镜像 + 重启
  bash install-centos85.sh start     # 启动
  bash install-centos85.sh stop      # 停止
  bash install-centos85.sh restart   # 重建容器并启动（不重新 build）
  bash install-centos85.sh status    # 查看状态
  bash install-centos85.sh logs      # 实时日志

可选环境变量：
  WAREHOUSE_AGENT_INSTALL_DIR=/opt/apps/warehouse-agent
  WAREHOUSE_AGENT_PORT=8000
  WAREHOUSE_AGENT_BRANCH=main
USAGE
    exit 2
    ;;
esac
