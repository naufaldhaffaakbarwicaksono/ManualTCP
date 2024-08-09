# server.py
import socket
import threading
import os
import time
import hashlib
import mimetypes

clients = {}
lock = threading.Lock()
BUFFER_SIZE = 4096

def handle_client(device_id, client_socket, addr):
    global clients
    while True:
        try:
            metadata = client_socket.recv(1024).decode('utf-8')
            if not metadata:
                break
            if metadata.startswith('file_transfer'):
                receive_file(client_socket, metadata[13:])
            elif metadata.startswith('serial_data'):
                handle_serial_data(client_socket, metadata[12:])
            elif metadata.startswith('serial_error'):
                handle_serial_error(client_socket, metadata[12:])
            else:
                print(f"Diterima dari {device_id} {addr}: {metadata}")
                response = f"Menggemakan: {metadata}"
                client_socket.send(response.encode('utf-8'))
        except Exception as e:
            print(f"Error handle_client: {e}")
            break
    with lock:
        del clients[device_id]
        print(f"{device_id} {addr} terputus")
    client_socket.close()

def handle_serial_data(client_socket, data):
    print(f"Data serial diterima: {data}")
    response = f"Data serial diterima: {data}"
    client_socket.send(response.encode('utf-8'))

def handle_serial_error(client_socket, error_message):
    print(f"Error dari klien: {error_message}")

def calculate_checksum(data):
    return hashlib.md5(data).hexdigest()

def receive_file(client_socket, metadata):
    filename, filesize, file_type = metadata.split(',')
    filesize = int(filesize)
    filepath = os.path.join('received_files', filename)
    try:
        with open(filepath, 'wb') as f:
            bytes_received = 0
            start_time = time.time()
            while bytes_received < filesize:
                try:
                    chunk = client_socket.recv(min(BUFFER_SIZE, filesize - bytes_received))
                    if not chunk:
                        break
                    f.write(chunk)
                    bytes_received += len(chunk)
                    elapsed_time = time.time() - start_time
                    transfer_speed = bytes_received / elapsed_time / 1024  # KB/s
                    percentage = (bytes_received / filesize) * 100
                    print(f"Diterima: {bytes_received}/{filesize} byte ({percentage:.2f}%), Kecepatan: {transfer_speed:.2f} KB/s")
                except Exception as e:
                    print(f"Error receive_file: {e}")
                    break
        print(f"File {filename} ({filesize} byte) diterima")

        # Verifikasi checksum
        client_socket.send("checksum_request".encode('utf-8'))
        received_checksum = client_socket.recv(1024).decode('utf-8')
        with open(filepath, 'rb') as f:
            file_data = f.read()
            calculated_checksum = calculate_checksum(file_data)

        if received_checksum != calculated_checksum:
            print(f"Checksum tidak cocok untuk {filename}. Meminta retransmisi.")
            client_socket.send("retransmit".encode('utf-8'))
            receive_file(client_socket, metadata)
        else:
            print(f"File {filename} diterima dengan benar dengan checksum {calculated_checksum}")
    except Exception as e:
        print(f"Error handling file reception: {e}")
        if os.path.exists(filepath):
            os.remove(filepath)

def get_ip_address():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        # Membuat koneksi tiruan ke server eksternal untuk mendapatkan alamat IP jaringan
        s.connect(('8.8.8.8', 1))  # Google Public DNS server
        ip_address = s.getsockname()[0]
    except Exception:
        ip_address = '127.0.0.1'
    finally:
        s.close()
    return ip_address

def start_server(port):
    global clients
    os.makedirs('received_files', exist_ok=True)
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.bind(('0.0.0.0', port))
    server_socket.listen(5)
    server_ip = get_ip_address()
    print(f"Server dimulai dan mendengarkan di IP {server_ip}, port {port}")

    while True:
        client_socket, addr = server_socket.accept()
        with lock:
            metadata = client_socket.recv(1024).decode('utf-8')
            if metadata.startswith('register'):
                device_id = metadata[9:]
                clients[device_id] = [addr, client_socket]
        print(f"Koneksi dari {device_id} {addr}")
        client_handler = threading.Thread(target=handle_client, args=(device_id, client_socket, addr))
        client_handler.start()

def send_to_client(client_id, message):
    global clients
    with lock:
        if client_id in clients:
            clients[client_id][1].send(message.encode('utf-8'))
        else:
            print(f"Klien {client_id} tidak terhubung")

if __name__ == "__main__":
    port = 12345  # Server port
    server_ip = get_ip_address()
    print(f"Server dimulai dan mendengarkan di IP {server_ip}, port {port}")
    server_thread = threading.Thread(target=start_server, args=(port,))
    server_thread.start()
    
    # Contoh mengirim pesan ke klien tertentu
    while True:
        try:
            menu = int(input("""
            Pilih salah satu menu ini!
            1. Daftar klien
            2. Kirim data
            3. Tampilkan IP server
            """))

            if menu == 1:
                if clients:
                    for client in clients:
                        print(f"{client} - {clients[client][0]}")
                else:
                    print("Tidak ada klien yang terhubung")
            elif menu == 2:
                if clients:
                    client_id = input("Masukkan ID klien: ")
                    data_type = input("Pilih jenis data yang akan dikirim (1. data serial, 2. data lain): ")
                    if data_type == '1':
                        data = input("Masukkan data serial: ")
                        send_to_client(client_id, f"serial_data{data}")
                    elif data_type == '2':
                        filepath = input("Masukkan path file yang akan dikirim: ")
                        send_to_client(client_id, f"file_transfer{os.path.basename(filepath)},{os.path.getsize(filepath)},{mimetypes.guess_type(filepath)[0]}")
                        try:
                            with open(filepath, 'rb') as f:
                                while (chunk := f.read(BUFFER_SIZE)):
                                    clients[client_id][1].send(chunk)
                        except Exception as e:
                            print(f"Error sending file to client: {e}")
                    else:
                        print("Pilihan tidak valid")
                else:
                    print("Tidak ada klien yang terhubung")
            elif menu == 3:
                print(f"IP server: {server_ip}, Port: {port}")
            else:
                print("Pilihan tidak valid")
        except KeyboardInterrupt:
            break