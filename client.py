import socket

def start_client():

    # ask the user for the server's IP address and port number
    server_ip = input("Enter server IP address: ")

    try:
        server_port = int(input("Enter server port number: "))
    except ValueError:
        # if the port is not a number, show an error and stop
        print("Invalid port number.")
        return

    # create a TCP socket 
    client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    try:
        # attempt to connect to the server
        client_socket.connect((server_ip, server_port))
    except:
        # if the connection fails, show an error and stop
        print("Error connecting to server.")
        return

    # keep sending messages until the user types "quit"
    while True:

        message = input("Enter message (type 'quit' to exit): ")

        if message.lower() == "quit":
            break

        # send the message to the server
        client_socket.send(message.encode())

        # wait for the server's response and display it 
        response = client_socket.recv(1024).decode()

        print("Server response:", response)

    # close the connection when done
    client_socket.close()

start_client()