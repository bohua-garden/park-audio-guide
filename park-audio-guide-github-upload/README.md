# 园区扫码听 AI 语音讲解

这是一个静态网站生成系统：从桌面 `/Users/daya/Desktop/全点位` 读取每个点位的讲解词和图片，生成手机端导览网页、AI 语音、压缩图片、二维码和质检报告。

游客页面不会显示点位序号、内部 `point_key`、源文件路径或技术信息。二维码地址使用稳定的 `/p/{point_key}/`，后续调整点位顺序时链接尽量保持不变。

## 安装依赖

```bash
cd park-audio-guide
pip install -r requirements.txt
cp .env.example .env
```

如果使用 `pydub` 合并真实 TTS 音频，建议安装 ffmpeg。macOS 可用：

```bash
brew install ffmpeg
```

## 配置 .env

至少填写：

```bash
BASE_URL=http://localhost:8000
TTS_PROVIDER=mock_tts
```

部署到 GitHub Pages 后，把 `BASE_URL` 改成正式地址，例如：

```bash
BASE_URL=https://你的用户名.github.io/park-audio-guide
```

真实 TTS 密钥只写在 `.env`，不要提交到 GitHub。

## 先试听 AI 音色

```bash
python scripts/01_scan_points.py --limit 2
python scripts/02_generate_ai_voice.py --sample
```

试听文件会生成到 `output/samples/`。

## 先生成 1-2 个样板

```bash
python scripts/run_sample.py --limit 2
```

等同于依次执行：

```bash
python scripts/01_scan_points.py --limit 2
python scripts/02_generate_ai_voice.py --limit 2
python scripts/03_optimize_images.py --limit 2
python scripts/04_build_site.py --limit 2
python scripts/05_generate_qrcodes.py --limit 2
python scripts/06_check_output.py --limit 2
```

本地预览：

```bash
cd public
python -m http.server 8000
```

浏览器打开 `http://localhost:8000`。

## 确认样板后全量生成

```bash
python scripts/run_all.py
```

只更新某一个点位：

```bash
python scripts/run_all.py --point p-8f3a21
```

强制重新生成音频：

```bash
python scripts/02_generate_ai_voice.py --force
```

## 修改讲解词

直接修改对应点位文件夹里的 `.docx`、`.txt` 或 `.md`。重新运行：

```bash
python scripts/01_scan_points.py
python scripts/02_generate_ai_voice.py --point 对应point_key
python scripts/04_build_site.py --point 对应point_key
```

讲解词内容变化后，脚本会根据 `text_hash` 重新生成音频。

## 替换图片

替换点位文件夹中的图片后运行：

```bash
python scripts/03_optimize_images.py --point 对应point_key
python scripts/04_build_site.py --point 对应point_key
```

脚本不会覆盖原图，只会输出压缩图到 `public/assets/images/`。

## 新增点位

在 `/Users/daya/Desktop/全点位` 下新增一个一级点位文件夹，放入讲解词和图片，然后运行：

```bash
python scripts/run_all.py
```

脚本会在点位文件夹中生成 `点位配置.json`，保存稳定 `point_key`。

## 重新生成二维码

先确认 `.env` 里的 `BASE_URL` 是正式访问地址，再运行：

```bash
python scripts/05_generate_qrcodes.py
```

二维码输出到 `output/qrcodes/`，清单输出到 `output/点位二维码清单.xlsx`。

## GitHub Pages 部署

项目已包含 `.github/workflows/deploy.yml`。发布时请只提交项目代码和 `public/` 下的处理后文件，不要提交 `.env`、桌面原始资料、原始 Word、原始高清图、cache 临时文件。

推荐流程：

```bash
git init
git branch -M main
git add README.md requirements.txt .env.example .gitignore data scripts templates public .github
git commit -m "Initial park audio guide"
git remote add origin https://github.com/你的用户名/park-audio-guide.git
git push -u origin main
```

在 GitHub 仓库 Settings → Pages 中选择 GitHub Actions。部署成功后，把 Pages 地址写回 `.env` 的 `BASE_URL`，再重新生成二维码。

## 常见问题

- 没有真实 TTS 密钥：使用 `mock_tts` 可跑通流程，报告会标注“未调用真实 TTS”。
- 二维码无法生成：确认已安装 `qrcode[pil]` 和 `pillow`。
- 图片处理失败：确认已安装 `pillow`，且图片不是损坏文件。
- 网页能打开但音频不能播放：确认 `public/assets/audio/{point_key}.mp3` 存在；如果使用本机 mock 音频，正式上线前建议换真实 TTS 或安装 ffmpeg 生成标准 MP3。
- 页面出现编号：运行 `python scripts/06_check_output.py`，质检报告会标红提示。
