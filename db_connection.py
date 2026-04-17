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