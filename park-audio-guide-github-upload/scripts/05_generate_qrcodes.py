from __future__ import annotations

from pathlib import Path

from common import OUTPUT_DIR, ensure_dirs, load_env, load_points, parse_common_args, safe_filename, save_workbook


def make_qr(url: str, title: str, out_path: Path) -> None:
    try:
        import qrcode
        from PIL import Image, ImageDraw, ImageFont
    except Exception as exc:
        raise SystemExit(f"缺少二维码依赖，请先安装 requirements.txt：{exc}")

    qr = qrcode.QRCode(version=None, error_correction=qrcode.constants.ERROR_CORRECT_M, box_size=12, border=3)
    qr.add_data(url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="#1f3b2d", back_color="white").convert("RGB")
    width, height = img.size
    label_h = 96
    canvas = Image.new("RGB", (width, height + label_h), "white")
    canvas.paste(img, (0, 0))
    draw = ImageDraw.Draw(canvas)
    try:
        font_title = ImageFont.truetype("/System/Library/Fonts/PingFang.ttc", 30)
        font_sub = ImageFont.truetype("/System/Library/Fonts/PingFang.ttc", 22)
    except Exception:
        font_title = ImageFont.load_default()
        font_sub = ImageFont.load_default()
    for text, y, font, fill in [(title, height + 12, font_title, "#203126"), ("扫码听解说", height + 54, font_sub, "#47765b")]:
        bbox = draw.textbbox((0, 0), text, font=font)
        draw.text(((width - (bbox[2] - bbox[0])) / 2, y), text, font=font, fill=fill)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(out_path)


def main() -> None:
    parser = parse_common_args("生成点位二维码")
    args = parser.parse_args()
    ensure_dirs()
    env = load_env()
    base_url = env.get("BASE_URL", "").strip().rstrip("/")
    if not base_url:
        raise SystemExit("BASE_URL 为空，请先在 .env 中填写本地或 GitHub Pages 地址")
    rows = []
    points = load_points(limit=args.limit, point_key=args.point)
    for point in points:
        url = f"{base_url}/p/{point['point_key']}/"
        filename = safe_filename(point["display_name"], "_扫码听解说.png")
        out_path = OUTPUT_DIR / "qrcodes" / filename
        try:
            make_qr(url, point["display_name"], out_path)
            status = "成功"
        except SystemExit:
            raise
        except Exception as exc:
            status = f"失败：{exc}"
        rows.append([point["display_name"], point["point_key"], url, filename, status])
    save_workbook(OUTPUT_DIR / "点位二维码清单.xlsx", ["点位名称", "point_key", "URL", "二维码文件名", "生成状态"], rows)
    print(f"已生成 {len(rows)} 个二维码")


if __name__ == "__main__":
    main()
