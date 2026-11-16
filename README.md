## cluster-file-sharing
Python TCP file sharing system running on a 4 node CentOS cluster. Supports uploads, downloads and multiple simultaneous clients.

## Cluster Setup

- Node1 runs the file server at 192.168.100.11.
- Node2 and Node3 are used as clients.
- Node4 stores the shared files using NFS.
- Node1 accesses the shared files at /mnt/shared/files.
- The server uses TCP port 12000.

## Files

- server.py runs the server.
- client.py shows the client menu.
- test_missing.py checks what happens when a file does not exist.

The programs use Python 3 and do not need extra Python packages.

## How It Works

The client connects to the server and sends a request to list, upload, or download files. Requests and responses use JSON. File contents are sent as bytes.

The program sends the file size so the receiver knows how much data to expect. The server uses a separate thread for each connection, allowing multiple clients to use it at the same time.

## Running the Server

On Node1, make sure /mnt/shared/files is mounted and your account can write to it.

From the folder containing server.py, run:

    python3 server.py

Leave this terminal open while using the clients.

If the firewall blocks connections, run these commands on Node1:

    sudo firewall-cmd --zone=public --add-port=12000/tcp
    sudo firewall-cmd --permanent --zone=public --add-port=12000/tcp

## Running the Client

On a client node, open the folder containing client.py and run:

    python3 client.py

The program creates uploads and downloads folders beside client.py.

The menu has four options:

1. List files on the server.
2. Upload a file.
3. Download a file.
4. Quit.

Put files you want to upload in the uploads folder. Downloaded files are saved in the downloads folder.

Uploading or downloading a file with an existing name replaces that file.

For a different setup, change SERVER in client.py and SHARED_FOLDER in server.py to match your network and storage folder.

## Tests

I tested listing files, uploading, and downloading from Node2. I compared the original and downloaded files using SHA-256. Their hashes matched.

I also tested two clients at the same time. Node2 uploaded a file slowly while Node3 requested the file list. Node3 received a response before the upload finished.

To test a missing file, run:

    python3 test_missing.py

The server returned an error message when the requested file did not exist.

## Limits

This is a class project for a local network. It does not include user accounts or encrypted connections. The server is started manually on Node1. Automatic failover was not configured or tested.
