import json
import os
import socketserver
import tempfile
from pathlib import Path

SHARED_FOLDER = Path("/mnt/shared/files")
PORT = 12000
CHUNK_SIZE = 65536


def send_message(connection, message):
    data = json.dumps(message).encode() + b"\n"
    connection.sendall(data)


def safe_path(filename):
    if (
        not isinstance(filename, str)
        or not filename
        or filename in (".", "..")
        or "/" in filename
        or "\\" in filename
        or filename.startswith(".")
    ):
        raise ValueError("Invalid filename.")

    path = SHARED_FOLDER / filename

    if path.is_symlink():
        raise ValueError("Symbolic links are not allowed.")

    return path


class FileHandler(socketserver.StreamRequestHandler):
    def handle(self):
        self.request.settimeout(60)
        temporary_path = None
        response_started = False

        print(f"Connected: {self.client_address}", flush=True)

        try:
            header = self.rfile.readline(65537)

            if len(header) > 65536 or not header.endswith(b"\n"):
                raise ValueError("Invalid request header.")

            request = json.loads(header)

            if not isinstance(request, dict):
                raise ValueError("Request must be an object.")

            action = request.get("action")

            if action == "list":
                files = sorted(
                    path.name
                    for path in SHARED_FOLDER.iterdir()
                    if path.is_file()
                    and not path.is_symlink()
                    and not path.name.startswith(".")
                )
                send_message(
                    self.request,
                    {"status": "ok", "files": files},
                )

            elif action == "upload":
                destination = safe_path(request.get("filename"))
                size = request.get("size")

                if type(size) is not int or size < 0:
                    raise ValueError("Invalid file size.")

                # Receive into a temporary file so incomplete uploads
                # never appear in the available-file list.
                with tempfile.NamedTemporaryFile(
                    dir=SHARED_FOLDER,
                    prefix=".upload-",
                    delete=False,
                ) as output:
                    temporary_path = output.name

                    send_message(
                        self.request,
                        {"status": "ready"},
                    )

                    remaining = size

                    while remaining:
                        data = self.rfile.read(
                            min(CHUNK_SIZE, remaining)
                        )

                        if not data:
                            raise ConnectionError("Upload interrupted.")

                        output.write(data)
                        remaining -= len(data)

                # Publish only after the complete file has arrived.
                # Uploads with the same name replace the previous file.
                os.replace(temporary_path, destination)
                temporary_path = None

                send_message(
                    self.request,
                    {"status": "ok", "message": "Upload complete."},
                )
                print(
                    f"Uploaded: {destination.name} ({size} bytes)",
                    flush=True,
                )

            elif action == "download":
                source = safe_path(request.get("filename"))

                with source.open("rb") as input_file:
                    size = os.fstat(input_file.fileno()).st_size

                    response_started = True
                    send_message(
                        self.request,
                        {"status": "ok", "size": size},
                    )

                    remaining = size

                    while remaining:
                        data = input_file.read(
                            min(CHUNK_SIZE, remaining)
                        )

                        if not data:
                            raise ConnectionError(
                                "File changed during download."
                            )

                        self.request.sendall(data)
                        remaining -= len(data)

                print(f"Downloaded: {source.name}", flush=True)

            else:
                raise ValueError("Unknown action.")

        except Exception as error:
            print(f"Error: {error}", flush=True)

            # Once download bytes begin, close on failure rather than
            # inserting an error message into the file's contents.
            if not response_started:
                try:
                    send_message(
                        self.request,
                        {"status": "error", "message": str(error)},
                    )
                except OSError:
                    pass

        finally:
            if temporary_path is not None:
                Path(temporary_path).unlink(missing_ok=True)

            print(f"Disconnected: {self.client_address}", flush=True)


class FileServer(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True


if __name__ == "__main__":
    if not SHARED_FOLDER.is_dir():
        raise SystemExit(
            f"Shared folder unavailable: {SHARED_FOLDER}"
        )

    with FileServer(("0.0.0.0", PORT), FileHandler) as server:
        print(f"File server listening on port {PORT}", flush=True)
        print(f"Shared folder: {SHARED_FOLDER}", flush=True)

        try:
            server.serve_forever()
        except KeyboardInterrupt:
            print("\nServer stopped.")
