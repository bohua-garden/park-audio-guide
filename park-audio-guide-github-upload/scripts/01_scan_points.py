from __future__ import annotations

from pathlib import Path

from common import (
    CONFIG_NAME,
    OUTPUT_DIR,
    POINTS_JSON,
    SOURCE_ROOT,
    clean_text,
    ensure_dirs,
    page_url,
    parse_common_args,
    parse_order_and_name,
    read_json,
    read_text_file,
    save_workbook,
    select_audio_file,
    select_image_files,
    select_text_file,
    sort_key_for_folder,
    stable_short_key,
    write_json,
)


def scan(limit: int | None = None, force_rescan: bool = False) -> list[dict]:
    ensure_dirs()
    if not SOURCE_ROOT.exists():
        raise SystemExit(f"未找到点位文件夹：{SOURCE_ROOT}")
    folders = [p for p in SOURCE_ROOT.iterdir() if p.is_dir() and not p.name.startswith(".")]
    folders.sort(key=sort_key_for_folder)
    if limit is not None:
        folders = folders[:limit]

    points: list[dict] = []
    report_rows: list[list] = []
    for idx, folder in enumerate(folders, start=1):
        order, display_name = parse_order_and_name(folder.name)
        show_order = order if order is not None else idx
        config_path = folder / CONFIG_NAME
        config = read_json(config_path, {}) if config_path.exists() and not force_rescan else {}
        point_key = config.get("point_key") or stable_short_key(folder.name)
        display_name = config.get("display_name") or display_name
        config_data = {
            "point_key": point_key,
            "display_name": display_name,
            "source_folder": folder.name,
            "show_order": show_order,
        }
        if config != config_data:
            write_json(config_path, config_data)

        files = [p for p in folder.iterdir() if p.is_file() and not p.name.startswith(".")]
        text_file = select_text_file(files)
        raw_text = read_text_file(text_file)
        cleaned = clean_text(raw_text)
        images = select_image_files(files)
        audio_source = select_audio_file(files)
        point = {
            "point_key": point_key,
            "display_name": display_name,
            "show_order": show_order,
            "source_folder": str(folder),
            "text_file": str(text_file) if text_file else "",
            "clean_text": cleaned,
            "images": [str(p) for p in images],
            "audio_source": str(audio_source) if audio_source else "",
            "page_url": page_url(point_key),
        }
        points.append(point)
        report_rows.append(
            [
                display_name,
                point_key,
                show_order,
                folder.name,
                "是" if text_file else "否",
                text_file.name if text_file else "",
                len(cleaned),
                len(images),
                "是" if audio_source else "否",
                "通过" if text_file and images else "缺少资料",
            ]
        )

    write_json(POINTS_JSON, points)
    save_workbook(
        OUTPUT_DIR / "点位资料检查表.xlsx",
        ["点位名称", "point_key", "内部排序", "源文件夹", "是否有讲解词", "讲解词文件", "文字长度", "图片数量", "是否已有音频", "检查结果"],
        report_rows,
    )
    return points


def main() -> None:
    parser = parse_common_args("扫描点位资料")
    parser.add_argument("--force-rescan", action="store_true", help="重新扫描并刷新点位配置")
    args = parser.parse_args()
    points = scan(limit=args.limit, force_rescan=args.force_rescan)
    print(f"已扫描 {len(points)} 个点位，结果写入 {POINTS_JSON}")


if __name__ == "__main__":
    main()
