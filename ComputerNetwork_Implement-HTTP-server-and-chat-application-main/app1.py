import threading
import socket
import time
import json
from unicodedata import name
import requests

# ========================================================
# HÀM START_PEER (Lấy từ testp2p.py)
#
# Hàm này làm 2 việc:
# 1. (Vai trò Server): Chạy 1 luồng 'listener' để lắng nghe
#    tin nhắn TCP thô trên cổng 'port' (ví dụ: 9001).
# 2. (Vai trò Client): Chủ động gọi đến Tracker (cổng 9000)
#    để đăng ký và gửi tin nhắn.
# ========================================================
def start_peer(name, port, peer_name=None, message=None):
    
    # --- 1. VAI TRÒ SERVER (Lắng nghe ở 'port') ---
    def listener():
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            # Ràng buộc vào cổng được chỉ định (ví dụ: 9001)
            s.bind(("127.0.0.1", port))
        except OSError as e:
            print(f"[{name}] (Vai tro Server) LOI FATAL: Port {port} da duoc su dung. {e}")
            return
            
        s.listen(5)
        print(f"[{name}] (Vai tro Server) Dang lang nghe tin nhan TCP o 127.0.0.1:{port}")
        
        while True:
            try:
                conn, addr = s.accept()
                data = conn.recv(1024).decode()
                if data:
                    # In tin nhắn P2P nhận được
                    print(f"[{name}] (Vai tro Server) Nhan duoc tin: {data}")
                conn.close()
            except Exception as e:
                print(f"[{name}] (Vai tro Server) Loi listener: {e}")

    # Chạy luồng listener
    t = threading.Thread(target=listener, daemon=True)
    t.start()
    time.sleep(0.5) # Chờ listener sẵn sàng

    # --- 2. VAI TRÒ CLIENT (Gọi đến Tracker 9000) ---
    TRACKER_URL = "http://127.0.0.1:9000"

    # Đăng ký (register) với Tracker 9000
    try:
        r = requests.post(f"{TRACKER_URL}/add-list",
                          json={"user": name, "item":"active", "host":"127.0.0.1","port":port})
        print(f"[{name}] (Vai tro Client) Dang ky voi Tracker 9000: {r.text}")
    except requests.exceptions.ConnectionError:
        print(f"[{name}] (Vai tro Client) LOI: Khong ket noi duoc voi Tracker 9000.")
        print("          Ban da chay 'py start_backend.py --server-port 9000' chua?")
        return # Dừng nếu không kết nối được

    # (Tùy chọn) Kết nối với một peer khác
    if peer_name:
        r = requests.post(f"{TRACKER_URL}/connect-peer",
                          json={"peer": peer_name})
        print(f"[{name}] (Vai tro Client) Ket noi voi '{peer_name}': {r.text}")
    
    r = requests.get(f"{TRACKER_URL}/get-list")
    print(f"[{name}] (Vai tro Client) Lay danh sach list: {r.json()}")
    
        # --- AUTO CONNECT (tự refresh cho đến khi connect được thì dừng) ---
    def auto_refresh_connect():
        known_peers = set()
        print(f"[{name}] (Auto-connect) Dang tim cac peer khac de ket noi...")
        while True:
            try:
                r_check = requests.get(f"{TRACKER_URL}/get-list")
                data = r_check.json()
                peer_list = data.get("list", [])
                new_connected = False

                for peer in peer_list:
                    peer_name_other = peer.get("user")
                    if peer_name_other and peer_name_other != name and peer_name_other not in known_peers:
                        resp = requests.post(
                            f"{TRACKER_URL}/connect-peer",
                            json={"from": name, "peer": peer_name_other}
                        )
                        print(f"[{name}] (Auto-connect) Phat hien peer moi '{peer_name_other}', da ket noi: {resp.text}")
                        known_peers.add(peer_name_other)
                        new_connected = True

                if new_connected:
                    print(f"[{name}] (Auto-connect) Ket noi thanh cong voi tat ca peer hien co → dung auto-refresh.")
                    break

                time.sleep(5)  # chờ 5s rồi thử lại
            except Exception as e:
                print(f"[{name}] (Auto-connect) Loi: {e}")
                time.sleep(5)

    # chạy thread nền để tự động tìm peer mới
    threading.Thread(target=auto_refresh_connect, daemon=True).start()



    # (Tùy chọn) Gửi tin nhắn riêng
    if peer_name and message:
        r = requests.post(f"{TRACKER_URL}/send-peer",
                          json={"from": name, "to": peer_name, "message": message})
        print(f"[{name}] (Vai tro Client) Gui tin nhan toi '{peer_name}': {r.text}")

    print(f"--- [{name}] da khoi dong xong. Dang chay... ---")
    # Giữ cho thread chính (ứng dụng) sống
    while True:
        time.sleep(5)

# =========================
# Main
# =========================
if __name__ == "__main__":
    print("--- Khoi chay PEER 'app1' ---")
    
    # Chạy peer 'app1'
    # Nó sẽ LẮNG NGHE ở cổng 9001 (để khớp với file proxy)
    # Và nó sẽ chủ động GỌI ĐẾN server 9000 (Tracker)
    
    # Cú pháp 1: Chỉ khởi động
    start_peer(name="app1", port=9001)
    
    # Cú pháp 2: Khởi động và gửi tin nhắn cho 'app2' ngay lập- tức
    # (Bạn cần chạy một 'app2' ở terminal khác)
    # start_peer(name="app1", port=9001, peer_name="app2", message="Hello app2 tu app1!")