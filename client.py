import json
import os
import socket
import tempfile
from pathlib import Path

SERVER = "192.168.100.11"
PORT = 12000
CHUNK_SIZE = 65536

BASE_FOLDER = Path(__file__).resolve().parent
UPLOAD_FOLDER = BASE_FOLDER / "uploads"
DOWNLOAD_FOLDER = BASE_FOLDER / "downloads"

UPLOAD_FOLDER.mkdir(exist_ok=True)
DOWNLOAD_FOLDER.mkdir(exist_ok=True)


def send_message(connection, message):
    connection.sendall(json.dumps(message).encode() + b"\n")


def receive_message(stream):
    line = stream.readline(1048577)

    if not line or len(line) > 1048576 or not line.endswith(b"\n"):
        raise ValueError("Invalid or missing server response.")

    message = json.loads(line)

    if not isinstance(message, dict):
        raise ValueError("Invalid server response.")

    if message.get("status") == "error":
        raise RuntimeError(message.get("message", "Server error."))

    return message


def connect():
    return socket.create_connection((SERVER, PORT), timeout=60)


def get_files():
    with connect() as connection:
        with connection.makefile("rb") as stream:
            send_message(connection, {"action": "list"})
            response = receive_message(stream)
            return response["files"]


def select_file(files):
    if not files:
        print("No files available.")
        return None

    for number, name in enumerate(files, start=1):
        print(f"{number}. {name}")

    try:
        selection = int(input("Select a file number (0 to cancel): "))
    except ValueError:
        print("Please enter a number.")
        return None

    if selection == 0:
        return None

    if 1 <= selection <= len(files):
        return files[selection - 1]

    print("Invalid selection.")
    return None


def list_files():
    files = get_files()

    if not files:
        print("The server folder is empty.")
        return

    print("\nFiles on the server:")
    for name in files:
        print(f"  {name}")


def upload_file():
    files = sorted(
        path.name
        for path in UPLOAD_FOLDER.iterdir()
        if path.is_file()
        and not path.is_symlink()
        and not path.name.startswith(".")
    )

    filename = select_file(files)
    if filename is None:
        return

    source = UPLOAD_FOLDER / filename

    with source.open("rb") as input_file:
        size = os.fstat(input_file.fileno()).st_size

        with connect() as connection:
            with connection.makefile("rb") as stream:
                send_message(
                    connection,
                    {
                        "action": "upload",
                        "filename": filename,
                        "size": size,
                    },
                )

                response = receive_message(stream)
                if response.get("status") != "ready":
                    raise RuntimeError("Server is not ready for upload.")

                remaining = size

                while remaining:
                    data = input_file.read(min(CHUNK_SIZE, remaining))
                    if not data:
                        raise RuntimeError("Source file changed.")

                    connection.sendall(data)
                    remaining -= len(data)

                response = receive_message(stream)
                if response.get("status") != "ok":
                    raise RuntimeError("Upload was not confirmed.")

    print(f"Uploaded: {filename} ({size} bytes)")


def download_file():
    filename = select_file(get_files())
    if filename is None:
        return

    if (
        not isinstance(filename, str)
        or filename in (".", "..")
        or "/" in filename
        or "\\" in filename
        or filename.startswith(".")
    ):
        raise ValueError("Unsafe filename received.")

    destination = DOWNLOAD_FOLDER / filename
    temporary_path = None

    try:
        with connect() as connection:
            with connection.makefile("rb") as stream:
                send_message(
                    connection,
                    {"action": "download", "filename": filename},
                )

                response = receive_message(stream)
                size = response.get("size")

                if type(size) is not int or size < 0:
                    raise ValueError("Invalid file size.")

                with tempfile.NamedTemporaryFile(
                    dir=DOWNLOAD_FOLDER,
                    prefix=".download-",
                    delete=False,
                ) as output:
                    temporary_path = output.name
                    remaining = size

                    while remaining:
                        data = stream.read(min(CHUNK_SIZE, remaining))

                        if not data:
                            raise ConnectionError("Download interrupted.")

                        output.write(data)
                        remaining -= len(data)

        os.replace(temporary_path, destination)
        temporary_path = None
        print(f"Downloaded: {destination} ({size} bytes)")

    finally:
        if temporary_path is not None:
            Path(temporary_path).unlink(missing_ok=True)


def main():
    print(f"Connecting to file server at {SERVER}:{PORT}")
    print("Same-name uploads and downloads replace existing files.")

    while True:
        print("\n1. List server files")
        print("2. Upload a file")
        print("3. Download a file")
        print("4. Quit")

        choice = input("Choose an option: ").strip()

        try:
            if choice == "1":
                list_files()
            elif choice == "2":
                upload_file()
            elif choice == "3":
                download_file()
            elif choice == "4":
                print("Goodbye.")
                break
            else:
                print("Please choose 1, 2, 3, or 4.")
        except (OSError, ValueError, RuntimeError, KeyError) as error:
            print(f"Error: {error}")


if __name__ == "__main__":
    main()
