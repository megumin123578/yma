import pickle
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

TOKEN_FILE = "token/megumin.pickle"


# ===========================
# TABLE PRINTER
# ===========================
def print_table(headers, rows):
    if not rows:
        print("\n⚠ No data returned.\n")
        return

    width = [len(h) for h in headers]
    for row in rows:
        for i, col in enumerate(row):
            width[i] = max(width[i], len(str(col)))

    def fmt_row(row):
        return " | ".join(str(row[i]).ljust(width[i]) for i in range(len(row)))

    print(fmt_row(headers))
    print("-" * (sum(width) + 3 * (len(headers) - 1)))

    for row in rows:
        print(fmt_row(row))


# ===========================
# MAIN APP
# ===========================
def main():
    print("\n=== YouTube Analytics Testing Tool ===\n")

    # Load OAuth token
    try:
        with open(TOKEN_FILE, "rb") as f:
            creds = pickle.load(f)
    except:
        print("❌ Cannot load token. Run OAuth login first.")
        return

    yta = build("youtubeAnalytics", "v2", credentials=creds)

    # User input
    dimensions = input("Nhập DIMENSIONS (ví dụ: video, insightTrafficSourceType, day): ").strip()
    metrics = input("Nhập METRICS (phân tách bằng dấu phẩy): ").strip()

    start_date = input("Start date (yyyy-mm-dd): ").strip() or "2023-01-01"
    end_date   = input("End date   (yyyy-mm-dd): ").strip() or "2025-12-31"

    # Query
    print("\n=== Sending Request ===")
    print(f"Dimensions → {dimensions}")
    print(f"Metrics    → {metrics}")
    print(f"Date range → {start_date} → {end_date}\n")

    try:
        resp = yta.reports().query(
            ids="channel==MINE",
            startDate=start_date,
            endDate=end_date,
            dimensions=dimensions,
            metrics=metrics,
        ).execute()

        headers = [c["name"] for c in resp.get("columnHeaders", [])]
        rows = resp.get("rows", [])

        print("\n=== RESULT TABLE ===\n")
        print_table(headers, rows)

    except HttpError as e:
        print("\n❌ API ERROR:")
        print(e)
        print("\n⚠ Lý do thường gặp:")
        print(" - Dimension không hỗ trợ metrics")
        print(" - Metrics không hợp lệ cho report đó")
        print(" - Sai dấu phẩy / khoảng trắng")
        print(" - Cần scope YouTube Analytics")
    except Exception as e:
        print("\n❌ Unexpected error:")
        print(e)


if __name__ == "__main__":
    main()
