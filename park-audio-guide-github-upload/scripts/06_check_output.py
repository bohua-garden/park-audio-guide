from __future__ import annotations

import re
import shutil
import subprocess
import wave
from pathlib import Path

from common import OUTPUT_DIR, PUBLIC_DIR, ensure_dirs, load_env, load_points, parse_common_args, public_audio_path, safe_filename, save_workbook


BAD_PATTERNS = [r"第\s*\d+\s*站", r"编号", r"point_key", r"生成时间", r"技术路径", r"源文件路径", r"\b0[1-9]\b"]


def audio_duration(path: Path) -> str:
    if not path.exists():
        return ""
    afinfo = shutil.which("afinfo")
    if afinfo:
        result = subprocess.run([afinfo, str(path)], capture_output=True, text=True)
        match = re.search(r"estimated duration:\s*([0-9.]+)\s*sec", result.stdout)
        if match:
            return f"{float(match.group(1)):.1f}秒"
    try:
        import mutagen

        audio = mutagen.File(str(path))
        if audio and audio.info and getattr(audio.info, "length", None):
            return f"{audio.info.length:.1f}秒"
    except Exception:
        pass
    try:
        with wave.open(str(path), "rb") as wf:
            return f"{wf.getnframes() / wf.getframerate():.1f}秒"
    except Exception:
        return "可播放性待人工确认"


def main() -> None:
    parser = parse_common_args("检查样板输出")
    args = parser.parse_args()
    ensure_dirs()
    env = load_env()
    base_url = env.get("BASE_URL", "").strip().rstrip("/")
    rows = []
    red_flags = {}
    points = load_points(limit=args.limit, point_key=args.point)
    for idx, point in enumerate(points, start=2):
        source_audio = Path(point["source_folder"]) / "AI讲解.mp3"
        site_audio = public_audio_path(point["point_key"])
        image_dir = PUBLIC_DIR / "assets" / "images" / point["point_key"]
        images = list(image_dir.glob("*.*")) if image_dir.exists() else []
        page = PUBLIC_DIR / "p" / point["point_key"] / "index.html"
        qr_file = OUTPUT_DIR / "qrcodes" / safe_filename(point["display_name"], "_扫码听解说.png")
        html = page.read_text(encoding="utf-8") if page.exists() else ""
        bad_hits = [pat for pat in BAD_PATTERNS if re.search(pat, html)]
        fail_reason = []
        if not point.get("clean_text"):
            fail_reason.append("缺少讲解词")
        if not source_audio.exists():
            fail_reason.append("未生成原文件夹音频")
        if not site_audio.exists():
            fail_reason.append("未生成网站音频")
        if not images:
            fail_reason.append("未处理图片")
        if not page.exists():
            fail_reason.append("未生成网页")
        if not qr_file.exists():
            fail_reason.append("未生成二维码")
        if bad_hits:
            fail_reason.append("游客页面疑似出现编号或技术信息")
        full_url = f"{base_url}/p/{point['point_key']}/" if base_url else ""
        rows.append(
            [
                point["display_name"],
                point["point_key"],
                "是" if point.get("clean_text") else "否",
                "是" if source_audio.exists() else "否",
                str(source_audio),
                str(site_audio),
                audio_duration(site_audio),
                f"{site_audio.stat().st_size/1024:.1f}KB" if site_audio.exists() else "",
                "是" if images else "否",
                len(images),
                f"{sum(p.stat().st_size for p in images)/1024:.1f}KB" if images else "",
                "是" if page.exists() else "否",
                "是" if qr_file.exists() else "否",
                "是" if bad_hits else "否",
                full_url,
                "是" if page.exists() and site_audio.exists() and images else "否",
                "；".join(fail_reason) or "通过",
            ]
        )
        red_flags[(idx, 14)] = bool(bad_hits)
        red_flags[(idx, 17)] = bool(fail_reason)
    save_workbook(
        OUTPUT_DIR / "质检报告.xlsx",
        [
            "点位名称",
            "point_key",
            "是否有讲解词",
            "是否生成AI讲解.mp3",
            "原点位文件夹音频路径",
            "网站音频路径",
            "音频时长",
            "音频大小",
            "是否处理图片",
            "图片数量",
            "图片总大小",
            "是否生成点位网页",
            "是否生成二维码",
            "页面是否显示了编号",
            "URL是否完整",
            "是否可部署",
            "失败原因",
        ],
        rows,
        red_flags=red_flags,
    )
    print(f"质检完成：{OUTPUT_DIR / '质检报告.xlsx'}")


if __name__ == "__main__":
    main()
