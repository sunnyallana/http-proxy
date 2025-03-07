import sys
import socket
import os
import signal
from urllib.parse import urlparse

def main():
    if len(sys.argv) != 2:
        print("Usage: k224149_proxy.py <port>")
        sys.exit(1)
    
    listenPort = int(sys.argv[1])
    serverSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    serverSocket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    serverSocket.bind(('', listenPort))
    serverSocket.listen(100)
    activeChildren = 0
    
    print(f"Proxy is running on http://127.0.0.1:{listenPort}")
    
    def sigChldHandler(signum, frame):
        nonlocal activeChildren
        while True:
            try:
                pid, status = os.waitpid(-1, os.WNOHANG)
                if pid == 0:
                    break
                activeChildren -= 1
                print(f"Child process {pid} terminated. Active connections: {activeChildren}")
            except OSError:
                break
    
    signal.signal(signal.SIGCHLD, sigChldHandler)
    
    while True:
        try:
            clientSocket, clientAddr = serverSocket.accept()
            print(f"New connection from {clientAddr[0]}:{clientAddr[1]}")
            
            if activeChildren >= 100:
                print(f"Too many connections ({activeChildren}). Refusing new connection.")
                clientSocket.close()
                continue
                
            pid = os.fork()
            if pid == 0:
                serverSocket.close()
                handleClientRequest(clientSocket)
                clientSocket.close()
                os._exit(0)
            else:
                clientSocket.close()
                activeChildren += 1
                print(f"Created child process {pid}. Active connections: {activeChildren}")
                
        except KeyboardInterrupt:
            print("Shutting down proxy server")
            serverSocket.close()
            sys.exit(0)

def handleClientRequest(clientSock):
    dataBuffer = b''
    while True:
        chunk = clientSock.recv(4096)
        if not chunk:
            break
        dataBuffer += chunk
        if b'\r\n\r\n' in dataBuffer:
            break
    
    if not dataBuffer:
        print("Empty request received")
        return
        
    try:
        headersPart = dataBuffer.split(b'\r\n\r\n')[0]
        headerLines = headersPart.split(b'\r\n')
        requestLine = headerLines[0].decode('latin-1')
        method, uri, version = requestLine.split()
        print(f"Request: {method} {uri} {version}")
    except:
        print("Invalid request format")
        sendErrorResponse(clientSock, 400)
        return
        
    if method.upper() != 'GET':
        print(f"Method not supported: {method}")
        sendErrorResponse(clientSock, 501)
        return
        
    try:
        parsedUri = urlparse(uri)
        if not parsedUri.hostname:
            raise ValueError("No host in URI")
            
        targetHost = parsedUri.hostname
        targetPort = parsedUri.port if parsedUri.port else 80
        targetPath = parsedUri.path
        if not targetPath:
            targetPath = '/'
        if parsedUri.query:
            targetPath += '?' + parsedUri.query
            
        print(f"Connecting to: {targetHost}:{targetPort}{targetPath}")
    except:
        print("Failed to parse URI")
        sendErrorResponse(clientSock, 400)
        return
        
    modifiedHeaders = []
    hostHeader = f"{targetHost}:{targetPort}" if targetPort != 80 else targetHost
    modifiedHeaders.append(f"Host: {hostHeader}")
    
    for h in headerLines[1:]:
        headerStr = h.decode('latin-1')
        if headerStr.lower().startswith('host:'):
            continue
        modifiedHeaders.append(headerStr)
        
    requestMsg = f"GET {targetPath} HTTP/1.0\r\n" + '\r\n'.join(modifiedHeaders) + '\r\n\r\n'
    
    try:
        targetSock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        targetSock.connect((targetHost, targetPort))
        targetSock.sendall(requestMsg.encode('latin-1'))
        
        print(f"Connected to {targetHost}:{targetPort}")
        
        totalBytes = 0
        while True:
            responseData = targetSock.recv(4096)
            if not responseData:
                break
            clientSock.sendall(responseData)
            totalBytes += len(responseData)
            
        print(f"Request completed. Sent {totalBytes} bytes to client")
        
    except Exception as e:
        print(f"Error connecting to target: {e}")
        sendErrorResponse(clientSock, 502)
    finally:
        targetSock.close()

def sendErrorResponse(sock, code):
    if code == 400:
        msg = b"HTTP/1.0 400 Bad Request\r\n\r\n"
        status = "Bad Request"
    elif code == 501:
        msg = b"HTTP/1.0 501 Not Implemented\r\n\r\n"
        status = "Not Implemented"
    elif code == 502:
        msg = b"HTTP/1.0 502 Bad Gateway\r\n\r\n"
        status = "Bad Gateway"
    else:
        msg = b"HTTP/1.0 500 Internal Server Error\r\n\r\n"
        status = "Internal Server Error"
        
    print(f"Sending error response: {code} {status}")
    sock.sendall(msg)

if __name__ == "__main__":
    main()