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
daemon.proxy
~~~~~~~~~~~~~~~~~

This module implements a simple proxy server using Python's socket and threading libraries.
It routes incoming HTTP requests to backend services based on hostname mappings and returns
the corresponding responses to clients.

Requirement:
-----------------
- socket: provides socket networking interface.
- threading: enables concurrent client handling via threads.
- response: customized :class: `Response <Response>` utilities.
- httpadapter: :class: `HttpAdapter <HttpAdapter >` adapter for HTTP request processing.
- dictionary: :class: `CaseInsensitiveDict <CaseInsensitiveDict>` for managing headers and cookies.

"""
import socket
import threading
import re
from .response import *
from .httpadapter import HttpAdapter
from .dictionary import CaseInsensitiveDict

#: A dictionary mapping hostnames to backend IP and port tuples.
#: Used to determine routing targets for incoming requests.



def forward_request(host, port, request):
    """
    Forwards an HTTP request to a backend server and retrieves the response.

    :params host (str): IP address of the backend server.
    :params port (int): port number of the backend server.
    :params request (str): incoming HTTP request.

    :rtype bytes: Raw HTTP response from the backend server. If the connection
                  fails, returns a 404 Not Found response.
    """

    backend = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    try:
        backend.connect((host, port))
        backend.sendall(request.encode())
        response = b""
        while True:
            chunk = backend.recv(4096)
            if not chunk:
                break
            response += chunk
        return response
    except socket.error as e:
      print("Socket error: {}".format(e))
      return (
            "HTTP/1.1 404 Not Found\r\n"
            "Content-Type: text/plain\r\n"
            "Content-Length: 13\r\n"
            "Connection: close\r\n"
            "\r\n"
            "404 Not Found"
        ).encode('utf-8')


def resolve_routing_policy(hostname, routes):
    """
    Handles an routing policy to return the matching proxy_pass.
    It determines the target backend to forward the request to.

    :params host (str): IP address of the request target server.
    :params port (int): port number of the request target server.
    :params routes (dict): dictionary mapping hostnames and location.
    """

    print(hostname)
    proxy_map, policy = routes.get(hostname,('127.0.0.1:9000','round-robin'))
    print (proxy_map)
    print (policy)

    proxy_host = ''
    proxy_port = '9000'
    if isinstance(proxy_map, list):
        if len(proxy_map) == 0:
            print("[Proxy] Emtpy resolved routing of hostname {}".format(hostname))
            print ("Empty proxy_map result")
            # TODO: implement the error handling for non mapped host
            #       the policy is design by team, but it can be 
            #       basic default host in your self-defined system
            # Use a dummy host to raise an invalid connection
            proxy_host = '127.0.0.1'
            proxy_port = '9000'
        elif len(proxy_map) == 1:
            proxy_host, proxy_port = proxy_map[0].split(":", 2)
        #elif: # apply the policy handling 
        #   proxy_map
        #   policy
        else:
            # Out-of-handle mapped host
            proxy_host = '127.0.0.1'
            proxy_port = '9000'
    else:
        print("[Proxy] resolve route of hostname {} is a singulair to".format(hostname))
        proxy_host, proxy_port = proxy_map.split(":", 2)

    return proxy_host, proxy_port

def handle_client(ip, port, conn, addr, routes):
    """
    Handles an individual client connection by parsing the request,
    determining the target backend, and forwarding the request.

    The handler extracts the Host header from the request to
    matches the hostname against known routes. In the matching
    condition,it forwards the request to the appropriate backend.

    The handler sends the backend response back to the client or
    returns 404 if the hostname is unreachable or is not recognized.

    :params ip (str): IP address of the proxy server.
    :params port (int): port number of the proxy server.
    :params conn (socket.socket): client connection socket.
    :params addr (tuple): client address (IP, port).
    :params routes (dict): dictionary mapping hostnames and location.
    """

    #request = conn.recv(1024).decode()
    #XUAN added code
    request = b""
    conn.settimeout(0.5)  # tránh treo khi client không gửi thêm
    try:
        while True:
            chunk = conn.recv(4096)
            if not chunk:
                break
            request += chunk
    except socket.timeout:
        pass
    request = request.decode(errors="ignore")
    #END XUAN added code

    # Extract hostname
    hostname = None
    for line in request.splitlines():
        if line.lower().startswith('host:'):
            hostname = line.split(':', 1)[1].strip()
            if hostname:
                parts = hostname.split(':')
              
                if len(parts) == 2:
                    host_part = parts[0]
                    port_part = parts[1]
                    if port_part == str(port) or port_part == '80':
                        hostname = host_part
                
                if hostname not in routes and f'{hostname}:{port}' in routes:
                     hostname = f'{hostname}:{port}'
         
            break 
    if hostname is None:
      
        print("[Proxy] Error: Missing Host header")
        response = b"HTTP/1.1 400 Bad Request\r\nContent-Length: 0\r\n\r\n"
        conn.sendall(response)
        conn.close()
        return

    print("[Proxy] {} at Host: {}".format(addr, hostname))

    # Resolve the matching destination in routes and need conver port
    # to integer value
    resolved_host, resolved_port = resolve_routing_policy(hostname, routes)
    try:
        resolved_port = int(resolved_port)
    except ValueError:
        print("Not a valid integer")

    if resolved_host:
        # --- nếu là host chính 127.0.0.1:8080 thì gửi song song ---
        if hostname == "127.0.0.1:8080":
            def send_to_backend():
                try:
                    resp = forward_request("127.0.0.1", 9000, request)
                except Exception as e:
                    print(f"[Proxy]  Backend error: {e}")

            def send_to_sampleapp():
                try:
                    resp = forward_request("127.0.0.1", 8000, request)
                except Exception as e:
                    print(f"[Proxy]  SampleApp error: {e}")

            # --- chạy 2 thread song song ---
            threading.Thread(target=send_to_backend, daemon=True).start()
            threading.Thread(target=send_to_sampleapp, daemon=True).start()

            # --- dùng backend làm phản hồi chính ---
            try:
                response = forward_request("127.0.0.1", 9000, request)
            except Exception:
                response = forward_request("127.0.0.1", 8000, request)

        else:
            # các host khác thì xử lý như cũ
            response = forward_request(resolved_host, resolved_port, request)

    else:
        response = (
            "HTTP/1.1 404 Not Found\r\n"
            "Content-Type: text/plain\r\n"
            "Content-Length: 13\r\n"
            "Connection: close\r\n"
            "\r\n"
            "404 Not Found"
        ).encode("utf-8")
    conn.sendall(response)
    conn.close()

def run_proxy(ip, port, routes):
    """
    Starts the proxy server and listens for incoming connections. 

    The process dinds the proxy server to the specified IP and port.
    In each incomping connection, it accepts the connections and
    spawns a new thread for each client using `handle_client`.
 

    :params ip (str): IP address to bind the proxy server.
    :params port (int): port number to listen on.
    :params routes (dict): dictionary mapping hostnames and location.

    """

    proxy = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    try:
        proxy.bind((ip, port))
        proxy.listen(50)
        print("[Proxy] Listening on IP {} port {}".format(ip,port))
        while True:
            #
            #  TODO: implement the step of the client incomping connection
            #        using multi-thread programming with the
            #        provided handle_client routine
            #
            conn, addr = proxy.accept()
            t = threading.Thread(target=handle_client, args=(ip, port, conn, addr, routes))
            t.daemon = True
            t.start()
    except socket.error as e:
      print("Socket error: {}".format(e))

def create_proxy(ip, port, routes):
    """
    Entry point for launching the proxy server.

    :params ip (str): IP address to bind the proxy server.
    :params port (int): port number to listen on.
    :params routes (dict): dictionary mapping hostnames and location.
    """

    run_proxy(ip, port, routes)
