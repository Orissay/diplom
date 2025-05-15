import streamlit as st
import requests
import os
import json
from datetime import datetime, time
from supabase import create_client, Client
from streamlit import config as _config

# Конфигурация Supabase
SUPABASE_URL = "https://hxowoktqmcgrckptjvnz.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Imh4b3dva3RxbWNncmNrcHRqdm56Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NDcyMDc0MzgsImV4cCI6MjA2Mjc4MzQzOH0.znG6XuvFzHE_iIpl3j79UW7dJORB3UhF-qAHvuSrOiY"
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# Настройки Streamlit
_config.set_option("theme.base", "light")
_config.set_option("server.headless", True)

st.markdown("""
<script>
  (function() {
    if (window.Telegram && window.Telegram.WebApp) {
      const init = Telegram.WebApp.initData;
      // если ещё нет в URL — добавляем и перезагружаем
      if (init && !window.location.search.includes("initData=")) {
        const qs = window.location.search ? window.location.search + "&" : "?";
        window.location.href = window.location.pathname + qs + "initData=" + encodeURIComponent(init);
      }
    }
  })();
</script>
""", unsafe_allow_html=True)

def get_telegram_user():
    # Считываем telegram_id из URL-параметров
    params = st.query_params()
    tid = params.get("telegram_id", [None])[0]
    try:
        return int(tid) if tid else None
    except:
        return None


if "telegram_id" not in st.session_state:
    st.session_state.telegram_id = get_telegram_user()
    st.session_state.is_webapp = bool(st.session_state.telegram_id)


def verify_webapp():
    if not st.session_state.get("is_webapp"):
        st.error("""
        ## Доступ только через Telegram бота!
        Для оформления заказа:
        1. Вернитесь в чат с ботом
        2. Нажмите кнопку **'Магазин'**
        3. Используйте интерфейс WebApp
        """)
        st.stop()

# === Database ===
class Database:
    @staticmethod
    def get_categories():
        response = supabase.table("categories").select("id, name").execute()
        return [(item['id'], item['name']) for item in response.data]

    @staticmethod
    def get_products(category_id=None, search=""):
        query = supabase.table("products").select("id, name, description, price, stock, image")

        if category_id:
            query = query.eq("category_id", category_id)
        elif search:
            query = query.ilike("name", f"%{search}%")

        query = query.order("stock", desc=True).order("name")
        response = query.execute()
        return [(item['id'], item['name'], item['description'], item['price'],
                 item['stock'], item['image']) for item in response.data]

    @staticmethod
    def get_product(pid):
        response = supabase.table("products").select("*").eq("id", pid).execute()
        if response.data:
            item = response.data[0]
            return (item['id'], item['name'], item['description'], item['price'],
                    item['stock'], item['image'])
        return None

    @staticmethod
    def create_order(city, department, phone, cart_items):
        try:
            # Проверяем WebApp контекст
            if not st.session_state.get("is_webapp"):
                raise PermissionError("Доступ запрещён: не WebApp контекст")

            # Создаём заказ
            order_data = {
                "telegram_id": st.session_state.telegram_id,
                "status": "pending",
                "city": city,
                "department": department,
                "contact_phone": phone,
            }

            response = supabase.table("orders").insert(order_data).execute()
            order_id = response.data[0]['id']

            # Добавляем товары
            order_items = [{
                "order_id": order_id,
                "product_id": item['id'],
                "quantity": item['qty'],
                "price": item['price']
            } for item in cart_items]

            supabase.table("order_items").insert(order_items).execute()

            # Закрываем WebApp
            if st.session_state.is_webapp:
                st.markdown("""
                <script>
                if (window.Telegram && window.Telegram.WebApp) {
                    Telegram.WebApp.close();
                }
                </script>
                """, unsafe_allow_html=True)

            return order_id

        except Exception as e:
            st.error(f"Ошибка создания заказа: {str(e)}")
            st.stop()
    
    

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
            return ["Київ", "Харків", "Одеса", "Львів"]

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
            return ["Відділення №1", "Відділення №2", "Відділення №3"]


# === Order UI ===
class OrderUI:
    @staticmethod
    def show_order_form():
        if not st.session_state.get("is_webapp"):
            verify_webapp()
            return

        st.header("Оформлення замовлення")

        if st.button("← На головну", key="back_to_main_from_order"):
            st.session_state.page = "main"
            st.rerun()

        cart_items = CartManager.get()
        if not cart_items:
            st.error("Кошик порожній")
            time.sleep(2)
            st.rerun()
            return

        total = sum(item["price"] * item["qty"] for item in cart_items)
        st.write(f"**Сума замовлення:** {total:.2f} грн")

        # Инициализация данных заказа
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

        # Форма заказа
        with st.form("order_form"):
            city = st.selectbox(
                "Місто",
                st.session_state.order_data["cities"],
                index=st.session_state.order_data["cities"].index(st.session_state.order_data["city"])
                if st.session_state.order_data["city"] in st.session_state.order_data["cities"]
                else 0
            )

            if city != st.session_state.order_data["city"]:
                st.session_state.order_data["city"] = city
                st.session_state.order_data["warehouses"] = NovaPoshtaAPI.get_warehouses(city)
                st.rerun()

            warehouse = st.selectbox(
                "Відділення Нової Пошти",
                st.session_state.order_data["warehouses"],
                index=st.session_state.order_data["warehouses"].index(st.session_state.order_data["warehouse"])
                if st.session_state.order_data["warehouse"] in st.session_state.order_data["warehouses"]
                else 0
            )

            phone = st.text_input(
                "Контактний телефон",
                value=st.session_state.order_data["phone"],
                max_chars=13,
                placeholder="+380XXXXXXXXX"
            )

            payment_method = st.radio(
                "Спосіб оплати:",
                ["Оплата при отриманні", "Переказ за реквізитами"]
            )

            submitted = st.form_submit_button("Підтвердити замовлення")

            if submitted:
                # Валидация телефона
                if len(phone) != 13 or not phone.startswith("+380") or not phone[1:].isdigit():
                    st.error("Будь ласка, введіть коректний номер телефону у форматі +380XXXXXXXXX")
                    st.stop()

                try:
                    # Сохраняем данные
                    st.session_state.order_data.update({
                        "city": city,
                        "warehouse": warehouse,
                        "phone": phone,
                        "payment_method": payment_method
                    })

                    # Создаем заказ
                    order_id = Database.create_order(
                        city=city,
                        department=warehouse,
                        phone=phone,
                        cart_items=cart_items
                    )

                    # Успешное оформление
                    st.success("Замовлення успішно оформлено!")

                    # Закрытие WebApp если это Telegram
                    if st.session_state.get("telegram_id"):
                        st.markdown("""
                        <script>
                        if (window.Telegram && window.Telegram.WebApp) {
                            Telegram.WebApp.close();
                        }
                        </script>
                        """, unsafe_allow_html=True)

                    CartManager.clear_cart()
                    time.sleep(2)
                    st.session_state.page = "main"
                    st.rerun()

                except Exception as e:
                    st.error(f"Помилка при оформленні: {str(e)}")
                    st.stop()

    @staticmethod
    def clean_phone_input():
        if 'phone_input_field' in st.session_state:
            current_value = st.session_state.phone_input_field
            cleaned_value = "+"
            if current_value.startswith("+"):
                digits = [c for c in current_value[1:] if c.isdigit()]
                cleaned_value += "".join(digits)
            else:
                digits = [c for c in current_value if c.isdigit()]
                cleaned_value += "".join(digits)

            cleaned_value = cleaned_value[:13]
            if not cleaned_value.startswith("+380"):
                if len(cleaned_value) > 4:
                    cleaned_value = "+380" + cleaned_value[4:]
                else:
                    cleaned_value = "+380"
                cleaned_value = cleaned_value[:13]

            st.session_state.phone_input = cleaned_value
            st.session_state.phone_input_field = cleaned_value

    def process_order():
        # Проверка WebApp окружения
        if not st.session_state.get("telegram_id"):
            st.error("Для оформления заказа используйте Telegram бота")
            return

        try:
            order_id = Database.create_order(
                city=st.session_state.order_data["city"],
                department=st.session_state.order_data["warehouse"],
                phone=st.session_state.order_data["phone"],
                cart_items=CartManager.get()
            )

            # Закрытие WebApp
            close_script = """
            <script>
            if (window.Telegram && window.Telegram.WebApp) {
                Telegram.WebApp.sendData(JSON.stringify({
                    status: "success",
                    order_id: %d
                }));
                Telegram.WebApp.close();
            }
            </script>
            """ % order_id

            st.components.v1.html(close_script, height=0)

        except Exception as e:
            st.error(f"Ошибка: {str(e)}")


# === Cart UI ===
class CartUI:
    @staticmethod
    def show_cart_item(item):
        col1, col2, col3 = st.columns([3, 6, 3])

        with col1:
            st.image(item["image"], width=100)

        with col2:
            st.write(f"**{item['name']}**")
            st.write(f"💰 {item['price']} грн/шт")

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

        if st.button("Оформити замовлення", type="primary"):
            st.session_state.page = "order"
            st.rerun()


class ProductUI:
    @staticmethod
    def show_product_card(prod):
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

        st.image(img, use_container_width=True)
        st.markdown(f"## {name}")
        st.markdown(desc)
        st.markdown(f"**Ціна:** <span style='font-size:1.5rem; color:#e67e22;'>{price} грн</span>",
                    unsafe_allow_html=True)

        if stock > 0:
            st.success(f"**Наявність:** {stock} шт")
        else:
            st.error("**Наявність:** Немає в наявності")

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
        if "cart" not in st.session_state:
            st.session_state.cart = []
        if "cart_initialized" not in st.session_state:
            st.session_state.cart_initialized = True

    @staticmethod
    def add(pid, name, price, image):
        CartManager.init()
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
        CartManager.init()
        return st.session_state.cart

    @staticmethod
    def total_items():
        CartManager.init()
        return sum(item["qty"] for item in st.session_state.cart)

    @staticmethod
    def remove(pid):
        CartManager.init()
        st.session_state.cart = [item for item in st.session_state.cart if item["id"] != pid]

    @staticmethod
    def clear_cart():
        CartManager.init()
        st.session_state.cart = []

    @staticmethod
    def update_qty(pid):
        CartManager.init()
        for item in st.session_state.cart:
            if item["id"] == pid:
                item["qty"] = st.session_state[f"qty_{pid}"]


class MainUI:
    verify_webapp()
    @staticmethod
    def show_header():
        # Создаем 3 колонки: кнопка дома, поиск, корзина
        col1, col2, col3 = st.columns([1, 5, 2])

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
                on_change=lambda: st.session_state.update({"search_text": st.session_state.search_input}),
                label_visibility="collapsed"
            )

        with col3:
            MainUI._show_cart_button("header")  # Используем внутренний метод для кнопки в шапке

        return st.session_state.get("search_text", "")

    @staticmethod
    def _show_cart_button(position="footer"):
        """Внутренний метод для отображения кнопки корзины"""
        cart_count = CartManager.total_items()
        cart_text = f"🛒 Кошик ({cart_count})" if cart_count > 0 else "🛒 Кошик"

        # Для нижней кнопки используем primary стиль, для верхней - secondary
        button_type = "primary" if position == "footer" else "secondary"

        if st.button(cart_text,
                     key=f"cart_btn_{position}",
                     use_container_width=True,
                     type=button_type):
            st.session_state.page = "cart"
            st.rerun()

    @staticmethod
    def show_cart_button():
        """Публичный метод для отображения кнопки корзины внизу"""
        MainUI._show_cart_button("footer")

    @staticmethod
    def show_categories(categories):
        cols = st.columns(len(categories))
        for idx, (cid, cname) in enumerate(categories):
            with cols[idx]:
                if st.button(cname,
                             key=f"cat_{cid}_{st.session_state.get('cat_key', 0)}",
                             on_click=lambda cid=cid: MainUI._set_category(cid)):
                    pass

    @staticmethod
    def _set_category(cid):
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
        st.session_state.update({
            "selected_category": None,
            "viewing_product": None,
            "back_key": st.session_state.get('back_key', 0) + 1
        })


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

    st.markdown("📞 **Контактний телефон:** +380 (44) 123-45-67")
    st.markdown("📧 **E-mail:** AwesomeZooShop@gmail.com")

    st.markdown("---")
    st.markdown("© 2025 AwesomeZooShop. Всі права захищені.",
                help="Наш інтернет-магазин")


# === Main App ===
def main():
    CartManager.init()

    # Инициализация состояния (остается без изменений)
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

    if st.session_state.page == "cart":
        CartUI.show_cart()
    elif st.session_state.page == "order":
        OrderUI.show_order_form()
    else:
        search = MainUI.show_header()
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

        # Добавляем кнопку корзины внизу (идентичную верхней)
        st.write("")  # Добавляем отступ
        MainUI.show_cart_button()

    show_footer()

if __name__ == "__main__":
    main()
