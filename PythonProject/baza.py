import asyncio
import aiosqlite

DB_PATH = "AwesomeZooShop.db"

products = [
    {
        "name": "Щітка-пуходерка Trixie двостороння, з дерев'яною ручкою та захисними кульками 10 см / 18 см",
        "description": """• для делікатного догляду за шерстю і підшерстям
• дерево
• м'яка нейлонова щетина і металева щетина з наконечниками
""",
        "category": "Грумінг",
        "price": 176,
        "stock": 116,
        "image": "https://masterzoo.ua/content/images/36/700x700l80mc0/73870233333985.webp"
    },
    {
        "name": "Інструмент для видалення підшерстя FURminator для довгошерстих котів, розмір M-L",
        "description": """Лезо інструменту захоплює і витягує слабо прикріплені волоски підшерстя, зменшуючи линьку на 90%. Залежно від розміру та довжини шерсті улюбленця, можна підібрати відповідне лезо, яке буде ефективно справлятися з проблемою усунення відмерлої шерсті вихованця.

Інформація про товар
- Покращує зовнішній вигляд тварини, сприяє зростанню здорової шерсті
- Лезо інструменту проникає крізь волосся, не пошкоджуючи його, і легко витягає мертві, слабо прикріплені волоски підшерстя
- Бокові пластини Skin Guard® попереджають тиск леза на шкіру
- Зігнуте лезо відповідає контурам тіла тварини для комфорту в процесі вичісування
- Кнопка самоочищення FURejector® допомагає швидко скинути шерсть з інструменту, роблячи процес вичісування простіше і зручніше
- Ергономічна ручка для комфорту і простоти використання
- Зменшує линьку на 90%
""",
        "category": "Грумінг",
        "price": 1237,
        "stock": 0,
        "image": "https://masterzoo.ua/content/images/43/700x700l80mc0/instrument-dlya-udaleniya-podsherstka-furminator-dlya-dlinnosherstnykh-koshek-razmer-m-l-16156695123102.webp"
    },
    {
        "name": "Інструмент для видалення підшерстя Trixie 11 см / 15 см",
        "description": """• для видалення зайвого підшерстя
• допомагає розчісувати і розрізати ковтуни
• насадка легко змінюється за допомогою вбудованого механізму
• лезо з нержавіючої сталі
• пластикова ручка з гумовим покриттям
• підходить для коней
""",
        "category": "Грумінг",
        "price": 973,
        "stock": 35,
        "image": "https://masterzoo.ua/content/images/4/700x700l80mc0/33299271391883.webp"
    }
]

async def insert_products():
    async with aiosqlite.connect(DB_PATH) as db:
        # Получаем ID категории "коти"
        async with db.execute("SELECT id FROM categories WHERE name = ?", ("Лежаки",)) as cursor:
            row = await cursor.fetchone()
            if not row:
                raise ValueError("Категорія 'коти' не знайдена в таблиці categories.")
            category_id = row[0]

        # Добавляем товары
        for product in products:
            await db.execute("""
                INSERT INTO products (name, description, category_id, price, stock, image)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                product["name"],
                product["description"],
                category_id,
                product["price"],
                product["stock"],
                product["image"]
            ))
        await db.commit()
        print("✅ Товари успішно додані.")

if __name__ == "__main__":
    asyncio.run(insert_products())
