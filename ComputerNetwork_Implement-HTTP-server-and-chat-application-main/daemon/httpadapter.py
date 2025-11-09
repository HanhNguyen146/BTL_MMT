#
# Copyright (C) 2025 pdnguyen of HCMC University of Technology VNU-HCM.
# All rights reserved.
# This file is part of the CO3093/CO3094 course.
#
# WeApRous release
#
# The authors hereby grant to Licensee personal permission to use
# and modify the Licensed Source Code for the sole purpose of studying
# while attending the course
#

"""
daemon.httpadapter
~~~~~~~~~~~~~~~~~

This module provides a http adapter object to manage and persist 
http settings (headers, bodies). The adapter supports both
raw URL paths and RESTful route definitions, and integrates with
Request and Response objects to handle client-server communication.
"""

from .request import Request
from .response import Response
from .dictionary import CaseInsensitiveDict

_global_list = []
peer_list = {}
class HttpAdapter:
    """
    A mutable :class:`HTTP adapter <HTTP adapter>` for managing client connections
    and routing requests.

    The `HttpAdapter` class encapsulates the logic for receiving HTTP requests,
    dispatching them to appropriate route handlers, and constructing responses.
    It supports RESTful routing via hooks and integrates with :class:`Request <Request>` 
    and :class:`Response <Response>` objects for full request lifecycle management.

    Attributes:
        ip (str): IP address of the client.
        port (int): Port number of the client.
        conn (socket): Active socket connection.
        connaddr (tuple): Address of the connected client.
        routes (dict): Mapping of route paths to handler functions.
        request (Request): Request object for parsing incoming data.
        response (Response): Response object for building and sending replies.
    """

    __attrs__ = [
        "ip",
        "port",
        "conn",
        "connaddr",
        "routes",
        "request",
        "response",
    ]

    def __init__(self, ip, port, conn, connaddr, routes):
        self.ip = ip
        self.port = port
        self.conn = conn
        self.connaddr = connaddr
        self.routes = routes
        self.request = Request()
        self.response = Response()

    def handle_client(self, conn, addr, routes):
        from . import backend
        import socket
        import os
        import time
        import urllib.parse
    
        import json
        from . import handler_login
        from .session_store import get_user_from_session

        self.conn = conn
        self.connaddr = addr
        req = self.request
        resp = self.response

        msg = b""
        conn.settimeout(0.5)
        deadline = time.time() + 2.0
        raw_req = ""

        handled = False

        while True:
            try:
                chunk = conn.recv(4096)
                if not chunk:
                    break
                msg += chunk
            except socket.timeout:
                if time.time() > deadline:
                    break
                continue

            try:
                raw_req = msg.decode(errors="ignore")
            except Exception:
                raw_req = ""

            header_end = raw_req.find("\r\n\r\n")
            if header_end == -1:
                if time.time() > deadline:
                    break
                else:
                    continue

            headers_part = raw_req[:header_end]
            content_len = 0
            for line in headers_part.split("\r\n"):
                if line.lower().startswith("content-length:"):
                    try:
                        content_len = int(line.split(":", 1)[1].strip())
                    except Exception:
                        content_len = 0
                    break

            body_bytes_len = len(msg) - (header_end + 4)
            if content_len == 0 or body_bytes_len >= content_len:
                break

            if time.time() > deadline:
                break
            deadline = max(deadline, time.time() + 2.0)
            continue

        try:
            raw_req = msg.decode(errors="ignore")
        except Exception:
            raw_req = ""

        try:
            first_line = raw_req.splitlines()[0] if raw_req else ""
        except Exception:
            first_line = ""

        if first_line.startswith("POST /login"):
            print(f"[HttpAdapter] recv bytes={len(msg)} header_end={raw_req.find('\\r\\n\\r\\n')}")

        req.prepare(raw_req, routes)

        if req.method == "GET" and req.path == "/login":
            try:
                with open(os.path.join("www", "login.html"), "r", encoding="utf-8") as fh:
                    body = fh.read()
                headers = "HTTP/1.1 200 OK\r\nContent-Type: text/html\r\n\r\n"
                conn.sendall(headers.encode() + body.encode())
            except Exception as e:
                body = f"<h1>500 Internal Server Error</h1><p>{e}</p>"
                conn.sendall(b"HTTP/1.1 500 Internal Server Error\r\n\r\n" + body.encode())
            conn.close()
            return

        if req.method == "POST" and req.path == "/login":
            try:
                header_end = raw_req.find("\r\n\r\n")
                content_len = 0
                if header_end != -1:
                    headers_part = raw_req[:header_end]
                    for line in headers_part.split("\r\n"):
                        if line.lower().startswith("content-length:"):
                            try:
                                content_len = int(line.split(":", 1)[1].strip())
                            except Exception:
                                content_len = 0
                            break

                body = ""
                if header_end != -1 and content_len > 0:
                    start = header_end + 4
                    body_bytes = msg[start:start + content_len]
                    try:
                        body = body_bytes.decode("utf-8")
                    except Exception:
                        body = body_bytes.decode("latin-1", errors="ignore")
                else:
                    body = ""
            except Exception:
                body = ""

            print(f"[HttpAdapter] POST /login received: content_len={content_len} body_len={len(body)}")
            form = urllib.parse.parse_qs(body)
            username = form.get("username", [""])[0]
            password = form.get("password", [""])[0]

            if username and password:
                print(f"[HttpAdapter] POST /login parsed username={username}")
            else:
                print(f"[HttpAdapter] POST /login parsed empty credentials")
            users_file = os.path.join("www", "users.json")
            users = {}
            try:
                if os.path.exists(users_file):
                    with open(users_file, "r", encoding="utf-8") as f:
                        users = json.load(f)
                else:
                    print("[HttpAdapter] users.json not found, using default users.")
                    users = {
                        "admin": "password",
                        "client1": "123",
                        "client2": "123"
                    }
            except Exception as e:
                print(f"[HttpAdapter] Error reading users.json: {e}")
                users = {
                    "admin": "password",
                    "client1": "123",
                    "client2": "123"
                }
            if username in users and users[username] == password:
                try:
                    with open(os.path.join("www", "index.html"), "r", encoding="utf-8") as fh:
                        body = fh.read()
                    headers = ("HTTP/1.1 200 OK\r\n"
                               "Content-Type: text/html\r\n"
                               "Set-Cookie: auth=true; Path=/; HttpOnly\r\n"
                               "\r\n")
                    conn.sendall(headers.encode() + body.encode())
                except Exception as e:
                    body = f"<h1>500 Internal Server Error</h1><p>{e}</p>"
                    conn.sendall(b"HTTP/1.1 500 Internal Server Error\r\n\r\n" + body.encode())
            else:
                try:
                    body = "<h1>401 Unauthorized</h1><p>Invalid credentials.</p>"
                    headers = ("HTTP/1.1 401 Unauthorized\r\n"
                               "Content-Type: text/html\r\n"
                               "Content-Length: {}\r\n"
                               "Connection: close\r\n"
                               "\r\n").format(len(body))
                    conn.sendall(headers.encode() + body.encode())
                except Exception:
                    conn.sendall(b"HTTP/1.1 401 Unauthorized\r\n\r\n<h1>401 Unauthorized</h1>")
            conn.close()
            return

        if req.method == "GET" and req.path == "/protected":
            conn.sendall(b"HTTP/1.1 200 OK\r\nContent-Type: text/html\r\n\r\n<h1>Protected Resource</h1><p>You are logged in!</p>")
            conn.close()
            return

        if req.method == "GET" and req.path in ("/", "/index", "/index.html"):
            auth_val = ""
            try:
                auth_val = req.cookies.get("auth", "")
                if isinstance(auth_val, str):
                    auth_val = auth_val.lower()
            except Exception:
                auth_val = ""

            if auth_val == "true":
                try:
                    with open(os.path.join("www", "index.html"), "r", encoding="utf-8") as fh:
                        body = fh.read()
                    headers = "HTTP/1.1 200 OK\r\nContent-Type: text/html\r\n\r\n"
                    conn.sendall(headers.encode() + body.encode())
                except Exception as e:
                    body = f"<h1>500 Internal Server Error</h1><p>{e}</p>"
                    conn.sendall(b"HTTP/1.1 500 Internal Server Error\r\n\r\n" + body.encode())
                conn.close()
                return
            else:
                body = "<h1>401 Unauthorized</h1><p>Login required. <a href=\"/login\">Login</a></p>"
                headers = ("HTTP/1.1 401 Unauthorized\r\n"
                           "Content-Type: text/html\r\n"
                           "Content-Length: {}\r\n"
                           "Connection: close\r\n"
                           "\r\n").format(len(body))
                conn.sendall(headers.encode() + body.encode())
                conn.close()
                return
        if req.method == "GET" and req.path.startswith("/submit-info"):
            try:
                with open(os.path.join("www", "submit-info.html"), "r", encoding="utf-8") as fh:
                    body = fh.read()
                headers = "HTTP/1.1 200 OK\r\nContent-Type: text/html\r\n\r\n"
                conn.sendall(headers.encode() + body.encode())
            except Exception as e:
                body = f"<h1>500 Internal Server Error</h1><p>{e}</p>"
                conn.sendall(b"HTTP/1.1 500 Internal Server Error\r\n\r\n" + body.encode())
            conn.close()
            return
        
        if req.method == "POST" and req.path == "/submit-info":
            try:
                header_end = raw_req.find("\r\n\r\n")
                content_len = 0
                if header_end != -1:
                    headers_part = raw_req[:header_end]
                    for line in headers_part.split("\r\n"):
                        if line.lower().startswith("content-length:"):
                            try:
                                content_len = int(line.split(":", 1)[1].strip())
                            except Exception:
                                content_len = 0
                            break

                body = ""
                if header_end != -1 and content_len > 0:
                    start = header_end + 4
                    body_bytes = msg[start:start + content_len]
                    try:
                        body = body_bytes.decode("utf-8")
                    except Exception:
                        body = body_bytes.decode("latin-1", errors="ignore")
                else:
                    body = ""
            except Exception:
                body = ""

            print(f"[HttpAdapter] POST /submit-info received: content_len={content_len} body_len={len(body)}")

            # Parse dữ liệu form
            form = urllib.parse.parse_qs(body)
            username = form.get("username", [""])[0]
            password = form.get("password", [""])[0]

            if not username or not password:
                body = "<h1>400 Bad Request</h1><p>Missing username or password.</p>"
                headers = ("HTTP/1.1 400 Bad Request\r\n"
                        "Content-Type: text/html\r\n"
                        "Content-Length: {}\r\n"
                        "Connection: close\r\n\r\n").format(len(body))
                conn.sendall(headers.encode() + body.encode())
                conn.close()
                return

            print(f"[HttpAdapter] Register attempt via /submit-info: {username}")

            # Đọc danh sách người dùng từ file
            users_file = os.path.join("www", "users.json")
            users = {}
            try:
                if os.path.exists(users_file):
                    with open(users_file, "r", encoding="utf-8") as f:
                        users = json.load(f)
            except Exception as e:
                print(f"[HttpAdapter] Warning: cannot read users.json: {e}")
                users = {}

            # Kiểm tra trùng tên
            if username in users:
                body = f"<h1>409 Conflict</h1><p>Username '{username}' already exists.</p>"
                headers = ("HTTP/1.1 409 Conflict\r\n"
                        "Content-Type: text/html\r\n"
                        "Content-Length: {}\r\n"
                        "Connection: close\r\n\r\n").format(len(body))
                conn.sendall(headers.encode() + body.encode())
                conn.close()
                return

            # Lưu tài khoản mới
            users[username] = password
            try:
                with open(users_file, "w", encoding="utf-8") as f:
                    json.dump(users, f, ensure_ascii=False, indent=2)
            except Exception as e:
                body = f"<h1>500 Internal Server Error</h1><p>Cannot save user: {e}</p>"
                conn.sendall(b"HTTP/1.1 500 Internal Server Error\r\n\r\n" + body.encode())
                conn.close()
                return

            # Gửi phản hồi thành công
            try:
                with open(os.path.join("www", "index.html"), "r", encoding="utf-8") as fh:
                    body = fh.read()
                    headers = ("HTTP/1.1 200 OK\r\n"
                               "Content-Type: text/html\r\n"
                               "Set-Cookie: auth=true; Path=/; HttpOnly\r\n"
                               "\r\n")
                    conn.sendall(headers.encode() + body.encode())
            except Exception as e:
                body = f"<h1>500 Internal Server Error</h1><p>{e}</p>"
                conn.sendall(b"HTTP/1.1 500 Internal Server Error\r\n\r\n" + body.encode())

            conn.close()
            return

        # --- Handle /add-list ---
        # server_routes.py
        # httpadapter.py

##############################################################################
        # --- /add-list ---
        if req.method == "POST" and req.path == "/add-list":
            try:
                # --- lấy content-length ---
                header_end = raw_req.find("\r\n\r\n")
                content_len = 0
                if header_end != -1:
                    headers_part = raw_req[:header_end]
                    for line in headers_part.split("\r\n"):
                        if line.lower().startswith("content-length:"):
                            try:
                                content_len = int(line.split(":", 1)[1].strip())
                            except Exception:
                                content_len = 0
                            break

                # --- đọc body bytes ---
                body = ""
                if header_end != -1 and content_len > 0:
                    start = header_end + 4
                    body_bytes = msg[start:start + content_len]
                    try:
                        body = body_bytes.decode("utf-8")
                    except Exception:
                        body = body_bytes.decode("latin-1", errors="ignore")
                else:
                    body = ""

                # --- parse JSON ---
                import json
                try:
                    data = json.loads(body)
                    item = data.get("item")
                    if not item:
                        raise ValueError("Missing 'item'")
                except Exception as e:
                    headers = {"Content-Type": "text/plain"}
                    resp_body = str(e)
                    response = f"HTTP/1.1 400 Bad Request\r\nContent-Type: text/plain\r\nContent-Length: {len(resp_body)}\r\nConnection: close\r\n\r\n{resp_body}"
                    conn.sendall(response.encode())
                    conn.close()
                    return

                # --- add item vào danh sách ---
                _global_list.append({
                    "user": data.get("user"),      # tên user
                    "item": item,          # item thêm
                    "host": data.get("host", "127.0.0.1"),   # host client
                    "port": data.get("port")                 # port client
                })
                resp = {"message": "Item added", "item": item}
                body_resp = json.dumps(resp)
                headers = f"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nContent-Length: {len(body_resp)}\r\nConnection: close\r\n\r\n"
                conn.sendall(headers.encode() + body_resp.encode())

            except Exception as e:
                body_bytes = f"<h1>500 Internal Server Error</h1><p>{e}</p>".encode()
                headers = ("HTTP/1.1 500 Internal Server Error\r\n"
                        f"Content-Type: text/html\r\n"
                        f"Content-Length: {len(body_bytes)}\r\n"
                        "Connection: close\r\n"
                        "\r\n").encode()
                conn.sendall(headers + body_bytes)
            finally:
                conn.close()

        # #################################################
        # --- /1sx1 ---
        if req.method == "GET" and req.path == "/get-list":
            try:
                sessionid = req.cookies.get("sessionid")
                user = get_user_from_session(sessionid) if sessionid else None

                # if not user:
                #     body_html = '<h1>401 Unauthorized</h1><p>Login required. <a href="/login">Login</a></p>'
                #     headers = f"HTTP/1.1 401 Unauthorized\r\nContent-Type: text/html; charset=utf-8\r\nContent-Length: {len(body_html)}\r\nConnection: close\r\n\r\n"
                #     conn.sendall(headers.encode() + body_html.encode())
                # else:
                    # Lấy danh sách trực tiếp từ _global_list
                resp = {"count": len(_global_list), "list": _global_list}
                body_resp = json.dumps(resp)
                headers = f"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nContent-Length: {len(body_resp)}\r\nConnection: close\r\n\r\n"
                conn.sendall(headers.encode() + body_resp.encode())
                handled = True
                return
            except Exception as e:
                body_bytes = f"<h1>500 Internal Server Error</h1><p>{e}</p>".encode()
                headers = f"HTTP/1.1 500 Internal Server Error\r\nContent-Type: text/html\r\nContent-Length: {len(body_bytes)}\r\nConnection: close\r\n\r\n"
                conn.sendall(headers + body_bytes)
                handled = True
                conn.close()
                return

##########################################################
        # --- /connect-peer ---
        if req.method == "POST" and req.path == "/connect-peer":
            try:
                # --- lấy content-length ---
                header_end = raw_req.find("\r\n\r\n")
                content_len = 0
                if header_end != -1:
                    headers_part = raw_req[:header_end]
                    for line in headers_part.split("\r\n"):
                        if line.lower().startswith("content-length:"):
                            try:
                                content_len = int(line.split(":", 1)[1].strip())
                            except Exception:
                                content_len = 0
                            break

                # --- đọc body bytes ---
                body = ""
                if header_end != -1 and content_len > 0:
                    start = header_end + 4
                    body_bytes = msg[start:start + content_len]
                    try:
                        body = body_bytes.decode("utf-8")
                    except Exception:
                        body = body_bytes.decode("latin-1", errors="ignore")
                else:
                    body = ""

                # --- parse JSON ---
                import json
                try:
                    data = json.loads(body)
                    # Ví dụ: lấy "peer" từ JSON
                    peer_user = data.get("peer")
                    if not peer_user:
                        raise ValueError("Missing 'peer'")
                except Exception as e:
                    resp_body = str(e)
                    response = f"HTTP/1.1 400 Bad Request\r\nContent-Type: text/plain\r\nContent-Length: {len(resp_body)}\r\nConnection: close\r\n\r\n{resp_body}"
                    conn.sendall(response.encode())
                    conn.close()
                    return

                # --- xử lý connect peer ---
                # Gọi handler nếu cần, hoặc chỉ echo peer:
                peer_info = next((entry for entry in _global_list if entry.get("user") == peer_user and "port" in entry), None)

                if not peer_info:
                    resp = {"message": "Peer not online"}
                else:
                    # Trả thông tin port và host để client connect
                    peer_name = peer_info["user"]
                    peer_host = peer_info.get("host", "127.0.0.1")
                    peer_port = peer_info["port"]
                    resp = {
                    "message": "Peer connected",
                    "peer_user": peer_name,
                    "host": peer_host,
                    "port": peer_port
                     }  
                    peer_list[peer_name] = (peer_host, peer_port)
                
                body_resp = json.dumps(resp)
                headers = f"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nContent-Length: {len(body_resp)}\r\nConnection: close\r\n\r\n"
                conn.sendall(headers.encode() + body_resp.encode())

            except Exception as e:
                body_bytes = f"<h1>500 Internal Server Error</h1><p>{e}</p>".encode()
                headers = f"HTTP/1.1 500 Internal Server Error\r\nContent-Type: text/html\r\nContent-Length: {len(body_bytes)}\r\nConnection: close\r\n\r\n"
                conn.sendall(headers + body_bytes)
            finally:
                conn.close()


        import socket

# --------------------------------------
# /broadcast-peer
# --------------------------------------
        if req.method == "POST" and req.path == "/broadcast-peer":
            try:
                # --- đọc body JSON ---
                header_end = raw_req.find("\r\n\r\n")
                content_len = 0
                if header_end != -1:
                    headers_part = raw_req[:header_end]
                    for line in headers_part.split("\r\n"):
                        if line.lower().startswith("content-length:"):
                            try:
                                content_len = int(line.split(":", 1)[1].strip())
                            except:
                                content_len = 0
                            break

                body = ""
                if header_end != -1 and content_len > 0:
                    start = header_end + 4
                    body_bytes = msg[start:start + content_len]
                    body = body_bytes.decode("utf-8", errors="ignore")

                data = json.loads(body)
                sender = data.get("from")
                message = data.get("message")

                if not sender or not message:
                    raise ValueError("Missing 'from' or 'message'")

                success = 0
                for peer_name, (ip, port) in peer_list.items():
                    if peer_name == sender:
                        continue
                    try:
                        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                        s.connect((ip, port))
                        s.sendall(f"[Broadcast] {sender}: {message}".encode("utf-8"))
                        s.close()
                        success += 1
                    except Exception as e:
                        print(f"[Broadcast] Không gửi được tới {peer_name}: {e}")

                body = f"<h1>Broadcast sent</h1><p>Message delivered to {success} peers.</p>"
                headers = ("HTTP/1.1 200 OK\r\n"
                        "Content-Type: text/html\r\n"
                        f"Content-Length: {len(body)}\r\n\r\n")
                conn.sendall(headers.encode() + body.encode())

            except Exception as e:
                err = f"<h1>500 Internal Server Error</h1><p>{e}</p>"
                conn.sendall(f"HTTP/1.1 500 Internal Server Error\r\nContent-Type: text/html\r\nContent-Length: {len(err)}\r\n\r\n".encode() + err.encode())
            finally:
                conn.close()


# --------------------------------------
# /send-peer
# --------------------------------------
        if req.method == "POST" and req.path == "/send-peer":
            try:
                # --- đọc body JSON ---
                header_end = raw_req.find("\r\n\r\n")
                content_len = 0
                if header_end != -1:
                    headers_part = raw_req[:header_end]
                    for line in headers_part.split("\r\n"):
                        if line.lower().startswith("content-length:"):
                            try:
                                content_len = int(line.split(":", 1)[1].strip())
                            except:
                                content_len = 0
                            break

                body = ""
                if header_end != -1 and content_len > 0:
                    start = header_end + 4
                    body_bytes = msg[start:start + content_len]
                    body = body_bytes.decode("utf-8", errors="ignore")

                data = json.loads(body)
                sender = data.get("from")
                target = data.get("to")
                message = data.get("message")

                if not sender or not target or not message:
                    raise ValueError("Missing required fields")

                if target not in peer_list:
                    conn.sendall(b"HTTP/1.1 404 Not Found\r\n\r\nPeer not found")
                    conn.close()
                    return

                ip, port = peer_list[target]
                try:
                    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    s.connect((ip, port))
                    s.sendall(f"[Private] {sender}: {message}".encode("utf-8"))
                    s.close()
                    body = f"<h1>Message sent</h1><p>{sender} to {target}</p>"
                    headers = ("HTTP/1.1 200 OK\r\n"
                            "Content-Type: text/html\r\n"
                            f"Content-Length: {len(body)}\r\n\r\n")
                    conn.sendall(headers.encode() + body.encode())
                except Exception as e:
                    raise RuntimeError(f"Send failed: {e}")

            except Exception as e:
                err = f"<h1>500 Internal Server Error</h1><p>{e}</p>"
                conn.sendall(f"HTTP/1.1 500 Internal Server Error\r\nContent-Type: text/html\r\nContent-Length: {len(err)}\r\n\r\n".encode() + err.encode())
            finally:
                conn.close()
        # --- 404 Not Found ---
        try:
            if not handled:
                conn.sendall(b"HTTP/1.1 404 Not Found\r\n\r\n<h1>404 Not Found</h1>")
        except Exception:
            pass
        finally:
            conn.close()
