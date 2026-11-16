import socket
import json

with socket.create_connection(("192.168.100.11", 12000), timeout=10) as connection:
    with connection.makefile("rb") as stream:
        request = {
            "action": "download",
            "filename": "missing-file-test.txt"
        }
        connection.sendall(json.dumps(request).encode() + b"\n")
        print(stream.readline().decode())
