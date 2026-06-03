// components/research/useSeoReport.js
// State + sinh/poll báo cáo SEO (Claude CLI) cho 1 watchlist. Tách khỏi UI
// để control (dropdown ngày + nút sinh) đặt chung hàng với chọn watchlist.
import { useEffect, useRef, useState } from "react";
import { generateSeoReport, getSeoReports } from "../../services/researchService";

export default function useSeoReport(wid, enabled = true) {
  const [items, setItems] = useState([]);
  const [selId, setSelId] = useState("");
  const [content, setContent] = useState("");
  const [generating, setGenerating] = useState(false);
  const [elapsed, setElapsed] = useState(0);
  const [msg, setMsg] = useState("");
  const pollRef = useRef(null);
  const timerRef = useRef(null);

  const applySelected = (r) => {
    if (r.selected) {
      setSelId(r.selected.id);
      setContent(r.selected.content || "");
    } else {
      setSelId("");
      setContent("");
    }
  };

  const stopPoll = () => {
    if (pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }
  };

  const stopTimer = () => {
    if (timerRef.current) {
      clearInterval(timerRef.current);
      timerRef.current = null;
    }
  };

  const startTimer = () => {
    stopTimer();
    setElapsed(0);
    timerRef.current = setInterval(() => setElapsed((s) => s + 1), 1000);
  };

  // Poll mỗi 5s tới khi sinh xong → tự hiển thị báo cáo mới nhất.
  const startPoll = (prevId) => {
    stopPoll();
    pollRef.current = setInterval(async () => {
      try {
        const r = await getSeoReports(wid);
        setItems(r.items || []);
        setGenerating(!!r.generating);
        if (!r.generating) {
          stopPoll();
          stopTimer();
          applySelected(r);
          const latest = r.items?.[0]?.id || "";
          setMsg(
            latest && latest !== prevId
              ? ""
              : "Sinh không thành công (kiểm tra claude.exe trên máy chủ)."
          );
        }
      } catch (e) {
        // lỗi tạm thời → tiếp tục poll
      }
    }, 5000);
  };

  const load = async (id = "") => {
    if (!wid) return;
    setMsg("");
    try {
      const r = await getSeoReports(wid, id);
      setItems(r.items || []);
      setGenerating(!!r.generating);
      applySelected(r);
      if (r.generating && !pollRef.current) {
        startTimer();
        startPoll(r.items?.[0]?.id || "");
      }
    } catch (e) {
      setMsg(e?.response?.data?.detail || e.message);
    }
  };

  useEffect(() => {
    if (enabled && wid) {
      load("");
    } else {
      setItems([]);
      setSelId("");
      setContent("");
      setGenerating(false);
      setMsg("");
    }
    return () => {
      stopPoll();
      stopTimer();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [wid, enabled]);

  const select = (id) => load(id);

  const generate = async () => {
    if (!wid) return;
    setMsg("");
    const prevId = items?.[0]?.id || "";
    try {
      await generateSeoReport(wid);
      setGenerating(true);
      startTimer();
      startPoll(prevId);
    } catch (e) {
      setMsg(e?.response?.data?.detail || e.message);
    }
  };

  return { items, selId, content, generating, elapsed, msg, select, generate };
}
