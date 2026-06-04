// components/research/SeoReport.jsx
// Trang Seo: báo cáo SEO do Claude CLI viết (state ở hook useSeoReport, control
// đặt cùng hàng chọn watchlist) + bảng số liệu tham chiếu từ getReport.
import { Box, CircularProgress, LinearProgress, Typography, useTheme } from "@mui/material";
import { DataTable, EmptyState, SectionCard, StatGrid, num } from "./primitives";
import Markdown from "./Markdown";

const PhaseTitle = ({ children }) => (
  <Typography variant="h6" fontWeight={800} sx={{ mt: 3, mb: 1.5 }}>
    {children}
  </Typography>
);

const mmss = (s) => `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;

const SeoReport = ({ report, seo, reportLoading }) => {
  const theme = useTheme();
  const d = report || {};
  const self = d.self || {};
  const { content = "", generating = false, elapsed = 0, msg = "" } = seo || {};

  const sb = d.sb_compare || [];
  const gaps = d.competitive_gaps || [];
  const kwRows = Object.entries(d.kw_enrich || {}).map(([kw, v]) => ({ kw, ...(v || {}) }));
  const seoComps = self.seo_comps || [];
  const titlePatterns = d.title_patterns || [];
  const selfVideos = self.all_v || [];

  return (
    <Box>
      <SectionCard>
        {generating && (
          <Box sx={{ mb: 1.5 }}>
            <Box display="flex" alignItems="center" gap={1} mb={0.75}>
              <CircularProgress size={16} />
              <Typography variant="caption" color="text.secondary">
                Đang sinh báo cáo SEO… {mmss(elapsed)} (thường ~2 phút)
              </Typography>
            </Box>
            <LinearProgress
              variant="determinate"
              color={theme.palette.mode === "dark" ? "success" : "primary"}
              value={Math.min(95, (elapsed / 120) * 100)}
            />
          </Box>
        )}
        {msg && (
          <Typography variant="caption" color="text.secondary" sx={{ display: "block", mb: 1 }}>
            {msg}
          </Typography>
        )}
        {content ? (
          <Markdown text={content} />
        ) : (
          !generating && (
            <EmptyState text='Chưa có báo cáo SEO. Bấm "Sinh báo cáo SEO" hoặc chạy WL để tạo.' />
          )
        )}
      </SectionCard>

      <PhaseTitle>Số liệu tham chiếu</PhaseTitle>

      {!report ? (
        <SectionCard>
          {reportLoading ? (
            <Box display="flex" alignItems="center" gap={1}>
              <CircularProgress size={16} />
              <Typography variant="caption" color="text.secondary">
                Đang tải số liệu tham chiếu…
              </Typography>
            </Box>
          ) : (
            <EmptyState text="Chọn watchlist để xem số liệu." />
          )}
        </SectionCard>
      ) : (
        <>
      <SectionCard
        title="Tổng quan SEO"
        subtitle={`Watchlist: ${d.wl || ""}${d.date ? ` • ${d.date}` : ""}`}
      >
        <StatGrid
          stats={[
            { label: "SEO score kênh chính", value: self.seo },
            { label: "Từ khoá ngách", value: kwRows.length },
            { label: "Đối thủ theo dõi", value: (d.competitors || []).length },
            { label: "Khoảng trống nội dung", value: gaps.length },
          ]}
        />
      </SectionCard>

      <SectionCard title="1.1 · Đối thủ & thị trường ngách" subtitle="So sánh tăng trưởng (SocialBlade)">
        {sb.length ? (
          <DataTable
            columns={[
              { key: "title", label: "Kênh", render: (r) => (r.is_self ? `★ ${r.title}` : r.title) },
              { key: "subs", label: "Subs", align: "right", render: (r) => num(r.subs) },
              { key: "subs_g", label: "Δ Subs", align: "right", render: (r) => num(r.subs_g) },
              { key: "views_g", label: "Δ Views", align: "right", render: (r) => num(r.views_g) },
              { key: "avg_sub", label: "Subs/ngày", align: "right", render: (r) => num(r.avg_sub) },
            ]}
            rows={sb}
            maxHeight={420}
          />
        ) : (
          <EmptyState text="Chưa có dữ liệu đối thủ." />
        )}
      </SectionCard>

      {gaps.length > 0 && (
        <SectionCard
          title="Khoảng trống nội dung (Topic Gap)"
          subtitle="Từ khoá đối thủ ăn mà kênh chính chưa khai thác"
        >
          <DataTable
            columns={[
              { key: "keyword", label: "Từ khoá" },
              { key: "n_competitors", label: "Số đối thủ", align: "right" },
              { key: "competitor_video_views_median", label: "View trung vị", align: "right", render: (r) => num(r.competitor_video_views_median) },
              { key: "competitor_top_video_title", label: "Video top đối thủ" },
            ]}
            rows={gaps}
            maxHeight={420}
          />
        </SectionCard>
      )}

      <SectionCard title="1.2 · Phân tích từ khoá">
        {kwRows.length ? (
          <DataTable
            columns={[
              { key: "kw", label: "Từ khoá" },
              { key: "vol", label: "Volume (KT)", align: "right", render: (r) => num(r.vol) },
              { key: "comp", label: "Cạnh tranh", align: "right", render: (r) => num(r.comp) },
              { key: "rc", label: "Kết quả YT", align: "right", render: (r) => num(r.rc) },
            ]}
            rows={kwRows}
            maxHeight={480}
          />
        ) : (
          <EmptyState text="Chưa có từ khoá enrich." />
        )}
      </SectionCard>

      <SectionCard
        title="2.3 · SEO components kênh chính"
        subtitle={self.seo != null ? `SEO score: ${self.seo}` : ""}
      >
        {seoComps.length ? (
          <DataTable
            columns={[
              { key: "name", label: "Thành phần" },
              { key: "avg", label: "TB", align: "right", render: (r) => num(r.avg) },
              { key: "max", label: "Max", align: "right", render: (r) => num(r.max) },
            ]}
            rows={seoComps}
          />
        ) : (
          <EmptyState text="Chưa có dữ liệu SEO components của kênh chính." />
        )}
      </SectionCard>

      <SectionCard
        title="Công thức tiêu đề (data-driven)"
        subtitle={d.title_n ? `${d.title_n} video phân tích` : ""}
      >
        {titlePatterns.length ? (
          <DataTable
            columns={[
              { key: "feat", label: "Đặc trưng" },
              { key: "n", label: "Số video", align: "right" },
              { key: "med_with", label: "Median có", align: "right", render: (r) => num(r.med_with) },
              { key: "med_without", label: "Median không", align: "right", render: (r) => num(r.med_without) },
              { key: "lift", label: "Lift", align: "right", render: (r) => (r.lift != null ? `${r.lift}x` : "—") },
            ]}
            rows={titlePatterns}
          />
        ) : (
          <EmptyState text="Chưa đủ video kênh chính để rút công thức tiêu đề." />
        )}
      </SectionCard>

      <SectionCard title="3.1 · Hiệu suất video kênh chính">
        {selfVideos.length ? (
          <DataTable
            columns={[
              { key: "title", label: "Video", render: (r) => r.title },
              { key: "views", label: "Views", align: "right", render: (r) => num(r.views) },
              { key: "vpd", label: "View/ngày", align: "right", render: (r) => num(Math.round(r.vpd || 0)) },
              { key: "age_days", label: "Tuổi (ngày)", align: "right" },
              { key: "eng", label: "Eng %", align: "right", render: (r) => (r.eng != null ? `${r.eng}%` : "—") },
            ]}
            rows={selfVideos}
            maxHeight={480}
          />
        ) : (
          <EmptyState text="Chưa có video kênh chính." />
        )}
      </SectionCard>
        </>
      )}
    </Box>
  );
};

export default SeoReport;
