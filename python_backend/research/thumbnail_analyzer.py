"""
Thumbnail Analyzer - phân tích thumbnail YouTube.

Phân tích cơ bản (Pillow): màu sắc, độ sáng, độ rực, dominant colors.

Phân tích NÂNG CAO (Tier 2 - 20/05, OpenCV bundled):
  - face_count: số mặt người trong thumbnail (Haar Cascade)
  - edge_density: % pixel cạnh (Canny edge detector) → 'busy' hay 'clean'
  - has_text_overlay: heuristic estimate có text overlay không (qua contour
    density vùng giữa-trên)
"""

from __future__ import annotations

from typing import Optional


# Bảng màu tham chiếu để đặt tên màu (RGB)
_COLOR_REF = {
    "Đỏ": (210, 35, 35),
    "Cam": (240, 140, 25),
    "Vàng": (245, 215, 45),
    "Lục": (45, 165, 65),
    "Lam": (45, 95, 200),
    "Xanh ngọc": (40, 180, 175),
    "Tím": (140, 55, 180),
    "Hồng": (240, 115, 170),
    "Nâu": (125, 80, 45),
    "Trắng": (244, 244, 244),
    "Đen": (22, 22, 22),
    "Xám": (128, 128, 128),
}


def _nearest_color_name(rgb: tuple) -> str:
    """Tìm tên màu gần nhất trong bảng tham chiếu."""
    r, g, b = rgb[:3]
    best, best_d = "Xám", 1e9
    for name, (rr, gg, bb) in _COLOR_REF.items():
        d = (r - rr) ** 2 + (g - gg) ** 2 + (b - bb) ** 2
        if d < best_d:
            best_d, best = d, name
    return best


def analyze_image(path) -> Optional[dict]:
    """Phân tích 1 ảnh. Trả dict {brightness, contrast, saturation,
    dominant_colors:[(name,pct),...]} hoặc None nếu lỗi."""
    try:
        from PIL import Image, ImageStat
    except Exception:
        return None
    try:
        img = Image.open(path).convert("RGB")
    except Exception:
        return None
    # Thu nhỏ để tính nhanh
    img.thumbnail((160, 160))

    # Độ sáng + tương phản (trên ảnh xám)
    gray = img.convert("L")
    st = ImageStat.Stat(gray)
    brightness = st.mean[0]            # 0-255
    contrast = st.stddev[0]            # 0-~128

    # Độ rực rỡ (saturation trung bình trên kênh S của HSV)
    hsv = img.convert("HSV")
    s_channel = hsv.split()[1]
    saturation = ImageStat.Stat(s_channel).mean[0]   # 0-255

    # Màu chủ đạo: gom về 6 màu rồi lấy top 3
    dom = []
    try:
        q = img.quantize(colors=6)
        pal = q.getpalette()
        counts = q.getcolors() or []   # list (count, palette_index)
        counts.sort(reverse=True)
        total = sum(c for c, _ in counts) or 1
        name_pct = {}
        for cnt, idx in counts[:6]:
            rgb = tuple(pal[idx * 3: idx * 3 + 3])
            name = _nearest_color_name(rgb)
            name_pct[name] = name_pct.get(name, 0) + cnt / total
        dom = sorted(name_pct.items(), key=lambda x: x[1], reverse=True)[:3]
    except Exception:
        pass

    result = {
        "brightness": brightness,
        "contrast": contrast,
        "saturation": saturation,
        "dominant_colors": dom,
    }

    # PHÂN TÍCH NÂNG CAO qua OpenCV (nếu có) - face, edge density, text overlay
    try:
        deep = _deep_analyze(path)
        if deep:
            result.update(deep)
    except Exception:
        pass

    return result


def _deep_analyze(path) -> Optional[dict]:
    """Phân tích nâng cao với OpenCV: face count, edge density, text overlay.
    Trả None nếu OpenCV không có."""
    try:
        import cv2
        import numpy as np
    except ImportError:
        return None
    try:
        img = cv2.imread(str(path))
        if img is None:
            return None
        h, w = img.shape[:2]
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

        # 1. Face count qua Haar Cascade
        face_count = 0
        try:
            cascade_path = (cv2.data.haarcascades
                            + "haarcascade_frontalface_default.xml")
            cascade = cv2.CascadeClassifier(cascade_path)
            faces = cascade.detectMultiScale(
                gray, scaleFactor=1.1, minNeighbors=5,
                minSize=(int(h * 0.05), int(h * 0.05)))
            face_count = len(faces) if faces is not None else 0
        except Exception:
            pass

        # 2. Edge density qua Canny - tỷ lệ pixel cạnh (busy/clean)
        edge_density = 0.0
        try:
            edges = cv2.Canny(gray, 100, 200)
            edge_density = float(np.count_nonzero(edges)) / float(h * w)
        except Exception:
            pass

        # 3. Text overlay heuristic - vùng giữa-trên có nhiều contour
        # nhỏ-trung bình (chữ thường có dạng box 8-40px)
        has_text = False
        try:
            top_third = gray[: h // 3, :]
            _, binary = cv2.threshold(top_third, 0, 255,
                                       cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL,
                                            cv2.CHAIN_APPROX_SIMPLE)
            text_like = 0
            for c in contours:
                x, y, cw, ch_ = cv2.boundingRect(c)
                # Contour có kích thước "text-like": cao 8-40px, ratio 0.3-3
                if 8 <= ch_ <= 40 and 8 <= cw <= 80:
                    ratio = cw / max(ch_, 1)
                    if 0.3 <= ratio <= 3.0:
                        text_like += 1
            # Nếu >5 contour text-like ở 1/3 trên → có overlay text
            has_text = text_like >= 5
        except Exception:
            pass

        return {
            "face_count": face_count,
            "edge_density": round(edge_density, 4),
            "has_text_overlay": has_text,
        }
    except Exception:
        return None


def _brightness_label(v: float) -> str:
    if v >= 170:
        return "sáng"
    if v >= 95:
        return "trung bình"
    return "tối"


def _saturation_label(v: float) -> str:
    if v >= 175:
        return "rất rực rỡ"
    if v >= 120:
        return "rực rỡ"
    if v >= 65:
        return "trung bình"
    return "nhạt màu"


def analyze_set(items: list) -> dict:
    """
    Phân tích 1 bộ thumbnail + đối chiếu nhiều view vs ít view.

    items: list dict {view_count, path, title}
    Trả dict:
      {
        "count": int,
        "avg_brightness", "avg_contrast", "avg_saturation": float,
        "brightness_label", "saturation_label": str,
        "top_colors": [(name, pct), ...],   # màu hay gặp nhất cả bộ
        "high_vs_low": { ... } hoặc None,
        "profile_text": str,   # mô tả công thức thumbnail ngách
      }
    """
    analyzed = []
    for it in items or []:
        p = it.get("path")
        if not p:
            continue
        a = analyze_image(p)
        if a:
            a["view_count"] = it.get("view_count", 0)
            a["title"] = it.get("title", "")
            analyzed.append(a)

    n = len(analyzed)
    if n == 0:
        return {"count": 0, "profile_text": "Không phân tích được ảnh nào."}

    avg_b = sum(a["brightness"] for a in analyzed) / n
    avg_c = sum(a["contrast"] for a in analyzed) / n
    avg_s = sum(a["saturation"] for a in analyzed) / n

    # Tier 2 - phân tích nâng cao: face/edge/text
    has_deep = any("face_count" in a for a in analyzed)
    avg_faces = (sum(a.get("face_count", 0) for a in analyzed) / n
                 if has_deep else None)
    avg_edge = (sum(a.get("edge_density", 0) for a in analyzed) / n
                if has_deep else None)
    pct_text = (sum(1 for a in analyzed if a.get("has_text_overlay")) / n
                if has_deep else None)

    # Màu hay gặp nhất cả bộ
    color_w = {}
    for a in analyzed:
        for name, pct in a["dominant_colors"]:
            color_w[name] = color_w.get(name, 0) + pct
    top_colors = sorted(color_w.items(), key=lambda x: x[1],
                        reverse=True)[:4]
    # Chuẩn hoá % theo tổng
    tot_w = sum(w for _, w in top_colors) or 1
    top_colors = [(name, w / tot_w) for name, w in top_colors]

    # Đối chiếu nhiều view vs ít view (chia 3, lấy nhóm trên & dưới)
    high_vs_low = None
    if n >= 6:
        ordered = sorted(analyzed, key=lambda a: a["view_count"],
                         reverse=True)
        third = max(1, n // 3)
        high = ordered[:third]
        low = ordered[-third:]
        hb = sum(a["brightness"] for a in high) / len(high)
        lb = sum(a["brightness"] for a in low) / len(low)
        hs = sum(a["saturation"] for a in high) / len(high)
        ls = sum(a["saturation"] for a in low) / len(low)
        b_diff = (hb - lb) / max(lb, 1) * 100
        s_diff = (hs - ls) / max(ls, 1) * 100
        parts = []
        if abs(b_diff) >= 8:
            parts.append(f"{'sáng hơn' if b_diff > 0 else 'tối hơn'} "
                         f"{abs(b_diff):.0f}%")
        if abs(s_diff) >= 8:
            parts.append(f"{'rực rỡ hơn' if s_diff > 0 else 'nhạt hơn'} "
                         f"{abs(s_diff):.0f}%")
        if parts:
            insight = ("Thumbnail video NHIỀU lượt xem có xu hướng "
                       + " và ".join(parts) + " so với video ít lượt xem.")
        else:
            insight = ("Thumbnail video nhiều/ít lượt xem không khác "
                       "biệt rõ về màu sắc — yếu tố khác (bố cục, chủ thể) "
                       "quyết định nhiều hơn.")
        high_vs_low = {
            "high_brightness": hb, "low_brightness": lb,
            "high_saturation": hs, "low_saturation": ls,
            "brightness_diff_pct": b_diff,
            "saturation_diff_pct": s_diff,
            "insight": insight,
        }

    color_str = ", ".join(f"{name} ({pct*100:.0f}%)"
                          for name, pct in top_colors)
    profile_text = (
        f"Công thức thumbnail (từ {n} video): "
        f"độ sáng {_brightness_label(avg_b)} ({avg_b:.0f}/255), "
        f"{_saturation_label(avg_s)} ({avg_s:.0f}/255). "
        f"Màu chủ đạo: {color_str}."
    )

    out = {
        "count": n,
        "avg_brightness": avg_b,
        "avg_contrast": avg_c,
        "avg_saturation": avg_s,
        "brightness_label": _brightness_label(avg_b),
        "saturation_label": _saturation_label(avg_s),
        "top_colors": top_colors,
        "high_vs_low": high_vs_low,
        "profile_text": profile_text,
    }
    if has_deep:
        out["avg_faces"] = round(avg_faces, 2)
        out["avg_edge_density"] = round(avg_edge, 4)
        out["pct_text_overlay"] = round(pct_text, 2)
    return out


def compare_channel_vs_niche(channel: dict, niche: dict) -> dict:
    """So sánh profile thumbnail KÊNH với profile thumbnail NGÁCH.

    channel, niche: kết quả analyze_set.
    Trả dict {brightness_diff_pct, saturation_diff_pct, contrast_diff_pct,
              observations:[...], channel, niche} hoặc None.
    """
    if not channel or not channel.get("count"):
        return None
    if not niche or not niche.get("count"):
        return None

    cb, nb = channel["avg_brightness"], niche["avg_brightness"]
    cs, ns = channel["avg_saturation"], niche["avg_saturation"]
    cc, nc = channel["avg_contrast"], niche["avg_contrast"]
    b_diff = (cb - nb) / max(nb, 1) * 100
    s_diff = (cs - ns) / max(ns, 1) * 100
    c_diff = (cc - nc) / max(nc, 1) * 100

    obs = []
    if abs(b_diff) >= 8:
        obs.append(
            f"Độ sáng: thumbnail kênh "
            f"{'SÁNG HƠN' if b_diff > 0 else 'TỐI HƠN'} ngách "
            f"{abs(b_diff):.0f}%")
    else:
        obs.append("Độ sáng: tương đương ngách")
    if abs(s_diff) >= 8:
        obs.append(
            f"Độ rực: thumbnail kênh "
            f"{'RỰC HƠN' if s_diff > 0 else 'NHẠT HƠN'} ngách "
            f"{abs(s_diff):.0f}%")
    else:
        obs.append("Độ rực: tương đương ngách")
    if abs(c_diff) >= 12:
        obs.append(
            f"Độ tương phản: kênh "
            f"{'CAO HƠN' if c_diff > 0 else 'THẤP HƠN'} ngách "
            f"{abs(c_diff):.0f}%")

    # So màu chủ đạo
    ch_colors = [name for name, _ in channel.get("top_colors", [])]
    ni_colors = [name for name, _ in niche.get("top_colors", [])]
    missing = [c for c in ni_colors if c not in ch_colors]
    if missing:
        obs.append(
            "Màu ngách hay dùng mà kênh ít dùng: "
            + ", ".join(missing))

    return {
        "brightness_diff_pct": b_diff,
        "saturation_diff_pct": s_diff,
        "contrast_diff_pct": c_diff,
        "observations": obs,
        "channel": {
            "brightness": cb, "saturation": cs, "contrast": cc,
            "colors": channel.get("top_colors", []),
            "count": channel.get("count", 0),
        },
        "niche": {
            "brightness": nb, "saturation": ns, "contrast": nc,
            "colors": niche.get("top_colors", []),
            "count": niche.get("count", 0),
        },
    }
