import socket
import psycopg2

# Replace with your Neon connection string
DATABASE_URL = ""

try:
    conn = psycopg2.connect(DATABASE_URL)
    cursor = conn.cursor()

    print("Connected to Neon database!")

    # Example query
    cursor.execute("SELECT NOW();")
    result = cursor.fetchone()
    print("Current time from DB:", result)

    cursor.close()
    conn.close()

except Exception as e:
    print("Connection failed:", e)
    

def start_server():
    host = "0.0.0.0"   # listen on all available network interfaces

    # ask the user what port the server should run on 
    port = int(input("Enter port number for server: "))

    # create a TCP socket 
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    # bind the socket to the host and port
    server_socket.bind((host, port))

    # start listening for incoming connections, allow only 1 connection at a time
    server_socket.listen(1)

    print(f"Server listening on port {port}...")

    # wait for a client to connect
    conn, addr = server_socket.accept()
    print("Connected by:", addr)

    # keep receiving messages until the client disconnects
    while True:
        data = conn.recv(1024)

        # if no data is received, it means the client has disconnected
        if not data:
            break

        message = data.decode()
        print("Received:", message)

        # convert the message to uppercase and send it back to the client
        response = message.upper()
        conn.send(response.encode())

    # close the connection and the server socket
    conn.close()
    server_socket.close()

start_server()