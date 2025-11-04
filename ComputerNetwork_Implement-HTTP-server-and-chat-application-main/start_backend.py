#
# Copyright (C) 2025 pdnguyen of HCMC University of Technology VNU-HCM.
# All rights reserved.
# This file is part of the CO3093/CO3094 course,
# and is released under the "MIT License Agreement". Please see the LICENSE
# file that should have been included as part of this package.
#
# WeApRous release
#
# The authors hereby grant to Licensee personal permission to use
# and modify the Licensed Source Code for the sole purpose of studying
# while attending the course
#


"""
start_backend
~~~~~~~~~~~~~~~~~

This module provides a simple entry point for deploying backend server process
using the socket framework. It parses command-line arguments to configure the
server's IP address and port, and then launches the backend server.
"""

import socket
import argparse

from daemon import create_backend
from daemon.weaprous import WeApRous

# Default port number used if none is specified via command-line arguments.
PORT = 9000 
app = WeApRous()

import json, threading, time
active_peers = {}
peer_lock = threading.Lock()

@app.route('/login', methods=['POST'])
def handle_login(headers, body):
    try:
        data = json.loads(body)
        username = data.get("username")
        password = data.get("password")
        # Bypass xác thực để test
        return json.dumps({"status": "success", "message": "Login OK"})
    except Exception as e:
        return json.dumps({"status": "error", "message": str(e)})

@app.route('/submit-info', methods=['POST'])
def handle_submit_info(headers, body):
    try:
        data = json.loads(body)
        peer_id = data["id"]
        peer_ip = data["ip"]
        peer_port = data["port"]
        with peer_lock:
            active_peers[peer_id] = {"ip": peer_ip, "port": peer_port, "last_seen": time.time()}
        print(f"[Backend] Registered peer {peer_id} at {peer_ip}:{peer_port}")
        return json.dumps({"status": "registered", "peer_id": peer_id})
    except Exception as e:
        return json.dumps({"status": "error", "message": str(e)})

@app.route('/connect-peer', methods=['POST'])
def handle_connect_peer(headers, body):
    try:
        data = json.loads(body)
        target_id = data.get("target_id")
        if not target_id or target_id not in active_peers:
            return json.dumps({"status": "error", "message": "Peer not found"})
        info = active_peers[target_id]
        return json.dumps({"status": "ok", "ip": info["ip"], "port": info["port"]})
    except Exception as e:
        return json.dumps({"status": "error", "message": str(e)})
# # --- Handle GET /peer ---
# @app.route('/api/peer', methods=['GET'])
# def handle_peer(headers, body):
#     """
#     Trả JSON thuần để client parse được.
#     """
#     print(f"[Backend] Handle GET /peer (JSON response)")
#     response = {
#         "status": "ok",
#         "msg": f"Peer alive at port {PORT}"
#     }
#     return json.dumps(response)



# # --- Handle POST /message ---
# @app.route('/api/message', methods=['POST'])
# def handle_message(headers, body):
#     """
#     Nhận JSON từ peer hoặc text, in ra console và trả JSON phản hồi.
#     """
#     print(f"[Backend] Handle POST /message (JSON response)")
#     try:
#         data = json.loads(body)
#     except Exception:
#         # nếu peer gửi text thường, vẫn chấp nhận
#         data = {"raw": body.strip()}

#     print(f"[Backend] Received message: {data}")

#     reply = {
#         "status": "ok",
#         "port": PORT,
#         "received": data
#     }
#     return json.dumps(reply)


if __name__ == "__main__":
    """
    Entry point for launching the backend server.

    This block parses command-line arguments to determine the server's IP address
    and port. It then calls `create_backend(ip, port)` to start the RESTful
    application server.

    :arg --server-ip (str): IP address to bind the server (default: 127.0.0.1).
    :arg --server-port (int): Port number to bind the server (default: 9000).
    """

    parser = argparse.ArgumentParser(
        prog='Backend',
        description='Start the backend process',
        epilog='Backend daemon for http_deamon application'
    )
    parser.add_argument('--server-ip',
        type=str,
        default='0.0.0.0',
        help='IP address to bind the server. Default is 0.0.0.0'
    )
    parser.add_argument(
        '--server-port',
        type=int,
        default=PORT,
        help='Port number to bind the server. Default is {}.'.format(PORT)
    )

    args = parser.parse_args()
    ip = args.server_ip
    port = args.server_port

    create_backend(ip, port,app.routes)
