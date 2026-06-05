// components/research/SeoBestPractice.jsx
// Tab tham chiếu TĨNH (port từ s11 gốc) — framework SEO, không phụ thuộc data.
import { Box, Typography } from "@mui/material";
import { DataTable, SectionCard } from "./primitives";

const TITLES = [
  { f: "How-to", mau: "Cách + [làm gì] + [cho ai/khi nào]", vd: "Cách trồng rau thuỷ canh tại nhà cho người mới (2026)" },
  { f: "List", mau: "[Số] + [danh từ] + [hứa hẹn]", vd: "10 mẹo SEO YouTube giúp video lên top sau 24h" },
  { f: "Versus", mau: "[A] vs [B]: [câu hỏi]", vd: "iPhone 17 vs Samsung S26: cái nào đáng mua 2026?" },
  { f: "Question", mau: "[Câu hỏi gây tò mò]", vd: "Tại sao 90% nhà sáng tạo không bao giờ đạt 10K subs?" },
];
const HOOKS = [
  { h: "Result First", how: "Show kết quả/end product TRƯỚC, rồi process" },
  { h: "Problem Punch", how: "Nêu PAIN POINT mạnh ngay đầu" },
  { h: "Bold Promise", how: 'Hứa benefit lớn + thời gian cụ thể ("5 phút nữa bạn sẽ biết...")' },
  { h: "Curiosity Gap", how: "Nêu fact gây tò mò không trả lời ngay" },
  { h: "Story Hook", how: "Bắt đầu bằng câu chuyện cá nhân với conflict" },
];
const LAYOUTS = [
  { l: "Face + Text", w: "75% face left, text right - tutorial, vlog, reaction" },
  { l: "Object + Face", w: "50/50 split - review, unboxing" },
  { l: "Before/After", w: "Split screen - transformation, comparison" },
  { l: "Versus", w: "A vs B split với chữ VS to giữa" },
  { l: "Number + Emoji + Object", w: "List video (Top 10...)" },
];
const RETENTION = [
  "Hook 10s mạnh — quan trọng nhất, dùng 5 công thức trên",
  "Pattern Interrupt mỗi 1-2 phút: zoom, sound, b-roll, jump cut",
  'Open Loops: "Tôi sẽ tiết lộ điều này ở cuối video..."',
  "Curiosity Gap: hứa hẹn revelation ở phần sau",
  'Numbered Lists: "5 mẹo — đặc biệt #4 thay đổi mọi thứ"',
  "Visual Variety: đổi shot type, angle, location",
  "Stake Escalation: vấn đề càng lúc càng to",
  "Strong CTA cuối: kéo session sang video tiếp",
];
const KPIS = [
  { k: "CTR", d: "% người thấy thumbnail click vào", m: "5-10% (>10% xuất sắc)" },
  { k: "AVD", d: "TB phút mỗi viewer xem video", m: "≥4 phút cho video 10p" },
  { k: "AVP", d: "% TB video xem", m: "≥40%" },
  { k: "Like/View", d: "Tỷ lệ like", m: "3-7%" },
  { k: "Comment/1K views", d: "Tỷ lệ comment", m: "0.5-2" },
  { k: "Session Duration", d: "Thời gian ở YouTube sau video bạn", m: "≥10 phút" },
  { k: "Returning Viewers %", d: "% viewer cũ quay lại", m: "20-40%" },
];
const LOOP = [
  { g: "0-2", a: "Verify upload, share Community tab, pin top comment, reply 5-10 comment đầu" },
  { g: "2-24", a: "Realtime monitor, reply comment trong 30 phút, share IG/FB/TikTok, CTR<3% sau 12h → đổi thumbnail" },
  { g: "24-48", a: "Check CTR + AVD vs benchmark, thấp → đổi thumbnail/title, cao → tăng ads boost" },
  { g: "48-72", a: "Đánh giá hit/miss, hit → lên variant, miss → ghi lesson learned" },
];
const DIAG = [
  { s: "CTR < 3%", n: "Thumbnail/Title yếu", fix: "Redesign thumbnail có face + contrast cao + title thêm benefit/curiosity" },
  { s: "AVP < 30%", n: "Hook yếu / clickbait", fix: "Quay lại hook 10s + title-thumbnail match nội dung" },
  { s: "Retention drop 50-70%", n: "Mid-video không giữ", fix: "Boost moment ở giữa: revelation/story/visual change" },
  { s: "CTR cao + AVP thấp", n: "Click bait", fix: "Title/thumbnail match nội dung hơn" },
  { s: "CTR thấp + AVP cao", n: "Title/thumbnail yếu, content tốt", fix: "Đổi title/thumbnail — content giữ nguyên" },
  { s: "Subs đứng yên 3+ kỳ", n: "Sai pillar / quality giảm", fix: "Audit 10 video gần nhất retention, quay lại pillar gốc" },
  { s: "Views/15d giảm âm", n: "Video bị ẩn/xoá", fix: "Kiểm tra YouTube Studio - khôi phục video nếu có" },
];
const REPURPOSE = [
  { src: "Video 15 phút", out: "→ 3-5 Shorts (highlight)" },
  { src: "Video tutorial", out: "→ Blog post + Pinterest pin + IG carousel" },
  { src: "Live 2 tiếng", out: "→ Highlight 10p + 5-10 Shorts + Podcast audio" },
  { src: "Interview", out: "→ Quote graphic + Article + Newsletter" },
];
const CHECKLIST = [
  "Title ≤70 ký tự, có keyword chính trong 50 ký tự đầu?",
  "Title KHÔNG clickbait sai sự thật?",
  "Description đoạn 1: tóm tắt 2-3 dòng có keyword?",
  "Description có chapters (timestamps)?",
  "Description có 3-5 link related?",
  "Description có 3-5 hashtag cuối?",
  "Tags 5-15, tag đầu = keyword chính?",
  "Thumbnail 1280×720px, có face/object rõ?",
  "Thumbnail text ≤5 từ, đọc được ở mobile?",
  "Thumbnail consistent với brand pattern?",
  "Captions/Subtitles ngôn ngữ chính đã upload?",
  "End Screen 4 elements (video + playlist + subscribe)?",
  "Cards (max 5) đặt đúng moment?",
  "Pinned comment chuẩn bị sẵn?",
  "Made for Kids: đã quyết định Yes/No đúng?",
  "Altered content: tick nếu dùng AI synthetic người thật?",
  "Hook 10s đầu MẠNH (1 trong 5 công thức)?",
  "Video length phù hợp ngách?",
  "Audio voice -16 LUFS, music -25 dB, không echo?",
  "Video 1080p hoặc 4K, bitrate đủ (8-12 Mbps)?",
  "Pattern interrupt mỗi 1-2 phút?",
  "CTA mid-video (Subscribe + Share)?",
  "Schedule publish đúng giờ peak audience?",
  "Add to playlist phù hợp?",
  "Sẵn sàng phản hồi comment 24h đầu?",
];
const PROMPTS = [
  ["Brainstorm tiêu đề", 'Tôi đang làm video về [TOPIC] cho ngách [NICHE], audience [PERSONA]. Brainstorm 10 tiêu đề ≤70 ký tự theo 5 công thức (How-to, List, Versus, Question, Story). Mỗi tiêu đề kèm CTR prediction high/medium/low + 1 câu giải thích.'],
  ["Viết description", "Viết YouTube description 250-300 từ cho video '[TITLE]' về [TOPIC]. Format: đoạn 1 (tóm tắt + keyword), đoạn 2 (timestamps), đoạn 3 (5 link + 5 social + 3 hashtag). Keyword chính: [KEYWORD]."],
  ["Phân tích retention", "Tôi có retention curve: [paste numbers]. Phân tích đâu là điểm drop >5%, đoạn nào spike up, đề xuất 3 hành động cụ thể cho video tiếp theo."],
];

const note = (t) => (
  <Typography variant="caption" color="text.secondary" sx={{ display: "block", mt: 1 }}>
    {t}
  </Typography>
);

export default function SeoBestPractice() {
  return (
    <>
      <SectionCard title="📚 SEO Best Practice — Framework chuẩn" subtitle='Trích từ "Chuyên môn SEO Cơ bản đến Nâng cao A-Z" (Funtime Media Corp).'>
        <Typography variant="subtitle2" fontWeight={700} mb={1}>🎯 4 công thức TITLE thắng</Typography>
        <DataTable
          limit={null}
          rows={TITLES}
          columns={[
            { key: "f", label: "Công thức" },
            { key: "mau", label: "Mẫu" },
            { key: "vd", label: "Ví dụ" },
          ]}
        />
        {note("Quy tắc: ≤70 ký tự, keyword chính ở 50 ký tự đầu, có yếu tố tò mò/lợi ích/năm, 1-2 emoji.")}
      </SectionCard>

      <SectionCard title="🎬 5 công thức HOOK 10 giây đầu">
        <DataTable
          limit={null}
          rows={HOOKS}
          columns={[
            { key: "h", label: "Hook" },
            { key: "how", label: "Cách triển khai" },
          ]}
        />
        {note("10 giây đầu quyết định 80% retention. Drop ở 10s = drop khắp video.")}
      </SectionCard>

      <SectionCard title="🖼️ 5 LAYOUT Thumbnail phổ biến">
        <DataTable
          limit={null}
          rows={LAYOUTS}
          columns={[
            { key: "l", label: "Layout" },
            { key: "w", label: "Khi nào dùng" },
          ]}
        />
        {note("Anatomy: Face 30-50% + Object 20-40% + Text 2-5 từ + contrast cao. Test ở 200×120px vẫn đọc được.")}
      </SectionCard>

      <SectionCard title="📈 8 kỹ thuật tăng RETENTION">
        <Box component="ol" sx={{ pl: 2.5, m: 0 }}>
          {RETENTION.map((t, i) => (
            <li key={i}>
              <Typography variant="body2" sx={{ lineHeight: 1.7 }}>{t}</Typography>
            </li>
          ))}
        </Box>
      </SectionCard>

      <SectionCard title="📊 7 KPI cốt lõi + Mốc tốt">
        <DataTable
          limit={null}
          rows={KPIS}
          columns={[
            { key: "k", label: "KPI" },
            { key: "d", label: "Định nghĩa" },
            { key: "m", label: "Mốc tốt" },
          ]}
        />
      </SectionCard>

      <SectionCard title="⏰ Vòng lặp tối ưu 48-72h sau publish">
        <DataTable
          limit={null}
          rows={LOOP}
          columns={[
            { key: "g", label: "Giờ", align: "right" },
            { key: "a", label: "Hành động" },
          ]}
        />
      </SectionCard>

      <SectionCard title="🩺 Bảng chẩn đoán triệu chứng → sửa">
        <DataTable
          limit={null}
          rows={DIAG}
          columns={[
            { key: "s", label: "Triệu chứng" },
            { key: "n", label: "Nguyên nhân" },
            { key: "fix", label: "Sửa" },
          ]}
        />
      </SectionCard>

      <SectionCard title="📋 Checklist 25 items pre-publish">
        <Box component="ul" sx={{ pl: 2.5, m: 0, columnGap: 4, columns: { xs: 1, md: 2 } }}>
          {CHECKLIST.map((t, i) => (
            <li key={i} style={{ breakInside: "avoid" }}>
              <Typography variant="body2" sx={{ lineHeight: 1.7 }}>☐ {t}</Typography>
            </li>
          ))}
        </Box>
      </SectionCard>

      <SectionCard title="🔄 Repurpose Content — 1 video → 4-10 assets">
        <DataTable
          limit={null}
          rows={REPURPOSE}
          columns={[
            { key: "src", label: "Source" },
            { key: "out", label: "Output" },
          ]}
        />
      </SectionCard>

      <SectionCard title="🤖 AI Prompt templates dùng hàng ngày">
        {PROMPTS.map(([title, body], i) => (
          <Box key={i} mb={1.5}>
            <Typography variant="subtitle2" fontWeight={700} mb={0.5}>{title}</Typography>
            <Box
              sx={{
                p: 1.25,
                borderRadius: 1,
                bgcolor: (t) => (t.palette.mode === "dark" ? "rgba(255,255,255,0.04)" : "rgba(15,23,42,0.03)"),
                border: (t) => `1px solid ${t.palette.divider}`,
              }}
            >
              <Typography variant="body2" sx={{ fontStyle: "italic", lineHeight: 1.6 }}>{body}</Typography>
            </Box>
          </Box>
        ))}
      </SectionCard>
    </>
  );
}
