# PixelPress · 离线批量图片压缩

一个本机离线运行的图片压缩工具：多格式、可批量、无损与有损双模、按百分比等比缩放，界面按专业工具规格制作。打包为免安装 exe，不联网、不上传。

![主界面](benchmarks/ui/final_03_done_1280x820.png)

---

## 功能

- **多格式**：JPEG、PNG、WebP、AVIF、TIFF、GIF、BMP 读写；ICO、TGA、PPM 可读可原样重存；**HEIC/HEIF 只读**（可读入，输出落到可写格式）。
- **无损 / 有损双模**：按格式能力自动约束——AVIF 无无损、TIFF/BMP 无有损，界面会禁用不可用的那一侧并说明原因。
- **质量可调**：1–100 滑杆 + 低/中/高/极高预设；各格式按自己的标尺换算（如 PNG 有损=调色板 16→256 色）。
- **等比缩放**：5–100% 百分比，纵横比锁定，100/75/50/25 快捷档，实时显示换算后的目标像素尺寸。
- **批量**：拖入文件或文件夹、多线程并行、逐文件状态与失败隔离、可中途取消。
- **前后对比**：拖动中缝比较原图与压缩结果，滚轮缩放、双击复位。
- **节省可视化**：每个文件一条节省量条形图，批次结束给出总节省大数字。
- **深色 / 浅色双主题**，字体随包内置，任何机器上都是设计的样子。

## 实测压缩效果

数据来自 `scripts/benchmark_codecs.py`（本机 Pillow 12.3.0 / oxipng 10.2.1）：

| 场景 | 结果 |
|---|---|
| WebP 无损 vs PNG 无损（UI 截图） | 502 B vs 5,849 B，**小 91%**，且逐位无损 |
| oxipng 重压缩 PNG 无损 | 照片 **−11.2%**，图形 **−75.5%** |
| JPEG 视觉无损（沿用原量化表） | 390 KB → 339 KB（−13%），PSNR 79.7 dB |
| JPEG 有损 q75 4:2:0 | 1.1 MB → 85 KB（−92%），PSNR 39.6 dB |

**无损模式优先选 WebP**——大多数情况下它同时赢过 PNG 的体积和保真度。

## 运行

开发态：

```bash
pip install -r requirements.txt
python scripts/fetch_fonts.py     # 首次拉取随包字体（OFL）
python PixelPress.py              # 启动界面
python PixelPress.py --headless   # 引擎自检，不打开窗口
```

打包：

```bash
python -m PyInstaller --clean --noconfirm PixelPress.spec
```

产物在 `dist/PixelPress/`，双击 `PixelPress.exe` 即可（约 120 MB，免装 Python 与任何运行时）。

## 快捷键

| 键 | 作用 |
|---|---|
| `Ctrl+O` / `Ctrl+Shift+O` | 添加文件 / 添加文件夹 |
| `Ctrl+Enter` | 开始压缩 |
| `Esc` | 取消 |
| `Delete` | 移除选中行 |
| `Ctrl+1` / `Ctrl+2` | 切到无损 / 有损 |
| `Ctrl+D` | 切换深色主题 |
| `Ctrl+` `+` / `-` / `0` | 预览放大 / 缩小 / 复位 |

## 目录结构

```
app/
├── main.py              入口（GUI / --headless 分派）
├── cli.py               打包自检（非用户级 CLI）
├── core/                纯 Python 引擎，零 Qt 依赖，可单测
│   ├── formats.py       格式注册表与能力位
│   ├── planner.py       模式/质量/力度 → 编码参数的唯一决策点
│   ├── pipeline.py      解码 → 方向烘焙 → 缩放 → 编码 → 校验 → 原子写盘
│   ├── naming.py        命名规则、冲突策略、原地覆盖保护
│   ├── encoders/        Pillow 全格式 + oxipng（PNG 无损增强）
│   ├── imaging.py       可选解码器注册（HEIC）
│   ├── settings_store.py 设置持久化（PIXELPRESS_SETTINGS_DIR 可覆盖）
│   └── paths.py         冻结/源码双模式的资源定位
└── ui/                  theme / fonts / icons / widgets / queue_model /
                         preview / panels / workers / ui_logic / main_window
scripts/
├── benchmark_codecs.py  编解码能力与压缩率实测
├── fetch_fonts.py       拉取随包 OFL 字体
├── ui_preview.py        离屏 / 实机像素审计 + 截图
├── verify_bundle.py     打包产物取证（TOC 模块名、资源、体积）
└── verify_live_window.ps1  实机启动与窗口截图
```

## 测试

```bash
python -m pytest tests -q          # 129 passed, 3 skipped（跳过项为刻意不可用的格式组合）
python scripts/ui_preview.py --platform real     # 像素审计 + 截图
python scripts/verify_bundle.py                  # 需先打包（读 build/ 下的 TOC）
```

## 设计说明

界面方向为「PRESS 印刷车间」：冷调纸白画布、墨黑文字、单一朱红信号色，半调网点作为唯一装饰——它本身就是印刷技法，与图像压缩同源。数值全部使用等宽字体以便扫读，节省量用条形图表达长度而非数字。

完整技术方案、能力矩阵与设计令牌见 [docs/技术方案.md](docs/技术方案.md)。

## 已知边界

1. **JPEG 无比特级无损**：`quality="keep"` 保留原量化表并优化熵编码，实测 79.7 dB，视觉不可辨但非逐位相同。界面文案严格写「视觉无损」。
2. **AVIF 无无损模式**：Pillow 12 未暴露 libavif 的 lossless，界面禁用该组合。
3. **动图跳过**：GIF/WebP 多帧不重编码，队列中标注原因后跳过。
4. **HEIC 仅读不写**：写回 HEIC 涉及额外授权考量，输出侧自动落到可写格式。
5. **中文依赖系统字体**：界面用随包 Archivo + IBM Plex Mono，中文走系统微软雅黑 UI（不打包 CJK 字体以省 10+ MB）。

## 许可

代码为本项目自有。随包分发的第三方组件及其许可：

- **oxipng** — MIT
- **Archivo**、**IBM Plex Mono** — SIL Open Font License 1.1（许可原文见 `app/assets/fonts/LICENSE-*.txt`）
- **Pillow** — MIT-CMU；**pillow-heif / libheif** — BSD-3；**PySide6 / Qt** — LGPL-3
