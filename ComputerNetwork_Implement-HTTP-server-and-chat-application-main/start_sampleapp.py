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
start_sampleapp
~~~~~~~~~~~~~~~~~

This module provides a sample RESTful web application using the WeApRous framework.

It defines basic route handlers and launches a TCP-based backend server to serve
HTTP requests. The application includes a login endpoint and a greeting endpoint,
and can be configured via command-line arguments.
"""

import json
import socket
import argparse

from daemon.weaprous import WeApRous

PORT = 8000  # Default port

app = WeApRous()

import socket, threading, json
from daemon.weaprous import WeApRous

PORT = 8000
peers = {}  # id -> (ip, port)

app = WeApRous()

@app.route('/submit-info', methods=['POST'])
def submit_info(headers="guest", body="anonymous"):
    data = json.loads(body)
    peer_id = data["id"]
    ip = data["ip"]
    port = data["port"]
    peers[peer_id] = (ip, port)
    print(f"[P2P] Registered peer {peer_id} at {ip}:{port}")
    return {"status": "ok"}

@app.route('/get-list', methods=['GET'])
def get_list(headers="guest", body="anonymous"):
    return {"peers": peers}

@app.route('/connect-peer', methods=['POST'])
def connect_peer(headers="guest", body="anonymous"):
    data = json.loads(body)
    target_id = data["target_id"]
    msg = data["message"]
    if target_id not in peers:
        return {"error": "peer not found"}
    target_ip, target_port = peers[target_id]
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect((target_ip, target_port))
    sock.sendall(msg.encode())
    sock.close()
    print(f"[P2P] Sent message to {target_id}: {msg}")
    return {"status": "sent"}


@app.route('/hello', methods=['PUT'])
def hello(headers, body):
    """
    Handle greeting via PUT request.

    This route prints a greeting message to the console using the provided headers
    and body.

    :param headers (str): The request headers or user identifier.
    :param body (str): The request body or message payload.
    """
    print("[SampleApp] ['PUT'] Hello in {} to {}".format(headers, body))

if __name__ == "__main__":
    def peer_listener(ip, port):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.bind((ip, port))
        s.listen(5)
        print(f"[Peer] Listening on {ip}:{port}")
        while True:
            conn, addr = s.accept()
            msg = conn.recv(1024).decode()
            print(f"[Peer] Message from {addr}: {msg}")
            conn.close()
    # Parse command-line arguments to configure server IP and port
    parser = argparse.ArgumentParser(prog='Backend', description='', epilog='Beckend daemon')
    parser.add_argument('--server-ip', default='0.0.0.0')
    parser.add_argument('--server-port', type=int, default=PORT)
 
    args = parser.parse_args()
    ip = args.server_ip
    port = args.server_port
    listener_thread = threading.Thread(target=peer_listener, args=(ip, port), daemon=True)
    listener_thread.start()
    
    
    # Prepare and launch the RESTful application
    app.prepare_address(ip, port)
    app.run()


