import streamlit as st
import sqlite3
import requests
from datetime import datetime

DB_NAME = "AwesomeZooShop.db"


# --- Database Class ---
class Database:
    @staticmethod
    def get_categories():
        with sqlite3.connect(DB_NAME) as db:
            cur = db.cursor()
            cur.execute("SELECT id, name FROM categories")
            return cur.fetchall()

    @staticmethod
    def get_products(category_id=None, search=""):
        query = "SELECT id, name, description, price, stock, image FROM products"
        params = []
        if category_id:
            query += " WHERE category_id = ?"
            params.append(category_id)
        elif search:
            query += " WHERE name LIKE ?"
            params.append(f"%{search}%")
        query += " ORDER BY stock > 0 DESC, name"

        with sqlite3.connect(DB_NAME) as db:
            cur = db.cursor()
            cur.execute(query, params)
            return cur.fetchall()

    @staticmethod
    def get_product(pid):
        with sqlite3.connect(DB_NAME) as db:
            cur = db.cursor()
            cur.execute(
                "SELECT id, name, description, price, stock, image FROM products WHERE id = ?",
                (pid,)
            )
            return cur.fetchone()

    @staticmethod
    def create_order(telegram_id, city, department, phone):
        with sqlite3.connect(DB_NAME) as db:
            cur = db.cursor()
            cur.execute(
                """INSERT INTO orders
                       (telegram_id, status, city, department, contact_phone, created_at)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (telegram_id, 'pending', city, department, phone,
                 datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
            order_id = cur.lastrowid
            db.commit()
            return order_id

    @staticmethod
    def add_order_items(order_id, items):
        with sqlite3.connect(DB_NAME) as db:
            cur = db.cursor()
            cur.executemany(
                """INSERT INTO order_items
                       (order_id, product_id, quantity, price)
                   VALUES (?, ?, ?, ?)""",
                [(order_id, item['id'], item['qty'], item['price']) for item in items]
            )
            db.commit()


# --- Telegram Notifier ---
class TelegramNotifier:
    API_TOKEN = "YOUR_TELEGRAM_BOT_TOKEN"
    API_URL = f"https://api.telegram.org/bot{API_TOKEN}"

    @staticmethod
    def notify_user(telegram_id, order_id, items, total, city, department, phone):
        try:
            items_text = "\n".join(
                f"➤ {item['name']} ({item['qty']} × {item['price']} грн) = {item['qty'] * item['price']:.2f} грн"
                for item in items
            )

            message = (
                f"🛒 *Ваше замовлення №{order_id}*\n\n"
                f"*Товари:*\n{items_text}\n\n"
                f"*Доставка:*\n"
                f"📍 Місто: {city}\n"
                f"📦 Відділення: {department}\n"
                f"📞 Телефон: {phone}\n\n"
                f"💵 *Загальна сума:* {total:.2f} грн\n\n"
                f"Статус: 🟡 Очікує підтвердження"
            )

            url = f"{TelegramNotifier.API_URL}/sendMessage"
            requests.post(url, json={
                'chat_id': telegram_id,
                'text': message,
                'parse_mode': 'Markdown'
            })

        except Exception as e:
            print(f"Telegram notification failed: {str(e)}")
            raise


# --- Cart Manager ---
class CartManager:
    @staticmethod
    def init():
        if "cart" not in st.session_state:
            st.session_state.cart = []

    @staticmethod
    def add(pid, name, price, image):
        for item in st.session_state.cart:
            if item["id"] == pid:
                item["qty"] += 1
                return
        st.session_state.cart.append({
            "id": pid,
            "name": name,
            "price": price,
            "qty": 1,
            "image": image
        })

    @staticmethod
    def get():
        return st.session_state.cart

    @staticmethod
    def total_items():
        return sum(item["qty"] for item in st.session_state.cart)

    @staticmethod
    def clear_cart():
        st.session_state.cart = []


# --- Product UI ---
class ProductUI:
    @staticmethod
    def show_product_card(prod):
        pid, name, desc, price, stock, img = prod

        with st.container():
            st.markdown(
                f"""
                <style>
                .product-card {{
                    border: 1px solid #ddd;
                    border-radius: 10px;
                    padding: 15px;
                    text-align: center;
                    height: 350px;
                    display: flex;
                    flex-direction: column;
                    justify-content: space-between;
                }}
                .product-image {{
                    max-height: 150px;
                    width: auto;
                    margin: 0 auto 10px;
                    object-fit: contain;
                }}
                </style>
                <div class="product-card">
                    <img src="{img}" class="product-image">
                    <h4>{name}</h4>
                    <p>💰 {price} грн</p>
                    <p style="color: {'red' if stock <= 0 else 'green'}">
                        {'Немає в наявності' if stock <= 0 else f'На складі: {stock}'}
                    </p>
                </div>
                """,
                unsafe_allow_html=True
            )

            if st.button("Детальніше", key=f"view_{pid}", use_container_width=True,
                         type="primary" if stock > 0 else "secondary"):
                st.session_state.viewing_product = pid
                st.rerun()

    @staticmethod
    def show_product_details(prod):
        pid, name, desc, price, stock, img = prod

        if st.button("← Назад", key="back_to_products"):
            st.session_state.viewing_product = None
            st.rerun()

        st.image(img, use_column_width=True)
        st.markdown(f"## {name}")
        st.markdown(desc)

        st.markdown(f"""
        <style>
        .detail-price {{
            font-size: 1.8rem;
            color: #e67e22;
            font-weight: bold;
            margin: 15px 0;
        }}
        </style>
        <div class="detail-price">{price} грн</div>
        """, unsafe_allow_html=True)

        if stock > 0:
            st.success(f"✅ В наявності: {stock} шт")
            if st.button("➕ Додати в кошик", key=f"add_{pid}", use_container_width=True):
                CartManager.add(pid, name, price, img)
                st.success(f"{name} додано до кошика!")
                st.rerun()
        else:
            st.error("❌ Немає в наявності")
            st.button("➕ Додати в кошик", key=f"add_disabled_{pid}", disabled=True)


# --- Order UI ---
class OrderUI:
    @staticmethod
    def show_order_form():
        st.header("Оформлення замовлення")

        if st.button("← На головну", key="back_to_main_from_order"):
            st.session_state.page = "main"
            st.rerun()

        cart_items = CartManager.get()
        total = sum(item["price"] * item["qty"] for item in cart_items)
        st.write(f"**Сума замовлення:** {total:.2f} грн")

        telegram_id = st.session_state.get('telegram_id')
        if not telegram_id:
            st.error("Будь ласка, увійдіть через Telegram")
            return

        city = st.selectbox("Місто", ["Київ", "Харків", "Одеса", "Львів"])
        department = st.selectbox("Відділення Нової Пошти",
                                  ["Відділення №1", "Відділення №2", "Відділення №3"])

        phone = st.text_input("Контактний телефон", value="+380", max_length=13)

        if st.button("Підтвердити замовлення", type="primary"):
            if len(phone) != 13 or not phone.startswith("+380"):
                st.error("Введіть коректний номер телефону")
                return

            try:
                order_id = Database.create_order(
                    telegram_id=telegram_id,
                    city=city,
                    department=department,
                    phone=phone
                )

                Database.add_order_items(order_id, cart_items)
                TelegramNotifier.notify_user(
                    telegram_id=telegram_id,
                    order_id=order_id,
                    items=cart_items,
                    total=total,
                    city=city,
                    department=department,
                    phone=phone
                )

                st.success(f"Замовлення №{order_id} оформлено!")
                CartManager.clear_cart()
                st.session_state.page = "main"
                st.rerun()

            except Exception as e:
                st.error(f"Помилка: {str(e)}")


# --- Main App ---
def main():
    CartManager.init()


    if "page" not in st.session_state:
        st.session_state.page = "main"
    if "viewing_product" not in st.session_state:
        st.session_state.viewing_product = None

    if st.session_state.page == "cart":
        CartManager.show_cart()
    elif st.session_state.page == "order":
        OrderUI.show_order_form()
    elif st.session_state.viewing_product:
        prod = Database.get_product(st.session_state.viewing_product)
        if prod:
            ProductUI.show_product_details(prod)
    else:
        search = st.text_input("Пошук товарів", key="search")
        cats = Database.get_categories()

        if cats:
            cols = st.columns(len(cats))
            for idx, (cid, cname) in enumerate(cats):
                with cols[idx]:
                    if st.button(cname, key=f"cat_{cid}"):
                        st.session_state.selected_category = cid
                        st.rerun()

        prods = Database.get_products(
            st.session_state.get("selected_category"),
            st.session_state.get("search", "")
        )

        cols = st.columns(3)
        for idx, prod in enumerate(prods):
            with cols[idx % 3]:
                ProductUI.show_product_card(prod)

        if CartManager.total_items() > 0:
            if st.button(f"🛒 Кошик ({CartManager.total_items()})", use_container_width=True):
                st.session_state.page = "cart"
                st.rerun()


if __name__ == "__main__":
    main()
