from __future__ import annotations

import re

from common import PUBLIC_DIR, ensure_dirs, html_escape, load_points, parse_common_args


CSS = """
:root{color-scheme:light;--bg:#f6f4ed;--paper:#fffdf7;--ink:#203126;--muted:#6d7b70;--green:#47765b;--gold:#b58a45;--line:rgba(42,64,49,.12);--shadow:0 18px 42px rgba(47,68,54,.14)}
*{box-sizing:border-box}body{margin:0;background:linear-gradient(180deg,#edf5ed 0,#f8f3e8 42%,#f6f4ed 100%);font-family:-apple-system,BlinkMacSystemFont,"PingFang SC","Noto Sans SC","Microsoft YaHei",sans-serif;color:var(--ink);letter-spacing:0}
a{color:inherit;text-decoration:none}.shell{max-width:760px;margin:0 auto;min-height:100vh;background:rgba(255,253,247,.78)}
.hero{position:relative;min-height:330px;overflow:hidden;background:#dce8dc}.hero img{width:100%;height:390px;object-fit:cover;display:block}.hero:after{content:"";position:absolute;inset:0;background:linear-gradient(180deg,rgba(14,42,25,.03) 0,rgba(14,42,25,.08) 45%,rgba(246,244,237,.94) 100%)}
.content{position:relative;margin-top:-56px;padding:0 18px 28px}.title-block{padding:0 2px 14px}.eyebrow{font-size:15px;color:var(--green);font-weight:700;margin:0 0 8px}.title{font-size:32px;line-height:1.18;margin:0;font-weight:800;color:#18291f}
.intro-verse{position:relative;margin:2px 0 14px;padding:18px;background:linear-gradient(135deg,rgba(255,253,247,.96),rgba(250,244,229,.94));border:1px solid rgba(181,138,69,.28);border-left:4px solid var(--gold);border-radius:8px;box-shadow:0 14px 32px rgba(91,72,41,.12)}.intro-verse:before{content:"“";position:absolute;top:-12px;left:12px;color:rgba(181,138,69,.23);font-size:74px;font-family:Georgia,serif;line-height:1}.intro-verse p{position:relative;margin:0;color:#2a3c2f;font-size:22px;line-height:1.65;font-weight:780}
.audio-card,.text-card,.index-card{background:rgba(255,253,247,.94);border:1px solid var(--line);border-radius:8px;box-shadow:var(--shadow)}.audio-card{padding:16px;margin:8px 0 16px}.audio-title{display:flex;align-items:center;gap:10px;font-weight:800;font-size:18px;margin:0 0 12px}.play-dot{width:38px;height:38px;border-radius:50%;display:grid;place-items:center;background:var(--green);color:#fff;box-shadow:0 8px 22px rgba(71,118,91,.24)}audio{width:100%;display:block}
.text-card{padding:18px 18px 20px}.article-kicker{display:flex;align-items:center;gap:8px;margin:0 0 12px;color:var(--green);font-size:15px;font-weight:850}.article-kicker:before{content:"";width:22px;height:2px;background:var(--gold);border-radius:2px}.text-card p{font-size:18px;line-height:1.88;margin:0;color:#26382d}.text-card p+p{margin-top:14px;padding-top:14px;border-top:1px solid rgba(42,64,49,.1)}.text-card .lead{margin-bottom:2px;padding:12px 13px;border:0;border-radius:8px;background:rgba(71,118,91,.08);color:#244532;font-size:19px;font-weight:780}.nav{display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-top:16px}.nav a,.home-link{height:48px;border-radius:8px;border:1px solid var(--line);background:#fffdf8;display:flex;align-items:center;justify-content:center;font-size:16px;font-weight:750;color:#315640}.home-link{margin-top:10px;width:100%}
.site-head{padding:22px 18px 10px}.site-title{font-size:30px;line-height:1.18;margin:0 0 8px}.site-sub{margin:0;color:var(--muted);font-size:16px;line-height:1.6}.grid{display:grid;gap:12px;padding:8px 18px 28px}.index-card{display:grid;grid-template-columns:112px 1fr;min-height:112px;overflow:hidden}.index-card img{width:112px;height:112px;object-fit:cover}.index-copy{padding:14px 14px 12px;display:flex;flex-direction:column;justify-content:center}.index-copy h2{font-size:20px;line-height:1.25;margin:0 0 8px}.index-copy p{font-size:14px;color:var(--muted);line-height:1.5;margin:0}.footer{padding:18px;color:var(--muted);font-size:13px;text-align:center}
@media (max-width:420px){.hero img{height:350px}.title{font-size:29px}.intro-verse{padding:16px}.intro-verse p{font-size:20px}.text-card p{font-size:17px}.text-card .lead{font-size:18px}.content{padding-left:14px;padding-right:14px}.index-card{grid-template-columns:104px 1fr}.index-card img{width:104px;height:112px}}
"""


def image_info(point: dict) -> dict:
    base = f"/assets/images/{point['point_key']}"
    point_dir = PUBLIC_DIR / "assets" / "images" / point["point_key"]
    return {
        "cover_webp": f"{base}/cover.webp" if (point_dir / "cover.webp").exists() else "",
        "cover_jpg": f"{base}/cover.jpg" if (point_dir / "cover.jpg").exists() else "",
        "thumb_webp": f"{base}/thumb.webp" if (point_dir / "thumb.webp").exists() else "",
        "thumb_jpg": f"{base}/thumb.jpg" if (point_dir / "thumb.jpg").exists() else "",
    }


def split_intro_verse(text: str) -> tuple[str, str]:
    text = text or ""
    match = re.match(r"^\s*[“\"]([^”\"]{8,80})[”\"]\s*(.*)$", text, flags=re.S)
    if not match:
        return "", text
    verse = match.group(1).strip()
    rest = match.group(2).lstrip()
    return verse, rest


def split_long_paragraph(paragraph: str, max_chars: int = 170) -> list[str]:
    if len(paragraph) <= max_chars:
        return [paragraph]
    sentences = [s.strip() for s in re.split(r"(?<=[。！？；])", paragraph) if s.strip()]
    chunks: list[str] = []
    current = ""
    for sentence in sentences:
        if current and len(current) + len(sentence) > max_chars:
            chunks.append(current)
            current = sentence
        else:
            current += sentence
    if current:
        chunks.append(current)
    return chunks or [paragraph]


def body_text_html(text: str) -> str:
    raw_parts = [p.strip() for p in re.split(r"\n{1,}", text or "") if p.strip()]
    parts: list[str] = []
    for part in raw_parts:
        parts.extend(split_long_paragraph(part))
    html_parts = ['<div class="article-kicker">点位介绍</div>']
    for idx, part in enumerate(parts):
        class_attr = ' class="lead"' if idx == 0 and len(part) <= 40 else ""
        html_parts.append(f"<p{class_attr}>{html_escape(part)}</p>")
    return "\n".join(html_parts)


def build_point_page(point: dict, prev_point: dict | None, next_point: dict | None) -> str:
    info = image_info(point)
    cover = info["cover_webp"] or info["cover_jpg"]
    prev_html = f'<a href="/p/{prev_point["point_key"]}/">上一处</a>' if prev_point else '<a href="/">导览首页</a>'
    next_html = f'<a href="/p/{next_point["point_key"]}/">下一处</a>' if next_point else '<a href="/">导览首页</a>'
    intro_verse, body_text = split_intro_verse(point.get("clean_text", ""))
    intro_html = f'<aside class="intro-verse"><p>{html_escape(intro_verse)}</p></aside>' if intro_verse else ""
    return f"""<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover"><title>{html_escape(point['display_name'])}</title><link rel="stylesheet" href="/assets/css/site.css"></head>
<body><main class="shell">
<section class="hero"><picture><source srcset="{info['cover_webp']}" type="image/webp"><img src="{cover}" alt="{html_escape(point['display_name'])}" loading="eager"></picture></section>
<section class="content"><div class="title-block"><p class="eyebrow">园区语音导览</p><h1 class="title">{html_escape(point['display_name'])}</h1></div>
{intro_html}
<div class="audio-card"><p class="audio-title"><span class="play-dot">▶</span><span>语音讲解</span></p><audio controls preload="metadata" src="/assets/audio/{point['point_key']}.mp3"></audio></div>
<article class="text-card">{body_text_html(body_text)}</article>
<div class="nav">{prev_html}{next_html}</div><a class="home-link" href="/">返回导览首页</a></section><footer class="footer">欢迎继续游览</footer></main></body></html>"""


def build_index(points: list[dict]) -> str:
    cards = []
    for point in points:
        info = image_info(point)
        thumb = info["thumb_webp"] or info["cover_webp"] or info["cover_jpg"]
        summary = (point.get("clean_text", "").replace("\n", "")[:54] + "……") if point.get("clean_text") else "点击收听讲解"
        cards.append(
            f"""<a class="index-card" href="/p/{point['point_key']}/"><picture><source srcset="{info['thumb_webp']}" type="image/webp"><img src="{thumb}" alt="{html_escape(point['display_name'])}" loading="lazy"></picture><div class="index-copy"><h2>{html_escape(point['display_name'])}</h2><p>{html_escape(summary)}</p></div></a>"""
        )
    return f"""<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>园区语音导览</title><link rel="stylesheet" href="/assets/css/site.css"></head><body><main class="shell"><header class="site-head"><h1 class="site-title">园区语音导览</h1><p class="site-sub">选择点位，收听温和清晰的 AI 语音讲解。</p></header><section class="grid">{''.join(cards)}</section><footer class="footer">扫码即可收听</footer></main></body></html>"""


def main() -> None:
    parser = parse_common_args("生成静态网页")
    args = parser.parse_args()
    ensure_dirs()
    points = load_points(limit=args.limit, point_key=args.point)
    if not points:
        raise SystemExit("没有可生成的点位，请先扫描资料")
    (PUBLIC_DIR / "assets" / "css" / "site.css").write_text(CSS, encoding="utf-8")
    all_points = points
    for idx, point in enumerate(all_points):
        prev_point = all_points[idx - 1] if idx > 0 else None
        next_point = all_points[idx + 1] if idx < len(all_points) - 1 else None
        page_dir = PUBLIC_DIR / "p" / point["point_key"]
        page_dir.mkdir(parents=True, exist_ok=True)
        (page_dir / "index.html").write_text(build_point_page(point, prev_point, next_point), encoding="utf-8")
    (PUBLIC_DIR / "index.html").write_text(build_index(all_points), encoding="utf-8")
    print(f"已生成网页：{PUBLIC_DIR}")


if __name__ == "__main__":
    main()
