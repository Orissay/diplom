import requests
import json
from supabase import create_client, Client
from config import BOT_TOKEN, SUPABASE_URL, SUPABASE_KEY, WEBSITE_URL

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

class TelegramBotHandler:
    def __init__(self):
        self.api_url = f"https://api.telegram.org/bot{BOT_TOKEN}"
        self._bot_info = None

    def get_me(self):
        if not self._bot_info:
            response = requests.get(f"{self.api_url}/getMe").json()
            if response.get('ok'):
                self._bot_info = response['result']
        return self._bot_info or {}

    def send_message(self, chat_id, text, parse_mode="Markdown", reply_markup=None):
        url = f"{self.api_url}/sendMessage"
        data = {
            'chat_id': chat_id,
            'text': text,
            'parse_mode': parse_mode
        }
        if reply_markup:
            data['reply_markup'] = reply_markup
        return requests.post(url, json=data).json()

    def get_updates(self, offset=None):
        url = f"{self.api_url}/getUpdates"
        params = {'timeout': 100, 'offset': offset}
        return requests.get(url, params=params).json()

    def answer_callback_query(self, callback_query_id, text=None, show_alert=False):
        url = f"{self.api_url}/answerCallbackQuery"
        data = {
            'callback_query_id': callback_query_id,
            'show_alert': show_alert
        }
        if text:
            data['text'] = text
        return requests.post(url, json=data).json()

    def get_user_orders(self, telegram_id):
        response = supabase.table("orders") \
            .select("id, status, city, department") \
            .eq("telegram_id", telegram_id) \
            .order("id", desc=True) \
            .execute()
        return [(order['id'], order['status'], order['city'], order['department']) for order in
                response.data] if response.data else []

    @staticmethod
    def get_order_details(order_id, telegram_id):
        order_response = supabase.table("orders") \
            .select("*") \
            .eq("id", order_id) \
            .eq("telegram_id", telegram_id) \
            .execute()
        if not order_response.data:
            return None, None

        order = order_response.data[0]
        items_response = supabase.table("order_items") \
            .select("products(name), quantity, price") \
            .eq("order_id", order_id) \
            .execute()
        items = [(item['products']['name'], item['quantity'], item['price']) for item in items_response.data]

        return (order['status'], order['city'], order['department'],
                order['contact_phone'], order['payment_method']), items


class BotLogic:
    def __init__(self, bot_handler):
        self.bot = bot_handler

    def handle_message(self, message):
        chat_id = message['chat']['id']
        text = message.get('text', '')

        if 'web_app_data' in message:
            try:
                order_data = json.loads(message['web_app_data']['data'])
                self.handle_webapp_order(chat_id, order_data)
                return
            except Exception as e:
                print(f"Помилка WebApp: {e}")

        if text.startswith('/start'):
            self.handle_start(chat_id, message)
        elif text.startswith('/myorders') or text == '📋 Мої замовлення':
            self.handle_myorders(chat_id)
        elif text.startswith('/order_'):
            self.handle_order_details(chat_id, text)

    def handle_callback_query(self, callback_query):
        data = callback_query.get('data')
        chat_id = callback_query['message']['chat']['id']
        message_id = callback_query['message']['message_id']

        self.bot.answer_callback_query(callback_query['id'])

        if data == 'my_orders':
            self.handle_myorders(chat_id)
            self.bot.delete_message(chat_id, message_id)

    def handle_start(self, chat_id, message):
        username = message['from'].get('username')
        response = supabase.table("users").select("*").eq("telegram_id", chat_id).execute()
        if not response.data:
            supabase.table("users").insert({
                "telegram_id": chat_id,
                "username": username
            }).execute()

        keyboard = {
            "keyboard": [
                [{"text": "🛍 Магазин", "web_app": {"url": f"{WEBSITE_URL}?telegram_id={chat_id}"}}],
                [{"text": "📋 Мої замовлення"}]
            ],
            "resize_keyboard": True
        }
        self.bot.send_message(
            chat_id,
            "Ласкаво просимо до AwesomeZooShop!\n\nНатисніть кнопку 'Магазин' для початку покупок.",
            reply_markup=json.dumps(keyboard)
        )

    def handle_myorders(self, chat_id):
        orders = self.bot.get_user_orders(chat_id)
        if not orders:
            self.bot.send_message(chat_id, "📭 У вас ще немає замовлень")
            return

        response = ["📋 *Ваші замовлення:*"]
        for order_id, status, city, department in orders:
            status_icon = {
                'pending': '🟡',
                'processing': '🟠',
                'completed': '🟢',
                'cancelled': '🔴'
            }.get(status, '⚪')

            response.append(
                f"{status_icon} *Замовлення #{order_id}*\n"
                f"📍 *Місто:* {city}\n"
                f"📦 *Відділення:* {department}\n"
                f"📌 *Статус:* {status}\n"
                f"Деталі: /order\\_{order_id}"
            )

        keyboard = {
            "inline_keyboard": [
                [{"text": "🛍 До магазину", "web_app": {"url": f"{WEBSITE_URL}?telegram_id={chat_id}"}}]
            ]
        }
        self.bot.send_message(
            chat_id,
            "\n\n".join(response),
            parse_mode="Markdown",
            reply_markup=json.dumps(keyboard)
        )

    def handle_order_details(self, chat_id, text):
        try:
            order_id = int(text.split('_')[1])
        except (IndexError, ValueError):
            self.bot.send_message(chat_id, "❌ Невірний формат команди")
            return

        order_info, items = self.bot.get_order_details(order_id, chat_id)
        if not order_info:
            self.bot.send_message(chat_id, f"❌ Замовлення #{order_id} не знайдено")
            return

        status, city, department, phone, payment_method = order_info
        items_text = "\n".join(f"▫ {name} - {quantity} × {price} грн" for name, quantity, price in items)
        total = sum(quantity * price for _, quantity, price in items)

        response = (
            f"📌 *Замовлення №{order_id}*\n\n"
            f"*Товари:*\n{items_text}\n\n"
            f"*Сума:* {total:.2f} грн\n"
            f"*Статус:* {status}\n"
            f"*Доставка:* {city}, {department}\n"
            f"*Телефон:* {phone}\n"
            f"*Оплата:* {payment_method}\n\n"
            f"Для перегляду всіх замовлень використовуйте /myorders"
        )

        keyboard = {
            "inline_keyboard": [
                [{"text": "🛍 До магазину", "web_app": {"url": f"{WEBSITE_URL}?telegram_id={chat_id}"}}]
            ]
        }

        self.bot.send_message(
            chat_id,
            response,
            parse_mode="Markdown",
            reply_markup=json.dumps(keyboard)
        )


def run_polling():
    bot_handler = TelegramBotHandler()
    logic = BotLogic(bot_handler)
    offset = None
    print("✅ Бот запущено в режимі polling...")

    while True:
        try:
            updates = bot_handler.get_updates(offset)
            for update in updates.get("result", []):
                offset = update["update_id"] + 1
                if "message" in update:
                    logic.handle_message(update["message"])
        except Exception as e:
            print(f"[Помилка]: {e}")

if __name__ == "__main__":
    run_polling()
