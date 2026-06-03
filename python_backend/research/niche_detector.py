# -*- coding: utf-8 -*-
"""Phát hiện NGÁCH (niche) của 1 watchlist + cung cấp guidance per-niche
cho AI prompt. Khác ngách có patterns thắng khác nhau → AI cần guidance
cụ thể để đề xuất ý tưởng video phù hợp.

Hàm chính:
  detect_niche(channels_data) → str (key niche)
  get_niche_guidance(niche_key) → str (đoạn text inject vào prompt AI)
"""
from __future__ import annotations

# Pattern khớp từ khoá / tiêu đề để detect ngách
_NICHE_PATTERNS = {
    "toy_unboxing": [
        "barbie", "doll", "unbox", "toy", "playset", "kitchen",
        "pinkfong", "satisfying", "miniature",
    ],
    "lego_animation": [
        "lego", "brick", "ninja", "ninjago", "minifigure",
        "stop motion", "brickfilm",
    ],
    "asmr_sand_slime": [
        "kinetic sand", "slime", "asmr satisfying", "rainbow slime",
        "magic sand", "satisfying video", "no talking",
    ],
    "car_crush_experiment": [
        "car crush", "crushing", "experiment test", "crunchy soft",
        "vs car", "mentos", "soda",
    ],
    "horror_stories": [
        "horror stor", "scary stor", "true scary", "haunted",
        "ghost stor", "creepy", "nightmare", "analog horror",
        "backrooms",
    ],
    "diy_mini_tractor": [
        "mini tractor", "drilling machine", "irrigation",
        "near crash", "disc harrow", "diy mini",
    ],
    "construction_vehicle": [
        "construction vehicle", "rescue truck", "excavator",
        "police car", "bibo toy", "jcb",
    ],
    "numberblocks_slime": [
        "numberblocks", "number a", "bonbon", "super bon",
        "rainbow paw patrol", "cocomelon slime",
    ],
    "paper_doll_glow": [
        "paper diy", "paper doll", "glow up", "kpop demon",
        "huntrix", "saja boys", "rumi", "mira zoey", "fashion paper",
        "couple glow", "dress up paper",
    ],
}


def detect_niche(channels_data: list) -> str:
    """Phát hiện niche key từ keywords + video titles toàn watchlist.

    channels_data: list dict có 'keywords' + 'videos' (xem core/insights_extra).
    Trả key niche (vd 'toy_unboxing') hoặc 'generic'.
    """
    text_pool = []
    for ch in channels_data:
        for kw in ch.get("keywords", []):
            text_pool.append(kw.lower())
        for v in ch.get("videos", []):
            title = v.get("title", "")
            if title:
                text_pool.append(title.lower())
    if not text_pool:
        return "generic"

    full_text = " ".join(text_pool)
    scores = {}
    for niche, patterns in _NICHE_PATTERNS.items():
        score = sum(full_text.count(p) for p in patterns)
        scores[niche] = score

    best_niche = max(scores, key=scores.get)
    if scores[best_niche] < 3:
        return "generic"
    return best_niche


_GUIDANCE = {
    "toy_unboxing": """## HƯỚNG DẪN PER-NGÁCH: TOY UNBOXING (Barbie/Pinkfong)
Khi đề xuất ý tưởng video cho ngách này, BẮT BUỘC tham khảo:
- ĐỘ DÀI SWEET SPOT: 8-13 phút (KHÔNG dưới 5 phút - thuật toán không đủ watch time)
- FORMAT TIÊU ĐỀ MẪU: "[N] Minutes Satisfying with Unboxing [Brand] [Playset]"
- PHỤ KIỆN HOT: Pinkfong Ambulance, Doctor Toys, Kitchen Playset,
  Wedding Castle, Pink Bedroom, Family Playset
- HÌNH MẪU 2026: My Toys Unboxing top 1,28M view "18 Minutes Doctor Toys
  Ambulance" 18 phút. Superstar Unboxing 71 subs có top 3,5M view 4 phút
  (bằng chứng subs nhỏ vẫn ăn nếu content đúng).
- HOOK 10S: Result First (show kết quả unbox cuối trước) hoặc Curiosity Gap
  (show 1 mảnh playset bí ẩn trước khi unbox)
- THUMBNAIL: layout "Face + Object" (50/50), pink dominant, child face
  emotion (surprise/joy), thumbnail có 3-5 phụ kiện đa dạng
- RETENTION TIP: pattern interrupt mỗi 60-90s bằng zoom + sound effect khi
  unbox phụ kiện mới
- TRÁNH: video dưới 5 phút, lặp tiêu đề y hệt nhau, playset đơn lẻ không
  có Mystery/Surprise element""",
    "lego_animation": """## HƯỚNG DẪN PER-NGÁCH: LEGO ANIMATION
Khi đề xuất ý tưởng video cho ngách này, BẮT BUỘC tham khảo:
- FORMAT TIÊU ĐỀ MẪU: "LEGO [Vehicle] [Saves/Rescues] [Animal/Object] from [Danger]"
- CỐT TRUYỆN: Rescue mission là yếu tố ăn view nhất
- NHÂN VẬT CỐ ĐỊNH: LEGO Ninja (xây nhận diện series)
- VẬT THỂ HOT: Excavator, Drill Truck, Crane, Police Car, Fire Truck
- ANIMAL: Pig, Fish, Crocodile, Snake, Tiger (gây tò mò)
- HOOK 10S: Problem Punch (show animal/object đang gặp nguy hiểm ngay 0-3s)
- THUMBNAIL: layout "Object + Face" (LEGO Ninja face emotion surprise +
  vehicle action), background contrast cao (đỏ nguy hiểm vs xanh an toàn)
- RETENTION TIP: stake escalation - vấn đề càng lúc càng to (animal nhỏ →
  animal lớn → multiple animals)
- TRÁNH: video build thuần (không cốt truyện), animation chậm, thiếu
  sound effect""",
    "asmr_sand_slime": """## HƯỚNG DẪN PER-NGÁCH: ASMR SAND / SLIME
Khi đề xuất ý tưởng video cho ngách này, BẮT BUỘC tham khảo:
- FORMAT THẮNG: "Bathtub Mixing" + "Rainbow Glitter" + "No Talking"
- ĐỘ DÀI: 3-10 phút (Sand ASMR ngắn) — NHƯNG ASMR Slime Pearl 72K subs
  có top 1,6M view 58 phút "Rainbow Foot Nail Polish Bathtub" → format
  DÀI 30-60 phút cũng RẤT ăn nếu content cuốn
- COMPILATION format: Sand Tagious 7 subs (!) top 405K view "Best of 2025
  Compilation" 10 phút → kênh nào cũng nên thử format này
- COMBO: kết hợp NHIỀU yếu tố hot trong 1 video (slime + sprunki +
  lollipop + labubu + paint mixing - tăng visual stimulation)
- KEYWORD MÀU: Rainbow, Glossy, Glitter, Color trong mọi tiêu đề
- HOOK 10S: Result First (show bathtub đầy đủ thành phẩm trước) hoặc
  Curiosity Gap (show 1 phần slime kỳ lạ ngay đầu)
- THUMBNAIL: layout "Object" + chữ "Bathtub Mixing" lớn, rainbow gradient
  background, KHÔNG cần face
- RETENTION TIP: đổi shot angle mỗi 15-30s (top-down → side → close-up)
- TRÁNH: 1 format lặp đi lặp lại nhiều video, video dưới 3 phút""",
    "car_crush_experiment": """## HƯỚNG DẪN PER-NGÁCH: CAR CRUSH EXPERIMENT
Khi đề xuất ý tưởng video cho ngách này, BẮT BUỘC tham khảo:
- CỤM TRIỆU VIEW: SODA + Mentos + Car (Coca-Cola, Fanta, Sprite, Mtn Dew)
- VẬT THỂ HOT: Balloons, Orbeez, Jelly Beads, Marble Beads, Foam, Clay Eggs
- FORMAT TIÊU ĐỀ: "Car Crush [Object] vs Car | Crushing Crunchy & Soft Things"
- HÌNH MẪU 2026: HaerteTest (19,5M subs) - chủ yếu Soda Balloon + Mentos.
  Crunchy EX 353K subs có video triệu view nhờ chủ đề Soda. Soft & Crunchy
  EX chỉ 1.1K subs cũng đạt 5K view với Coca + Fanta + Mirinda Mentos.
- NHÂN BIẾN THỂ: học HaerteTest - mỗi chủ đề tốt làm 5-10 phiên bản
- HOOK 10S: Result First (show kết quả phun trào màu rực rỡ trước)
- THUMBNAIL: layout "Object" với explosion/splash visual mạnh, KHÔNG cần
  face, color contrast cực cao (red/yellow soda vs black car)
- RETENTION TIP: build-up tension trước khi crush (countdown 3-2-1 hoặc
  slow-mo close-up)
- TƯƠNG TÁC: tỷ lệ bình luận quan trọng - hỏi trong description
  "What should we crush next?"
- TRÁNH: chỉ dùng 1 loại object, video không có "moment crush" rõ""",
    "horror_stories": """## HƯỚNG DẪN PER-NGÁCH: HORROR STORIES / RADIO
Khi đề xuất ý tưởng video cho ngách này, BẮT BUỘC tham khảo:
- FORMAT TRIỆU VIEW: "N TRUE [Setting] Scary Stories" (Mr. Nightmare style)
- BỐI CẢNH HOT 2026: Night Shift, Deep Woods, Craigslist, Hospital,
  Apartment, OnlyFans, AIRBNB, 7-Eleven, Padel, Driving At Night,
  Conspiracy Killers, Teen Girl Alone, Bowling At Night, Countryside,
  Rainy Night, Isolated Mansion (càng cụ thể-ngách-nhỏ càng ăn)
- HÌNH MẪU 2026: Mr. Nightmare 7,09M subs top 1,6M "Deep Woods" 38 phút.
  Dark Asia with Megan 1,16M subs top 749K view 20 phút (kể chuyện thật
  châu Á). Martin Animations 334 subs có top 258K view 27 phút (subs nhỏ
  vẫn ăn được nếu chủ đề/format đúng).
- COMPILATION format LONG-FORM 60-180 PHÚT: MỎ VÀNG 2026. Whispered
  Diaries 265K subs top 365K view "3+ Hours Dead of Night" 191 phút.
  MJV Animations 584K top 311K view 149 phút. Broccoli Animations 213
  subs (!) top 224K view 129 phút compilation.
- SUB-GENRE NÓNG: Analog Horror, Backrooms Found Footage
- HOOK 10S: Story Hook (bắt đầu in media res - giữa câu chuyện đang căng)
  hoặc Curiosity Gap (1 fact gây sốc về câu chuyện)
- THUMBNAIL: layout "Face" với expression fear/concern, background tối
  đen 70%+, 1 điểm nhấn ánh đèn đỏ, chữ "TRUE" hoặc "[N] Stories" to
- RETENTION TIP: chia 5-10 phút/story, transition card giữa các story
- TRÁNH: copy narrator hoặc story từ kênh khác (bị takedown), video
  không có visual layer (chỉ audio + static image)""",
    "diy_mini_tractor": """## HƯỚNG DẪN PER-NGÁCH: DIY MINI TRACTOR
Khi đề xuất ý tưởng video cho ngách này, BẮT BUỘC tham khảo:
- CỤM ĂN: Drilling Machine, Irrigation/Water Rescue, Disc Harrow, Bricks
  Construction (cụm Bricks mới phát hiện 2026)
- HÌNH MẪU 2026: Top Mini Gear 2M subs top 50,7M view "Real Concrete
  Bridge" 16 phút. Sano Creator 4,59M subs top 25,8M view "Mini Bricks
  House" 19 phút. Tech Creators 1,27M subs top 4,2M view "Mini JCB 3dx +
  tractor combo" 26 phút. Tiny Farming 305K subs top 425K view "Modern
  Fireproof Fish House" 26 phút.
- CỐT TRUYỆN: "Near Crash", "Rescue Mission", "Disaster", "Snake Attack",
  "Storm Damage", "Ground Collapse", "Heavy Rain Destroyed Road"
  (Sun Farming 3M subs có 237K view 0d hôm nay với chủ đề này)
- TIÊU ĐỀ: "DIY Mini Tractor [Action] [Drama Setting]"
- ĐỘ DÀI SWEET SPOT: 8-15 phút bình thường, NÊN TEST format DÀI 18-30
  phút (đối thủ lớn ăn ở format này)
- TỪ KHOÁ HOT: Hard Soil, Drought Rescue, Underground, Tunnel, Cement,
  Bricks, JCB Combo, Storm
- HOOK 10S: Problem Punch (show disaster đang xảy ra) hoặc Result First
  (show vehicle hoàn thành rescue cuối)
- THUMBNAIL: layout "Object" (Tractor + Disaster element), no-face OK,
  color: brown/red drama background
- RETENTION TIP: pattern interrupt với close-up shot mechanical work
- TRÁNH: video build thuần không drama, video dưới 5 phút""",
    "construction_vehicle": """## HƯỚNG DẪN PER-NGÁCH: CONSTRUCTION VEHICLE RESCUE
Khi đề xuất ý tưởng video cho ngách này, BẮT BUỘC tham khảo:
- FORMAT VIRAL: "Construction Vehicle Falls into Hole | Rescue [Vehicle]"
- NHÂN VẬT: Excavator, Crane Truck, Mixer Truck, Police Car, Dump Truck,
  Roller, Bulldozer
- CỐT TRUYỆN: Rescue Mission ALWAYS - không có video tĩnh
- BIBO TOYS pattern: top video 49M view dạng "Vehicle falls + Rescue"
- KHÁN GIẢ: trẻ em → đơn giản, nhiều màu, không thoại phức tạp
- HOOK 10S: Problem Punch (vehicle đang gặp nguy hiểm 0-5s)
- THUMBNAIL: layout "Object" với multiple vehicles, color cực rực rỡ
  (rainbow + bright), KHÔNG cần face, character cartoon
- RETENTION TIP: rescue mission gồm 3 stage (problem → attempt 1 fail →
  attempt 2 success) — pattern này keep retention cao
- TRÁNH: video không có hành động/rescue, narration phức tạp""",
    "numberblocks_slime": """## HƯỚNG DẪN PER-NGÁCH: NUMBERBLOCKS / CHARACTER SLIME
Khi đề xuất ý tưởng video cho ngách này, BẮT BUỘC tham khảo:
- ĐỊNH VỊ: chọn 1 vũ trụ nhân vật (Numberblocks / Paw Patrol /
  Cocomelon / Bluey) và đầu tư sâu
- FORMAT: Slime Bathtub Mixing + Rainbow + Character
- TIÊU ĐỀ: "Satisfying ASMR | Rainbow [Color] [Character] Slime Bathtub Mixing"
- ĐỘ DÀI: 30+ phút (Number A 154K subs top 53K view; Number B 59K subs
  top 21K view; cả 2 đều 30 phút)
- HÌNH MẪU 2026: Bonbon 552K subs top 109K+ view Numberblocks. Super Bon
  111K subs top 350K view nhờ format "TÌM NHÂN VẬT GIẤU TRONG SLIME/TRỨNG/
  VALI" — đây là format ăn nhất ngách 2026, các kênh khác nên copy.
  Rainbow Egg 459K dẫn Paw Patrol cluster. COCO SLIME dẫn Cocomelon.
- CLAY EGGS LAI NUMBERBLOCKS: cơ hội còn trống - chưa kênh nào làm. Number
  B (59K subs) làm Clay Eggs, Super Bon làm Numberblocks. Lai 2 = mỏ vàng.
- SEO 90+ là điều kiện sống còn (Number SKC/Slime Sau SEO 19-21 chết view
  dù có hàng trăm nghìn subs)
- HOOK 10S: Curiosity Gap (show egg/slime mystery sẽ chứa nhân vật gì)
  hoặc Result First (show character emerged cuối trước)
- THUMBNAIL: layout "Object" với character + slime/egg, rainbow color
  dominant, chữ tên character to (NUMBERBLOCK 1, PAW PATROL...)
- RETENTION TIP: reveal character mỗi 3-5 phút (multiple reveals trong 1
  video 30 phút)
- TRÁNH: dàn trải nhiều vũ trụ nhân vật, video <20 phút""",
    "paper_doll_glow": """## HƯỚNG DẪN PER-NGÁCH: PAPER DOLL / KPOP GLOW UP
Khi đề xuất ý tưởng video cho ngách này, BẮT BUỘC tham khảo:
- FORMAT VIRAL 2026: "[A] vs [B] vs [C]" 3-PHE đối đầu (Poor vs Rich vs
  Giga Rich, Rainbow vs Black vs Gold, Nerd vs Popular vs Diamond)
- NARRATIVE ARC trong tiêu đề: "From Nerd To Popular", "Glow Up From
  Poor", "Sick Girl vs Diamond Princess"
- ĐỘ DÀI SWEET SPOT 2026: 25-30 phút (KHÔNG dưới 20 phút). Đối thủ ăn
  triệu view đều ở 17-60 phút.
- HÌNH MẪU 2026: Wow Princess Toys 134K subs top 11,5 TRIỆU view
  "Barbie Princess Pink Kitchen" 18 phút. Lyra Dolls 119K subs top 1,99
  TRIỆU view "K-Pop Demon Hunters" 27 phút. Eira Doll CHỈ 223 SUBS có
  top 1,94M view (29 phút). BaBaBop 140 subs top 289K view 60 phút —
  CHỨNG MINH kênh siêu nhỏ vẫn ăn được nếu format đúng.
- KPOP DEMON HUNTERS: nhân vật Rumi, Mira, Zoey, Jinu, Huntrix, Saja Boys
  đang trending nhất 2026
- HOOK 10S: Result First (show 3 character glowed up cuối trước) hoặc
  Curiosity Gap (show 1 character mystery)
- THUMBNAIL: layout "Versus" 3 split với 3 nhân vật mỗi phe, chữ "VS"
  RẤT TO giữa, background mỗi phe contrast đối lập (đen/trắng/vàng)
- RETENTION TIP: cấu trúc episode: intro (poor) → glow up 1 (medium) →
  reveal glow up final (rich) — pacing 3 act như phim
- TRÁNH: video dưới 20 phút, thumbnail couple đơn giản không 3 phe""",
    "generic": "",
}


def get_niche_guidance(niche_key: str) -> str:
    """Trả đoạn text guidance để inject vào prompt AI (rỗng nếu generic)."""
    return _GUIDANCE.get(niche_key, "").strip()
