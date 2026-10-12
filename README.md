# voice-zero-zh

中文 TTS 参考音频库（Chinese reference audio for zero-shot TTS）。

为 IndexTTS / CosyVoice / GPT-SoVITS 等 zero-shot TTS 模型提供**干净、标准化、可溯源**的中文参考音频。每个说话人一个 5–10 秒的样本，统一响度、统一采样率，可直接作为参考音频使用。

> 参考 [voice-zero](https://github.com/OwenTyme/voice-zero) 的思路构建，但面向中文，数据源为 [AISHELL-1](https://www.openslr.org/33/)（Apache-2.0）。

## 当前样本

| 来源 | 数量 | 说明 |
|---|---|---|
| **aishell1** | 340 | AISHELL-1（161 男 + 179 女），录音棚级，Apache-2.0 |
| **indextts_demo** | 13 | IndexTTS 官方 demo 片段 |
| **spark_tts_demo** | 8 | Spark-TTS 官方 demo（含名人/角色音色） |
| **cosyvoice_demo** | 2 | CosyVoice 官方 zero-shot / cross-lingual prompt |
| **f5_tts_demo** | 1 | F5-TTS 官方中文参考 |

- 共 **364 个样本**。AISHELL-1 的 `speaker.info` 列有 400 位说话人，但公开镜像只覆盖 340 位（S0002–S0723），已全部补齐；其余 60 位（S0724–S0916）在任何公开镜像中都不存在。
- ⚠️ 部分 demo（尤其 Spark-TTS 的名人音色）涉及真实人物声音，公开分发前请自行评估声音权益。

## 数据源

- **AISHELL-1**：`speaker.info` 列有 400 位说话人（214 女 / 186 男），录音棚级普通话朗读音频，Apache-2.0 许可。
- 音频下载自 HuggingFace 镜像 [`AISHELL/AISHELL-1`](https://huggingface.co/datasets/AISHELL/AISHELL-1)（按说话人打包的 tar.gz，仅含 S0002–S0101）；不在该镜像中的说话人自动回退到 [`shenyunhang/AISHELL-1`](https://huggingface.co/datasets/shenyunhang/AISHELL-1)（逐文件存放，覆盖 S0002–S0723 共 340 位）。
- 说话人信息（性别）来自官方 `speaker.info`（[openslr.org/33](https://www.openslr.org/33/)）。
- 大规模补齐用 `bash scripts/fill_parallel.sh 8`（8 路并行，约 40 分钟补完 340 位）。

## 清洗流程

每个样本的处理步骤（`scripts/build_voices.py`）：

1. 下载该说话人的全部音频（`data_aishell/wav/Sxxxx.tar.gz`）；
2. 用 ffprobe 探测每条音频时长，挑选**时长最接近 7 秒**（5–10 秒范围内）的一条；
3. ffmpeg 清洗：截取前 7 秒 → `loudnorm` 响度归一化（目标 -8 LUFS，真峰 -2 dB，LRA 11）→ 重采样 16 kHz 单声道；
4. 输出 `voices/aishell1/Sxxxx.wav`，并写入 `metadata/aishell1/Sxxxx.json` 记录完整溯源信息。

AISHELL-1 本身是录音棚干声（无混响、无背景音乐、无噪声），因此不需要 RNNoise / 去混响等额外处理。

## 目录结构

```
voices/
  aishell1/        # AISHELL-1 清洗后的参考音频（16 kHz mono wav）
  indextts_demo/   # IndexTTS 官方 demo 音频
  spark_tts_demo/  # Spark-TTS 官方 demo
  f5_tts_demo/     # F5-TTS 官方 demo
  <source>/        # 其他来源…
metadata/
  index.json       # 全部样本的聚合索引（跨所有来源）
  aishell1/
    Sxxxx.json     # 单个样本的溯源信息
    speaker.info   # 官方说话人信息（ID + 性别）
  <source>/
    <id>.json      # 单个样本的溯源信息
scripts/
  build_voices.py        # AISHELL-1 构建脚本（下载 → 挑选 → 清洗 → 元数据）
  fill_parallel.sh       # 并行补齐缺失说话人（N 路并发，最后统一 reindex）
  fetch_demos.py         # 通用 TTS demo 抓取（由 demo_sources.json 驱动）
  demo_sources.json      # demo 来源清单（加新来源只改这里）
  fetch_indextts_demo.py # IndexTTS demo 抓取（早期专用脚本）
  reindex.py             # 重建 metadata/index.json
```

## 使用

### 配合 indextts-api

```bash
# 注册为音色
curl -F "file=@voices/aishell1/S0002.wav" -F "name=aishell_S0002" -F "consent=yes" \
  http://127.0.0.1:8000/v1/voices

# 合成
curl -X POST http://127.0.0.1:8000/v1/audio/speech \
  -H "Content-Type: application/json" \
  -d '{"model":"indextts","voice":"aishell_S0002","input":"你好，世界。"}' \
  --output out.wav
```

### 直接作为参考音频

任何接受参考音频的 zero-shot TTS 模型都可以直接使用 `voices/` 下的 wav 文件。

## 扩充样本

```bash
# 构建指定 AISHELL-1 说话人
python3 scripts/build_voices.py S0022 S0023 S0024

# 构建 speaker.info 中所有尚未构建的说话人（共 119 位）
python3 scripts/build_voices.py --all-missing

# 抓取所有 TTS demo（由 demo_sources.json 驱动）
python3 scripts/fetch_demos.py

# 只抓取某个来源
python3 scripts/fetch_demos.py spark_tts_demo

# 仅重建 index.json
python3 scripts/reindex.py
```

### 添加新的 demo 来源

编辑 `scripts/demo_sources.json`，加一个条目即可（路径支持中文，脚本会自动 URL 编码）：

```json
{
  "source": "my_tts_demo",
  "base": "https://raw.githubusercontent.com/owner/repo/main",
  "dataset": "MyTTS official demo (owner/repo)",
  "license": "See repo LICENSE",
  "default_language": "zh-CN",
  "files": {
    "sample_1": {"path": "asset/sample_1.wav", "gender": "F", "label": "示例音色"}
  }
}
```

然后运行 `python3 scripts/fetch_demos.py my_tts_demo`。

依赖：`curl`、`tar`、`ffmpeg`（含 ffprobe）、Python 3.8+（仅标准库）。

## 许可

- 音频数据：**Apache-2.0**（AISHELL-1，北京科技大学 & 数据堂）。
- 使用时请保留对 AISHELL-1 的署名。详见 [LICENSE](LICENSE)。
