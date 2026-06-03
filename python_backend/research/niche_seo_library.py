# -*- coding: utf-8 -*-
"""
Niche SEO Library — knowledge base chi tiết cho 9 niche.

Mỗi niche có ~14 mảng SEO + Production specifics. Tab Inside × SEO Synthesis
sẽ tra cứu library này theo niche detected từ niche_detector.py.

Khi user thay đổi nội dung guidance, sửa CHỈ ở file này — không phải sửa code.

Module này KHÔNG phụ thuộc data — chỉ là constants. Dùng được offline.
"""
from __future__ import annotations
from typing import Dict, Any


# ============================================================
# NICHE LIBRARY — 9 niche
# ============================================================

NICHE_SEO_DATA: Dict[str, Dict[str, Any]] = {

    "toy_unboxing": {
        "name": "Toy Unboxing & Review (kid playset)",
        "title": {
            "formula_best": ("[X Minutes] [Satisfying/ASMR] [Unboxing/Review] "
                             "[Brand/Product] [Playset/Collection] | "
                             "[Review Toys/Play Toys ASMR]"),
            "examples": [
                "12 Minutes Satisfying Unboxing Pinkfong Doctor Toys Playset | Review Toys ASMR",
                "20 Minutes Unboxing Disney Frozen Collection Playset ASMR | Play Toys",
            ],
            "keyword_position": "Minute number ở từ thứ 1; niche keyword trong 25 ký tự đầu",
            "optimal_length": (70, 95),
            "clickbait_avoid": ["ULTIMATE", "INSANE", "SHOCKED", "OMG",
                                "MUST WATCH", "GONE WRONG"],
        },
        "description": {
            "min_words": 200,
            "template": (
                "🎬 [Một câu mô tả hook — what's in this video]\n\n"
                "⏱️ Timestamps:\n"
                "00:00 - Intro & Unboxing\n"
                "XX:XX - [Toy 1 reveal]\n"
                "XX:XX - [Toy 2 reveal]\n"
                "XX:XX - Playtime & Sound\n"
                "XX:XX - Final Compilation\n\n"
                "🔔 Subscribe daily satisfying toy unboxing video!\n\n"
                "📦 Toys featured in this video:\n"
                "- [Brand 1] [Product]\n"
                "- [Brand 2] [Product]\n\n"
                "💡 More playlists:\n"
                "[Playlist 1] - [link]\n"
                "[Playlist 2] - [link]\n\n"
                "📱 Social:\n"
                "Instagram: @[channel]\n"
                "Facebook: [link]\n\n"
                "#unboxing #satisfying #toys #playset #asmr #review"),
            "keyword_distribution": ("Primary keyword trong 25 từ đầu + lặp "
                                      "3-5 lần toàn bài + 5-6 hashtag cuối"),
            "hashtags_count": (5, 8),
        },
        "tags": {
            "count_range": (12, 15),
            "broad": ["unboxing", "satisfying", "asmr toys", "toys", "review toys",
                      "play toys", "kid friendly"],
            "specific": ["playset toys", "kitchen playset", "doll playset",
                         "doctor playset", "miniature toys", "review toys asmr"],
            "question": ["how to play with toys", "best toy unboxing channel"],
            "branded_template": "[channel name] + [brand name]",
            "trending_template": "satisfying [year] + viral toy [year]",
        },
        "thumbnail": {
            "primary_layout": "Product-Hero",
            "layouts": {
                "Product-Hero": ("Toy chiếm 60-70%, background mờ pastel, "
                                  "text 3-5 từ góc trên/dưới"),
                "Face-Reveal": ("Mặt em bé/người chiếm 30%, toy 40%, "
                                "text 'Look!' / 'Wow!' / 'New'"),
                "Split-Compare": "Trước/sau, before/after toys",
            },
            "color_palette": "Pastel pink + yellow + light blue (target girl 4-10y + mom 25-34)",
            "text_words_max": 4,
            "text_size_min_px": 60,
            "face_size_pct": (20, 40),
        },
        "hook_10s": [
            "0-2s: Close-up product trong tay (KHÔNG logo intro, KHÔNG 'Hello guys')",
            "2-5s: Tay mở hộp/reveal toy đầu tiên",
            "5-8s: Satisfying sound (ASMR ASMR) + mặt em bé/người react",
            "8-10s: Text overlay '15 Minutes Satisfying' + ASMR sound layer",
        ],
        "pacing": {
            "cuts_per_min": (20, 30),
            "b_roll_pct": (30, 50),
            "pattern_interrupt_sec": 60,
        },
        "retention_techniques": [
            "Reveal escalation: toy nhỏ → to → đẹp nhất ở cuối",
            "Sound layering: ASMR sound liên tục (không gap)",
            "Pattern interrupt: text overlay mỗi 60s",
            "Curiosity gap: 'What's in the pink box?' chờ 30s",
            "Visual variety: macro + wide + face shot xen kẽ",
            "Compilation rhythm: video 10-15 phút = 6-8 reveals",
            "Outro tease: 'Next video preview' + thumbnail",
            "Stake escalation: toy cuối to/đẹp nhất + sound climax",
        ],
        "ctr": {
            "sweet_spot_pct": (5, 10),
            "decay_days": (60, 90),
            "high_excellent": 10,
            "low_warning": 3,
        },
        "upload_time": {
            "best_hours_local": [(8, 11), (15, 18)],
            "best_days": ["Saturday", "Sunday", "Wednesday"],
            "frequency_per_week": (3, 5),
            "premiere": False,
        },
        "engagement_baseline": {
            "like_view_pct": 4.0,
            "comment_view_pct": 0.5,
            "share_view_pct": 0.2,
        },
        "caption": {
            "priority_languages": ["English", "Spanish", "Portuguese", "Indonesian"],
            "auto_translate_title": True,
            "auto_caption": True,
        },
        "content_pillars": [
            "unboxing-kitchen-playset",
            "unboxing-doll-playset",
            "unboxing-doctor-playset",
            "unboxing-food-restaurant-playset",
            "unboxing-vehicle-playset",
            "compilation-monthly-best",
        ],
        "session_strategy": ("Tạo playlist 30-60 phút compilation theo loại "
                              "(Kitchen All / Doll All) — boost session length 2-3x"),
    },

    "asmr_sand_slime": {
        "name": "ASMR Sand / Slime Satisfying",
        "title": {
            "formula_best": ("[X Minutes] [Satisfying] [ASMR] [Slime/Sand] "
                             "[Color/Texture] | [No Music ASMR]"),
            "examples": [
                "30 Minutes Satisfying Rainbow Slime ASMR | No Music No Talking",
                "Crunchy Slime ASMR Mixing | Satisfying Sleep Sound 1 Hour",
            ],
            "keyword_position": "ASMR/Satisfying trong 20 ký tự đầu",
            "optimal_length": (55, 80),
            "clickbait_avoid": ["LOUDEST", "INSANE", "EXTREME"],
        },
        "description": {
            "min_words": 150,
            "template": (
                "✨ [Soft hook line — perfect for relaxation]\n\n"
                "⏱️ Sounds in this video:\n"
                "00:00 - [Texture 1]\n"
                "XX:XX - [Texture 2]\n\n"
                "🔔 Subscribe for daily ASMR slime/sand satisfying\n\n"
                "📌 More ASMR:\n"
                "Sleep sounds playlist\n"
                "Slime mixing playlist\n\n"
                "#asmr #satisfying #slime #nomusic #relaxing"),
            "keyword_distribution": "ASMR trong 15 từ đầu + lặp 5-7 lần",
            "hashtags_count": (5, 7),
        },
        "tags": {
            "count_range": (10, 14),
            "broad": ["asmr", "satisfying", "slime", "no music", "relaxing"],
            "specific": ["crunchy slime", "rainbow slime", "kinetic sand",
                          "asmr sleep aid", "satisfying mixing"],
            "question": ["how to make slime", "best asmr for sleep"],
            "branded_template": "[channel name] asmr",
            "trending_template": "asmr [year] viral + slime [year]",
        },
        "thumbnail": {
            "primary_layout": "Texture-Macro",
            "layouts": {
                "Texture-Macro": "Close-up texture chiếm 80%, no text hoặc 2-3 từ",
                "Color-Burst": "Rainbow/pastel saturation cao, text 'ASMR' bold",
                "Hand-Action": "Tay đang manipulate slime, action freeze frame",
            },
            "color_palette": "Saturated pastel + white background; KHÔNG dark",
            "text_words_max": 3,
            "text_size_min_px": 55,
            "face_size_pct": (0, 20),
        },
        "hook_10s": [
            "0-2s: Texture macro shot + soft sound (NO talking)",
            "2-5s: Hand manipulate slime/sand, slow motion",
            "5-8s: Sound layer build-up (crunch/squish)",
            "8-10s: Wide shot + text overlay '30 Minutes ASMR'",
        ],
        "pacing": {
            "cuts_per_min": (10, 18),
            "b_roll_pct": (50, 70),
            "pattern_interrupt_sec": 90,
        },
        "retention_techniques": [
            "Sound consistency: NO gap, no music, only texture sound",
            "Texture variety: 5-7 different textures per video",
            "Color escalation: rainbow → mix → muddy",
            "Slow zoom out: từ macro → wide gradual",
            "Audio dynamics: tăng/giảm volume tự nhiên",
            "Long-form bait: 30-60 min video cho sleep audience",
            "Reset moments: tay rửa, sạch sẽ tween textures",
            "Outro fade: sound fade dần, NOT abrupt",
        ],
        "ctr": {
            "sweet_spot_pct": (4, 8),
            "decay_days": (90, 180),
            "high_excellent": 8,
            "low_warning": 2,
        },
        "upload_time": {
            "best_hours_local": [(20, 23), (6, 9)],  # bedtime + morning
            "best_days": ["Sunday", "Tuesday", "Thursday"],
            "frequency_per_week": (2, 4),
            "premiere": True,  # Premiere giúp sleep audience set timer
        },
        "engagement_baseline": {
            "like_view_pct": 2.5,
            "comment_view_pct": 0.2,
            "share_view_pct": 0.3,
        },
        "caption": {
            "priority_languages": ["English"],
            "auto_translate_title": False,  # ASMR universal
            "auto_caption": False,  # No talking
        },
        "content_pillars": [
            "slime-mixing-rainbow",
            "slime-crunchy-foam",
            "kinetic-sand-cutting",
            "sleep-1hour-compilation",
            "stress-relief-textures",
        ],
        "session_strategy": ("Long-form 30-60 min + premiere ban đêm → "
                              "viewer set as sleep timer, session 1-2h thường xuyên"),
    },

    "horror_stories": {
        "name": "Horror Radio / Scary Narrated Stories",
        "title": {
            "formula_best": ("[Number] [Scary/Horror] [Story Type] [Setting] | "
                             "[True/Reddit/Original] [Time of Day]"),
            "examples": [
                "3 TRUE Scary Hospital Horror Stories | r/nosleep Compilation",
                "5 Hours Creepy Stories For Sleep | Rain Sounds Horror Radio",
            ],
            "keyword_position": "Scary/Horror trong 15 ký tự đầu",
            "optimal_length": (55, 75),
            "clickbait_avoid": ["DEADLY", "FATAL", "BLOODY", "MURDER"],
        },
        "description": {
            "min_words": 180,
            "template": (
                "🌒 [Hook 2 dòng — what you'll feel]\n\n"
                "⏱️ Stories in this video:\n"
                "00:00 - Intro Music\n"
                "01:30 - Story 1: [Title]\n"
                "XX:XX - Story 2: [Title]\n"
                "XX:XX - Story 3: [Title]\n\n"
                "🌧️ Background ambient: [Rain/Wind/Empty Room]\n\n"
                "🔔 Subscribe weekly horror radio compilations\n\n"
                "📌 More horror:\n"
                "Compilation playlist\n"
                "True scary stories playlist\n\n"
                "Submit your story: [link]\n\n"
                "#horror #scarystories #truescary #sleep #creepy"),
            "keyword_distribution": "Horror trong 10 từ đầu + ambient mood",
            "hashtags_count": (5, 7),
        },
        "tags": {
            "count_range": (10, 14),
            "broad": ["horror", "scary stories", "true scary", "creepy", "nightmare"],
            "specific": ["r/nosleep", "reddit horror", "narrated horror",
                          "rain sound horror", "compilation horror"],
            "question": ["scariest stories ever", "true scary reddit"],
            "branded_template": "[channel name] horror",
            "trending_template": "horror [year] new + scary [year]",
        },
        "thumbnail": {
            "primary_layout": "Dark-Face-Text",
            "layouts": {
                "Dark-Face-Text": ("Mặt người ánh sáng yếu 30%, dark background, "
                                    "text RED/WHITE bold 3-5 từ"),
                "Setting-Mood": "Hospital/forest/road đêm + small figure",
                "Object-Horror": "Cái đáng sợ (búp bê / mask) zoom in",
            },
            "color_palette": "Dark blue + red accent + desaturated; NEVER bright",
            "text_words_max": 5,
            "text_size_min_px": 65,
            "face_size_pct": (25, 40),
        },
        "hook_10s": [
            "0-2s: Creepy ambient sound (rain/wind/whisper)",
            "2-5s: Visual hint (foggy hallway, dark room)",
            "5-8s: Narrator first line: 'It was 3am when...'",
            "8-10s: Text overlay 'TRUE STORY' + tense music",
        ],
        "pacing": {
            "cuts_per_min": (3, 8),  # ít cut, slow pacing
            "b_roll_pct": (60, 80),
            "pattern_interrupt_sec": 120,
        },
        "retention_techniques": [
            "Slow build-up: tension tăng từ từ qua 3-5 phút",
            "Narrator voice consistency: deep + slow",
            "Ambient sound layer: rain/wind/crackle dưới",
            "Story structure: 3 acts (normal → strange → climax)",
            "Cliffhanger between stories: cắt ở moment tension cao",
            "Compilation 30-60-90 min cho sleep audience",
            "Premiere live cùng sleep timer",
            "Outro: tease next story ngay khi vừa hết",
        ],
        "ctr": {
            "sweet_spot_pct": (3, 6),
            "decay_days": (120, 365),  # evergreen
            "high_excellent": 7,
            "low_warning": 1.5,
        },
        "upload_time": {
            "best_hours_local": [(21, 24), (0, 3)],  # ban đêm
            "best_days": ["Friday", "Saturday", "Sunday"],
            "frequency_per_week": (1, 3),
            "premiere": True,
        },
        "engagement_baseline": {
            "like_view_pct": 3.0,
            "comment_view_pct": 0.4,
            "share_view_pct": 0.15,
        },
        "caption": {
            "priority_languages": ["English"],
            "auto_translate_title": False,
            "auto_caption": True,  # transcript SEO mạnh
        },
        "content_pillars": [
            "reddit-nosleep-compilation",
            "true-scary-real-people",
            "rain-sounds-horror-sleep",
            "hospital-school-setting",
            "old-house-haunted",
        ],
        "session_strategy": ("Long-form 1-3 hour compilation + premiere ban đêm. "
                              "Audience target: sleep-listen → session 2-4h."),
    },

    "car_crush_experiment": {
        "name": "Car Crushing Experiment / Funny Crushing",
        "title": {
            "formula_best": ("[Action verb] [Object] vs [Car/Heavy] | "
                             "[Satisfying/Funny] [Compilation/Experiment]"),
            "examples": [
                "Car Crushing Toys vs Pool — Funny Experiment Compilation",
                "Satisfying Crushing Marbles Car Wheel | ASMR Experiment",
            ],
            "keyword_position": "Crushing/Experiment trong 20 ký tự đầu",
            "optimal_length": (50, 75),
            "clickbait_avoid": ["DESTROYED", "GONE WRONG", "WILL BREAK"],
        },
        "description": {
            "min_words": 180,
            "template": (
                "🚗 [Action hook 1 dòng]\n\n"
                "⏱️ Crushes in this video:\n"
                "00:00 - Intro\n"
                "XX:XX - [Object 1] crush\n"
                "XX:XX - [Object 2] crush\n\n"
                "🔔 Subscribe for daily satisfying crushing experiment\n\n"
                "⚠️ Disclaimer: Done in controlled environment.\n\n"
                "📌 More:\n"
                "Crushing playlist\n"
                "Experiment playlist\n\n"
                "#crushing #satisfying #experiment #asmr #compilation"),
            "keyword_distribution": "Crushing/experiment 5-6 lần",
            "hashtags_count": (5, 7),
        },
        "tags": {
            "count_range": (10, 14),
            "broad": ["crushing", "satisfying", "experiment", "compilation", "asmr"],
            "specific": ["car crushing", "satisfying crushing", "funny experiment",
                          "crushing toys", "crushing food"],
            "question": ["satisfying crushing video", "what happens if car crush"],
            "branded_template": "[channel name] crushing",
            "trending_template": "crushing [year] viral + experiment [year]",
        },
        "thumbnail": {
            "primary_layout": "Before-After-Split",
            "layouts": {
                "Before-After-Split": ("Object intact bên trái, crushed bên phải, "
                                        "text 'CRUSHED' bold"),
                "Action-Freeze": "Khoảnh khắc bánh xe đè xuống object, slow-mo freeze",
                "Object-Pile": "Pile object + car wheel zoom in",
            },
            "color_palette": "Bold saturated + outdoor outdoor look",
            "text_words_max": 4,
            "text_size_min_px": 70,
            "face_size_pct": (0, 25),
        },
        "hook_10s": [
            "0-2s: Car wheel approaching + heavy sound",
            "2-5s: Object placement reveal",
            "5-8s: First crush + satisfying sound",
            "8-10s: Result + 'More to come' overlay",
        ],
        "pacing": {
            "cuts_per_min": (15, 25),
            "b_roll_pct": (40, 60),
            "pattern_interrupt_sec": 75,
        },
        "retention_techniques": [
            "Anticipation build: setup → tension → crush release",
            "Slow-mo capture: critical crush moment ở 1/4 speed",
            "Sound layering: heavy + satisfying crunch",
            "Variety per video: 5-8 different objects",
            "Compilation finale: object cuối to nhất / explosive",
            "Reaction cut-in: facial expression sometimes",
            "Risk teaser: 'will it survive?' before crush",
            "Outro: next crush preview teaser",
        ],
        "ctr": {
            "sweet_spot_pct": (4, 8),
            "decay_days": (60, 120),
            "high_excellent": 8,
            "low_warning": 2,
        },
        "upload_time": {
            "best_hours_local": [(15, 19), (20, 22)],
            "best_days": ["Saturday", "Sunday", "Friday"],
            "frequency_per_week": (2, 4),
            "premiere": False,
        },
        "engagement_baseline": {
            "like_view_pct": 3.5,
            "comment_view_pct": 0.3,
            "share_view_pct": 0.2,
        },
        "caption": {
            "priority_languages": ["English", "Spanish"],
            "auto_translate_title": True,
            "auto_caption": False,
        },
        "content_pillars": [
            "crushing-toys-compilation",
            "crushing-food-experiment",
            "car-wheel-vs-objects",
            "satisfying-crushing-asmr",
            "monthly-best-compilation",
        ],
        "session_strategy": ("Compilation 20-40 min cho weekend binge. "
                              "Playlist 'All crushing' cho session 1-2h."),
    },

    "diy_mini_tractor": {
        "name": "DIY Mini Tractor / Mini Machinery",
        "title": {
            "formula_best": ("[Action] [Mini Tractor/Machine] [Activity] | "
                             "[Build/DIY/Test] [Result]"),
            "examples": [
                "Building Mini Tractor with Irrigation System | DIY Working Model",
                "Mini Tractor Plowing Real Field | Satisfying DIY Build",
            ],
            "keyword_position": "Mini Tractor / DIY trong 20 ký tự đầu",
            "optimal_length": (55, 80),
            "clickbait_avoid": ["INCREDIBLE", "GENIUS", "AMAZING"],
        },
        "description": {
            "min_words": 200,
            "template": (
                "🚜 [Hook 1 dòng — what we build today]\n\n"
                "⏱️ Steps in this video:\n"
                "00:00 - Materials & Tools\n"
                "XX:XX - Frame Build\n"
                "XX:XX - Engine Install\n"
                "XX:XX - Test Drive\n\n"
                "🔧 Materials used:\n"
                "- [Item 1]\n"
                "- [Item 2]\n\n"
                "🔔 Subscribe for weekly DIY mini machinery\n\n"
                "📌 More builds:\n"
                "Mini tractor playlist\n"
                "DIY irrigation playlist\n\n"
                "#minitractor #diy #farming #handmade #satisfying"),
            "keyword_distribution": "Mini Tractor 6-8 lần, DIY 4-5 lần",
            "hashtags_count": (5, 7),
        },
        "tags": {
            "count_range": (12, 15),
            "broad": ["mini tractor", "diy", "handmade", "farming", "satisfying"],
            "specific": ["mini machinery", "diy irrigation", "small tractor",
                          "mini farm", "mini engine"],
            "question": ["how to make mini tractor", "diy mini machinery"],
            "branded_template": "[channel name] mini tractor",
            "trending_template": "mini tractor [year] + diy [year]",
        },
        "thumbnail": {
            "primary_layout": "Action-Field",
            "layouts": {
                "Action-Field": ("Tractor working in field, outdoor wide, "
                                  "text bold 3-5 từ"),
                "Before-After-Build": "Frame → Complete machine split",
                "Close-Engine": "Macro engine close-up + steam/smoke",
            },
            "color_palette": "Earth tone (brown/green/yellow) + outdoor light",
            "text_words_max": 5,
            "text_size_min_px": 65,
            "face_size_pct": (0, 20),
        },
        "hook_10s": [
            "0-2s: Mini tractor working close-up + engine sound",
            "2-5s: Wide shot field + tractor in action",
            "5-8s: Tilt down to plow/irrigation working",
            "8-10s: Text overlay 'Building from scratch' + sound",
        ],
        "pacing": {
            "cuts_per_min": (12, 20),
            "b_roll_pct": (45, 65),
            "pattern_interrupt_sec": 90,
        },
        "retention_techniques": [
            "Build sequence: clear before → during → after",
            "Sound design: engine + tools + ambient nature",
            "Slow-mo on critical mechanism work",
            "Multiple test shots: irrigation/plow/spray",
            "Wide-to-macro variety: full view → engine close",
            "Real-world test: field work, dirt, working",
            "Maker satisfaction: pause to show finished detail",
            "Outro: next build preview + 'will it work?' tease",
        ],
        "ctr": {
            "sweet_spot_pct": (3, 7),
            "decay_days": (180, 365),
            "high_excellent": 7,
            "low_warning": 1.5,
        },
        "upload_time": {
            "best_hours_local": [(10, 14), (18, 21)],
            "best_days": ["Saturday", "Sunday", "Tuesday"],
            "frequency_per_week": (1, 3),
            "premiere": False,
        },
        "engagement_baseline": {
            "like_view_pct": 3.0,
            "comment_view_pct": 0.4,
            "share_view_pct": 0.2,
        },
        "caption": {
            "priority_languages": ["English", "Hindi", "Spanish"],
            "auto_translate_title": True,
            "auto_caption": True,  # nhiều ngôn ngữ
        },
        "content_pillars": [
            "mini-tractor-build",
            "mini-irrigation-system",
            "mini-plowing-field",
            "mini-tools-diy",
            "test-vs-real-tractor",
        ],
        "session_strategy": ("Series build 5-10 video → playlist 'Complete build'. "
                              "Audience binge full series cho session 2-3h."),
    },

    "construction_vehicle": {
        "name": "Construction Vehicle Toys (kid)",
        "title": {
            "formula_best": ("[Vehicle Type] [Action] [Setting] | [For Kids] "
                             "[Educational/Fun]"),
            "examples": [
                "Excavator Digging Sand Pit | Construction Vehicle Toys for Kids",
                "Dump Truck and Bulldozer Working Together | Kids Vehicle Adventures",
            ],
            "keyword_position": "Vehicle type trong 15 ký tự đầu",
            "optimal_length": (60, 85),
            "clickbait_avoid": ["DESTROYED", "CRASH", "WRECKED"],
        },
        "description": {
            "min_words": 180,
            "template": (
                "🏗️ [Hook 1 dòng — fun activity for kids]\n\n"
                "⏱️ Vehicles in this video:\n"
                "00:00 - Intro\n"
                "XX:XX - Excavator\n"
                "XX:XX - Dump Truck\n\n"
                "🔔 Subscribe daily kids construction vehicle\n\n"
                "📌 More:\n"
                "Vehicle playlist\n"
                "Sandbox adventures\n\n"
                "#construction #vehicles #kids #toys #educational"),
            "keyword_distribution": "Construction/Vehicle 5-7 lần",
            "hashtags_count": (5, 7),
        },
        "tags": {
            "count_range": (10, 14),
            "broad": ["construction toys", "vehicle", "kids toys", "excavator", "dump truck"],
            "specific": ["sandbox excavator", "bulldozer kids", "construction site toys",
                          "kid vehicle adventure", "remote control construction"],
            "question": ["best vehicle toys for kids", "how to play sandbox"],
            "branded_template": "[channel name] kids vehicle",
            "trending_template": "construction toys [year] kids",
        },
        "thumbnail": {
            "primary_layout": "Vehicle-Action-Kid",
            "layouts": {
                "Vehicle-Action-Kid": ("Vehicle 50% + kid mặt cười 30% + "
                                        "text 'Fun!' bold"),
                "Site-Wide": "Sandbox/dirt + 2-3 vehicles working together",
                "Vehicle-Macro": "Close-up vehicle moving part",
            },
            "color_palette": "Bright yellow/orange/red + outdoor",
            "text_words_max": 4,
            "text_size_min_px": 65,
            "face_size_pct": (25, 45),
        },
        "hook_10s": [
            "0-2s: Vehicle moving + engine sound",
            "2-5s: Kid pointing + smiling",
            "5-8s: Action moment (digging, dumping)",
            "8-10s: Title text + 'Let's go!' sound",
        ],
        "pacing": {
            "cuts_per_min": (18, 28),
            "b_roll_pct": (35, 55),
            "pattern_interrupt_sec": 60,
        },
        "retention_techniques": [
            "Story arc: vehicles work to complete project",
            "Sound effects: engine, beeping, dumping",
            "Multi-vehicle interaction: excavator + truck",
            "Kid narration / participation",
            "Progress visible: pile gets bigger",
            "Music upbeat + kid-friendly",
            "Outro: 'next adventure' tease",
            "Stake escalation: bigger pile, bigger vehicle",
        ],
        "ctr": {
            "sweet_spot_pct": (4, 8),
            "decay_days": (90, 180),
            "high_excellent": 9,
            "low_warning": 2,
        },
        "upload_time": {
            "best_hours_local": [(8, 11), (15, 18)],
            "best_days": ["Saturday", "Sunday", "Wednesday"],
            "frequency_per_week": (3, 5),
            "premiere": False,
        },
        "engagement_baseline": {
            "like_view_pct": 3.5,
            "comment_view_pct": 0.4,
            "share_view_pct": 0.25,
        },
        "caption": {
            "priority_languages": ["English", "Spanish", "Portuguese"],
            "auto_translate_title": True,
            "auto_caption": True,
        },
        "content_pillars": [
            "excavator-sandbox",
            "dump-truck-adventure",
            "construction-site-multi",
            "vehicle-counting-learn",
            "monthly-compilation",
        ],
        "session_strategy": ("Playlist 'All construction' cho kid binge. "
                              "Compilation 30-60 min weekly."),
    },

    "numberblocks_slime": {
        "name": "Numberblocks Slime / Rainbow Number Edu",
        "title": {
            "formula_best": ("[Number(s)] [Slime/Color] [Activity] | "
                             "[Numberblocks/Learning/ASMR]"),
            "examples": [
                "Rainbow Number 1 to 10 Slime ASMR | Numberblocks Learn",
                "Number Block Counting with Slime | Educational Satisfying",
            ],
            "keyword_position": "Number / Numberblocks trong 20 ký tự đầu",
            "optimal_length": (55, 80),
            "clickbait_avoid": ["BIGGEST", "FAIL", "WRONG"],
        },
        "description": {
            "min_words": 150,
            "template": (
                "🌈 [Hook 1 dòng — learn numbers with slime]\n\n"
                "⏱️ Numbers in this video:\n"
                "00:00 - Number 1\n"
                "XX:XX - Number 2\n\n"
                "🔔 Subscribe for daily rainbow number slime\n\n"
                "📌 More:\n"
                "Number slime playlist\n"
                "Counting fun playlist\n\n"
                "#numbers #slime #numberblocks #learning #asmr #rainbow"),
            "keyword_distribution": "Number/Numberblocks 5-6 lần",
            "hashtags_count": (5, 7),
        },
        "tags": {
            "count_range": (10, 14),
            "broad": ["numberblocks", "number slime", "learning", "asmr",
                       "rainbow", "satisfying"],
            "specific": ["rainbow number slime", "number 1 to 10",
                          "numberblocks asmr", "counting slime"],
            "question": ["how to count with slime", "learn numbers fun"],
            "branded_template": "[channel name] numbers",
            "trending_template": "numberblocks [year] viral",
        },
        "thumbnail": {
            "primary_layout": "Number-Color-Burst",
            "layouts": {
                "Number-Color-Burst": ("Số to chiếm 40% + slime rainbow 40% + "
                                        "kid friendly text"),
                "Block-Stack": "Numberblocks character stack + slime",
                "Sequence": "Number 1-10 grid + slime drops",
            },
            "color_palette": "Rainbow full spectrum + bright kid colors",
            "text_words_max": 3,
            "text_size_min_px": 70,
            "face_size_pct": (0, 25),
        },
        "hook_10s": [
            "0-2s: Number macro + slime drop",
            "2-5s: 'Let's count!' upbeat tune",
            "5-8s: Number 1 + slime drop sound",
            "8-10s: Title rainbow text",
        ],
        "pacing": {
            "cuts_per_min": (15, 25),
            "b_roll_pct": (40, 60),
            "pattern_interrupt_sec": 50,
        },
        "retention_techniques": [
            "Sequential count: 1 → 2 → 3 → 10 (predictable, kid-friendly)",
            "Color escalation: rainbow progression",
            "Sound layer: slime + counting voice",
            "Numberblocks character cameo",
            "Quiz moment: 'What number is this?' pause",
            "Compilation finale: all numbers together",
            "Music: upbeat kid melody",
            "Outro: 'next number adventure'",
        ],
        "ctr": {
            "sweet_spot_pct": (4, 8),
            "decay_days": (90, 180),
            "high_excellent": 9,
            "low_warning": 2,
        },
        "upload_time": {
            "best_hours_local": [(8, 12), (16, 19)],
            "best_days": ["Saturday", "Sunday", "Tuesday", "Thursday"],
            "frequency_per_week": (3, 6),
            "premiere": False,
        },
        "engagement_baseline": {
            "like_view_pct": 3.0,
            "comment_view_pct": 0.3,
            "share_view_pct": 0.2,
        },
        "caption": {
            "priority_languages": ["English", "Spanish", "Hindi"],
            "auto_translate_title": True,
            "auto_caption": True,
        },
        "content_pillars": [
            "number-1-to-10-slime",
            "numberblocks-character",
            "counting-with-objects",
            "color-mixing-rainbow",
            "alphabet-too (cross)",
        ],
        "session_strategy": ("Playlist '1-100 Numbers Adventure'. "
                              "Kid loop watch session 1-2h."),
    },

    "paper_doll_glow": {
        "name": "Paper Doll DIY / Glow Up / Couple Paper",
        "title": {
            "formula_best": ("[Paper] [Doll/Couple] [Glow Up/DIY] [Theme] | "
                             "[Satisfying/ASMR/TikTok Trend]"),
            "examples": [
                "Paper Doll Glow Up Couple | DIY Satisfying ASMR",
                "Paper Couple Wedding Outfit Drawing | Glow Up Trend",
            ],
            "keyword_position": "Paper Doll / Glow Up trong 25 ký tự đầu",
            "optimal_length": (60, 85),
            "clickbait_avoid": ["MOST BEAUTIFUL", "PERFECT", "BEST EVER"],
        },
        "description": {
            "min_words": 150,
            "template": (
                "✨ [Hook 1 dòng — satisfying paper craft]\n\n"
                "⏱️ Steps in this video:\n"
                "00:00 - Outfit Selection\n"
                "XX:XX - Drawing\n"
                "XX:XX - Coloring\n"
                "XX:XX - Final Glow Up\n\n"
                "🔔 Subscribe for daily paper doll DIY\n\n"
                "📌 More:\n"
                "Glow up playlist\n"
                "Couple paper playlist\n\n"
                "#paperdoll #glowup #diy #satisfying #couple #asmr"),
            "keyword_distribution": "Paper Doll / Glow Up 5-6 lần",
            "hashtags_count": (5, 7),
        },
        "tags": {
            "count_range": (10, 14),
            "broad": ["paper doll", "glow up", "paper diy", "satisfying", "asmr"],
            "specific": ["paper couple", "doll dress up", "fashion paper",
                          "tiktok glow up", "kpop demon paper"],
            "question": ["how to make paper doll", "paper glow up trend"],
            "branded_template": "[channel name] paper",
            "trending_template": "paper doll [year] + glow up [year]",
        },
        "thumbnail": {
            "primary_layout": "Before-After-Doll",
            "layouts": {
                "Before-After-Doll": ("Paper doll plain bên trái, glow up "
                                        "đẹp bên phải, text 'Glow Up'"),
                "Outfit-Variety": "5-7 outfit grid + doll center",
                "Couple-Wedding": "2 doll couple với outfit chính",
            },
            "color_palette": "Pastel pink + gold + sparkle effects",
            "text_words_max": 3,
            "text_size_min_px": 60,
            "face_size_pct": (0, 25),
        },
        "hook_10s": [
            "0-2s: Plain paper doll macro",
            "2-5s: Hand picking pencil/scissor",
            "5-8s: First color stroke + ASMR sound",
            "8-10s: Text 'Watch the glow up' + transition",
        ],
        "pacing": {
            "cuts_per_min": (12, 20),
            "b_roll_pct": (50, 70),
            "pattern_interrupt_sec": 75,
        },
        "retention_techniques": [
            "Process reveal: blank → outline → color → final",
            "ASMR sound: pencil/marker/scissor close mic",
            "Multiple outfit per video: 3-7 variations",
            "Time-lapse fast-forward intro",
            "Theme variety: wedding, school, kpop, casual",
            "Final reveal: full doll spin",
            "Couple chemistry: 2 doll interaction",
            "Outro: 'next outfit' teaser",
        ],
        "ctr": {
            "sweet_spot_pct": (5, 10),
            "decay_days": (60, 120),
            "high_excellent": 10,
            "low_warning": 2.5,
        },
        "upload_time": {
            "best_hours_local": [(15, 19), (20, 23)],
            "best_days": ["Friday", "Saturday", "Sunday"],
            "frequency_per_week": (3, 5),
            "premiere": False,
        },
        "engagement_baseline": {
            "like_view_pct": 4.5,
            "comment_view_pct": 0.6,
            "share_view_pct": 0.3,
        },
        "caption": {
            "priority_languages": ["English", "Vietnamese", "Korean"],
            "auto_translate_title": True,
            "auto_caption": False,
        },
        "content_pillars": [
            "paper-doll-glow-up",
            "paper-couple-wedding",
            "kpop-demon-hunter-paper",
            "tiktok-trend-paper",
            "paper-fashion-show",
        ],
        "session_strategy": ("Playlist 'Paper Doll Glow Up All' — gen Z "
                              "audience binge 1-2h sau giờ học."),
    },

    "lego_animation": {
        "name": "LEGO Animation / Brick Stop-motion",
        "title": {
            "formula_best": ("[LEGO] [Character/Theme] [Action] | "
                             "[Stop Motion/Brickfilm] [Story Type]"),
            "examples": [
                "LEGO Ninjago Final Battle | Stop Motion Animation",
                "LEGO Brick Build Compilation | Satisfying Stop Motion",
            ],
            "keyword_position": "LEGO trong 10 ký tự đầu",
            "optimal_length": (50, 75),
            "clickbait_avoid": ["EPIC", "INSANE", "ULTIMATE"],
        },
        "description": {
            "min_words": 150,
            "template": (
                "🧱 [Hook 1 dòng — LEGO story/build today]\n\n"
                "⏱️ In this video:\n"
                "00:00 - Intro\n"
                "XX:XX - Build Process\n"
                "XX:XX - Animation Sequence\n\n"
                "🔔 Subscribe weekly LEGO stop motion\n\n"
                "📌 More:\n"
                "LEGO playlist\n"
                "Stop motion playlist\n\n"
                "#lego #stopmotion #brickfilm #animation #satisfying"),
            "keyword_distribution": "LEGO / Stop motion 5-7 lần",
            "hashtags_count": (5, 7),
        },
        "tags": {
            "count_range": (10, 14),
            "broad": ["lego", "stop motion", "brickfilm", "animation", "satisfying"],
            "specific": ["lego ninjago", "lego star wars", "lego marvel",
                          "lego stop motion", "lego brick build"],
            "question": ["how to make lego stop motion", "best lego brickfilm"],
            "branded_template": "[channel name] lego",
            "trending_template": "lego [year] new + brickfilm [year]",
        },
        "thumbnail": {
            "primary_layout": "Action-Scene",
            "layouts": {
                "Action-Scene": ("LEGO scene action moment + dramatic lighting, "
                                  "text bold"),
                "Character-Closeup": "Minifigure macro shot + scene background",
                "Build-Result": "Finished build wide shot + 'How I built it'",
            },
            "color_palette": "Vibrant LEGO colors + dramatic lighting",
            "text_words_max": 4,
            "text_size_min_px": 65,
            "face_size_pct": (0, 30),
        },
        "hook_10s": [
            "0-2s: LEGO scene action moment",
            "2-5s: Character introduction shot",
            "5-8s: Conflict/setup tease",
            "8-10s: Title text + music intro",
        ],
        "pacing": {
            "cuts_per_min": (20, 35),  # stop motion frame-based
            "b_roll_pct": (60, 80),
            "pattern_interrupt_sec": 60,
        },
        "retention_techniques": [
            "Story structure: 3 acts (setup, conflict, climax)",
            "Sound design: voice + music + brick clack",
            "Camera variety: wide, medium, close, top-down",
            "Animation smoothness: 12-24 fps stop motion",
            "Build process intro: time-lapse setup",
            "Character development: minifigure personality",
            "Final climax: explosive scene or twist",
            "Outro: next story preview",
        ],
        "ctr": {
            "sweet_spot_pct": (3, 7),
            "decay_days": (180, 365),
            "high_excellent": 8,
            "low_warning": 1.5,
        },
        "upload_time": {
            "best_hours_local": [(15, 19), (20, 22)],
            "best_days": ["Saturday", "Sunday", "Friday"],
            "frequency_per_week": (1, 2),
            "premiere": True,
        },
        "engagement_baseline": {
            "like_view_pct": 5.0,
            "comment_view_pct": 0.7,
            "share_view_pct": 0.3,
        },
        "caption": {
            "priority_languages": ["English", "Spanish", "Portuguese"],
            "auto_translate_title": True,
            "auto_caption": True,
        },
        "content_pillars": [
            "lego-ninjago-saga",
            "lego-marvel-action",
            "lego-build-tutorial",
            "lego-compilation-monthly",
            "lego-brick-story-original",
        ],
        "session_strategy": ("Series 5-10 episode → playlist. "
                              "Audience binge full saga session 1-3h."),
    },

    # Default fallback
    "general": {
        "name": "General (not matched specific niche)",
        "title": {
            "formula_best": "[Number/Hook] + [Niche Keyword] + [Promise/Result] + | + [Brand/Channel]",
            "examples": ["10 Tips to Grow YouTube Channel", "Best Method for X | Tutorial"],
            "keyword_position": "Niche keyword trong 30 ký tự đầu",
            "optimal_length": (50, 80),
            "clickbait_avoid": ["ULTIMATE", "INSANE", "SHOCKED", "YOU WON'T BELIEVE"],
        },
        "description": {
            "min_words": 150,
            "template": "Mô tả ngắn + Timestamps + Subscribe CTA + Playlist + Social + 3-5 Hashtag",
            "keyword_distribution": "Keyword chính trong 25 từ đầu + lặp 3-5 lần",
            "hashtags_count": (3, 5),
        },
        "tags": {
            "count_range": (8, 15),
            "broad": ["[niche broad]"],
            "specific": ["[long-tail keyword]"],
            "question": ["how to [niche]"],
            "branded_template": "[channel name]",
            "trending_template": "[niche] [year]",
        },
        "thumbnail": {
            "primary_layout": "Face-Centered",
            "layouts": {
                "Face-Centered": "Mặt 40% + text 3-5 từ",
                "Object-Hero": "Object chiếm 60% + text",
                "Split-Compare": "Before/after split",
            },
            "color_palette": "High contrast + saturation",
            "text_words_max": 5,
            "text_size_min_px": 60,
            "face_size_pct": (20, 40),
        },
        "hook_10s": [
            "0-3s: Result first hoặc problem punch",
            "3-7s: Setup/expectation",
            "7-10s: Title + transition to body",
        ],
        "pacing": {
            "cuts_per_min": (15, 25),
            "b_roll_pct": (30, 50),
            "pattern_interrupt_sec": 60,
        },
        "retention_techniques": [
            "Hook 10s mạnh",
            "Pacing 3-7s/shot",
            "Pattern interrupt mỗi 60-90s",
            "Curiosity gap mid-video",
            "Stake escalation",
        ],
        "ctr": {
            "sweet_spot_pct": (4, 8),
            "decay_days": (60, 180),
            "high_excellent": 8,
            "low_warning": 2,
        },
        "upload_time": {
            "best_hours_local": [(15, 19)],
            "best_days": ["Saturday", "Sunday"],
            "frequency_per_week": (1, 3),
            "premiere": False,
        },
        "engagement_baseline": {
            "like_view_pct": 3.0,
            "comment_view_pct": 0.3,
            "share_view_pct": 0.2,
        },
        "caption": {
            "priority_languages": ["English"],
            "auto_translate_title": False,
            "auto_caption": True,
        },
        "content_pillars": ["[pillar 1]", "[pillar 2]", "[pillar 3]"],
        "session_strategy": "Playlist + series consistent → boost session",
    },
}


def get_niche_seo(niche_key: str) -> Dict[str, Any]:
    """Lookup niche SEO data, fallback to general."""
    return NICHE_SEO_DATA.get(niche_key) or NICHE_SEO_DATA["general"]


def list_niche_keys() -> list:
    """Liệt kê niche key có trong library."""
    return list(NICHE_SEO_DATA.keys())
