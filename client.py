# client.py
import socket
import threading
import sys
import os
import time
import hashlib
import mimetypes

BUFFER_SIZE = 4096

def receive_messages(client_socket):
    while True:
        try:
            message = client_socket.recv(1024).decode('utf-8')
            if not message:
                break
            print(f"Diterima dari server: {message}")
        except Exception as e:
            print(f"Error receive_messages: {e}")
            break

def calculate_checksum(data):
    return hashlib.md5(data).hexdigest()

def send_file(client_socket, filepath, retries=3):
    if not os.path.exists(filepath):
        print(f"File {filepath} tidak ditemukan.")
        send_serial_error(client_socket, f"File {filepath} tidak ditemukan.")
        return

    if not os.path.isfile(filepath):
        print(f"{filepath} bukan file yang valid.")
        send_serial_error(client_socket, f"{filepath} bukan file yang valid.")
        return

    filename = os.path.basename(filepath)
    filesize = os.path.getsize(filepath)
    mime_type, _ = mimetypes.guess_type(filepath)
    file_type = mime_type if mime_type else 'application/octet-stream'
    client_socket.send(f'file_transfer{filename},{filesize},{file_type}'.encode('utf-8'))
    
    try:
        with open(filepath, 'rb') as f:
            bytes_sent = 0
            start_time = time.time()
            while (chunk := f.read(BUFFER_SIZE)):
                try:
                    client_socket.send(chunk)
                    bytes_sent += len(chunk)
                    elapsed_time = time.time() - start_time
                    transfer_speed = bytes_sent / elapsed_time / 1024  # KB/s
                    percentage = (bytes_sent / filesize) * 100
                    print(f"Terkirim: {bytes_sent}/{filesize} byte ({percentage:.2f}%), Kecepatan: {transfer_speed:.2f} KB/s")
                except Exception as e:
                    print(f"Error send_file: {e}")
                    if retries > 0:
                        print(f"Mengirim pesan error serial ke server... {retries} upaya tersisa")
                        send_serial_error(client_socket, str(e))
                        reconnect_and_resend(client_socket, filepath, retries - 1)
                    else:
                        print("Pengiriman file dibatalkan setelah 3 kali percobaan gagal.")
                    return
    except Exception as e:
        print(f"Error opening file: {e}")
        if retries > 0:
            print(f"Mengirim pesan error serial ke server... {retries} upaya tersisa")
            send_serial_error(client_socket, str(e))
            reconnect_and_resend(client_socket, filepath, retries - 1)
        else:
            print("Pengiriman file dibatalkan setelah 3 kali percobaan gagal.")
        return
    
    try:
        with open(filepath, 'rb') as f:
            file_data = f.read()
            checksum = calculate_checksum(file_data)
            client_socket.send(checksum.encode('utf-8'))

        print(f"File {filename} berhasil dikirim dengan checksum {checksum}")

        response = client_socket.recv(1024).decode('utf-8')
        if response == 'retransmit':
            print(f"Retransmisi file {filename} karena kesalahan checksum")
            send_file(client_socket, filepath, retries)
    except Exception as e:
        print(f"Error finalizing send: {e}")
        if retries > 0:
            print(f"Mengirim pesan error serial ke server... {retries} upaya tersisa")
            send_serial_error(client_socket, str(e))
            reconnect_and_resend(client_socket, filepath, retries - 1)
        else:
            print("Pengiriman file dibatalkan setelah 3 kali percobaan gagal.")
        return

def send_serial_error(client_socket, error_message):
    try:
        client_socket.send(f'serial_error{error_message}'.encode('utf-8'))
    except Exception as e:
        print(f"Error sending serial error: {e}")

def reconnect_and_resend(client_socket, filepath, retries):
    try:
        client_socket.close()
        host = input("Masukkan IP server untuk reconnect: ")
        port = 12345
        robot_id = input("Masukkan ID robot untuk reconnect: ")
        client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        client_socket.connect((host, port))
        print(f"{robot_id} terhubung kembali ke server di {host}:{port}")
        
        initial_message = f'register {robot_id}'
        client_socket.send(initial_message.encode('utf-8'))
        
        send_file(client_socket, filepath, retries)
    except Exception as e:
        print(f"Error reconnecting: {e}")
        if retries > 0:
            reconnect_and_resend(client_socket, filepath, retries - 1)
        else:
            print("Pengiriman file dibatalkan setelah 3 kali percobaan gagal.")
            return

def start_client(host, port, robot_id):
    client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    client_socket.connect((host, port))
    print(f"{robot_id} terhubung ke server di {host}:{port}")

    receive_thread = threading.Thread(target=receive_messages, args=(client_socket,))
    receive_thread.start()

    initial_message = f'register {robot_id}'
    client_socket.send(initial_message.encode('utf-8'))

    while True:
        try:
            choice = input("Pilih opsi (1. Kirim pesan, 2. Kirim data): ")
            if choice == '1':
                message = f'[{robot_id}] '
                message += input("Masukkan pesan yang akan dikirim: ")
                client_socket.send(message.encode('utf-8'))
            elif choice == '2':
                data_type = input("Pilih jenis data yang akan dikirim (1. data serial, 2. data lain): ")
                if data_type == '1':
                    data = input("Masukkan data serial: ")
                    client_socket.send(f'serial_data{data}'.encode('utf-8'))
                elif data_type == '2':
                    filepath = input("Masukkan path file yang akan dikirim: ")
                    send_file(client_socket, filepath)
                else:
                    print("Pilihan tidak valid")
            else:
                print("Pilihan tidak valid")
        except Exception as e:
            print(f"Error start_client: {e}")
            client_socket.close()
            break

if __name__ == "__main__":
    host = input("Masukkan IP server: ")
    port = 12345  # Server port
    robot_id = input("Masukkan ID robot: ")
    start_client(host, port, robot_id)
