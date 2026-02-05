import struct

RAW_FILE = "raw.bin"

packets = []

with open(RAW_FILE, "rb") as f:
    data = f.read()

i = 0
while i < len(data) - 6:
    # packet header: AA 55
    if data[i] == 0xAA and data[i + 1] == 0x55:
        length = data[i + 2]          # 0x11 = 17
        opcode = data[i + 4]          # 0x01 / 0x02
        payload_start = i + 5
        payload_end = payload_start + (length - 1)

        payload = data[payload_start:payload_end]

        packets.append((opcode, payload))

        i = payload_end + 2           # skip 55 AA
    else:
        i += 1


print(f"Toplam paket: {len(packets)}")

# ---------------- ITEM PARSE ----------------

def parse_item(payload: bytes):
    item_id, count, price, flags = struct.unpack("<4I", payload)
    return item_id, count, price, flags


items = []

for opcode, payload in packets:
    if opcode == 0x02 and len(payload) == 16:
        items.append(parse_item(payload))


print(f"Item sayısı: {len(items)}\n")

for i, item in enumerate(items[:10]):
    print(i, item)
