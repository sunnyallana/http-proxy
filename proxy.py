# Author: Sunny Shaban Ali
# Student ID: k224149
# Context: Computer Networks - Assignment 1
# Purpose: Implement a simple HTTP proxy server that can handle multiple clients concurrently.
# Date: 07/03/2025


# Importing the required libraries
import sys
import socket as so
import os
import signal as si
from urllib.parse import urlparse
import time

# Function to parse the headers
def parseHeaders(headerLines):
    headers = {}
    for line in headerLines:
        if b':' in line:
            key, value = line.split(b':', 1)
            headers[key.strip().decode()] = value.strip().decode()
    return headers

# Function to process the request
def processRequest(sock):
    dataBuffer = b''
    while True:
        part = sock.recv(4096)
        if not part:
            break
        dataBuffer += part
        if b'\r\n\r\n' in dataBuffer:
            break
    
    if not dataBuffer:
        print("Empty request received.")
        return
        
    try:
        headers = dataBuffer.split(b'\r\n\r\n')[0]
        lines = headers.split(b'\r\n')
        reqLine = lines[0].decode()
        method, uri, ver = reqLine.split()
        print(f"Request: {method} {uri} {ver}")
    except:
        print("Malformed request received.")
        sendError(sock, 400)
        return
        
    if method.upper() != 'GET':
        print(f"Unsupported method: {method}")
        sendError(sock, 501)
        return
        
    try:
        parsed = urlparse(uri)
        host = parsed.hostname
        port = parsed.port if parsed.port else 80
        path = parsed.path or '/'
        if parsed.query:
            path += '?' + parsed.query
        print(f"Parsed URL: Host={host}, Port={port}, Path={path}")
    except:
        print("Failed to parse URL.")
        sendError(sock, 400)
        return
        
    try:
        headersDict = parseHeaders(lines[1:])
        print("Parsed Headers:", headersDict)
    except Exception as e:
        print(f"Failed to parse headers: {e}")
        sendError(sock, 400)
        return
        
    hostHeader = f"{host}:{port}" if port !=80 else host
    headersList = [f"Host: {hostHeader}"]
    
    for h in lines[1:]:
        hText = h.decode()
        if hText.lower().startswith('host:'):
            continue
        headersList.append(hText)
        
    newReq = f"GET {path} {ver}\r\n" + '\r\n'.join(headersList) + '\r\n\r\n'
    
    try:
        destSock = so.socket(so.AF_INET, so.SOCK_STREAM)
        destSock.connect((host, port))
        destSock.sendall(newReq.encode())
        
        totalSize = 0
        start = time.time()
        while True:
            res = destSock.recv(4096)
            if not res:
                break
            try:
                sock.sendall(res)
                totalSize += len(res)
            except BrokenPipeError:
                print("Client disconnected before receiving the full response.")
                break
        
        elapsed = time.time() - start
        print(f"Request completed in {elapsed:.2f}s. Sent {totalSize} bytes.")
        
    except so.error as e:
        print(f"Socket error: {e}")
        sendError(sock, 502)
    except Exception as e:
        print(f"Unexpected error: {e}")
        sendError(sock, 500)
    finally:
        destSock.close()

# Function to send error response
def sendError(s, code):
    errors = {
        400: b"HTTP/1.0 400 Bad Request\r\n\r\n",
        501: b"HTTP/1.0 501 Not Implemented\r\n\r\n",
        502: b"HTTP/1.0 502 Bad Gateway\r\n\r\n",
        500: b"HTTP/1.0 500 Internal Error\r\n\r\n"
    }
    msg = errors.get(code, errors[500])
    try:
        s.sendall(msg)
        print(f"Sent error response: {code}")
    except BrokenPipeError:
        print("Client disconnected before receiving the error response.")
    finally:
        s.close()

# Driver code to run the proxy server
def main():
    if len(sys.argv) != 2:
        print("Kindly run the code in this format: python3 k224149_proxy.py <port_number>")
        return

    portNumber = int(sys.argv[1])
    mainSocket = so.socket(so.AF_INET, so.SOCK_STREAM)
    mainSocket.setsockopt(so.SOL_SOCKET, so.SO_REUSEADDR, 1)
    mainSocket.bind(('', portNumber))
    mainSocket.listen(100)
    
    activeCount = 0
    maxActive = 100
    childTerminated = False
    
    print(f"Proxy server is running on the port number: {portNumber}")

    def handleSignal(sig, f):
        nonlocal childTerminated
        childTerminated = True

    si.signal(si.SIGCHLD, handleSignal)
    
    while 1:
        if childTerminated:
            while 1:
                try:
                    pid, stat = os.waitpid(-1, os.WNOHANG)
                    if pid == 0:
                        break
                    activeCount -= 1
                    print(f"Child process {pid} is now terminated. Active connections: {activeCount}")
                except OSError:
                    break
            childTerminated = False

        try:
            conn, addr = mainSocket.accept()
            ip, prt = addr
            print(f"New connection from {ip}:{prt}")
            
            if activeCount >= maxActive:
                print(f"Maximum active connections ({maxActive}) reached. Closing connection.")
                conn.close()
                continue
            
            childId = os.fork()
            if childId == 0:
                mainSocket.close()
                processRequest(conn)
                conn.close()
                os._exit(0)
            else:
                conn.close()
                activeCount += 1
                print(f"New child process {childId} created. Active connections: {activeCount}")
                
        except KeyboardInterrupt:
            print("\nCtrl + c pressed. Shutting down proxy server...")
            mainSocket.close()
            return

if __name__ == "__main__":
    main()
