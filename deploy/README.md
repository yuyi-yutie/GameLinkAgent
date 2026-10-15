# 部署说明（Windows 云服务器）

GameLink Agent 的一键部署目标是一台 **Windows 云服务器**。Godot 服务端是 headless 的 ENet(UDP) 服务，部署与常见的 HTTP/TCP 场景不同。

## 前置条件（服务器侧）

- **OpenSSH Server**：允许智能体通过 `ssh`/`scp` 下发产物（`Add-WindowsCapability -Online -Name OpenSSH.Server~~~~0.0.1.0`）。
- **NSSM**：把服务端注册为 Windows 服务，实现开机自启与崩溃重启：<https://nssm.cc/>
- **安全组**：在云厂商控制台放行服务端使用的 **UDP** 端口（默认 7000）。这是最容易漏的一步。

## 部署流程

```powershell
# 1. 放通防火墙 UDP 端口
.\deploy\windows\open_firewall.ps1 -Port 7000

# 2. 注册并启动服务（传入导出的 headless 服务端可执行文件）
.\deploy\windows\install_service.ps1 -ServerExe C:\GameLink\server\gamelink-server.exe -Port 7000
```

智能体侧：

```bash
# 预览部署计划（默认，不改动任何东西）
gamelink deploy out/snake-server --dry-run

# 实际执行上传 + 放通端口
gamelink deploy out/snake-server --apply
```

## 可选：容器化

见 [`Dockerfile`](./Dockerfile)。在 Windows 主机上通过 WSL2 / Docker Desktop 运行 Linux 容器。

## 安全提示

- 部署脚本应保持**幂等**：重复执行不产生副作用。
- 使用受限账号与密钥，凭据只从环境变量读取，不写入仓库与日志。
- 对外只暴露游戏 UDP 端口；不要暴露管理接口。
