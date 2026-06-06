# Lite Node Gateway

一个轻量级 Docker 节点网关。它可以在 Web 页面里导入多个订阅，选择某个订阅里的节点，然后把这个节点固定暴露到一个本地代理端口。

底层代理核心使用 `mihomo`。原来的开源观察面板 `MetaCubeXD` 仍然保留，新加的 `Manager` 面板负责订阅和端口管理。

## 地址

- Manager 管理面板：`http://127.0.0.1:8089`
- MetaCubeXD 面板：`http://127.0.0.1:8088`
- Mihomo 控制接口：`http://127.0.0.1:9090`
- 主代理端口：`http://127.0.0.1:7896`
- 固定端口池：`http://127.0.0.1:7900-7999`

默认只绑定到 `127.0.0.1`，适合本机和 Docker Desktop 内的本地容器使用。部署到服务器时，如果要给外部机器访问，需要修改 `docker-compose.yml` 的端口绑定，并配置防火墙和访问控制。

## 启动

```powershell
cd C:\project\lite-node-gateway
docker compose up -d --build
```

查看状态：

```powershell
docker compose ps
```

## Web 管理流程

打开：

```text
http://127.0.0.1:8089
```

常用操作：

- 导入一个或多个订阅地址
- 点击左侧订阅，查看该订阅的节点
- 选择节点
- 填写端口，例如 `7903`
- 点击保存端口

保存后会自动生成 Mihomo 配置并热重载，不需要手动重启容器。

## 当前示例映射

当前已经配置了这些端口：

- `7901 -> AUTO`
- `7902 -> DIRECT`
- `7903 -> csjc / 日本 aws 优化线路`

应用里使用时：

```text
http://127.0.0.1:7903
```

如果是另一个 Docker 容器访问，例如 `sub2api`：

```text
protocol: http
host: host.docker.internal
port: 7903
```

## 验证代理

宿主机测试：

```powershell
Invoke-WebRequest -UseBasicParsing -Uri 'https://ipinfo.io/json' -Proxy 'http://127.0.0.1:7903' -TimeoutSec 60
```

从 `sub2api` 容器测试：

```powershell
docker exec sub2api sh -lc 'curl -sS --max-time 60 -x http://host.docker.internal:7903 https://ipinfo.io/json'
```

## 旧脚本

旧脚本仍可用，但建议优先使用 Manager 面板。

```powershell
.\scripts\list-nodes.ps1
.\scripts\bind-port.ps1 -Port 7901 -Node AUTO
.\scripts\list-port-bindings.ps1
```

## 数据文件

- Manager 状态：`data\manager-state.json`
- 订阅节点缓存：`data\subscriptions\*.yaml`
- Mihomo 配置：`data\config.yaml`
- 首次接管前备份：`data\config.yaml.before-manager`

订阅 URL 会保存在本地状态文件里，用于刷新订阅；Web API 返回时会自动隐藏 token/key 等敏感查询参数。
