import socket
import threading
import json
import time

TRACKER_IP = "127.0.0.1"
TRACKER_PORT = 8000

# ======== Tracker Server ============
class TrackerServer:
    def __init__(self, ip=TRACKER_IP, port=TRACKER_PORT):
        self.ip = ip
        self.port = port
        self.peers = {}  # {peer_id: (ip, port)}

    def handle_client(self, conn, addr):
        try:
            msg = conn.recv(1024).decode()
            data = json.loads(msg)
            cmd = data.get("cmd")

            if cmd == "register":
                peer_id = data["peer_id"]
                self.peers[peer_id] = (data["ip"], data["port"])
                print(f"[Tracker] Registered peer {peer_id} at {data['ip']}:{data['port']}")
                conn.send(b"OK")

            elif cmd == "get_peers":
                conn.send(json.dumps(self.peers).encode())

        except Exception as e:
            print("[Tracker] Error:", e)
        finally:
            conn.close()

    def run(self):
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.bind((self.ip, self.port))
        server.listen(5)
        print(f"[Tracker] Listening on {self.ip}:{self.port}")
        while True:
            conn, addr = server.accept()
            threading.Thread(target=self.handle_client, args=(conn, addr), daemon=True).start()


# ======== Peer Node ============
class PeerNode:
    def __init__(self, peer_id, ip, port):
        self.peer_id = peer_id
        self.ip = ip
        self.port = port
        self.peers = {}

    def register_with_tracker(self):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.connect((TRACKER_IP, TRACKER_PORT))
        msg = json.dumps({"cmd": "register", "peer_id": self.peer_id, "ip": self.ip, "port": self.port})
        s.send(msg.encode())
        resp = s.recv(1024)
        print(f"[{self.peer_id}] Registered with tracker -> {resp.decode()}")
        s.close()

    def update_peers(self):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.connect((TRACKER_IP, TRACKER_PORT))
        msg = json.dumps({"cmd": "get_peers"})
        s.send(msg.encode())
        data = s.recv(4096)
        self.peers = json.loads(data.decode())
        print(f"[{self.peer_id}] Peer list:", self.peers)
        s.close()

    def send_message(self, target_id, msg):
        if target_id not in self.peers:
            print(f"[{self.peer_id}] Target {target_id} not found")
            return
        ip, port = self.peers[target_id]
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.connect((ip, port))
        s.send(f"{self.peer_id}: {msg}".encode())
        s.close()
        print(f"[{self.peer_id}] Sent message to {target_id}")

    def listen_for_messages(self):
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.bind((self.ip, self.port))
        server.listen(5)
        print(f"[{self.peer_id}] Listening for P2P on {self.ip}:{self.port}")
        while True:
            conn, addr = server.accept()
            msg = conn.recv(1024).decode()
            print(f"[{self.peer_id}] Received: {msg}")
            conn.close()


# ======== Test Launcher ============
if __name__ == "__main__":
    # Step 1: Start Tracker
    threading.Thread(target=TrackerServer().run, daemon=True).start()
    time.sleep(1)

    # Step 2: Start 2 Peers
    peer1 = PeerNode("Peer1", "127.0.0.10", 9001)
    peer2 = PeerNode("Peer2", "127.0.0.11", 9002)

    # Listen threads
    threading.Thread(target=peer1.listen_for_messages, daemon=True).start()
    threading.Thread(target=peer2.listen_for_messages, daemon=True).start()
    time.sleep(1)

    # Register with tracker
    peer1.register_with_tracker()
    peer2.register_with_tracker()

    # Update peer lists
    peer1.update_peers()
    peer2.update_peers()

    # Step 3: Send messages (P2P)
    time.sleep(1)
    peer1.send_message("Peer2", "Hello from Peer1!")
    peer2.send_message("Peer1", "Hey Peer1, got your message!")
    time.sleep(3)
