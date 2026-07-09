from __future__ import annotations

import json
import tempfile
import shutil
import subprocess
import re
from pathlib import Path

from common import (
    CACHE_DIR,
    OUTPUT_DIR,
    clean_text,
    copy_file,
    ensure_dirs,
    load_env,
    load_points,
    now_text,
    parse_common_args,
    public_audio_path,
    save_workbook,
    split_for_tts,
    text_hash,
    tts_text,
    write_json,
)


def format_srt_time(seconds: float) -> str:
    millis = int(round(seconds * 1000))
    hours, rest = divmod(millis, 3600_000)
    minutes, rest = divmod(rest, 60_000)
    secs, ms = divmod(rest, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{ms:03d}"


def audio_duration_seconds(path: Path) -> float:
    afinfo = shutil.which("afinfo")
    if afinfo:
        result = subprocess.run([afinfo, str(path)], capture_output=True, text=True)
        match = re.search(r"estimated duration:\s*([0-9.]+)\s*sec", result.stdout)
        if match:
            return float(match.group(1))
    try:
        import mutagen

        audio = mutagen.File(str(path))
        if audio and audio.info and getattr(audio.info, "length", None):
            return float(audio.info.length)
    except Exception:
        pass
    return 0.0


def point_audio_basename(point: dict) -> str:
    order = point.get("show_order")
    prefix = str(order) if order is not None else point["point_key"]
    return f"{prefix}-{point['display_name']}"


def paragraph_parts(text: str) -> list[str]:
    parts = [p.strip() for p in re.split(r"\n{1,}", clean_text(text)) if p.strip()]
    return parts or [clean_text(text)]


def write_subtitles(point: dict, source_folder: Path, original_text: str, timeline: list[dict], total_duration: float) -> None:
    base = point_audio_basename(point)
    (source_folder / f"{base}_原文.txt").write_text(original_text, encoding="utf-8")
    data = {
        "point_key": point["point_key"],
        "display_name": point["display_name"],
        "audio_file": f"{base}.mp3",
        "duration": round(total_duration, 3),
        "captions": timeline,
    }
    write_json(source_folder / f"{base}_字幕时间轴.json", data)
    write_json(public_audio_path(point["point_key"]).with_name(f"{point['point_key']}_captions.json"), data)
    srt_lines = []
    for idx, item in enumerate(timeline, start=1):
        srt_lines.extend(
            [
                str(idx),
                f"{format_srt_time(item['start'])} --> {format_srt_time(item['end'])}",
                item["text"],
                "",
            ]
        )
    srt_text = "\n".join(srt_lines)
    (source_folder / f"{base}_字幕时间轴.srt").write_text(srt_text, encoding="utf-8")
    public_audio_path(point["point_key"]).with_name(f"{point['point_key']}_captions.srt").write_text(srt_text, encoding="utf-8")


async def synthesize_edge_tts_segments(parts: list[str], cache_dir: Path, env: dict[str, str]) -> list[Path]:
    import edge_tts

    voice = env.get("EDGE_TTS_VOICE", "zh-CN-XiaoxiaoNeural")
    rate = env.get("EDGE_TTS_RATE", "-8%")
    volume = env.get("EDGE_TTS_VOLUME", "+0%")
    segment_paths: list[Path] = []
    for idx, part in enumerate(parts, start=1):
        out = cache_dir / f"segment-{idx:03d}.mp3"
        communicate = edge_tts.Communicate(part, voice=voice, rate=rate, volume=volume)
        await communicate.save(str(out))
        if not out.exists() or out.stat().st_size < 1024:
            raise RuntimeError(f"第 {idx} 段语音生成失败")
        segment_paths.append(out)
    return segment_paths


def edge_tts_to_audio(point: dict, text: str, out_path: Path, env: dict[str, str]) -> tuple[bool, str]:
    import asyncio

    parts = paragraph_parts(text)
    with tempfile.TemporaryDirectory(dir=str(CACHE_DIR)) as tmp:
        cache_dir = Path(tmp)
        try:
            segments = asyncio.run(synthesize_edge_tts_segments(parts, cache_dir, env))
        except Exception as exc:
            return False, f"edge_tts 生成失败：{exc}"

        timeline = []
        cursor = 0.0
        for part, segment in zip(parts, segments):
            duration = audio_duration_seconds(segment)
            if duration <= 0:
                duration = max(2.5, len(part) / 4.8)
            timeline.append(
                {
                    "start": round(cursor, 3),
                    "end": round(cursor + duration, 3),
                    "text": part,
                }
            )
            cursor += duration

        out_path.parent.mkdir(parents=True, exist_ok=True)
        with out_path.open("wb") as final:
            for segment in segments:
                final.write(segment.read_bytes())
        if not out_path.exists() or out_path.stat().st_size < 1024:
            return False, "edge_tts 合并后音频过小"
        named_audio = Path(point["source_folder"]) / f"{point_audio_basename(point)}.mp3"
        shutil.copy2(out_path, named_audio)
    write_subtitles(point, Path(point["source_folder"]), text, timeline, cursor)
    return True, f"edge_tts: {env.get('EDGE_TTS_VOICE', 'zh-CN-XiaoxiaoNeural')}，按 {len(parts)} 段生成字幕时间轴"


def aiff_to_mp3(aiff_path: Path, mp3_path: Path, bit_rate: int = 128) -> None:
    import aifc
    import audioop
    import lameenc

    with aifc.open(str(aiff_path), "rb") as audio:
        channels = audio.getnchannels()
        sample_width = audio.getsampwidth()
        frame_rate = audio.getframerate()
        pcm = audio.readframes(audio.getnframes())
    if sample_width > 1:
        pcm = audioop.byteswap(pcm, sample_width)
    encoder = lameenc.Encoder()
    encoder.set_bit_rate(bit_rate)
    encoder.set_in_sample_rate(frame_rate)
    encoder.set_channels(channels)
    encoder.set_quality(2)
    mp3 = encoder.encode(pcm) + encoder.flush()
    mp3_path.parent.mkdir(parents=True, exist_ok=True)
    mp3_path.write_bytes(mp3)


def macos_say_to_audio(text: str, out_path: Path, voice: str = "Tingting", rate: int = 155) -> tuple[bool, str]:
    """Create a local preview voice and encode it as a real MP3."""

    out_path.parent.mkdir(parents=True, exist_ok=True)
    say = shutil.which("say")
    if not say:
        return False, "本机未找到 macOS say 命令"
    with tempfile.TemporaryDirectory(dir=str(CACHE_DIR)) as tmp:
        aiff_path = Path(tmp) / "say.aiff"
        cmd = [say, "-v", voice, "-r", str(rate), text, "-o", str(aiff_path)]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0 or not aiff_path.exists() or aiff_path.stat().st_size < 512:
            fallback = [say, "-r", str(rate), text, "-o", str(aiff_path)]
            result = subprocess.run(fallback, capture_output=True, text=True)
        if result.returncode != 0 or not aiff_path.exists() or aiff_path.stat().st_size < 512:
            return False, (result.stdout + result.stderr).strip()
        try:
            aiff_to_mp3(aiff_path, out_path)
        except Exception as exc:
            return False, f"本机朗读已生成，但 MP3 编码失败：{exc}"
    if out_path.exists() and out_path.stat().st_size > 1024:
        return True, "mock_tts: 使用本机语音生成预览 MP3，未调用真实 TTS"
    return False, "mock_tts 输出音频过小，疑似不可播放"


def generate_silent_placeholder(out_path: Path) -> tuple[bool, str]:
    import math
    import struct
    import lameenc

    out_path.parent.mkdir(parents=True, exist_ok=True)
    sample_rate = 44100
    seconds = 4
    frames = bytearray()
    for i in range(sample_rate * seconds):
        envelope = 0.35 if i < sample_rate * 3 else max(0.0, (sample_rate * 4 - i) / sample_rate) * 0.35
        value = int(3000 * envelope * math.sin(2 * math.pi * 523.25 * i / sample_rate))
        frames.extend(struct.pack("<h", value))
    encoder = lameenc.Encoder()
    encoder.set_bit_rate(96)
    encoder.set_in_sample_rate(sample_rate)
    encoder.set_channels(1)
    encoder.set_quality(2)
    out_path.write_bytes(encoder.encode(bytes(frames)) + encoder.flush())
    return True, "mock_tts: 未调用真实 TTS，仅生成标准 MP3 占位提示音"


def call_real_provider(provider: str, text: str, out_path: Path, env: dict[str, str]) -> tuple[bool, str]:
    if provider == "edge_tts":
        return False, "edge_tts 需要点位上下文，请走 generate_one 分支"
    # Provider adapters are intentionally isolated. Fill the matching API fields
    # in .env, then replace this placeholder with the vendor HTTP request.
    api_key = env.get(f"{provider.upper()}_API_KEY") or env.get("TTS_API_KEY")
    if not api_key:
        return False, f"{provider}: 未配置 API Key，自动改用 mock_tts"
    return False, f"{provider}: provider 插槽已预留，当前样板未接入真实接口"


def generate_one(point: dict, force: bool = False) -> dict:
    env = load_env()
    provider = env.get("TTS_PROVIDER", "mock_tts")
    voice = env.get("TTS_VOICE", "natural_female_guide")
    rate = float(env.get("TTS_RATE", "0.92"))
    source_folder = Path(point["source_folder"])
    audio_path = source_folder / "AI讲解.mp3"
    record_path = source_folder / "AI讲解_生成记录.json"
    text = clean_text(point.get("clean_text") or "")
    digest = text_hash(text)
    old = json.loads(record_path.read_text(encoding="utf-8")) if record_path.exists() else {}
    skipped = (
        not force
        and audio_path.exists()
        and old.get("text_hash") == digest
        and old.get("provider") == provider
        and old.get("voice") == voice
    )
    status = "跳过，讲解词未变化" if skipped else ""
    note = old.get("note", "")
    if not skipped:
        chunks = split_for_tts(text, max_chars=int(env.get("TTS_MAX_CHARS", "900")))
        final_text = "\n\n".join(chunks)
        ok = False
        note = ""
        if provider == "edge_tts":
            ok, note = edge_tts_to_audio(point, text, audio_path, env)
        if provider != "mock_tts":
            if not ok:
                ok, note = call_real_provider(provider, final_text, audio_path, env)
        if not ok:
            preview_text = final_text[:1800]
            ok, note = macos_say_to_audio(preview_text, audio_path, voice=env.get("MOCK_TTS_MAC_VOICE", "Tingting"), rate=int(170 * rate))
        if not ok:
            ok, note = generate_silent_placeholder(audio_path)
        status = "成功" if ok else "失败"
        record = {
            "point_key": point["point_key"],
            "display_name": point["display_name"],
            "text_hash": digest,
            "provider": provider,
            "actual_provider": provider if ok and not note.startswith("mock_tts") else "mock_tts",
            "voice": voice,
            "edge_tts_voice": env.get("EDGE_TTS_VOICE", ""),
            "rate": rate,
            "created_at": now_text(),
            "audio_file": "AI讲解.mp3",
            "note": note,
        }
        write_json(record_path, record)

    copy_file(audio_path, public_audio_path(point["point_key"]))
    return {
        "display_name": point["display_name"],
        "point_key": point["point_key"],
        "text_hash": digest,
        "provider": provider,
        "voice": voice,
        "audio_path": str(audio_path),
        "public_audio": str(public_audio_path(point["point_key"])),
        "status": status,
        "note": note,
    }


def generate_samples() -> None:
    ensure_dirs()
    points = load_points(limit=1)
    if not points:
        raise SystemExit("请先运行 01_scan_points.py")
    text = tts_text(points[0].get("clean_text", ""))[:150]
    env = load_env()
    if env.get("TTS_PROVIDER") == "edge_tts":
        voices = [
            ("zh-CN-XiaoxiaoNeural", -8),
            ("zh-CN-XiaoyiNeural", -8),
            ("zh-CN-XiaoxuanNeural", -8),
        ]
        rows = []
        for idx, (voice, rate) in enumerate(voices, start=1):
            out = OUTPUT_DIR / "samples" / f"sample_voice_{idx}.mp3"
            sample_env = dict(env)
            sample_env["EDGE_TTS_VOICE"] = voice
            sample_env["EDGE_TTS_RATE"] = f"{rate:+d}%"
            ok, note = edge_tts_to_audio({"point_key": f"sample_voice_{idx}", "display_name": f"试听音色{idx}", "show_order": idx, "source_folder": str(OUTPUT_DIR / "samples")}, text, out, sample_env)
            rows.append([f"sample_voice_{idx}.mp3", voice, str(out), "成功" if ok else "失败", note])
        save_workbook(OUTPUT_DIR / "AI配音生成清单.xlsx", ["文件", "音色", "路径", "状态", "说明"], rows)
        print(f"已生成试听音色：{OUTPUT_DIR / 'samples'}")
        return
    voices = [("Tingting", 145), ("Sin-ji", 142), ("Mei-Jia", 148)]
    rows = []
    for idx, (voice, rate) in enumerate(voices, start=1):
        out = OUTPUT_DIR / "samples" / f"sample_voice_{idx}.mp3"
        ok, note = macos_say_to_audio(text, out, voice=voice, rate=rate)
        if not ok:
            ok, note = generate_silent_placeholder(out)
        rows.append([f"sample_voice_{idx}.mp3", voice, str(out), "成功" if ok else "失败", note])
    save_workbook(OUTPUT_DIR / "AI配音生成清单.xlsx", ["文件", "音色", "路径", "状态", "说明"], rows)
    print(f"已生成试听音色：{OUTPUT_DIR / 'samples'}")


def main() -> None:
    parser = parse_common_args("生成 AI 语音讲解")
    parser.add_argument("--sample", action="store_true", help="只生成试听音色")
    args = parser.parse_args()
    ensure_dirs()
    if args.sample:
        generate_samples()
        return
    points = load_points(limit=args.limit, point_key=args.point)
    if not points:
        raise SystemExit("没有可处理的点位，请先扫描资料")
    rows = []
    for point in points:
        result = generate_one(point, force=args.force)
        rows.append(
            [
                result["display_name"],
                result["point_key"],
                result["provider"],
                result["voice"],
                result["audio_path"],
                result["public_audio"],
                result["status"],
                result["note"],
            ]
        )
    save_workbook(OUTPUT_DIR / "AI配音生成清单.xlsx", ["点位名称", "point_key", "provider", "voice", "原文件夹音频", "网站音频", "状态", "说明"], rows)
    print(f"已处理 {len(rows)} 个点位音频")


if __name__ == "__main__":
    main()
