"""
Seed script — inserts fake server data into MongoDB for UI testing.
Run once before starting the web app.

Usage:
    python seed_test_data.py
"""

import asyncio
from datetime import datetime, timezone
from motor.motor_asyncio import AsyncIOMotorClient

MONGO_URI = "mongodb+srv://roiblum05:0548818978@test.ymcnygm.mongodb.net/?appName=Test&tlsAllowInvalidCertificates=true"
DB_NAME = "server_scanner"
COLLECTION = "servers"

FAKE_SERVERS = [
    # Zone: zone-a — HP
    {
        "_id": "ocp4-hypershift-zone-a-01",
        "vendor": "HP",
        "zone": "zone-a",
        "bmc_address": "10.10.1.101",
        "mac_address": "aa:bb:cc:11:22:01",
        "cpu_model": "Intel Xeon Gold 6230R",
        "cpu_count": 2,
        "cpu_cores": 26,
        "memory_gb": 256,
        "model": "ProLiant DL380 Gen10",
        "serial": "MXQ12345AA",
        "disks": [{"size_gb": 960, "type": "SSD", "model": "MO000960JWFWR"}, {"size_gb": 960, "type": "SSD", "model": "MO000960JWFWR"}],
        "maintenance": None,
        "last_scanned": datetime.now(timezone.utc),
    },
    {
        "_id": "ocp4-hypershift-zone-a-02",
        "vendor": "HP",
        "zone": "zone-a",
        "bmc_address": "10.10.1.102",
        "mac_address": "aa:bb:cc:11:22:02",
        "cpu_model": "Intel Xeon Gold 6230R",
        "cpu_count": 2,
        "cpu_cores": 26,
        "memory_gb": 256,
        "model": "ProLiant DL380 Gen10",
        "serial": "MXQ12345AB",
        "disks": [{"size_gb": 960, "type": "SSD", "model": "MO000960JWFWR"}],
        "maintenance": None,
        "last_scanned": datetime.now(timezone.utc),
    },
    {
        "_id": "ocp4-hypershift-zone-a-03",
        "vendor": "HP",
        "zone": "zone-a",
        "bmc_address": "10.10.1.103",
        "mac_address": "aa:bb:cc:11:22:03",
        "cpu_model": "Intel Xeon Gold 6230R",
        "cpu_count": 2,
        "cpu_cores": 26,
        "memory_gb": 128,
        "model": "ProLiant DL360 Gen10",
        "serial": "MXQ12345AC",
        "disks": [{"size_gb": 480, "type": "SSD", "model": "MO000480JWFWR"}],
        "maintenance": {
            "reason": "Faulty NIC — replacement ordered",
            "severity": "high",
            "timestamp": "2025-03-10T09:00:00Z",
            "created_by": "roi.blum",
        },
        "last_scanned": datetime.now(timezone.utc),
    },
    # Zone: zone-b — HP + Dell
    {
        "_id": "ocp4-hypershift-zone-b-01",
        "vendor": "HP",
        "zone": "zone-b",
        "bmc_address": "10.10.2.101",
        "mac_address": "aa:bb:cc:22:33:01",
        "cpu_model": "Intel Xeon Silver 4210R",
        "cpu_count": 2,
        "cpu_cores": 10,
        "memory_gb": 192,
        "model": "ProLiant DL380 Gen10 Plus",
        "serial": "MXQ54321BA",
        "disks": [{"size_gb": 1920, "type": "SSD", "model": "MO001920JWFWR"}],
        "maintenance": None,
        "last_scanned": datetime.now(timezone.utc),
    },
    {
        "_id": "ocp4-hypershift-zone-b-02",
        "vendor": "DELL",
        "zone": "zone-b",
        "bmc_address": "10.10.2.201",
        "mac_address": "dd:ee:ff:22:33:01",
        "cpu_model": "Intel Xeon Gold 5220R",
        "cpu_count": 2,
        "cpu_cores": 24,
        "memory_gb": 384,
        "model": "PowerEdge R740",
        "serial": "DELL7890BA",
        "disks": [{"size_gb": 1200, "type": "HDD", "model": "ST1200MM0129"}, {"size_gb": 1200, "type": "HDD", "model": "ST1200MM0129"}],
        "maintenance": None,
        "last_scanned": datetime.now(timezone.utc),
    },
    {
        "_id": "ocp4-hypershift-zone-b-03",
        "vendor": "DELL",
        "zone": "zone-b",
        "bmc_address": "10.10.2.202",
        "mac_address": "dd:ee:ff:22:33:02",
        "cpu_model": "Intel Xeon Gold 5220R",
        "cpu_count": 2,
        "cpu_cores": 24,
        "memory_gb": 384,
        "model": "PowerEdge R740",
        "serial": "DELL7890BB",
        "disks": [{"size_gb": 1200, "type": "HDD", "model": "ST1200MM0129"}],
        "maintenance": None,
        "last_scanned": datetime.now(timezone.utc),
    },
    # Zone: zone-c — Cisco
    {
        "_id": "ocp4-hypershift-zone-c-01",
        "vendor": "CISCO",
        "zone": "zone-c",
        "bmc_address": "10.10.3.101",
        "mac_address": "cc:11:22:33:44:01",
        "cpu_model": "Intel Xeon Gold 6248R",
        "cpu_count": 2,
        "cpu_cores": 24,
        "memory_gb": 512,
        "model": "UCS B200 M5",
        "serial": "FCH2247ABCD",
        "disks": [{"size_gb": 240, "type": "SSD", "model": "UCS-SD-240G6S1"}],
        "maintenance": None,
        "last_scanned": datetime.now(timezone.utc),
    },
    {
        "_id": "ocp4-hypershift-zone-c-02",
        "vendor": "CISCO",
        "zone": "zone-c",
        "bmc_address": "10.10.3.102",
        "mac_address": "cc:11:22:33:44:02",
        "cpu_model": "Intel Xeon Gold 6248R",
        "cpu_count": 2,
        "cpu_cores": 24,
        "memory_gb": 512,
        "model": "UCS B200 M5",
        "serial": "FCH2247ABCE",
        "disks": [{"size_gb": 240, "type": "SSD", "model": "UCS-SD-240G6S1"}],
        "maintenance": {
            "reason": "Memory DIMM replacement scheduled",
            "severity": "medium",
            "timestamp": "2025-03-11T14:00:00Z",
            "created_by": "ops-team",
        },
        "last_scanned": datetime.now(timezone.utc),
    },
    {
        "_id": "ocp4-hypershift-zone-c-03",
        "vendor": "CISCO",
        "zone": "zone-c",
        "bmc_address": "10.10.3.103",
        "mac_address": "cc:11:22:33:44:03",
        "cpu_model": "Intel Xeon Gold 6248R",
        "cpu_count": 2,
        "cpu_cores": 24,
        "memory_gb": 256,
        "model": "UCS C240 M5",
        "serial": "FCH2247ABCF",
        "disks": [{"size_gb": 960, "type": "SSD", "model": "UCS-SD-960GS1"}, {"size_gb": 960, "type": "SSD", "model": "UCS-SD-960GS1"}],
        "maintenance": None,
        "last_scanned": datetime.now(timezone.utc),
    },
    # Zone: zone-a — Dell (mixed zone)
    {
        "_id": "ocp4-hypershift-zone-a-04",
        "vendor": "DELL",
        "zone": "zone-a",
        "bmc_address": "10.10.1.201",
        "mac_address": "dd:ee:ff:11:22:01",
        "cpu_model": "AMD EPYC 7542",
        "cpu_count": 2,
        "cpu_cores": 32,
        "memory_gb": 512,
        "model": "PowerEdge R7525",
        "serial": "DELL1234AA",
        "disks": [{"size_gb": 3840, "type": "SSD", "model": "MTFDDAV3T8TDS"}],
        "maintenance": None,
        "last_scanned": datetime.now(timezone.utc),
    },
]


async def seed():
    client = AsyncIOMotorClient(MONGO_URI)
    db = client[DB_NAME]
    col = db[COLLECTION]

    try:
        # Verify connection
        await client.admin.command("ping")
        print(f"✓ Connected to MongoDB cluster")

        # Drop existing test data
        await col.drop()
        print(f"✓ Cleared existing '{COLLECTION}' collection")

        # Insert fake servers
        result = await col.insert_many(FAKE_SERVERS)
        print(f"✓ Inserted {len(result.inserted_ids)} fake server documents")

        # Summary
        print("\nSeeded servers:")
        zones = {}
        for s in FAKE_SERVERS:
            z = s["zone"]
            zones.setdefault(z, []).append(f"  [{s['vendor']}] {s['_id']}")
        for zone, names in sorted(zones.items()):
            print(f"  {zone}:")
            for n in names:
                maint = " ⚠ MAINTENANCE" if FAKE_SERVERS[[s["_id"] for s in FAKE_SERVERS].index(n.split("] ")[1])].get("maintenance") else ""
                print(f"{n}{maint}")

    finally:
        client.close()

    print("\n✓ Done — start the web app with:")
    print("  MONGO_URI='<uri>' MONGO_DB_NAME=server_scanner python -m src.web_ui")


if __name__ == "__main__":
    asyncio.run(seed())
