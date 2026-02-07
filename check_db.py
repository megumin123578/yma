
import os
from sqlalchemy import create_engine, text

def check():
    pg_url = os.getenv("PG_URL")
    if not pg_url:
        print("PG_URL not found")
        return
    
    engine = create_engine(pg_url)
    with engine.connect() as conn:
        # Check zzTESTzz videos
        v_count = conn.execute(text("SELECT count(*) FROM videos WHERE account_tag = 'zzTESTzz'")).scalar()
        print(f"Videos for zzTESTzz: {v_count}")
        
        r_count = conn.execute(text("SELECT count(*) FROM reach_video_metrics WHERE account_tag = 'zzTESTzz'")).scalar()
        print(f"Reach rows for zzTESTzz: {r_count}")

        # Check stats for zzTESTzz
        s_count = conn.execute(text("""
            SELECT count(*) 
            FROM video_daily_stats s 
            JOIN videos v ON s.video_id = v.video_id 
            WHERE v.account_tag = 'zzTESTzz' 
            AND s.day >= '2026-01-10'
        """)).scalar()
        print(f"Stats rows for zzTESTzz since 2026-01-10: {s_count}")
        
        # Sample data
        sample = conn.execute(text("""
            SELECT v.video_id, SUM(s.views) as total_views
            FROM videos v
            JOIN video_daily_stats s ON v.video_id = s.video_id
            WHERE v.account_tag = 'zzTESTzz'
            AND s.day >= '2026-01-10'
            GROUP BY v.video_id
            HAVING SUM(s.views) > 0
            LIMIT 5
        """)).fetchall()
        print(f"Sample videos with views: {sample}")

if __name__ == "__main__":
    check()
