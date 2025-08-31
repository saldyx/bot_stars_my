import asyncio
import logging
from typing import Optional

from aiogram import Bot
from pyrogram import Client
from pyrogram.errors import FloodWait, UserDeactivated, AuthKeyUnregistered, PeerIdInvalid

from settings import channel_viplat_id, channel_osn, chater

_userbot_client: Optional[Client] = None

MAX_RETRIES = 3
RETRY_DELAY_SECONDS = 600  # 10 минут


async def start_userbot(name: str = "userbot_session", workdir: str = "."):
    """Инициализирует и запускает Pyrogram клиент."""
    global _userbot_client
    if _userbot_client:
        logging.warning("Userbot уже запущен.")
        return _userbot_client

    try:
        # Убедитесь, что у вас установлен kurigram, а не pyrogram
        # pip uninstall pyrogram -y
        # pip install kurigram
        _userbot_client = Client(name=name, workdir=workdir)
        await _userbot_client.start()
        logging.info("Userbot успешно запущен.")
        return _userbot_client
    except Exception as e:
        logging.error(f"Не удалось запустить юзербота: {e}", exc_info=True)
        _userbot_client = None
        return None

async def stop_userbot():
    """Останавливает Pyrogram клиент."""
    global _userbot_client
    if _userbot_client and _userbot_client.is_connected:
        await _userbot_client.stop()
        logging.info("Userbot остановлен.")
    _userbot_client = None

def get_userbot_client() -> Optional[Client]:
    """Возвращает активный экземпляр Pyrogram клиента."""
    return _userbot_client

async def send_gift_from_userbot(bot: Bot, user_id: int, username: Optional[str], gift_id: int, delay_seconds: int, stars: int, withdrawal_id: int, user_full_name: str, bot_username: str, retry_count: int = 0):
    """Обертка для отправки подарка, которая использует глобальный клиент."""
    client = get_userbot_client()
    if not client:
        logging.error("Попытка отправить подарок без запущенного юзербота.")
        return

    # Запускаем отправку в фоне, чтобы не блокировать основной поток
    asyncio.create_task(_send_gift_logic(client, bot, user_id, username, gift_id, delay_seconds, stars, withdrawal_id, user_full_name, bot_username, retry_count))

async def _send_gift_logic(client: Client, bot: Bot, user_id: int, username: Optional[str], gift_id: int, delay_seconds: int, stars: int, withdrawal_id: int, user_full_name: str, bot_username: str, retry_count: int = 0):
    """Логика отправки подарка, адаптированная из ball_bot."""
    peer_identifier = username if username else user_id
    try:
        await asyncio.sleep(delay_seconds)

        logging.info(f"Цель для отправки подарка: {peer_identifier} (ID: {user_id}), попытка {retry_count + 1}")

        await client.send_gift(
            chat_id=peer_identifier,
            gift_id=gift_id
        )
        logging.info(f"Подарок {gift_id} успешно отправлен пользователю {peer_identifier}.")

        # Формируем и отправляем уведомление в канал
        bot_link = f"https://t.me/{bot_username}"
        message_text = (
            f"<b>✅ Запрос на вывод №{withdrawal_id}</b>\n\n"
            f"👤 Пользователь: {user_full_name}\n"
            f"💫 Количество: {stars}⭐️\n\n"
            f"🔄 Статус: <b>Подарок отправлен 🎁</b>\n\n"
            f"<a href='{channel_osn}'>Основной канал</a> | <a href='{chater}'>Чат</a> | <a href='{bot_link}'>Бот</a>"
        )
        await bot.send_message(
            chat_id=channel_viplat_id,
            text=message_text,
            parse_mode='HTML',
            disable_web_page_preview=True
        )
        logging.info(f"Уведомление о выводе №{withdrawal_id} отправлено в канал {channel_viplat_id}.")

    except FloodWait as e:
        logging.error(f"FloodWait: ожидание {e.value} секунд перед повторной попыткой.")
        await asyncio.sleep(e.value)
        # Повторяем эту же попытку, не увеличивая счетчик
        await _send_gift_logic(client, bot, user_id, username, gift_id, 0, stars, withdrawal_id, user_full_name, bot_username, retry_count)
    except (UserDeactivated, AuthKeyUnregistered) as e:
        # Критические ошибки, не требующие повтора
        logging.error(f"Пользователь {peer_identifier} деактивирован или сессия юзербота невалидна. Отправка отменена. Ошибка: {e}")
    except (PeerIdInvalid, Exception) as e:
        # Прочие ошибки (включая PeerIdInvalid и сетевые проблемы), которые можно попробовать повторить
        logging.error(f"Ошибка при отправке подарка пользователю {peer_identifier} (попытка {retry_count + 1}): {e}")
        if retry_count < MAX_RETRIES:
            logging.info(f"Планирую повторную отправку через {RETRY_DELAY_SECONDS / 60:.0f} минут.")
            schedule_gift(
                bot=bot,
                user_id=user_id,
                username=username,
                gift_id=gift_id,
                delay_seconds=RETRY_DELAY_SECONDS,
                stars=stars,
                withdrawal_id=withdrawal_id,
                user_full_name=user_full_name,
                bot_username=bot_username,
                retry_count=retry_count + 1
            )
        else:
            logging.error(f"Достигнут лимит попыток ({MAX_RETRIES + 1}) для отправки подарка пользователю {peer_identifier}. Отправка отменена.")


# Эта функция остается простой оберткой для создания задачи,
# но теперь она просто вызывает новую фоновую задачу.
def schedule_gift(bot: Bot, user_id: int, username: Optional[str], gift_id: int, delay_seconds: int, stars: int, withdrawal_id: int, user_full_name: str, bot_username: str, retry_count: int = 0):
    # Задержка теперь обрабатывается внутри _send_gift_logic
    asyncio.create_task(send_gift_from_userbot(bot, user_id, username, gift_id, delay_seconds, stars, withdrawal_id, user_full_name, bot_username, retry_count))


