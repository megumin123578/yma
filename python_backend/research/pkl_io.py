# -*- coding: utf-8 -*-
"""I/O an toàn cho pkl đã save (.history/channels/*.pkl).

Khi pipeline chạy song song nhiều luồng (YouTube monitor + SocialBlade
refresh + Google Trends refresh), nhiều luồng có thể đọc-sửa-ghi cùng 1
file pkl. Module này cung cấp lock GLOBAL để serialize tất cả thao tác
read-modify-write → tránh race condition.

Lưu ý: lock chỉ work trong CÙNG 1 process Python. YouTube monitor save pkl
trong process con (ProcessPool) - không share lock với main process. Tuy
nhiên YouTube chỉ save MỖI PKL 1 LẦN khi cào xong, sau đó không động đến
→ không có race với SB/Trends thread trong main process.
"""
import pickle
import threading

# Lock global cho mọi thao tác pkl. Dùng RLock để 1 thread có thể acquire
# nhiều lần (lồng nhau) mà không deadlock.
_LOCK = threading.RLock()


def safe_read(path):
    """Đọc pkl an toàn. Trả None nếu file không tồn tại/lỗi."""
    with _LOCK:
        try:
            with open(path, "rb") as f:
                return pickle.load(f)
        except Exception:
            return None


def safe_write(path, data):
    """Ghi pkl an toàn. Trả True nếu thành công."""
    with _LOCK:
        try:
            with open(path, "wb") as f:
                pickle.dump(data, f, protocol=pickle.HIGHEST_PROTOCOL)
            return True
        except Exception:
            return False


def safe_update(path, update_fn):
    """Read-modify-write trong cùng 1 lock. update_fn(data) sẽ được gọi
    với dict đã load - sửa tại chỗ. Trả True nếu thành công."""
    with _LOCK:
        try:
            with open(path, "rb") as f:
                data = pickle.load(f)
            update_fn(data)
            with open(path, "wb") as f:
                pickle.dump(data, f, protocol=pickle.HIGHEST_PROTOCOL)
            return True
        except Exception:
            return False
