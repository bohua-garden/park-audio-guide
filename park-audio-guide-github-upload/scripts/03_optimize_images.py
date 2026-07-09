from __future__ import annotations

from pathlib import Path

from common import OUTPUT_DIR, PUBLIC_DIR, ensure_dirs, load_points, parse_common_args, save_workbook


def optimize_image(src: Path, dst_webp: Path, dst_jpg: Path, max_side: int, quality: int = 82) -> tuple[int, int]:
    from PIL import Image, ImageOps

    dst_webp.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(src) as im:
        im = ImageOps.exif_transpose(im)
        im.thumbnail((max_side, max_side))
        if im.mode not in ("RGB", "RGBA"):
            im = im.convert("RGB")
        rgb = im.convert("RGB")
        rgb.save(dst_jpg, "JPEG", quality=quality, optimize=True, progressive=True)
        rgb.save(dst_webp, "WEBP", quality=quality, method=6)
    return dst_webp.stat().st_size, dst_jpg.stat().st_size


def main() -> None:
    parser = parse_common_args("压缩点位图片")
    args = parser.parse_args()
    ensure_dirs()
    rows = []
    points = load_points(limit=args.limit, point_key=args.point)
    for point in points:
        point_dir = PUBLIC_DIR / "assets" / "images" / point["point_key"]
        point_dir.mkdir(parents=True, exist_ok=True)
        image_paths = [Path(p) for p in point.get("images", [])]
        count = 0
        total = 0
        for idx, src in enumerate(image_paths, start=1):
            if not src.exists():
                rows.append([point["display_name"], point["point_key"], src.name, "", "", "失败：原图不存在"])
                continue
            stem = "cover" if idx == 1 else f"image-{idx}"
            webp = point_dir / f"{stem}.webp"
            jpg = point_dir / f"{stem}.jpg"
            try:
                webp_size, jpg_size = optimize_image(src, webp, jpg, 1600, 82)
                total += webp_size + jpg_size
                count += 1
                rows.append([point["display_name"], point["point_key"], src.name, f"{webp_size/1024:.1f}KB", f"{jpg_size/1024:.1f}KB", "成功"])
                if idx == 1:
                    thumb_webp = point_dir / "thumb.webp"
                    thumb_jpg = point_dir / "thumb.jpg"
                    optimize_image(src, thumb_webp, thumb_jpg, 600, 78)
            except Exception as exc:
                rows.append([point["display_name"], point["point_key"], src.name, "", "", f"失败：{exc}"])
        if not image_paths:
            rows.append([point["display_name"], point["point_key"], "", "", "", "失败：无图片"])
        point["optimized_image_count"] = count
        point["optimized_image_total_size"] = total
    save_workbook(OUTPUT_DIR / "图片压缩清单.xlsx", ["点位名称", "point_key", "原图", "webp大小", "jpg大小", "状态"], rows)
    print(f"已处理 {len(points)} 个点位图片")


if __name__ == "__main__":
    main()
