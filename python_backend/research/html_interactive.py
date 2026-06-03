# -*- coding: utf-8 -*-
"""HTML interactive helpers — vanilla JS cho báo cáo HTML.

Trả về string `<script>...</script>` chèn vào báo cáo HTML để:
- Sort cột bất kỳ khi click header (`<th>` có class `js-sortable`)
- Filter table theo input box trên đầu (class `js-filter-input`
  data-target="#table_id")
- Search global (input class `js-global-search`)
- Drill-down row (click row có class `js-expandable` → toggle chi tiết)

Cách dùng trong core/html_report.py:
    from .html_interactive import inject_interactive_script
    html = ...build báo cáo...
    html = html.replace("</body>", inject_interactive_script() + "</body>")
"""


INTERACTIVE_CSS = """
<style>
.js-sortable { cursor: pointer; user-select: none; position: relative; }
.js-sortable:hover { background: #f0f0f0; }
.js-sortable::after { content: " ⇅"; opacity: 0.3; font-size: 0.8em; }
.js-sortable.sort-asc::after { content: " ▲"; opacity: 1; color: #0a7; }
.js-sortable.sort-desc::after { content: " ▼"; opacity: 1; color: #0a7; }
.js-filter-input, .js-global-search {
  padding: 4px 8px; border: 1px solid #ccc; border-radius: 4px;
  font-size: 14px; margin-bottom: 6px; width: 220px;
}
.js-global-search { width: 320px; }
.js-expandable { cursor: pointer; }
.js-expandable:hover { background: #fafbe8; }
.js-expand-detail { background: #f9f9f9; padding: 8px 12px;
  border-left: 3px solid #0a7; font-size: 0.92em; }
tr.js-hidden { display: none; }
</style>
"""

INTERACTIVE_JS = """
<script>
(function(){
  // ============== 1. SORT TABLE BY COLUMN ==============
  document.querySelectorAll('th.js-sortable').forEach(function(th){
    th.addEventListener('click', function(){
      var table = th.closest('table');
      var tbody = table.querySelector('tbody');
      if (!tbody) return;
      var rows = Array.from(tbody.querySelectorAll('tr'));
      var idx = Array.from(th.parentNode.children).indexOf(th);
      var asc = !th.classList.contains('sort-asc');
      // Clear other sort classes
      th.parentNode.querySelectorAll('th').forEach(function(h){
        h.classList.remove('sort-asc', 'sort-desc');
      });
      th.classList.add(asc ? 'sort-asc' : 'sort-desc');
      // Sort
      rows.sort(function(a, b){
        var av = (a.children[idx]||{}).textContent || '';
        var bv = (b.children[idx]||{}).textContent || '';
        // Try number compare first
        var an = parseFloat(av.replace(/[^\\d.-]/g,''));
        var bn = parseFloat(bv.replace(/[^\\d.-]/g,''));
        if (!isNaN(an) && !isNaN(bn)) {
          return asc ? (an - bn) : (bn - an);
        }
        return asc ? av.localeCompare(bv) : bv.localeCompare(av);
      });
      rows.forEach(function(r){ tbody.appendChild(r); });
    });
  });

  // ============== 2. FILTER TABLE (input per-table) ==============
  document.querySelectorAll('.js-filter-input').forEach(function(inp){
    inp.addEventListener('input', function(){
      var target = inp.dataset.target;
      if (!target) return;
      var table = document.querySelector(target);
      if (!table) return;
      var query = inp.value.toLowerCase().trim();
      var rows = table.querySelectorAll('tbody tr');
      rows.forEach(function(r){
        if (!query) { r.classList.remove('js-hidden'); return; }
        var text = r.textContent.toLowerCase();
        if (text.indexOf(query) >= 0) r.classList.remove('js-hidden');
        else r.classList.add('js-hidden');
      });
    });
  });

  // ============== 3. GLOBAL SEARCH (filter all js-table) ==============
  document.querySelectorAll('.js-global-search').forEach(function(inp){
    inp.addEventListener('input', function(){
      var query = inp.value.toLowerCase().trim();
      document.querySelectorAll('table.js-table tbody tr').forEach(function(r){
        if (!query) { r.classList.remove('js-hidden'); return; }
        var text = r.textContent.toLowerCase();
        if (text.indexOf(query) >= 0) r.classList.remove('js-hidden');
        else r.classList.add('js-hidden');
      });
    });
  });

  // ============== 4. DRILL-DOWN ROW ==============
  document.querySelectorAll('tr.js-expandable').forEach(function(row){
    row.addEventListener('click', function(e){
      // Ignore click on link/button inside row
      if (e.target.tagName === 'A' || e.target.tagName === 'BUTTON') return;
      var detailId = row.dataset.detail;
      if (!detailId) return;
      var detail = document.getElementById(detailId);
      if (!detail) return;
      var hidden = detail.style.display === 'none' || !detail.style.display;
      detail.style.display = hidden ? 'block' : 'none';
    });
  });
})();
</script>
"""


def inject_interactive_html() -> str:
    """Trả về chuỗi CSS + JS để chèn vào báo cáo HTML."""
    return INTERACTIVE_CSS + INTERACTIVE_JS


def make_sortable_th(label: str) -> str:
    """Render <th class="js-sortable">label</th>."""
    return f'<th class="js-sortable">{label}</th>'


def make_filter_input(target_table_id: str, placeholder: str = "") -> str:
    """Render filter input cho 1 table cụ thể."""
    p = placeholder or f"Lọc {target_table_id}..."
    return (f'<input class="js-filter-input" data-target="#{target_table_id}" '
            f'placeholder="{p}">')


def make_global_search(placeholder: str = "🔎 Tìm trong toàn bộ báo cáo...") -> str:
    """Render search input global (filter tất cả table.js-table)."""
    return (f'<input class="js-global-search" placeholder="{placeholder}">')


def make_expandable_row(row_html: str, detail_id: str,
                        detail_html: str = "") -> str:
    """Render row có drill-down + detail panel.

    Returns: <tr class="js-expandable" data-detail="X">...</tr>
             <tr><td colspan="999"><div id="X" class="js-expand-detail"
                 style="display:none">...</div></td></tr>
    """
    return (
        f'<tr class="js-expandable" data-detail="{detail_id}">{row_html}</tr>'
        f'<tr><td colspan="99"><div id="{detail_id}" '
        f'class="js-expand-detail" style="display:none">'
        f'{detail_html}</div></td></tr>'
    )
