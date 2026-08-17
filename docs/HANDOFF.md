# 硬件测试离线包(同事开箱指南)

这个包是为"拿到就能测硬件"打的:解压后不需要安装 ESP-IDF、不需要 uv sync、
不需要 npm install。前提是同事的电脑是 **macOS Apple Silicon(arm64)**——
`.venv` 与 `node_modules` 里的原生二进制是 arm64/macOS 专用的。

## 快速开始

```bash
# 1. 解压(macOS 命令行;Finder 双击也能解压)
tar -xzf wifi-spatial-council-handoff-*.tar.gz
cd wifi-spatial-council-prompt-engineering

# 2. 重新指向打包机自带的 Python(只跑一次,约 5 秒)
scripts/relink_venv.sh

# 3. 烧录三块板(端口必须写全,绝不自动猜测)
scripts/flash_bundle.sh \
  TX_PORT=/dev/cu.usbmodemXXXX \
  RX_A_PORT=/dev/cu.usbmodemYYYY \
  RX_B_PORT=/dev/cu.usbmodemZZZZ

# 4. 启动 live 模式(两个终端,不需要 uv/ESP-IDF)
#    终端 1(API):
APP_MODE=live DEMO_AUTOSTART=1 \
RX_PORTS="rx-a=/dev/cu.usbmodemYYYY,rx-b=/dev/cu.usbmodemZZZZ" \
LIVE_TOPOLOGY_HASH="sha256:<hardware/topology.json 中的 64 位哈希>" \
CALIBRATION_PROFILE="data/calibration/<live-profile>/profile.json" \
.venv/bin/python -m uvicorn wifi_api.app:app --host 127.0.0.1 --port 8000
#    终端 2(前端,Web UI 在 http://127.0.0.1:5173):
cd apps/web && node_modules/.bin/vite --host 127.0.0.1
```

启动后必须检查 `http://127.0.0.1:8000/api/stream/status`: `mode` 必须为
`live`,两个 RX 端口必须出现在 source health 中。任何 `mock` / `replay`、
缺失 profile、拓扑不匹配或 `unknown` 都不能记成 Live 通过。

烧录不需要 ESP-IDF:包里只有每个板三个 bin + flash_args,
由预装的 `esptool`(在 `.venv` 里)直接写入。`.elf` 一并打包,固件若 panic
可据此解析地址。Python 运行时(CPython 3.11.15 arm64)已随包携带,
`relink_venv.sh` 把 `.venv` 指向它,所以不需要安装 uv 或 Python。
前端需要同事机器已装 Node.js 18+。

## 当前可执行的硬件检查

```bash
make hardware-sanity RX_PORTS=rx-a=...,rx-b=... TX_PORT=...
```

`hardware-sanity` 会真实读取两个 RX 并生成采集 QA。当前 checkout 中
`calibrate-live`、`test-hardware`、`compare-live-replay` 仍是安全占位门禁，
会返回非零而不会伪造通过结果；在它们接入真实 raw recording 与 held-out
评估前，不要把这三个命令写入已完成的验收记录。

详见 `docs/LIVE_SETUP.md` 与 `docs/CALIBRATION.md`。

## 如果同事的电脑不是 macOS arm64

`.venv` 和 `node_modules` 无法跨平台/架构使用,这个包不适用。改用源码包
(约 15 MB),同事在本机执行:

```bash
make setup               # uv sync + npm ci + 契约生成
make firmware-build      # 本地重编固件(需要 ESP-IDF)
scripts/flash_bundle.sh TX_PORT=... RX_A_PORT=... RX_B_PORT=...
make live RX_PORTS=rx-a=...,rx-b=... \
  LIVE_TOPOLOGY_HASH=sha256:REPLACE_WITH_64_HEX \
  CALIBRATION_PROFILE=data/calibration/live_room_v1/profile.json
```

`make setup` 与 `make firmware-build` 的依赖清单见
`docs/QUICKSTART.md` 和 `docs/LIVE_SETUP.md`。

## 包里有什么 / 没包什么

包含:

- `.venv`(Python 依赖,含 esptool/pyserial)、`apps/web/node_modules`
- `.handoff-python`(自包含 CPython 3.11.15 arm64,~64 MB)
- 固件烧录件:`firmware/*/build/{bootloader,partition_table,*.bin,flash_args,*.elf}`
- 源码、`data/fixtures`、`data/calibration`、知识库、文档、`uv.lock`

排除(本机状态或可再生内容):

- `firmware/*/build` 中间对象(每板约 148 MB,仅保留烧录件)
- `data/raw` 本地敏感采集；需要交接时应单独选择并校验具体 bundle
- `.git` 与本机 `.env*`；代码同步应使用共享私有远程仓库，不依赖压缩包历史
- `data/derived/stream` 运行日志、`.mypy_cache`、Playwright 截图
- `apps/web/dist`、`*.egg-info`、`__pycache__`

## 版本清单与两道发布门

Replay 候选默认使用明确标记为 `simulated` 的 fixture 拓扑，生成的清单
仍会把模拟标定和 Mock 原始来源列为警告：

```bash
uv run python scripts/generate_demo_manifest.py --gate replay_candidate
```

交付时把 `demo-version-manifest.json`、handoff `.tar.gz` 与同名 `.sha256`
放在一起；源码协作走 Git，压缩包只负责固定版本的离线运行与烧录。

硬件最终版必须显式传入 Live 录制、非模拟标定和硬件拓扑；不得用 Replay
拓扑替代：

```bash
uv run python scripts/generate_demo_manifest.py \
  --gate final_demo_ready \
  --bundle data/raw/<live-recording> \
  --profile data/calibration/<live-profile>/profile.json \
  --topology hardware/topology.json
```
