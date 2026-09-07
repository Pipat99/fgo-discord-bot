import random

def _parse_items(raw_input: str) -> list[str]:
    if ',' in raw_input:
        return [item.strip() for item in raw_input.split(',') if item.strip()]
    return [item.strip() for item in raw_input.split() if item.strip()]

def pick_one(raw_input: str) -> str:
    items = _parse_items(raw_input)
    if not items:
        return "กรุณาระบุรายการที่ต้องการสุ่ม"
    chosen = random.choice(items)
    return f"ผลลัพธ์ที่สุ่มได้: {chosen}"

def split_teams(raw_input: str) -> str:
    items = _parse_items(raw_input)
    if len(items) < 2:
        return "กรุณาระบุรายการอย่างน้อย 2 รายการเพื่อแบ่งกลุ่ม"
    random.shuffle(items)
    mid = (len(items) + 1) // 2
    team1 = items[:mid]
    team2 = items[mid:]
    return f"**ทีมที่ 1** ({len(team1)} คน):\n{', '.join(team1)}\n\n**ทีมที่ 2** ({len(team2)} คน):\n{', '.join(team2)}"

