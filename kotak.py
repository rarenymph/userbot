from telethon import TelegramClient, events
import requests
import logging
import re
import asyncio

# === ВАШИ ДАННЫЕ ===
api_id = 29737257
api_hash = '84d29cf5869fe64901f262157ba27abb'
BOT_TOKEN = '8350809624:AAH4gWZrHi9994EkQgR6IjodYeodJsccaZY'
TARGET_GROUP_ID = -1003229459588

client = TelegramClient('userbot_session', api_id, api_hash)

# Задержки отправки в секундах для каждого канала
SEND_DELAYS = {
    'portals_notifications': 20 * 60,  # 20 минут
    'GiftNotification': 50 * 60        # 50 минут
}

def parse_nft_owner(raw_message, source):
    """Определяем владельца NFT из сообщения"""
    nft_data = {
        'nft_link': 'https://example.com/nft/123',
        'owner': 'Неизвестный владелец',
        'source': source,
        'found_owner': False
    }
    
    # Поиск ссылки
    link_match = re.search(r'(https?://[^\s]+)', raw_message)
    if link_match:
        nft_data['nft_link'] = link_match.group(1)
    
    # Паттерны для поиска ВЛАДЕЛЬЦА
    owner_patterns = [
        r'от\s*@?([a-zA-Z0-9_]{3,32})',
        r'владелец[:\s]*@?([a-zA-Z0-9_]{3,32})',
        r'owner[:\s]*@?([a-zA-Z0-9_]{3,32})',
        r'author[:\s]*@?([a-zA-Z0-9_]{3,32})',
        r'продавец[:\s]*@?([a-zA-Z0-9_]{3,32})',
        r'seller[:\s]*@?([a-zA-Z0-9_]{3,32})',
        r'создатель[:\s]*@?([a-zA-Z0-9_]{3,32})',
        r'creator[:\s]*@?([a-zA-Z0-9_]{3,32})',
        r'by\s*@?([a-zA-Z0-9_]{3,32})',
        r'from\s*@?([a-zA-Z0-9_]{3,32})'
    ]
    
    for pattern in owner_patterns:
        match = re.search(pattern, raw_message, re.IGNORECASE)
        if match:
            owner = match.group(1).strip()
            if owner.startswith('@'):
                owner = owner[1:]
            nft_data['owner'] = owner
            nft_data['found_owner'] = True
            logging.info(f"🔍 Найден владелец: {owner}")
            break
    
    # Если не нашли по паттернам, ищем первое упоминание
    if not nft_data['found_owner']:
        first_mention = re.search(r'@([a-zA-Z0-9_]{3,32})', raw_message)
        if first_mention:
            nft_data['owner'] = first_mention.group(1)
            nft_data['found_owner'] = True
            logging.info(f"🔍 Владелец из первого упоминания: {nft_data['owner']}")
    
    logging.info(f"📊 Результат парсинга: владелец='{nft_data['owner']}'")
    return nft_data

def send_to_bot(nft_data):
    """Отправляем данные официальному боту через Bot API"""
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    
    # УПРОЩЕННОЕ СООБЩЕНИЕ (только NFT, юз владельца и источник)
    message_text = f"""
🎁 <b>Новый лог сделки</b>

<b>NFT:</b> {nft_data['nft_link']}
<b>Владелец:</b> {nft_data['owner']}
<b>Канал:</b> {nft_data['source']}
    """
    
    # Создаем клавиатуру с кнопками
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
        
        if response.status_code == 200:
            logging.info("✅ Сообщение отправлено успешно!")
            return True
        else:
            error_data = response.json()
            logging.error(f"❌ Ошибка Telegram API: {error_data}")
            return False
            
    except Exception as e:
        logging.error(f"❌ Ошибка отправки боту: {e}")
        return False

async def delayed_send(nft_data, delay_seconds, channel_name):
    """Отложенная отправка сообщения"""
    logging.info(f"⏳ Отложенная отправка для {channel_name}: ждем {delay_seconds/60:.1f} минут")
    
    # Ждем указанное время
    await asyncio.sleep(delay_seconds)
    
    # Отправляем сообщение
    success = send_to_bot(nft_data)
    if success:
        logging.info(f"✅ Лог из {channel_name} отправлен после задержки!")
    else:
        logging.error(f"❌ Не удалось отправить лог из {channel_name}")

@client.on(events.NewMessage(chats=['@GiftNotification', '@portals_notifications']))
async def channel_handler(event):
    """Обработчик сообщений из каналов (мгновенное получение, отложенная отправка)"""
    try:
        chat_title = event.chat.title if event.chat else "Неизвестный канал"
        chat_username = event.chat.username if event.chat else None
        
        logging.info(f"📨 Получено сообщение из {chat_title} (@{chat_username})")
        logging.info(f"📝 Текст: {event.text}")
        
        # Пропускаем сообщения из неизвестных каналов
        if not chat_username or chat_username not in ['GiftNotification', 'portals_notifications']:
            logging.info(f"🚫 Пропускаем сообщение из неизвестного канала: {chat_username}")
            return
        
        # Парсим данные NFT
        nft_data = parse_nft_owner(event.text, chat_title)
        
        # Определяем задержку для канала
        delay_seconds = SEND_DELAYS.get(chat_username, 0)
        
        # Создаем задачу для отложенной отправки
        asyncio.create_task(delayed_send(nft_data, delay_seconds, chat_title))
        
        logging.info(f"⏰ Сообщение из {chat_title} запланировано к отправке через {delay_seconds/60:.1f} минут")
        
    except Exception as e:
        logging.error(f"❌ Ошибка обработки: {e}")

@client.on(events.NewMessage(pattern='/test'))
async def test_command(event):
    """Тестовая команда"""
    test_messages = [
        "🎁 NFT от @test_owner куплен за 100 Stars\nhttps://example.com/nft/1",
        "💰 Продажа! Владелец: @owner123\nhttps://example.com/nft/2",
        "Новый гифт! От @seller\nhttps://example.com/nft/3",
        "Просто сообщение без владельца\nhttps://example.com/nft/4"
    ]
    
    for i, test_msg in enumerate(test_messages):
        nft_data = parse_nft_owner(test_msg, "Тестовый канал")
        await event.reply(f"Тест {i+1}:\n"
                         f"Сообщение: {test_msg}\n"
                         f"Владелец: {nft_data['owner']}\n"
                         f"Найден: {nft_data['found_owner']}")

@client.on(events.NewMessage(pattern='/delays'))
async def delays_command(event):
    """Показать текущие задержки"""
    delays_msg = f"""
⏰ <b>Текущие задержки отправки:</b>

• @portals_notifications: {SEND_DELAYS['portals_notifications']/60} минут
• @GiftNotification: {SEND_DELAYS['GiftNotification']/60} минут

📝 <b>Принцип работы:</b>
• Сообщения получаются мгновенно
• Отправка в группу происходит с задержкой
• Каждое сообщение обрабатывается индивидуально
"""
    await event.reply(delays_msg, parse_mode='HTML')

@client.on(events.NewMessage(pattern='/status'))
async def status_command(event):
    """Статус бота"""
    status_msg = f"""
🤖 <b>Статус юзербота</b>

📡 <b>Мониторинг каналов:</b>
• @GiftNotification (отправка через {SEND_DELAYS['GiftNotification']/60} мин)
• @portals_notifications (отправка через {SEND_DELAYS['portals_notifications']/60} мин)

🕒 <b>Режим работы:</b>
• Получение сообщений: мгновенное
• Отправка в группу: с задержкой
• Только указанные каналы

💡 <b>Команды:</b>
/test - тест парсинга
/delays - показать задержки
/status - статус бота
    """
    await event.reply(status_msg, parse_mode='HTML')

async def main():
    await client.start()
    logging.info("🤖 Юзербот запущен и мониторит каналы!")
    logging.info(f"📡 Мониторинг: @GiftNotification, @portals_notifications")
    logging.info(f"⏰ Задержки отправки: @portals_notifications - 20 мин, @GiftNotification - 50 мин")
    logging.info(f"🏠 Целевая группа: {TARGET_GROUP_ID}")
    await client.run_until_disconnected()

if __name__ == '__main__':
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    client.loop.run_until_complete(main())