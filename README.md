# Assignment 8: Distributed End-to-End IoT System

**CECS 327 – Intro to Networking and Distributed Systems**

---

## Overview

This project implements a distributed end-to-end IoT system in which two student environments (House A and House B) each generate sensor data through their own DataNiz virtual devices and Neon PostgreSQL databases. A TCP client/server architecture allows either teammate to query the combined dataset, including data from before and after the DataNiz sharing period began.

---

## System Architecture

```
[TCP Client] ──query──► [TCP Server]
                              │
              ┌───────────────┴───────────────┐
              ▼                               ▼
   [Local Neon DB (House A)]      [Peer Neon DB (House B)]
   - All own historical data      - Queried only for pre-sharing
   - Peer data after sharing        historical data not yet in
     start time (replicated)        the local DB
```

- **House A** is associated with the DataNiz account `nsn131203@gmail.com`
- **House B** is associated with the DataNiz account `smngo100@gmail.com`
- Sharing began at: **2026-04-20 18:30:00 UTC**

The system applies **forward-only replication semantics**: shared data appears in the local database only from the sharing start time onward. For query windows that extend before that timestamp, the server queries the peer's original database for the missing historical portion.

---

## Prerequisites

- Python 3.11+
- `psycopg2` library

Install dependencies:

```bash
pip install psycopg2-binary
```

---

## Running the System

### 1. Start the TCP Server

Run `server.py` on any machine with internet access to the Neon databases:

```bash
python server.py
```

You will be prompted to enter a port number (e.g., `5000`). The server will then listen for incoming client connections.

### 2. Start the TCP Client

Run `client.py` on any machine that can reach the server:

```bash
python client.py
```

You will be prompted for:

- **Server IP address** — the IP of the machine running `server.py`
- **Server port number** — the port you entered when starting the server

---

## Supported Queries

The client accepts only the following three queries (case-insensitive):

1. `What is the average moisture inside our kitchen fridges in the past hours, week and month?`
2. `What is the average water consumption per cycle across our smart dishwashers in the past hour, week and month?`
3. `Which house consumed more electricity in the past 24 hours, and by how much?`

Any other input is rejected with a friendly message and the supported queries are re-displayed.

To exit, type `quit`.

---

## How Distributed Query Processing Works

All query logic lives in `server.py`. For each query, the server:

1. Determines the required time window (e.g., past hour, past week, past month, or past 24 hours).
2. Calls `query_complete_locally(start_time_utc)` to check whether the local database already contains the full replicated peer dataset for that window.
   - If `start_time_utc >= SHARING_START_UTC`, the local DB has all shared peer data → **no peer query needed**.
   - Otherwise, the server queries the **peer database** for the sub-window `[start_time_utc, SHARING_START_UTC)` to fill the gap.
3. Merges local and peer rows using `merge_rows()`, which deduplicates by a composite key of `(house_id, device_id, board_name, sensor_name, value, time)`.
4. Filters the merged dataset by the relevant sensor type for the query.
5. Computes results (averages or totals) and returns a formatted response to the client.

---

## How House Ownership Is Preserved

The function `determine_house_id()` in `server.py` inspects the `topic` field embedded in each row's JSON payload. If the topic contains:

- `nsn131203@gmail.com` → the record belongs to **House A**
- `smngo100@gmail.com` → the record belongs to **House B**

This ensures that even after DataNiz forwards House B's data into House A's database, every record retains its original house label throughout processing.

---

## How DataNiz Metadata Was Used

Each IoT payload from DataNiz contains metadata fields used by the server:

| Field                | Usage                                                           |
| -------------------- | --------------------------------------------------------------- |
| `topic`              | Identifies which student account (house) owns the record        |
| `board_name`         | Used to filter relevant device types (e.g., fridge, dishwasher) |
| `asset_uid`          | Used as `device_id` to track individual devices                 |
| `parent_asset_uid`   | Used as `parent_device_id` for device hierarchy                 |
| Numeric payload keys | Parsed as sensor readings (moisture, water flow, current)       |

Non-numeric and metadata-only fields (`timestamp`, `topic`, `asset_uid`, etc.) are skipped during sensor expansion to avoid polluting the readings dataset.

---

## Calculations and Unit Conventions

All timestamps are stored in UTC in the database and converted to **Pacific Time (America/Los_Angeles)** before display.

| Query             | Sensor                          | Unit                 | Notes                                            |
| ----------------- | ------------------------------- | -------------------- | ------------------------------------------------ |
| Moisture          | Moisture sensor                 | %                    | Raw percentage value from DataNiz                |
| Water consumption | Water flow / dishwasher sensor  | gallons/cycle        | Converted from raw sensor value if needed        |
| Electricity       | Ammeter / ACS712 current sensor | Amperes (cumulative) | Summed absolute readings per house over 24 hours |

> **Note on electricity units:** The ACS712 sensor reports current in Amperes. The reported values represent cumulative summed current readings across all ammeter sensors for each house over the 24-hour window. True energy (kWh) would require multiplying by voltage and time, which requires stable voltage assumptions. The unit is documented in the report.

---

## Database Configuration

| Variable                | Description                                                |
| ----------------------- | ---------------------------------------------------------- |
| `LOCAL_DATABASE_URL`    | Neon PostgreSQL connection string for House A's database   |
| `PEER_DATABASE_URL`     | Neon PostgreSQL connection string for House B's database   |
| `LOCAL_TABLE_NAME`      | `IoT_virtual` (case-sensitive, schema: `public`)           |
| `PEER_TABLE_NAME`       | `sensor_data_virtual` (case-insensitive, schema: `public`) |
| `SHARING_START_UTC_STR` | `"2026-04-20 18:30:00"` — when DataNiz sharing was enabled |

---

## Repository Structure

```
├── server.py       # TCP server with distributed query logic
├── client.py       # TCP client with query validation
└── README.md       # This file
```

---

## Known Limitations

- The system does not support concurrent client connections (connections are handled sequentially).
- Electricity unit is reported as summed current (A); true kWh calculation would require known voltage and sampling interval.
- If both databases are unreachable simultaneously, the server returns an error message to the client.
