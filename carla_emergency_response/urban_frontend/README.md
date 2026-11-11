# Urban — Digital Twin Command Center

CARLA 数字孪生城市指挥中心前端。深色工业级 HMI,支持 MJPEG / WebRTC 视频流、Socket.IO 实时遥测、智能体指令双向通道。

## 设计原则

1. 去 sci-fi tells:无扫描线 / 霓虹辉光 / 十字准星 / Orbitron 字体
2. 单色调主导 + 一个克制的强调色 (electric blue)
3. 层次靠间距和明度,不靠边框和颜色
4. 数字 Tabular Numerals + 翻牌动效
5. 过渡曲线统一 `cubic-bezier(0.32, 0.72, 0, 1)`,时长 `140 / 240 / 360ms`

## 技术栈

| 层 | 选型 |
|---|---|
| 构建 | Vite 5 |
| 框架 | React 18 + TypeScript (strict) |
| 样式 | Tailwind 3 + CSS variables 设计 token |
| 状态 | Zustand (telemetry / system / command 三库) |
| 动效 | Framer Motion |
| 图标 | Phosphor Icons (duotone) |
| 实时 | Socket.IO Client + 原生 WebRTC + MJPEG |
| 容器 | nginx 1.27 alpine + Docker multi-stage |
| CI | GitHub Actions → GHCR |

## 快速启动

### 本地开发

```bash
npm install
npm run dev          # http://localhost:5173,默认 DEMO 模式
```

### 连真实 CARLA 后端

```bash
cp .env.example .env.development
# 编辑 .env.development 设置 VITE_SOCKET_URL=http://localhost:5000
npm run dev
```

后端无响应时自动退化到 DEMO,后端恢复时自动切回真实流。

### Docker

```bash
docker build -t urban-frontend .
docker run -p 8080:80 -e BACKEND_HOST=host.docker.internal:5000 urban-frontend
# http://localhost:8080
```

或:

```bash
docker compose up
```

`BACKEND_HOST` 环境变量在容器启动时被 nginx 模板替换,无需重新构建镜像。

### CI / 发布

- 所有 PR 触发 `.github/workflows/ci.yml` (typecheck + build)
- main 分支推送或 `v*.*.*` tag 触发 `.github/workflows/release.yml`,镜像推到 `ghcr.io/<owner>/urban_frontend:latest`

## 键盘快捷键

| 组合 | 行为 |
|---|---|
| `1` / `2` / `3` | 全屏 无人机 / 无人车 / 鸟瞰 |
| `Esc` | 退出全屏 / 关闭弹层 |
| `Ctrl+/` | 聚焦指令输入框 |
| `↑` / `↓` | 指令历史 |
| `?` | 快捷键面板 |

## 目录

```
src/
├─ components/
│  ├─ primitives/    Panel · Button · Input · Stat · Badge · NumberFlow · StatusDot
│  ├─ layout/        Header · Footer · ShortcutHint
│  ├─ feeds/         AerialFeed · GroundFeed · CityBirdView · VideoSurface · PlaceholderScene
│  ├─ system/        FleetStatus · Telemetry · EventLog · ErrorBoundary
│  └─ command/       CommandPanel
├─ store/            useTelemetryStore · useSystemStore · useCommandStore
├─ services/         socket.ts · webrtc.ts · mockBridge.ts · commandApi.ts
├─ hooks/            useBridge · useFullscreen · useKeyboardShortcuts
├─ types/            Type contracts
├─ lib/              cn (clsx + tailwind-merge)
├─ styles/           globals.css (设计 token)
└─ main.tsx
nginx/
├─ nginx.conf            global config
├─ site.conf.template    proxy + SPA + cache (BACKEND_HOST 运行时注入)
└─ entrypoint.sh         envsubst 渲染
.github/workflows/
├─ ci.yml                typecheck + build
└─ release.yml           docker → GHCR
```

## 后端契约

前端期望 Python bridge 提供以下端点:

| 端点 | 协议 | 用途 |
|---|---|---|
| `GET /video_feed?camera=<id>` | MJPEG | 视频流 |
| `POST /webrtc/<id>` | HTTP JSON | WebRTC SDP 交换 |
| `WS /socket.io/` | Socket.IO | 状态 / 日志 / 指令 |

Socket.IO 事件:

| 方向 | 事件 | 载荷 |
|---|---|---|
| ← server | `state_update` | `{ uav?, ugv?, city? }` |
| ← server | `system_metrics` | `{ cpu?, gpu?, mem?, net?, fps? }` |
| ← server | `event_log` | `{ severity, source, message }` |
| ← server | `agent_ack` | `{ id, target?, latency_ms? }` |
| ← server | `agent_reject` | `{ id, target?, reason }` |
| → server | `agent_command` | `{ id, target, priority, text }` |

## 路线图

- [x] **M1** 工程基建 + 视觉系统 + 静态原型
- [x] **M2** Socket.IO + 三 store + MJPEG + ErrorBoundary
- [x] **M3** WebRTC + 全屏 + 键盘快捷键
- [x] **M4** Docker + nginx 反代 + GitHub Actions
- [ ] **M5** Lighthouse 95+ / 无障碍 / E2E 测试
