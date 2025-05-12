import streamlit as st
import sqlite3
import requests
import os
from datetime import datetime

DB_NAME = os.path.join(os.path.dirname(__file__), "AwesomeZooShop.db")

from streamlit import config as _config
_config.set_option("theme.base", "light")  # Фиксируем светлую тему
_config.set_option("server.headless", True)  # Отключаем лишние элементы


# === Database ===
class Database:
    @staticmethod
    def get_categories():
        with sqlite3.connect(DB_NAME) as db:
            cur = db.cursor()
            cur.execute("SELECT id, name FROM categories")
            return cur.fetchall()

    @staticmethod
    def get_products(category_id=None, search=""):
        query = """
                SELECT id, name, description, price, stock, image
                FROM products \
                """
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
    def create_order(city, department, phone, cart_items):
        with sqlite3.connect(DB_NAME) as db:
            cur = db.cursor()
            # Для совместимости с вашей структурой, telegram_id установлен как 0
            cur.execute(
                """INSERT INTO orders
                       (telegram_id, status, city, department, contact_phone)
                   VALUES (?, ?, ?, ?, ?)""",
                (0, 'pending', city, department, phone)
            )
            order_id = cur.lastrowid

            # Добавляем элементы заказа
            cur.executemany(
                """INSERT INTO order_items
                       (order_id, product_id, quantity, price)
                   VALUES (?, ?, ?, ?)""",
                [(order_id, item['id'], item['qty'], item['price']) for item in cart_items]
            )

            db.commit()
            return order_id


# === Nova Poshta API ===
class NovaPoshtaAPI:
    API_KEY = "78bdffdabccd762699b69916b9f3d6c3"

    @staticmethod
    def get_cities():
        try:
            response = requests.post("https://api.novaposhta.ua/v2.0/json/", json={
                "apiKey": '78bdffdabccd762699b69916b9f3d6c3',
                "modelName": "Address",
                "calledMethod": "getCities",
                "methodProperties": {}
            })
            return [city["Description"] for city in response.json()["data"]]
        except:
            return ["Київ", "Харків", "Одеса", "Львів"]  # Fallback список

    @staticmethod
    def get_warehouses(city_name):
        try:
            response = requests.post("https://api.novaposhta.ua/v2.0/json/", json={
                "apiKey": '78bdffdabccd762699b69916b9f3d6c3',
                "modelName": "Address",
                "calledMethod": "getWarehouses",
                "methodProperties": {
                    "CityName": city_name
                }
            })
            return [wh["Description"] for wh in response.json()["data"]]
        except:
            return ["Відділення №1", "Відділення №2", "Відділення №3"]  # Fallback список


# === Order UI ===
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

        # Инициализация состояния
        if "order_data" not in st.session_state:
            st.session_state.order_data = {
                "cities": NovaPoshtaAPI.get_cities(),
                "city": "",
                "warehouses": [],
                "warehouse": "",
                "phone": "+380",
                "payment_method": "Оплата при отриманні"
            }
            if st.session_state.order_data["cities"]:
                st.session_state.order_data["city"] = st.session_state.order_data["cities"][0]
                st.session_state.order_data["warehouses"] = NovaPoshtaAPI.get_warehouses(
                    st.session_state.order_data["city"]
                )
                if st.session_state.order_data["warehouses"]:
                    st.session_state.order_data["warehouse"] = st.session_state.order_data["warehouses"][0]

        # Выбор города
        city = st.selectbox(
            "Місто",
            st.session_state.order_data["cities"],
            index=st.session_state.order_data["cities"].index(st.session_state.order_data["city"])
            if st.session_state.order_data["city"] in st.session_state.order_data["cities"]
            else 0,
            key="city_select"
        )

        # Обновляем список отделений при изменении города
        if city != st.session_state.order_data["city"]:
            st.session_state.order_data["city"] = city
            st.session_state.order_data["warehouses"] = NovaPoshtaAPI.get_warehouses(city)
            st.session_state.order_data["warehouse"] = (
                st.session_state.order_data["warehouses"][0]
                if st.session_state.order_data["warehouses"]
                else ""
            )
            st.rerun()

        # Выбор отделения
        if st.session_state.order_data["city"]:
            warehouse = st.selectbox(
                "Відділення Нової Пошти",
                st.session_state.order_data["warehouses"],
                index=st.session_state.order_data["warehouses"].index(st.session_state.order_data["warehouse"])
                if st.session_state.order_data["warehouse"] in st.session_state.order_data["warehouses"]
                else 0,
                key="warehouse_select"
            )
            st.session_state.order_data["warehouse"] = warehouse

        # Поле телефона с моментальной очисткой
        st.markdown("**Контактний телефон**")

        # Инициализация значения телефона
        if 'phone_input' not in st.session_state:
            st.session_state.phone_input = "+380"

        # Создаем текстовое поле с обработчиком изменений
        phone_input = st.text_input(
            "",
            value=st.session_state.phone_input,
            max_chars=13,
            key="phone_input_field",
            on_change=OrderUI.clean_phone_input,
            label_visibility="collapsed",
            placeholder="+380XXXXXXXXX"
        )

        # Сохраняем очищенное значение
        st.session_state.order_data["phone"] = st.session_state.phone_input

        # Выбор способа оплаты
        payment_method = st.radio(
            "Спосіб оплати:",
            ["Оплата при отриманні", "Переказ за реквізитами"],
            index=0 if st.session_state.order_data["payment_method"] == "Оплата при отриманні" else 1
        )
        st.session_state.order_data["payment_method"] = payment_method

        # Кнопка подтверждения заказа
        if st.button("Підтвердити замовлення", key="confirm_order"):
            phone = st.session_state.order_data["phone"]
            if len(phone) != 13 or not phone.startswith("+380") or not phone[1:].isdigit():
                st.error("Будь ласка, введіть коректний номер телефону у форматі +380XXXXXXXXX")
            else:
                OrderUI.process_order(
                    payment_method,
                    city,
                    warehouse,
                    phone,
                    cart_items,
                    total
                )

    @staticmethod
    def clean_phone_input():
        """Моментально очищает ввод телефона от недопустимых символов"""
        if 'phone_input_field' in st.session_state:
            current_value = st.session_state.phone_input_field

            # Оставляем только + в начале и цифры
            cleaned_value = "+"
            if current_value.startswith("+"):
                # Для части после + оставляем только цифры
                digits = [c for c in current_value[1:] if c.isdigit()]
                cleaned_value += "".join(digits)
            else:
                # Если + нет, добавляем его и цифры
                digits = [c for c in current_value if c.isdigit()]
                cleaned_value += "".join(digits)

            # Ограничиваем длину
            cleaned_value = cleaned_value[:13]

            # Форсируем начало +380
            if not cleaned_value.startswith("+380"):
                if len(cleaned_value) > 4:
                    cleaned_value = "+380" + cleaned_value[4:]
                else:
                    cleaned_value = "+380"
                cleaned_value = cleaned_value[:13]

            # Обновляем значения
            st.session_state.phone_input = cleaned_value
            st.session_state.phone_input_field = cleaned_value

    @staticmethod
    def process_order(payment_method, city, warehouse, phone, cart_items, total):
        """Обработка оформленного заказа"""
        try:
            order_id = Database.create_order(city, warehouse, phone, cart_items)

            order_details = (
                f"📦 **Нове замовлення №{order_id}**\n\n"
                f"🛒 **Товари:**\n"
            )

            for item in cart_items:
                order_details += f"- {item['name']} x{item['qty']} = {item['price'] * item['qty']:.2f} грн\n"

            order_details += (
                f"\n💰 **Загальна сума:** {total:.2f} грн\n"
                f"💳 **Спосіб оплати:** {payment_method}\n"
                f"🏙️ **Місто:** {city}\n"
                f"📮 **Відділення:** {warehouse}\n"
                f"📱 **Телефон:** {phone}\n"
            )

            st.success("Замовлення успішно оформлено! Очікуйте дзвінка для підтвердження.")
            CartManager.clear_cart()
            st.session_state.page = "main"
            st.rerun()

        except Exception as e:
            st.error(f"Помилка при оформленні замовлення: {str(e)}")


# === Cart UI ===
class CartUI:
    @staticmethod
    def show_cart_item(item):
        """Отображает один товар в корзине с компактным управлением количеством"""
        col1, col2, col3 = st.columns([3, 6, 3])

        with col1:
            st.image(item["image"], width=100)

        with col2:
            st.write(f"**{item['name']}**")
            st.write(f"💰 {item['price']} грн/шт")

            # Компактное управление количеством
            q_col1, q_col2 = st.columns([3, 1])
            with q_col1:
                st.number_input(
                    "",
                    min_value=1,
                    value=item["qty"],
                    key=f"qty_{item['id']}",
                    label_visibility="collapsed",
                    on_change=CartManager.update_qty,
                    args=(item["id"],)
                )

        with col3:
            if st.button("✕", key=f"del_{item['id']}"):
                CartManager.remove(item["id"])
                st.rerun()

        st.markdown("<hr style='margin: 0.5rem 0;'>", unsafe_allow_html=True)

    @staticmethod
    def show_cart():
        """Отображает всю корзину с новым дизайном"""
        st.header("🧺 Кошик")

        if st.button("← Назад до магазину", key="back_to_shop"):
            st.session_state.page = "main"
            st.rerun()

        cart_items = CartManager.get()
        if not cart_items:
            st.info("Кошик порожній")
            return

        for item in cart_items:
            CartUI.show_cart_item(item)

        total = sum(item["price"] * item["qty"] for item in cart_items)
        st.subheader(f"**Разом:** {total:.2f} грн")

        # Кнопка оформления заказа
        if st.button("Оформити замовлення", type="primary"):
            st.session_state.page = "order"
            st.rerun()


class ProductUI:
    @staticmethod
    def show_product_card(prod):
        """Отображает карточку товара с выделенной ценой"""
        pid, name, desc, price, stock, img = prod

        with st.container():
            st.markdown(
                f"""
                <style>
                .product-card {{
                    border: 1px solid #e0e0e0;
                    border-radius: 12px;
                    padding: 20px 15px;
                    text-align: center;
                    height: 400px;
                    display: flex;
                    flex-direction: column;
                    justify-content: space-between;
                    margin-bottom: 25px;
                    background: white;
                    box-shadow: 0 2px 8px rgba(0,0,0,0.1);
                }}
                .product-image-container {{
                    height: 150px;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    margin-bottom: 20px;
                    padding: 10px;
                }}
                .product-image {{
                    max-height: 100%;
                    max-width: 100%;
                    object-fit: contain;
                }}
                .product-name {{
                    font-size: 1.2rem;
                    font-weight: 600;
                    margin: 0 0 12px 0;
                    min-height: 3.2rem;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    line-height: 1.4;
                }}
                .product-price {{
                    margin: 18px 0;
                    font-size: 1.5rem;
                    font-weight: 700;
                }}
                .product-stock {{
                    margin: 12px 0 0 0;
                    font-size: 1.05rem;
                    color: {'#e74c3c' if stock <= 0 else '#27ae60'};
                    font-weight: 500;
                }}
                </style>

                <div class="product-card">
                    <div class="product-image-container">
                        <img src="{img}" class="product-image">
                    </div>
                    <div class="product-name">{name}</div>
                    <div class="product-price">{price} грн</div>
                    <div class="product-stock">
                        {'Немає в наявності' if stock <= 0 else f'В наявності: {stock} шт'}
                    </div>
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

        # Отображение информации о товаре
        st.image(img, use_container_width=True)
        st.markdown(f"## {name}")
        st.markdown(desc)
        st.markdown(f"**Ціна:** <span style='font-size:1.5rem; color:#e67e22;'>{price} грн</span>",
                    unsafe_allow_html=True)

        if stock > 0:
            st.success(f"**Наявність:** {stock} шт")
        else:
            st.error("**Наявність:** Немає в наявності")

        # Кнопка "Добавить в корзину"
        if stock > 0:
            if st.button("🛒 Додати до кошика",
                         key=f"add_{pid}",
                         use_container_width=True,
                         type="primary"):
                CartManager.add(pid, name, price, img)
                st.success(f"Товар '{name}' додано до кошика!")
                st.rerun()
        else:
            st.button("🛒 Додати до кошика",
                      key=f"add_disabled_{pid}",
                      disabled=True,
                      use_container_width=True)


# === Cart Manager ===
class CartManager:
    @staticmethod
    def init():
        """Инициализация корзины и всех необходимых переменных состояния"""
        if "cart" not in st.session_state:
            st.session_state.cart = []
        if "cart_initialized" not in st.session_state:
            st.session_state.cart_initialized = True

    @staticmethod
    def add(pid, name, price, image):
        CartManager.init()  # Гарантируем инициализацию
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
        CartManager.init()  # Гарантируем инициализацию
        return st.session_state.cart

    @staticmethod
    def total_items():
        CartManager.init()  # Гарантируем инициализацию
        return sum(item["qty"] for item in st.session_state.cart)

    @staticmethod
    def remove(pid):
        CartManager.init()  # Гарантируем инициализацию
        st.session_state.cart = [item for item in st.session_state.cart if item["id"] != pid]

    @staticmethod
    def clear_cart():
        CartManager.init()  # Гарантируем инициализацию
        st.session_state.cart = []

    @staticmethod
    def update_qty(pid):
        CartManager.init()  # Гарантируем инициализацию
        for item in st.session_state.cart:
            if item["id"] == pid:
                item["qty"] = st.session_state[f"qty_{pid}"]


# === Main UI ===
class MainUI:
    @staticmethod
    def search_bar():
        col1, col2 = st.columns([1, 5])
        with col1:
            if st.button("🏠", help="На головну", key="home_btn"):
                st.session_state.update({
                    "search_text": "",
                    "selected_category": None,
                    "viewing_product": None,
                    "page": "main",
                    "force_update": not st.session_state.get('force_update', False)
                })
        with col2:
            search = st.text_input(
                "Пошук",
                value=st.session_state.get("search_text", ""),
                key="search_input",
                placeholder="🔍 Пошук товарів",
                on_change=lambda: st.session_state.update({"search_text": st.session_state.search_input})
            )
        return st.session_state.get("search_text", "")

    @staticmethod
    def show_categories(categories):
        """Отображает категории в горизонтальном ряду"""
        cols = st.columns(len(categories))
        for idx, (cid, cname) in enumerate(categories):
            with cols[idx]:
                if st.button(cname,
                           key=f"cat_{cid}_{st.session_state.get('cat_key', 0)}",
                           on_click=lambda cid=cid: MainUI._set_category(cid)):
                    pass

    @staticmethod
    def _set_category(cid):
        """Обработчик выбора категории"""
        st.session_state.update({
            "selected_category": cid,
            "viewing_product": None,
            "cat_key": st.session_state.get('cat_key', 0) + 1
        })

    @staticmethod
    def category_header(selected_category, categories):
        c1, c2 = st.columns([1, 10])
        if selected_category:
            if c1.button("← Назад",
                        key=f"back_btn_{st.session_state.get('back_key', 0)}",
                        on_click=MainUI._reset_category):
                pass
            name = next((n for (i, n) in categories if i == selected_category), "")
            c2.subheader(name)
        else:
            c2.subheader("Головна")

    @staticmethod
    def _reset_category():
        """Обработчик кнопки Назад"""
        st.session_state.update({
            "selected_category": None,
            "viewing_product": None,
            "back_key": st.session_state.get('back_key', 0) + 1
        })

    @staticmethod
    def show_cart_button():
        n = CartManager.total_items()
        if n > 0:
            if st.button(f"🛒 Кошик ({n})",
                        key=f"cart_btn_{st.session_state.get('cart_key', 0)}",
                        on_click=lambda: st.session_state.update({
                            "page": "cart",
                            "cart_key": st.session_state.get('cart_key', 0) + 1
                        })):
                pass


def show_footer():
    st.markdown("""
    <style>
    .footer-button {
        background: none !important;
        border: none !important;
        padding: 0 !important;
        color: inherit !important;
        text-decoration: none !important;
        cursor: pointer !important;
        font-size: 1rem !important;
        text-align: left !important;
    }
    .footer-button:hover {
        text-decoration: underline !important;
    }
    </style>
    """, unsafe_allow_html=True)

    st.markdown("---")

    # Создаем 2 колонки для кнопок
    col1, col2 = st.columns(2)

    with col1:
        if st.button("Про магазин", key="footer_about", help="Информация о нашем магазине"):
            st.info("AwesomeZooShop - інтернет-магазин товарів для домашніх улюбленців. "
                    "Ми працюємо з 2025 року та пропонуємо якісні товари для котів та собак.")

        if st.button("Доставка", key="footer_delivery", help="Условия доставки"):
            st.info("Після замовлення з вами зв'яжеться менеджер для підтвердження. "
                    "Обробка замовлень з понеділка по п'ятницю з 9:00 до 20:00. "
                    "Доставка здійснюється Новою Поштою.")

    with col2:
        if st.button("Оплата", key="footer_payment", help="Способы оплаты"):
            st.info("Оплата здійснюється на відділенні Нової Пошти або за реквізитами на карту. "
                    "Мінімальної суми замовлення немає.")

        if st.button("Повернення", key="footer_returns", help="Условия возврата"):
            st.info("Для повернення товару зв'яжіться з нами по телефону або email.")

    # Контактный телефон
    st.markdown("📞 **Контактний телефон:** +380 (44) 123-45-67")
    st.markdown("📞 **E-mail:** AwesomeZooShop@gmail.com")

    st.markdown("---")
    st.markdown("© 2025 AwesomeZooShop. Всі права захищені.",
                help="Наш інтернет-магазин")


# === Main App ===
def main():
    # Инициализация всех состояний
    CartManager.init()  # Явная инициализация корзины

    if "page" not in st.session_state:
        st.session_state.page = "main"
    if "selected_category" not in st.session_state:
        st.session_state.selected_category = None
    if "viewing_product" not in st.session_state:
        st.session_state.viewing_product = None
    if "search_text" not in st.session_state:
        st.session_state.search_text = ""
    if "force_update" not in st.session_state:
        st.session_state.force_update = False
    if "cat_key" not in st.session_state:
        st.session_state.cat_key = 0
    if "back_key" not in st.session_state:
        st.session_state.back_key = 0
    if "cart_key" not in st.session_state:
        st.session_state.cart_key = 0

    # Отрисовка интерфейса
    if st.session_state.page == "cart":
        CartUI.show_cart()
    elif st.session_state.page == "order":
        OrderUI.show_order_form()
    else:
        search = MainUI.search_bar()
        cats = Database.get_categories()
        MainUI.category_header(st.session_state.selected_category, cats)

        if not st.session_state.selected_category and not st.session_state.search_text:
            MainUI.show_categories(cats)

        if st.session_state.viewing_product:
            prod = Database.get_product(st.session_state.viewing_product)
            if prod:
                ProductUI.show_product_details(prod)
        else:
            prods = Database.get_products(
                st.session_state.selected_category,
                st.session_state.search_text
            )
            cols = st.columns(3, gap="medium")
            for idx, prod in enumerate(prods):
                with cols[idx % 3]:
                    ProductUI.show_product_card(prod)

        MainUI.show_cart_button()

    show_footer()

if __name__ == "__main__":
    main()
