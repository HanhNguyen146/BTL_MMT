import socket
import threading
import requests
import json
import time

# ===============================
# Cấu hình
# ===============================
BACKEND_URL = "http://127.0.0.1:9000"   # backend server bạn đang chạy
MY_HOST = "127.0.0.1"
MY_PORT = 9102
MY_NAME = "clientB"

# ===============================
# Thread lắng nghe tin nhắn P2P
# ===============================
def peer_listener(host, port):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind((host, port))
    s.listen(5)
    print(f"[{MY_NAME}] Listening for peer messages on {host}:{port} ...")
    while True:
        conn, addr = s.accept()
        data = conn.recv(1024).decode("utf-8")
        if data:
            print(f"[{MY_NAME}] Received: {data}")
        conn.close()

# ===============================
# Khởi động listener trong thread riêng
# ===============================
thread = threading.Thread(target=peer_listener, args=(MY_HOST, MY_PORT), daemon=True)
thread.start()
time.sleep(1)

# ===============================
# Đăng ký bản thân vào server
# ===============================
print(f"[{MY_NAME}] Registering to backend...")

add_data = {
    "user": MY_NAME,
    "item": "active_peerB",
    "host": MY_HOST,
    "port": MY_PORT
}
r = requests.post(f"{BACKEND_URL}/add-list", json=add_data)
print("ADD-LIST RESPONSE:", r.status_code, r.text)

# ===============================
# Kết nối tới 1 peer khác (ví dụ: clientB)
# ===============================
connect_data = {"peer": "clientA"}
r = requests.post(f"{BACKEND_URL}/connect-peer", json=connect_data)
print("CONNECT-PEER RESPONSE:", r.status_code, r.text)

# ===============================
# Gửi broadcast tin nhắn
# ===============================
broad_data = {"from": MY_NAME, "message": "Xin chào tất cả peer!"}
r = requests.post(f"{BACKEND_URL}/broadcast-peer", json=broad_data)
print("BROADCAST RESPONSE:", r.status_code, r.text)

# ===============================
# Gửi tin riêng tới clientB
# ===============================
send_data = {"from": MY_NAME, "to": "clientA", "message": "Hello A!"}
r = requests.post(f"{BACKEND_URL}/send-peer", json=send_data)
print("SEND-PEER RESPONSE:", r.status_code, r.text)

# ===============================
# Đợi nhận tin
# ===============================
print("\n--- Waiting for incoming messages ---\n")
while True:
    time.sleep(1)
