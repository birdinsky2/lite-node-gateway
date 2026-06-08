# Lite Node Gateway

Lite Node Gateway 是一个本地节点网关管理器。它用 `mihomo` 作为代理核心，提供一个 Manager Web 面板，用来导入订阅、浏览节点、测试延迟，并把指定节点固定暴露到本机端口。

你可以把它理解成一个“本地代理端口分配器”：导入订阅后，把某个节点绑定到 `7900-7999` 中的一个端口。之后脚本、浏览器、Docker 容器或其他程序只需要访问这个固定端口，不用关心当前订阅里节点名称怎么变、节点列表怎么刷新。

## 功能

- 导入和刷新多个订阅地址
- 浏览订阅节点，按名称、类型、地区、延迟筛选
- 一键测试节点延迟
- 把节点、`AUTO` 或 `DIRECT` 固定绑定到本地端口
- 自动生成并热重载 `mihomo` 配置
- 在 Windows 和支持 `gsettings` 的 Linux 桌面环境中切换系统代理
- 支持三种运行方式：安装包、非 Docker 一键脚本、Docker Compose

## 界面预览

![Manager 端口映射示例](docs/images/manager-ports.png)

## 快速选择

| 场景 | 推荐方式 | 适合谁 |
| --- | --- | --- |
| 普通用户安装后长期使用 | 安装包 | Windows 用 exe，Debian/Ubuntu 用 deb |
| 源码运行，不想用 Docker | 非 Docker 一键脚本 | 开发、调试、临时部署 |
| 已经有容器环境 | Docker Compose | 服务器、NAS、容器化工作流 |

默认访问地址：

| 服务 | 地址 |
| --- | --- |
| Manager 管理面板 | `http://127.0.0.1:8089` |
| 主代理端口 | `http://127.0.0.1:7896` |
| 固定端口池 | `http://127.0.0.1:7900-7999` |
| Mihomo 控制接口 | `http://127.0.0.1:9090` |
| System proxy helper | `http://127.0.0.1:18089/api/system-proxy` |

默认只监听 `127.0.0.1`。如果要开放到局域网或公网，请先处理鉴权、防火墙和控制接口暴露风险。

## 方式一：安装包

这是面向普通用户的推荐方式，不需要 Docker。

### Windows exe

构建便携包：

```powershell
.\packaging\windows\build-windows.ps1
```

运行：

```powershell
.\dist\lite-node-gateway-windows\lite-node-gateway.exe
```

便携包目录需要整体复制，不要只复制单个 exe：

```text
dist\lite-node-gateway-windows\
  lite-node-gateway.exe
  manager.exe
  system-proxy-helper.exe
  bin\mihomo.exe
```

冒烟测试：

```powershell
.\dist\lite-node-gateway-windows\lite-node-gateway.exe --no-browser --run-seconds 5
```

### Debian/Ubuntu deb

构建 deb 包：

```powershell
.\packaging\deb\build-deb.ps1
```

生成文件：

```text
dist\lite-node-gateway_0.1.0_amd64.deb
```

安装：

```bash
sudo apt install ./lite-node-gateway_0.1.0_amd64.deb
```

查看服务：

```bash
sudo systemctl status lite-node-gateway-mihomo
sudo systemctl status lite-node-gateway-manager
```

重启服务：

```bash
sudo systemctl restart lite-node-gateway-mihomo lite-node-gateway-manager
```

deb 包会安装 `mihomo` 和 Manager systemd 服务。服务器或 headless 环境通常不能修改桌面系统代理，但订阅管理、节点绑定和代理端口功能不受影响。

## 方式二：非 Docker 一键脚本

源码目录里可以直接运行，不需要 Docker。脚本会准备 Python 虚拟环境、下载或复用 `mihomo`、创建初始配置、启动核心进程，并等待健康检查通过。

Windows：

```powershell
cd C:\project\lite-node-gateway
powershell -ExecutionPolicy Bypass -File .\start-native.ps1
```

Linux：

```bash
cd /path/to/lite-node-gateway
bash ./start-native.sh
```

脚本默认会保持终端窗口不退出。用完按 `Ctrl+C` 停止。

常用参数：

```powershell
.\start-native.ps1 -NoBrowser
.\start-native.ps1 -SkipHelper
.\start-native.ps1 -BuildFrontend
.\start-native.ps1 -ManagerPort 8091 -ProxyPort 7898 -ControllerPort 9191 -HelperPort 18091
```

```bash
bash ./start-native.sh --no-browser
bash ./start-native.sh --skip-helper
bash ./start-native.sh --build-frontend
bash ./start-native.sh --manager-port 8091 --proxy-port 7898 --controller-port 9191 --helper-port 18091
```

需要的环境：

| 系统 | 必需 | 仅在需要重建前端时需要 |
| --- | --- | --- |
| Windows | PowerShell、Python 3.11+、curl.exe | Node.js、npm |
| Linux | bash、python3、python3-venv、python3-pip、curl 或 wget、gzip | Node.js、npm |

脚本会把本地运行状态放在这些目录：

```text
.venv-windows\ 或 .venv-linux\
vendor\mihomo\
data\
```

## 方式三：Docker Compose

适合已经使用 Docker Desktop、服务器容器环境或 NAS 的用户。

纯 Compose：

```bash
docker compose up -d --build --remove-orphans
```

Windows 一键启动 Docker 版：

```powershell
.\start.ps1 -Build
```

Linux 一键启动 Docker 版：

```bash
bash ./start.sh --build
```

查看状态：

```bash
docker compose ps
```

停止：

```bash
docker compose down
```

Compose 只启动两个容器：

- `mihomo`：代理核心
- `manager`：本项目的管理后台

纯 Docker Compose 不能可靠修改宿主机系统代理。`start.ps1` / `start.sh` 会先在宿主机启动 system proxy helper，再启动 Compose；如果直接执行 `docker compose up`，系统代理开关可能不可用，但订阅、节点、端口绑定仍可正常工作。

## 日常使用

打开 Manager：

```text
http://127.0.0.1:8089
```

基本流程：

1. 进入“订阅管理”，导入订阅地址。
2. 进入“节点浏览”，查看节点并测试延迟。
3. 进入“端口绑定”，选择订阅、节点和端口。
4. 保存后，Manager 会生成 `mihomo` 配置并热重载。
5. 其他程序通过固定端口使用代理。

例如把某个节点绑定到 `7903` 后，本机程序使用：

```text
http://127.0.0.1:7903
```

另一个 Docker 容器访问宿主机固定端口：

```text
host: host.docker.internal
port: 7903
protocol: http
```

## 验证

检查 Manager：

```powershell
Invoke-RestMethod http://127.0.0.1:8089/api/health
```

测试固定端口代理：

```powershell
Invoke-WebRequest -UseBasicParsing `
  -Uri 'https://ipinfo.io/json' `
  -Proxy 'http://127.0.0.1:7903' `
  -TimeoutSec 60
```

从 Docker 容器测试：

```bash
docker exec sub2api sh -lc 'curl -sS --max-time 60 -x http://host.docker.internal:7903 https://ipinfo.io/json'
```

## 数据目录

| 运行方式 | 默认数据目录 |
| --- | --- |
| Docker Compose | `data\` |
| 非 Docker 脚本 | `data\` |
| Windows exe | `dist\lite-node-gateway-windows\data\` |
| Debian/Ubuntu deb | `/var/lib/lite-node-gateway` |

主要文件：

```text
manager-state.json
subscriptions\*.yaml
config.yaml
config.yaml.before-manager
logs\
```

订阅 URL 会保存在本地状态文件里，用于后续刷新。API 返回时会隐藏 `token`、`key`、`secret`、`password` 等敏感查询参数。

## 开发

前端：

```powershell
cd manager\frontend
npm ci
npm run build
```

后端语法检查：

```powershell
python -m py_compile manager\app.py scripts\system_proxy_helper.py
```

Docker 构建检查：

```powershell
docker compose config --services
docker compose up -d --build --remove-orphans
```

Windows 便携包：

```powershell
.\packaging\windows\build-windows.ps1
```

Debian/Ubuntu 包：

```powershell
.\packaging\deb\build-deb.ps1
```

## 排障

### 双击 ps1 打开了记事本

不要双击 `.ps1` 文件。打开 PowerShell，进入项目目录后执行：

```powershell
powershell -ExecutionPolicy Bypass -File .\start-native.ps1
```

Docker 方式则执行：

```powershell
powershell -ExecutionPolicy Bypass -File .\start.ps1 -Build
```

### 端口被占用

默认会使用 `8089`、`7896`、`9090`、`18089` 和 `7900-7999`。如果冲突，可以换端口：

```powershell
.\start-native.ps1 -ManagerPort 8091 -ProxyPort 7898 -ControllerPort 9191 -HelperPort 18091
```

### 系统代理开关不可用

系统代理需要宿主机 helper：

- Windows exe 和 `start-native.ps1` 默认会启动 helper。
- Docker 纯 Compose 不会启动 helper；用 `start.ps1 -Build` 或 `start.sh --build`。
- Linux 桌面环境需要可用的 `gsettings` 和桌面 DBus 会话；服务器环境通常不支持。

### Docker 里不能访问 127.0.0.1:7903

容器里的 `127.0.0.1` 是容器自身。访问宿主机端口请用：

```text
host.docker.internal:7903
```

## 许可证

Apache-2.0。详见 [LICENSE](LICENSE)。
