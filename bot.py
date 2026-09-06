import os
import time
import asyncio
from datetime import datetime
import requests
import discord
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv
from google import genai
from aiohttp import web

load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

ai_client = genai.Client(api_key=GEMINI_API_KEY)

intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)

CLASS_COLORS = {
    "saber": 0x00A2E8,
    "archer": 0x22B14C,
    "lancer": 0x3F48CC,
    "rider": 0xFFAEC9,
    "caster": 0xA349A4,
    "assassin": 0x7F7F7F,
    "berserker": 0xED1C24,
    "ruler": 0xEFE4B0,
    "avenger": 0x880015,
    "alterEgo": 0xB5E61D,
    "moonCancer": 0x00B7EB,
    "foreigner": 0x4A154B,
    "pretender": 0x5865F2,
    "beast": 0x300000,
}

def get_class_color(class_name: str) -> int:
    if not class_name:
        return 0x5865F2
    return CLASS_COLORS.get(class_name.lower(), 0x5865F2)

def fetch_servant_data(name: str):
    url = f"https://api.atlasacademy.io/nice/NA/servant/search?name={name}"
    resp = requests.get(url)
    if resp.status_code != 200 or not resp.json():
        url_jp = f"https://api.atlasacademy.io/nice/JP/servant/search?name={name}"
        resp = requests.get(url_jp)
        if resp.status_code != 200 or not resp.json():
            return None
    return resp.json()[0]

def fetch_servant_gacha_history(servant_id: int):
    url = f"https://api.atlasacademy.io/nice/JP/servant/{servant_id}"
    try:
        resp = requests.get(url, timeout=3)
        if resp.status_code != 200:
            return []
        data = resp.json()
        matched_banners = []
        # ดึงประวัติตู้และอีเวนต์ที่เกี่ยวข้องจากข้อมูล Servant โดยตรง
        rel_quests = data.get("relateQuest", [])
        # หากไม่มี relateQuest ให้ fallback เป็นข้อมูล release date พื้นฐาน
        return matched_banners
    except Exception:
        return []

def _call_gemini(prompt: str) -> str:
    candidate_models = ["gemini-3.6-flash", "gemini-3-flash"]
    
    for model_name in candidate_models:
        for attempt in range(2):
            try:
                res = ai_client.models.generate_content(
                    model=model_name,
                    contents=prompt
                )
                if res.text:
                    return res.text
            except Exception as e:
                print(f"[AI Error] Model {model_name} (Attempt {attempt + 1}) failed: {e}")
                time.sleep(1)
                continue
                
    return "ขออภัย ระบบ AI กำลังมีผู้ใช้งานหนาแน่นชั่วคราว กรุณาลองใหม่อีกครั้งในอีกสักครู่"

def resolve_servant_name(query: str) -> str:
    prompt = f"""Translate or map this FGO character query/nickname into their official English Servant name in Fate/Grand Order.
Examples:
- "Castoria" -> "Artoria Caster"
- "Koyan Light" -> "Koyanskaya of Light"
- "Spishtar" -> "Space Ishtar"
- "Oberon" -> "Oberon"
- "Gil" -> "Gilgamesh"

Query: "{query}"
Output ONLY the resolved official English name without explanation or punctuation:"""
    try:
        res_text = _call_gemini(prompt)
        return res_text.strip().replace('"', '')
    except Exception:
        return query

async def handle_health_check(request):
    return web.Response(text="Bot is alive!")

async def start_web_server():
    app = web.Application()
    app.router.add_get("/", handle_health_check)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.getenv("PORT", 8080))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()

@bot.event
async def on_ready():
    await start_web_server()
    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} command(s)")
    except Exception as e:
        print(f"Failed to sync commands: {e}")
    print(f"Logged in as {bot.user}")

@bot.tree.command(name="servant", description="ค้นหาข้อมูลสเตตัสและสกิลของ Servant")
@app_commands.describe(name="ชื่อหรือฉายาของ Servant เช่น Castoria, Oberon")
async def servant_slash(interaction: discord.Interaction, name: str):
    await interaction.response.defer()
    
    official_name = resolve_servant_name(name)
    data = fetch_servant_data(official_name)
    if not data and official_name != name:
        data = fetch_servant_data(name)

    if not data:
        await interaction.followup.send(f"❌ ไม่พบข้อมูล Servant: `{name}` (แปลงเป็น `{official_name}`) ใน Atlas Academy")
        return

    c_name = data.get("className", "unknown")
    embed_color = CLASS_COLORS.get(c_name.lower(), 0xF1C40F)

    embed = discord.Embed(
        title=f"★{data.get('rarity', '?')} {data.get('name', 'Unknown')}",
        description=f"**Class:** {c_name.capitalize()} | **Cost:** {data.get('cost', '?')}",
        color=embed_color
    )

    embed.add_field(
        name="⚔️ Max ATK / HP (Lv.Max)",
        value=f"ATK: `{data.get('atkMax', '?'):,}` | HP: `{data.get('hpMax', '?'):,}`",
        inline=False
    )

    skills = data.get("skills", [])
    if skills:
        skill_list = []
        for idx, s in enumerate(skills[:3], 1):
            s_name = s.get("name", "Skill")
            skill_list.append(f"**{idx}.** {s_name}")
        embed.add_field(name="✨ Active Skills", value="\n".join(skill_list), inline=False)

    nps = data.get("noblePhantasms", [])
    if nps:
        np_info = nps[-1]
        card_map = {
            "1": "Arts", 1: "Arts", "arts": "Arts",
            "2": "Buster", 2: "Buster", "buster": "Buster",
            "3": "Quick", 3: "Quick", "quick": "Quick"
        }
        raw_card = np_info.get("card")
        card_name = card_map.get(raw_card, card_map.get(str(raw_card).lower(), "Arts"))
        embed.add_field(
            name="💥 Noble Phantasm",
            value=f"**{np_info.get('name', '?')}** [{card_name}]\n*{np_info.get('detail', 'No details available')[:150]}...*",
            inline=False
        )

    faces = data.get("extraAssets", {}).get("faces", {})
    face_icon = None
    if isinstance(faces, dict):
        def find_url(obj):
            if isinstance(obj, str) and obj.startswith("http"):
                return obj
            if isinstance(obj, dict):
                for v in obj.values():
                    res = find_url(v)
                    if res:
                        return res
            return None
        face_icon = find_url(faces)

    if face_icon:
        embed.set_thumbnail(url=face_icon)

    embed.set_footer(text=f"Matched: {official_name} | Source: Atlas Academy DB")
    await interaction.followup.send(embed=embed)

@bot.tree.command(name="fgo", description="ถามคำถามเกี่ยวกับ FGO หรือกำหนดการตู้รีรัน (แสดงผลแบบ Embed)")
@app_commands.describe(question="คำถาม เช่น Castoria จะมีตู้รีรันช่วงไหน")
async def fgo_slash(interaction: discord.Interaction, question: str):
    await interaction.response.defer(thinking=True)
    
    current_date_str = datetime.now().strftime("%B %Y")
    
    # พยายามค้นหา Servant จากคำถามเพื่อเอารูปและ Class
    servant_name = resolve_servant_name(question)
    servant_info = fetch_servant_data(servant_name) if servant_name else None
    
    class_name = servant_info.get("className", "") if servant_info else ""
    embed_color = get_class_color(class_name)
    thumbnail_url = servant_info.get("face") if servant_info else None
    if not thumbnail_url and servant_info:
        faces = servant_info.get("extraAssets", {}).get("faces", {})
        if isinstance(faces, dict):
            def find_url(obj):
                if isinstance(obj, str) and obj.startswith("http"):
                    return obj
                if isinstance(obj, dict):
                    for v in obj.values():
                        res = find_url(v)
                        if res:
                            return res
                return None
            thumbnail_url = find_url(faces)
    
    prompt = f"""You are an expert Fate/Grand Order (FGO) assistant.

IMPORTANT TIMELINE & CONTEXT:
- Current Date: {current_date_str} (Year 2026).
- Baseline: NA is roughly 2 years behind JP.
- CRITICAL: Any 2024 or 2025 event has already passed. Focus only on 2026 onwards.

User Question: {question}

You MUST structure your response into these exact 3 sections:
[JP_PROJECTION]
(Detail the scheduled banner projection based on JP +2 years from 2026 onwards)

[NA_SURPRISE]
(Detail any NA-exclusive possibilities, e.g., Thanksgiving, Special Milestones, Anime Expo)

[ADVICE]
(Short advice or SQ management recommendation for the player)

Answer clearly in Thai."""

    try:
        raw_answer = await asyncio.to_thread(_call_gemini, prompt)
        
        # แยกส่วนข้อความตามแท็ก
        jp_text = "ไม่มีข้อมูล"
        na_text = "ไม่มีข้อมูล"
        advice_text = "ไม่มีคำแนะนำเพิ่มเติม"
        
        if "[JP_PROJECTION]" in raw_answer and "[NA_SURPRISE]" in raw_answer:
            parts = raw_answer.split("[NA_SURPRISE]")
            jp_text = parts[0].replace("[JP_PROJECTION]", "").strip()
            
            if "[ADVICE]" in parts[1]:
                na_sub = parts[1].split("[ADVICE]")
                na_text = na_sub[0].strip()
                advice_text = na_sub[1].strip()
            else:
                na_text = parts[1].strip()
        else:
            jp_text = raw_answer.strip()

        title = f"🔮 พยากรณ์ตู้กาชา / ข้อมูล: {servant_info.get('name', 'FGO Assistant') if servant_info else 'FGO Query'}"
        embed = discord.Embed(
            title=title,
            description=f"**คำถาม:** *{question}*",
            color=embed_color,
            timestamp=datetime.now()
        )
        
        if thumbnail_url:
            embed.set_thumbnail(url=thumbnail_url)
            
        if jp_text:
            embed.add_field(
                name="📌 กำหนดการตามตาราง JP (+2 ปี)",
                value=jp_text[:1024],
                inline=False
            )
        if na_text and na_text != "ไม่มีข้อมูล":
            embed.add_field(
                name="🎁 โอกาสตู้เซอร์ไพรส์ / แคมเปญพิเศษ (NA Only)",
                value=na_text[:1024],
                inline=False
            )
        if advice_text and advice_text != "ไม่มีคำแนะนำเพิ่มเติม":
            embed.add_field(
                name="💡 คำแนะนำสำหรับผู้เล่น",
                value=advice_text[:1024],
                inline=False
            )
            
        embed.set_footer(text="Fate/Grand Order Assistant • ข้อมูลอิงตาม Atlas Academy & Gemini")
        await interaction.followup.send(embed=embed)

    except Exception as e:
        print(f"Error in /fgo: {e}")
        await interaction.followup.send(f"❌ เกิดข้อผิดพลาด: {e}")

bot.run(DISCORD_TOKEN)