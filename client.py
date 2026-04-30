import socket

# The three supported queries (stripped for flexible matching)
SUPPORTED_QUERIES = [
    "What is the average moisture inside our kitchen fridges in the past hours, week and month?",
    "What is the average water consumption per cycle across our smart dishwashers in the past hour, week and month?",
    "Which house consumed more electricity in the past 24 hours, and by how much?"
]

def display_supported_queries():
    print("\nSupported queries:")
    for i, query in enumerate(SUPPORTED_QUERIES, 1):
        print(f"  {i}. {query}")
    print()

def is_valid_query(user_input):
    """
    Returns the full query string if the input is valid (number or full text),
    or None if it is not recognized.
    """
    stripped = user_input.strip()

    # Accept number shortcuts 1, 2, 3
    if stripped in ("1", "2", "3"):
        return SUPPORTED_QUERIES[int(stripped) - 1]

    # Accept full query text (case-insensitive)
    for query in SUPPORTED_QUERIES:
        if stripped.lower() == query.lower():
            return query

    return None

def start_client():

    # Ask the user for the server's IP address and port number
    server_ip = input("Enter server IP address: ")

    try:
        server_port = int(input("Enter server port number: "))
    except ValueError:
        # If the port is not a number, show an error and stop
        print("Invalid port number.")
        return

    # Create a TCP socket
    client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    try:
        # Attempt to connect to the server
        client_socket.connect((server_ip, server_port))
        print(f"\nConnected to server at {server_ip}:{server_port}")
    except:
        # If the connection fails, show an error and stop
        print("Error connecting to server.")
        return

    display_supported_queries()

    # Keep sending messages until the user types "quit"
    while True:

        message = input("Enter query number (1-3) or full query text (or 'quit' to exit): ").strip()

        if message.lower() == "quit":
            print("Closing connection. Goodbye!")
            break

        # Resolve number shortcut or full query text
        resolved = is_valid_query(message)

        if resolved is None:
            print("\nSorry, this query cannot be processed. Please try one of the supported queries.")
            display_supported_queries()
            continue

        # Send the resolved full query to the server
        client_socket.send(resolved.encode())

        # Wait for the server's response and display it
        response = client_socket.recv(4096).decode()
        print(f"\nServer response: {response}\n")

    # Close the connection when done
    client_socket.close()

start_client()