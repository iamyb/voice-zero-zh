# voice-zero-zh

中文 TTS 参考音频库（Chinese reference audio for zero-shot TTS）。

为 IndexTTS / CosyVoice / GPT-SoVITS 等 zero-shot TTS 模型提供**干净、标准化、可溯源**的中文参考音频。每个说话人一个 5–10 秒的样本，统一响度、统一采样率，可直接作为参考音频使用。

> 参考 [voice-zero](https://github.com/OwenTyme/voice-zero) 的思路构建，但面向中文，数据源为 [AISHELL-1](https://www.openslr.org/33/)（Apache-2.0）。

## 当前样本

- **aishell1**：30 个参考音频（20 位男性 S0002–S0021 + 10 位女性 S0124–S0133）。
- **indextts_demo**：IndexTTS 官方 demo 音频（待抓取）。
- 完整 AISHELL-1 数据集共 119 位说话人，可用 `--all-missing` 一键补齐。

## 数据源

- **AISHELL-1**：119 位说话人、5.8 小时录音棚级普通话朗读音频，Apache-2.0 许可。
- 音频下载自 HuggingFace 镜像 [`AISHELL/AISHELL-1`](https://huggingface.co/datasets/AISHELL/AISHELL-1)（按说话人打包的 tar.gz，仅含 S0002–S0101）；不在该镜像中的说话人自动回退到 [`shenyunhang/AISHELL-1`](https://huggingface.co/datasets/shenyunhang/AISHELL-1)（逐文件存放，覆盖全部 119 位说话人）。
- 说话人信息（性别）来自官方 `speaker.info`（[openslr.org/33](https://www.openslr.org/33/)）。

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
  <source>/        # 其他来源…
metadata/
  index.json       # 全部样本的聚合索引（跨所有来源）
  aishell1/
    Sxxxx.json     # 单个样本的溯源信息
    speaker.info   # 官方说话人信息（ID + 性别）
  indextts_demo/
    demo_xx.json   # 单个样本的溯源信息
scripts/
  build_voices.py        # AISHELL-1 构建脚本（下载 → 挑选 → 清洗 → 元数据）
  fetch_indextts_demo.py # 抓取 IndexTTS 官方 demo
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

# 抓取 IndexTTS 官方 demo 音频
python3 scripts/fetch_indextts_demo.py

# 仅重建 index.json
python3 scripts/reindex.py
```

依赖：`curl`、`tar`、`ffmpeg`（含 ffprobe）、Python 3.8+（仅标准库）。

## 许可

- 音频数据：**Apache-2.0**（AISHELL-1，北京科技大学 & 数据堂）。
- 使用时请保留对 AISHELL-1 的署名。详见 [LICENSE](LICENSE)。
