import asyncio
import logging
import aiosqlite
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

TOKEN = "7244593523:AAGhMM2XuHgKQ0zII5zE0xNSe5mS5-N0vWw"
DB_NAME = "AwesomeZooShop.db"

bot = Bot(token=TOKEN)
dp = Dispatcher()


# --- Database Functions ---
async def get_user_orders(telegram_id):
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute(
            "SELECT id, status, created_at FROM orders WHERE telegram_id = ? ORDER BY created_at DESC",
            (telegram_id,)
        )
        return await cursor.fetchall()


async def get_order_details(order_id, telegram_id):
    async with aiosqlite.connect(DB_NAME) as db:
        # Order info
        cursor = await db.execute(
            """SELECT status, city, department, contact_phone, created_at
               FROM orders
               WHERE id = ?
                 AND telegram_id = ?""",
            (order_id, telegram_id)
        )
        order = await cursor.fetchone()

        if not order:
            return None, None

        # Order items
        cursor = await db.execute(
            """SELECT p.name, oi.quantity, oi.price
               FROM order_items oi
                        JOIN products p ON oi.product_id = p.id
               WHERE oi.order_id = ?""",
            (order_id,)
        )
        items = await cursor.fetchall()

        return order, items


# --- Command Handlers ---
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    # Register user if not exists
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute(
            "INSERT OR IGNORE INTO users (telegram_id, username) VALUES (?, ?)",
            (message.from_user.id, message.from_user.username)
        )
        await db.commit()

    web_app = types.WebAppInfo(url=f"https://yourwebsite.com/?tgid={message.from_user.id}")
    keyboard = [
        [types.KeyboardButton(text="🛍 Магазин", web_app=web_app)],
        [types.KeyboardButton(text="📋 Мої замовлення")]
    ]
    reply_markup = types.ReplyKeyboardMarkup(
        keyboard=keyboard,
        resize_keyboard=True
    )

    await message.answer(
        "Ласкаво просимо до AwesomeZooShop!",
        reply_markup=reply_markup
    )


@dp.message(Command("myorders"))
async def cmd_myorders(message: types.Message):
    orders = await get_user_orders(message.from_user.id)

    if not orders:
        await message.answer("У вас ще немає замовлень")
        return

    response = ["📋 *Ваші замовлення:*"]
    for order in orders:
        order_id, status, created_at = order
        status_icon = {
            'pending': '🟡',
            'processing': '🟠',
            'completed': '🟢',
            'cancelled': '🔴'
        }.get(status, '⚪')

        response.append(
            f"{status_icon} *Замовлення #{order_id}*\n"
            f"📅 *Дата:* {created_at}\n"
            f"📌 *Статус:* {status}\n"
            f"Деталі: /order_{order_id}"
        )

    await message.answer("\n\n".join(response), parse_mode="Markdown")


@dp.message(lambda message: message.text and message.text.startswith('/order_'))
async def show_order_details(message: types.Message):
    try:
        order_id = int(message.text.split('_')[1])
    except:
        await message.answer("Невірний формат команди")
        return

    order, items = await get_order_details(order_id, message.from_user.id)

    if not order:
        await message.answer("Замовлення не знайдено")
        return

    status, city, department, phone, created_at = order

    items_text = "\n".join(
        f"▫ {name} - {quantity} × {price} грн = {quantity * price:.2f} грн"
        for name, quantity, price in items
    )

    total = sum(quantity * price for _, quantity, price in items)

    response = (
        f"📌 *Замовлення №{order_id}*\n\n"
        f"*Товари:*\n{items_text}\n\n"
        f"*Доставка:*\n"
        f"📍 Місто: {city}\n"
        f"📦 Відділення: {department}\n"
        f"📞 Телефон: {phone}\n\n"
        f"💵 *Загальна сума:* {total:.2f} грн\n"
        f"🔄 *Статус:* {status}"
    )

    await message.answer(response, parse_mode="Markdown")


# --- Main ---
async def main():
    await dp.start_polling(bot)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())