import os
import asyncio
from telethon import TelegramClient, events
import requests
import logging
import re
from collections import defaultdict
from dotenv import load_dotenv

load_dotenv()

# === НАСТРОЙКИ ===
api_id = int(os.getenv('API_ID', 29737257))
api_hash = os.getenv('API_HASH', '84d29cf5869fe64901f262157ba27abb')
BOT_TOKEN = os.getenv('BOT_TOKEN', '8350809624:AAH4gWZrHi9994EkQgR6IjodYeodJsccaZY')
TARGET_GROUP_ID = int(os.getenv('TARGET_GROUP_ID', -1003229459588))

client = TelegramClient('userbot_session', api_id, api_hash)

# Черный список каналов
BLACKLIST_CHANNELS = ['@virusgift', '@GiftsToPortals', '@giftrelayer']

# Задержки отправки
SEND_DELAYS = {
    'portals_notifications': 20 * 60,
    'GiftNotification': 50 * 60
}

processed_messages = set()
active_tasks = defaultdict(list)

def parse_nft_owner(raw_message, source):
    nft_data = {
        'nft_link': 'https://example.com/nft/123',
        'owner': 'Неизвестный владелец',
        'source': source,
        'found_owner': False
    }
    
    link_match = re.search(r'(https?://[^\s]+)', raw_message)
    if link_match:
        nft_data['nft_link'] = link_match.group(1)
    
    owner_patterns = [
        r'от\s*@?([a-zA-Z0-9_]{3,32})',
        r'владелец[:\s]*@?([a-zA-Z0-9_]{3,32})',
        r'owner[:\s]*@?([a-zA-Z0-9_]{3,32})',
    ]
    
    for pattern in owner_patterns:
        match = re.search(pattern, raw_message, re.IGNORECASE)
        if match:
            owner = match.group(1).strip()
            if owner.startswith('@'):
                owner = owner[1:]
            nft_data['owner'] = owner
            nft_data['found_owner'] = True
            break
    
    if not nft_data['found_owner']:
        first_mention = re.search(r'@([a-zA-Z0-9_]{3,32})', raw_message)
        if first_mention:
            nft_data['owner'] = first_mention.group(1)
            nft_data['found_owner'] = True
    
    return nft_data

def send_to_bot(nft_data):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    
    message_text = f"""
🎁 <b>Новый лог сделки</b>

<b>NFT:</b> {nft_data['nft_link']}
<b>Владелец:</b> {nft_data['owner']}
<b>Канал:</b> {nft_data['source']}
    """
    
    keyboard = {
        "inline_keyboard": [
            [{"text": "🔄 Забрать лог", "callback_data": "claim_log"}],
            [{"text": "🔗 Открыть NFT", "url": nft_data['nft_link']}]
        ]
    }
    
    payload = {
        "chat_id": TARGET_GROUP_ID,
        "text": message_text,
        "parse_mode": "HTML",
        "reply_markup": keyboard
    }
    
    try:
        response = requests.post(url, json=payload)
        return response.status_code == 200
    except:
        return False

async def delayed_send(nft_data, delay_seconds, channel_name, message_id):
    logging.info(f"⏳ Ожидание {delay_seconds/60} мин для {channel_name}")
    await asyncio.sleep(delay_seconds)
    success = send_to_bot(nft_data)
    if success:
        logging.info(f"✅ Лог отправлен из {channel_name}")
    
    if message_id in active_tasks[channel_name]:
        active_tasks[channel_name].remove(message_id)

@client.on(events.NewMessage(chats=['@GiftNotification', '@portals_notifications']))
async def channel_handler(event):
    try:
        chat_title = event.chat.title if event.chat else "Неизвестный канал"
        chat_username = event.chat.username if event.chat else None
        message_id = event.id
        
        if not chat_username or chat_username not in ['GiftNotification', 'portals_notifications']:
            return
        
        if f"@{chat_username}" in BLACKLIST_CHANNELS:
            return
        
        message_key = f"{chat_username}_{message_id}"
        if message_key in processed_messages:
            return
        
        processed_messages.add(message_key)
        if len(processed_messages) > 1000:
            processed_messages.clear()
        
        if message_id in active_tasks[chat_username]:
            return
        
        nft_data = parse_nft_owner(event.text, chat_title)
        delay_seconds = SEND_DELAYS.get(chat_username, 0)
        
        active_tasks[chat_username].append(message_id)
        asyncio.create_task(delayed_send(nft_data, delay_seconds, chat_title, message_id))
        
        logging.info(f"⏰ Запланирована отправка через {delay_seconds/60} мин")
        
    except Exception as e:
        logging.error(f"❌ Ошибка: {e}")

async def main():
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[logging.StreamHandler()]
    )
    
    await client.start()
    logging.info("🤖 Юзербот запущен на Render!")
    await client.run_until_disconnected()

if __name__ == '__main__':
    asyncio.run(main())