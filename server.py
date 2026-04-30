import socket
from matplotlib.pylab import rint
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

# ============================================================
# NETWORK CONFIG
# ============================================================

HOST = "0.0.0.0"

LOCAL_DATABASE_URL = "postgresql://neondb_owner:npg_Nqr2szKZOla8@ep-autumn-term-an4pvkxw-pooler.c-6.us-east-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require"
PEER_DATABASE_URL = "postgresql://neondb_owner:npg_u1GTlNjaIR4D@ep-odd-breeze-am7dbemd-pooler.c-5.us-east-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require"


SHARING_START_UTC_STR = "2026-04-20 18:30:00"

PACIFIC_TZ = ZoneInfo("America/Los_Angeles")

# ============================================================
# TABLE CONFIG
# ============================================================

LOCAL_TABLE_SCHEMA = "public"
LOCAL_TABLE_NAME = "IoT_virtual"
LOCAL_TABLE_CASE_SENSITIVE = True

PEER_TABLE_SCHEMA = "public"
PEER_TABLE_NAME = "sensor_data_virtual"
PEER_TABLE_CASE_SENSITIVE = False

# ============================================================
# SUPPORTED QUERIES
# ============================================================

QUERY_1 = "what is the average moisture inside our kitchen fridges in the past hours, week and month?"
QUERY_2 = "what is the average water consumption per cycle across our smart dishwashers in the past hour, week and month?"
QUERY_3 = "which house consumed more electricity in the past 24 hours, and by how much?"


# ============================================================
# TIME HELPERS
# ============================================================

def parse_sharing_start():
    dt = datetime.strptime(SHARING_START_UTC_STR, "%Y-%m-%d %H:%M:%S")
    return dt.replace(tzinfo=timezone.utc)

SHARING_START_UTC = parse_sharing_start()


def utc_now():
    return datetime.now(timezone.utc)


def to_pacific_string(dt_utc):
    return dt_utc.astimezone(PACIFIC_TZ).strftime("%Y-%m-%d %I:%M:%S %p %Z")


# ============================================================
# DB HELPERS
# ============================================================

def get_connection(db_url):
    return psycopg2.connect(db_url, cursor_factory=RealDictCursor)


def build_table_name(schema, table_name, case_sensitive):
    if case_sensitive:
        return f'{schema}."{table_name}"'
    return f"{schema}.{table_name}"


def safe_float(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def average(values):
    return sum(values) / len(values) if values else 0.0


def query_complete_locally(start_time_utc):
    """
    Local DB contains:
    - all of your own history
    - partner shared data only after sharing began
    """
    return start_time_utc >= SHARING_START_UTC


def merge_rows(local_rows, peer_rows):
    seen = set()
    merged = []

    for row in local_rows + peer_rows:
        key = (
            row.get("house_id"),
            row.get("device_id"),
            row.get("board_name"),
            row.get("sensor_name"),
            row.get("value"),
            row.get("time"),
        )
        if key not in seen:
            seen.add(key)
            merged.append(row)

    return merged


# ============================================================
# HOUSE OWNERSHIP LOGIC
# ============================================================

def determine_house_id(payload_topic, board_name, asset_uid):

    if payload_topic:
        topic_lower = payload_topic.strip().lower()

        if "nsn131203@gmail.com" in topic_lower:
            return "House A"

        if  "smngo100@gmail.com" in topic_lower:
            return "House B"

    return "Unknown House"


# ============================================================
# RAW FETCH + PAYLOAD EXPANSION
# ============================================================

def fetch_sensor_rows(db_url, start_time_utc, end_time_utc, source="local"):
    if source == "local":
        full_table_name = build_table_name(
            LOCAL_TABLE_SCHEMA,
            LOCAL_TABLE_NAME,
            LOCAL_TABLE_CASE_SENSITIVE
        )
    else:
        full_table_name = build_table_name(
            PEER_TABLE_SCHEMA,
            PEER_TABLE_NAME,
            PEER_TABLE_CASE_SENSITIVE
        )

    sql = f"""
        SELECT
            id,
            topic,
            time,
            payload
        FROM {full_table_name}
        WHERE time >= %s
          AND time <= %s
        ORDER BY time ASC
    """

    with get_connection(db_url) as conn:
        with conn.cursor() as cursor:
            cursor.execute(sql, [start_time_utc, end_time_utc])
            raw_rows = cursor.fetchall()

    expanded = []

    for row in raw_rows:
        payload = row.get("payload") or {}

        payload_topic = payload.get("topic")
        board_name = payload.get("board_name")
        asset_uid = payload.get("asset_uid")
        parent_asset_uid = payload.get("parent_asset_uid")

        house_id = determine_house_id(payload_topic, board_name, asset_uid)

        for key, val in payload.items():
            if key in {
                "timestamp",
                "topic",
                "parent_asset_uid",
                "asset_uid",
                "board_name",
            }:
                continue

            numeric_val = safe_float(val)
            if numeric_val is None:
                continue

            expanded.append({
                "house_id": house_id,
                "device_id": asset_uid,
                "parent_device_id": parent_asset_uid,
                "board_name": board_name,
                "sensor_name": key,
                "value": numeric_val,
                "time": row["time"],
                "payload_topic": payload_topic,
                "db_topic": row["topic"],
                "source": source,
            })

    return expanded


def get_complete_sensor_dataset(start_time_utc, end_time_utc):
    local_rows = fetch_sensor_rows(
        LOCAL_DATABASE_URL,
        start_time_utc,
        end_time_utc,
        source="local"
    )

    if query_complete_locally(start_time_utc):
        return local_rows

    peer_end = min(end_time_utc, SHARING_START_UTC)
    peer_rows = fetch_sensor_rows(
        PEER_DATABASE_URL,
        start_time_utc,
        peer_end,
        source="peer"
    )

    return merge_rows(local_rows, peer_rows)


# ============================================================
# SENSOR FILTERS
# ============================================================

def filter_moisture_rows(rows):
    results = []
    for r in rows:
        sensor_name = (r.get("sensor_name") or "").lower()
        board_name = (r.get("board_name") or "").lower()

        if "moisture" in sensor_name:
            # tighten this later if needed
            if "kitchen" in board_name or "fridge" in board_name or True:
                results.append(r)

    return results


def filter_dishwasher_water_rows(rows):
    results = []
    for r in rows:
        sensor_name = (r.get("sensor_name") or "").lower()
        board_name = (r.get("board_name") or "").lower()

        if ("water" in sensor_name or "flow" in sensor_name) and (
            "dishwasher" in board_name or "dishwasher" in sensor_name
        ):
            results.append(r)

    return results


def filter_electricity_rows(rows):
    results = []
    for r in rows:
        sensor_name = (r.get("sensor_name") or "").lower()

        if (
            "acs712 - dishwasher current sensor" in sensor_name
            or "dishwasher ammeter" in sensor_name
            or "fride-ammeter" in sensor_name
            or sensor_name == "ammeter"
            or "ammeter - acs712" in sensor_name
            or sensor_name.startswith("ammeter ")
        ):
            results.append(r)

    return results


# ============================================================
# QUERY PROCESSORS
# ============================================================

def process_fridge_moisture():
    now_utc = utc_now()

    windows = [
        ("Past hour", now_utc - timedelta(hours=1), now_utc),
        ("Past week", now_utc - timedelta(days=7), now_utc),
        ("Past month", now_utc - timedelta(days=30), now_utc),
    ]

    lines = []

    for label, start_utc, end_utc in windows:
        rows = get_complete_sensor_dataset(start_utc, end_utc)
        moisture_rows = filter_moisture_rows(rows)

        values = [r["value"] for r in moisture_rows]
        avg_value = average(values)

        lines.append(
            f"{label}: {avg_value:.2f}% "
            f"(window: {to_pacific_string(start_utc)} to {to_pacific_string(end_utc)})"
        )

    return "Average moisture inside our kitchen fridges:\n" + "\n".join(lines)


def process_dishwasher_water():
    now_utc = utc_now()

    windows = [
        ("Past hour", now_utc - timedelta(hours=1), now_utc),
        ("Past week", now_utc - timedelta(days=7), now_utc),
        ("Past month", now_utc - timedelta(days=30), now_utc),
    ]

    lines = []

    for label, start_utc, end_utc in windows:
        rows = get_complete_sensor_dataset(start_utc, end_utc)
        water_rows = filter_dishwasher_water_rows(rows)

        LITERS_TO_GALLONS = 0.264172
        values = [r["value"] for r in water_rows]
        avg_value = average(values)

        lines.append(
            f"{label}: {avg_value:.2f} gallons/cycle "
            f"(converted from L/min using x 0.264172; "
            f"window: {to_pacific_string(start_utc)} to {to_pacific_string(end_utc)})"
        )

    return "Average water consumption per cycle across our smart dishwashers:\n" + "\n".join(lines)


def process_electricity_comparison():
    end_utc = utc_now()
    start_utc = end_utc - timedelta(hours=24)

    rows = get_complete_sensor_dataset(start_utc, end_utc)
    partner_rows = [r for r in rows if r["house_id"] == "House B"]

    for r in partner_rows[:50]:
        print(
            "HOUSE B RAW ->",
            "sensor:", r["sensor_name"],
            "board:", r["board_name"],
            "topic:", r["payload_topic"]
        )


    electricity_rows = filter_electricity_rows(rows)

    totals = {}
    for r in electricity_rows:
        house_id = r["house_id"]
        totals[house_id] = totals.get(house_id, 0.0) + abs(r["value"])

    valid_totals = {k: v for k, v in totals.items() if k != "Unknown House"}
    print("VALID TOTALS:", valid_totals)

    if len(valid_totals) < 2:
        return (
            "Could not compare both houses because fewer than two house groups were found. "
            "Check the terminal output for SENSOR NAME COUNTS and update "
            "filter_electricity_rows() and determine_house_id()."
        )

    ranked = sorted(valid_totals.items(), key=lambda x: x[1], reverse=True)
    winner_house, winner_value = ranked[0]
    loser_house, loser_value = ranked[1]
    difference = winner_value - loser_value

    return (
        f"Electricity comparison for the past 24 hours "
        f"({to_pacific_string(start_utc)} to {to_pacific_string(end_utc)}):\n"
        f"{winner_house} consumed more electricity.\n"
        f"{winner_house}: {winner_value:.2f}\n"
        f"{loser_house}: {loser_value:.2f}\n"
        f"Difference: {difference:.2f}\n"
    )


# ============================================================
# QUERY ROUTER
# ============================================================

def handle_query(message):
    normalized = message.strip().lower()

    if normalized == QUERY_1:
        return process_fridge_moisture()
    elif normalized == QUERY_2:
        return process_dishwasher_water()
    elif normalized == QUERY_3:
        return process_electricity_comparison()
    else:
        return "Sorry, this query cannot be processed. Please try one of the supported queries."


# ============================================================
# TCP SERVER
# ============================================================

def start_server():
    port = int(input("Enter port number for server: "))

    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.bind((HOST, port))
    server_socket.listen(5)

    print(f"Server listening on {HOST}:{port}")

    while True:
        conn, addr = server_socket.accept()
        print("Connected by:", addr)

        try:
            while True:
                data = conn.recv(4096)
                if not data:
                    break

                message = data.decode().strip()
                print("Received:", message)

                try:
                    response = handle_query(message)
                except Exception as e:
                    response = f"Server error while processing query: {e}"

                conn.sendall(response.encode())

        finally:
            conn.close()


if __name__ == "__main__":
    start_server()