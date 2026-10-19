# -*- coding: utf-8 -*-
"""
HabitFlow Pro - Phần mềm Theo Dõi Thói Quen & Phân Tích Đa Kỳ
Desktop application powered by pywebview (Native Windows Desktop Bridge)
"""

import os
import sys
import json
import datetime
import random
import tempfile
import threading
import webview

# Xác định đường dẫn thư mục thực thi (lưu habit_data.json) và thư mục tài nguyên (nạp ui.html & js/)
if getattr(sys, "frozen", False):
    BASE_DIR = os.path.dirname(os.path.abspath(sys.executable))
    RESOURCE_DIR = getattr(sys, "_MEIPASS", BASE_DIR)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    RESOURCE_DIR = BASE_DIR

DATA_FILE = os.path.join(BASE_DIR, "habit_data.json")
UI_FILE = os.path.join(RESOURCE_DIR, "ui.html")

# pywebview chạy mỗi lời gọi js_api trên một thread riêng -> tuần tự hóa việc ghi file.
# Lưu ý: lock chỉ ngăn hai lần ghi chồng lên nhau, KHÔNG bảo đảm thứ tự các lần lưu.
_SAVE_LOCK = threading.Lock()


def atomic_write_json(path, data):
    """
    Ghi JSON theo kiểu atomic replacement:
      1. Serialize trước (lỗi dữ liệu -> không chạm vào file đích).
      2. Ghi vào file tạm cùng thư mục, flush + fsync.
      3. os.replace() thay thế file đích trong một thao tác.
    Nếu có lỗi, file tạm được dọn và file đích cũ được giữ nguyên.
    Giới hạn: không bảo đảm chống mọi lỗi phần cứng / mất điện (phụ thuộc
    hệ điều hành, filesystem và cache của ổ đĩa).
    """
    payload = json.dumps(data, indent=2, ensure_ascii=False)
    dir_name = os.path.dirname(os.path.abspath(path))
    fd, tmp_path = tempfile.mkstemp(prefix=".habit_data.", suffix=".tmp", dir=dir_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(payload)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, path)
    except BaseException:
        try:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
        except OSError:
            pass
        raise


def normalize_log_entry(entry):
    """
    Adapter chuẩn hóa 1 bản ghi log (tương thích ngược 100% với kiểu boolean cũ):
      - True/False -> {"completed": bool(entry), "focusMinutes": 0, "sessions": []}
      - dict -> {"completed": bool, "focusMinutes": number, "sessions": [...], "note"?: str}
    """
    if isinstance(entry, bool):
        return {
            "completed": entry,
            "focusMinutes": 0,
            "sessions": []
        }
    if isinstance(entry, (int, float)):
        mins = max(0, round(float(entry), 2))
        return {
            "completed": mins > 0,
            "focusMinutes": int(mins) if mins.is_integer() else mins,
            "sessions": []
        }
    if isinstance(entry, dict):
        raw_sessions = entry.get("sessions")
        sessions = []
        session_sum = 0.0
        if isinstance(raw_sessions, list):
            for s in raw_sessions:
                if isinstance(s, dict):
                    dur = max(0.0, float(s.get("duration", 0) or 0))
                    session_sum += dur
                    sessions.append({
                        "start": s.get("start"),
                        "end": s.get("end"),
                        "duration": int(dur) if dur.is_integer() else round(dur, 2),
                        "mode": "stopwatch" if s.get("mode") == "stopwatch" else "pomodoro",
                        "note": str(s.get("note", "") or "")
                    })
        raw_focus = entry.get("focusMinutes", 0)
        try:
            focus_val = max(0.0, float(raw_focus or 0), session_sum)
        except (TypeError, ValueError):
            focus_val = session_sum
        focus_minutes = int(focus_val) if focus_val.is_integer() else round(focus_val, 2)
        normalized = {
            "completed": bool(entry.get("completed", False)),
            "focusMinutes": focus_minutes,
            "sessions": sessions
        }
        note_val = entry.get("note")
        if isinstance(note_val, str) and note_val.strip():
            normalized["note"] = note_val.strip()
        return normalized
    return {
        "completed": bool(entry),
        "focusMinutes": 0,
        "sessions": []
    }


def normalize_logs_schema(logs):
    """
    Adapter chuyển đổi toàn bộ dict logs[date][habitId] sang schema mới
    nhưng vẫn giữ nguyên tính tương thích ngược với dữ liệu boolean cũ.
    """
    if not isinstance(logs, dict):
        return {}
    normalized_logs = {}
    for date_str, day_map in logs.items():
        if not isinstance(day_map, dict):
            continue
        normalized_logs[date_str] = {}
        for habit_id, val in day_map.items():
            normalized_logs[date_str][habit_id] = normalize_log_entry(val)
    return normalized_logs


def generate_seed_data():
    """
    Sinh dữ liệu mẫu 400 ngày gần nhất (Rich Seed Data từ năm trước sang năm nay)
    cho đúng 5 thói quen cốt lõi:
      1. Đọc sách Toán lý thuyết (Học tập)
      2. Chạy bộ 2km (Thể thao)
      3. Viết tài liệu LaTeX (Kỹ thuật)
      4. Lập trình mô phỏng (Kỹ thuật)
      5. Uống đủ 2L nước (Sức khỏe)
    """
    today = datetime.date.today()
    start_date = datetime.date(2024, 1, 1)

    habits = [
        {
            "id": "habit-1",
            "name": "Đọc sách Toán lý thuyết",
            "category": "Học tập",
            "color": "#3B82F6",
            "icon": "book-open",
            "targetDays": 7,
            "targetMinutes": 30,
            "createdAt": "2025-09-01"
        },
        {
            "id": "habit-2",
            "name": "Chạy bộ 2km",
            "category": "Thể thao",
            "color": "#10B981",
            "icon": "activity",
            "targetDays": 5,
            "targetMinutes": 25,
            "createdAt": "2025-09-01"
        },
        {
            "id": "habit-3",
            "name": "Viết tài liệu LaTeX",
            "category": "Kỹ thuật",
            "color": "#8B5CF6",
            "icon": "file-text",
            "targetDays": 6,
            "targetMinutes": 45,
            "createdAt": "2025-09-01"
        },
        {
            "id": "habit-4",
            "name": "Lập trình mô phỏng",
            "category": "Kỹ thuật",
            "color": "#F59E0B",
            "icon": "code",
            "targetDays": 6,
            "targetMinutes": 50,
            "createdAt": "2025-09-01"
        },
        {
            "id": "habit-5",
            "name": "Uống đủ 2L nước",
            "category": "Sức khỏe",
            "color": "#06B6D4",
            "icon": "droplet",
            "targetDays": 7,
            "targetMinutes": 15,
            "createdAt": "2025-09-01"
        }
    ]

    logs = {}
    random.seed(101)  # Seed cố định để dữ liệu thống nhất, chân thực

    probs = {
        "habit-1": (0.80, 0.70),  # (ngày trong tuần, cuối tuần)
        "habit-2": (0.72, 0.60),
        "habit-3": (0.76, 0.65),
        "habit-4": (0.84, 0.78),
        "habit-5": (0.92, 0.88),
    }

    current = start_date
    while current <= today:
        d_str = current.strftime("%Y-%m-%d")
        logs[d_str] = {}
        is_weekend = current.weekday() >= 5
        days_from_today = (today - current).days

        for h in habits:
            hid = h["id"]
            pw, pwe = probs[hid]
            base_p = pwe if is_weekend else pw

            # Giữ chuỗi hiện tại đang hoạt động ấn tượng
            if hid == "habit-5" and days_from_today < 28:
                logs[d_str][hid] = True
            elif hid == "habit-4" and days_from_today < 16:
                logs[d_str][hid] = True
            elif hid == "habit-1" and days_from_today < 12:
                logs[d_str][hid] = True
            elif hid == "habit-3" and days_from_today < 9:
                logs[d_str][hid] = True
            elif hid == "habit-2" and days_from_today < 6:
                logs[d_str][hid] = True
            else:
                if random.random() < base_p:
                    logs[d_str][hid] = True

        current += datetime.timedelta(days=1)

    categories = [
        {"id": "cat-1", "name": "Học tập", "color": "#6366F1", "icon": "book-open"},
        {"id": "cat-2", "name": "Kỹ thuật", "color": "#F59E0B", "icon": "code"},
        {"id": "cat-3", "name": "Thể thao", "color": "#10B981", "icon": "activity"},
        {"id": "cat-4", "name": "Sức khỏe", "color": "#F43F5E", "icon": "heart"}
    ]

    return {
        "settings": {
            "theme": "dark"
        },
        "categories": categories,
        "habits": habits,
        "logs": logs
    }


class Api:
    """
    Python Bridge API truyền vào js_api của pywebview
    """
    def __init__(self):
        self._window = None

    def set_window(self, window):
        self._window = window

    def load_data(self):
        """
        Đọc dữ liệu từ habit_data.json. Nếu file chưa có thì tự động sinh 400 ngày mẫu.
        Tự động bảo đảm cấu trúc categories động tương thích ngược.
        """
        try:
            if not os.path.exists(DATA_FILE):
                data = generate_seed_data()
                with open(DATA_FILE, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=2, ensure_ascii=False)
                return data

            with open(DATA_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)

            # Đảm bảo trường categories luôn tồn tại trong habit_data.json
            if "categories" not in data or not data["categories"]:
                data["categories"] = [
                    {"id": "cat-1", "name": "Học tập", "color": "#6366F1", "icon": "book-open"},
                    {"id": "cat-2", "name": "Kỹ thuật", "color": "#F59E0B", "icon": "code"},
                    {"id": "cat-3", "name": "Thể thao", "color": "#10B981", "icon": "activity"},
                    {"id": "cat-4", "name": "Sức khỏe", "color": "#F43F5E", "icon": "heart"}
                ]
                with open(DATA_FILE, "w", encoding="utf-8") as fw:
                    json.dump(data, fw, indent=2, ensure_ascii=False)

            return data
        except Exception as e:
            print(f"[Api.load_data] Lỗi: {e}")
            return {"error": str(e)}

    def save_data(self, data_json):
        """
        Ghi dữ liệu xuống habit_data.json (indent=2, ensure_ascii=False) bằng atomic replacement.
        Hợp đồng trả về giữ nguyên: {"status": "ok"|"error", "message": ...}
        """
        try:
            if isinstance(data_json, str):
                data = json.loads(data_json)
            else:
                data = data_json

            with _SAVE_LOCK:
                atomic_write_json(DATA_FILE, data)

            return {"status": "ok", "message": "Đã lưu vào habit_data.json"}
        except Exception as e:
            print(f"[Api.save_data] Lỗi: {e}")
            return {"status": "error", "message": str(e)}

    def export_backup(self):
        """
        Mở hộp thoại lưu file của Windows để xuất bản sao dự phòng
        """
        try:
            window = self._window or (webview.windows[0] if webview.windows else None)
            now = datetime.datetime.now()
            default_filename = f"HabitFlow_Backup_{now.strftime('%Y%m%d_%H%M%S')}.json"

            save_path = None
            if window:
                result = window.create_file_dialog(
                    webview.FileDialog.SAVE,
                    save_filename=default_filename,
                    file_types=('JSON Files (*.json)', 'All Files (*.*)')
                )
                if result:
                    save_path = result if isinstance(result, str) else result[0]

            if not save_path:
                return {"status": "cancelled", "message": "Người dùng đã hủy chọn nơi lưu"}

            # Đọc nội dung hiện tại và sao chép sang save_path
            with open(DATA_FILE, "r", encoding="utf-8") as src:
                content = src.read()
            with open(save_path, "w", encoding="utf-8") as dst:
                dst.write(content)

            return {
                "status": "ok",
                "message": f"Đã xuất sao lưu thành công: {os.path.basename(save_path)}",
                "path": save_path
            }
        except Exception as e:
            print(f"[Api.export_backup] Lỗi: {e}")
            return {"status": "error", "message": str(e)}

    def get_system_date(self):
        """Trả về ngày hôm nay theo giờ địa phương YYYY-MM-DD"""
        return datetime.date.today().strftime("%Y-%m-%d")

    def minimize_window(self):
        """Thu nhỏ cửa sổ xuống Taskbar"""
        try:
            window = self._window or (webview.windows[0] if webview.windows else None)
            if window:
                window.minimize()
                return {"status": "ok"}
        except Exception as e:
            print(f"[Api.minimize_window] Lỗi: {e}")
            return {"status": "error", "message": str(e)}

    def toggle_fullscreen(self):
        """Chuyển đổi toàn màn hình (Fullscreen / Maximize)"""
        try:
            window = self._window or (webview.windows[0] if webview.windows else None)
            if window:
                window.toggle_fullscreen()
                return {"status": "ok"}
        except Exception as e:
            print(f"[Api.toggle_fullscreen] Lỗi: {e}")
            return {"status": "error", "message": str(e)}

    def close_window(self):
        """Đóng ứng dụng"""
        try:
            window = self._window or (webview.windows[0] if webview.windows else None)
            if window:
                window.destroy()
                return {"status": "ok"}
        except Exception as e:
            print(f"[Api.close_window] Lỗi: {e}")
            return {"status": "error", "message": str(e)}


def main():
    api = Api()
    window = webview.create_window(
        title='HabitFlow Pro - Phần mềm Theo Dõi Thói Quen & Phân Tích Đa Kỳ',
        url=UI_FILE,
        js_api=api,
        width=1400,
        height=900,
        min_size=(1100, 750),
        frameless=True,
        easy_drag=True,
        background_color='#070A13'
    )
    api.set_window(window)
    webview.start(debug=False)


if __name__ == '__main__':
    main()

