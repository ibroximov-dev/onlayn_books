import aiosqlite
import logging
from datetime import datetime, date

DB_PATH = "kitobbot.db"
logger = logging.getLogger(__name__)


async def init_db():
    """Barcha jadvallarni yaratadi"""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.executescript("""
            -- Foydalanuvchilar jadvali
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                telegram_id INTEGER UNIQUE NOT NULL,
                fullname TEXT NOT NULL,
                username TEXT,
                points INTEGER DEFAULT 0,
                reading_time INTEGER DEFAULT 0,  -- daqiqalarda
                books_read INTEGER DEFAULT 0,
                tests_passed INTEGER DEFAULT 0,
                streak INTEGER DEFAULT 0,
                last_login DATE,
                joined_date DATETIME DEFAULT CURRENT_TIMESTAMP,
                is_banned INTEGER DEFAULT 0
            );

            -- Kategoriyalar jadvali
            CREATE TABLE IF NOT EXISTS categories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                emoji TEXT DEFAULT '📚',
                book_type TEXT DEFAULT 'pdf'  -- 'pdf', 'audio', 'tale'
            );

            -- Kitoblar jadvali
            CREATE TABLE IF NOT EXISTS books (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                author TEXT,
                description TEXT,
                pdf_file_id TEXT,        -- Telegram file_id
                image_file_id TEXT,      -- Muqova rasmi
                category_id INTEGER,
                downloads INTEGER DEFAULT 0,
                added_date DATETIME DEFAULT CURRENT_TIMESTAMP,
                is_active INTEGER DEFAULT 1,
                FOREIGN KEY (category_id) REFERENCES categories(id)
            );

            -- Audio kitoblar jadvali
            CREATE TABLE IF NOT EXISTS audio_books (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                author TEXT,
                description TEXT,
                image_file_id TEXT,
                category_id INTEGER,
                total_parts INTEGER DEFAULT 1,
                added_date DATETIME DEFAULT CURRENT_TIMESTAMP,
                is_active INTEGER DEFAULT 1,
                FOREIGN KEY (category_id) REFERENCES categories(id)
            );

            -- Audio qismlar
            CREATE TABLE IF NOT EXISTS audio_parts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                audio_book_id INTEGER NOT NULL,
                part_number INTEGER NOT NULL,
                title TEXT,
                audio_file_id TEXT NOT NULL,  -- Telegram file_id
                duration INTEGER DEFAULT 0,    -- sekundlarda
                FOREIGN KEY (audio_book_id) REFERENCES audio_books(id)
            );

            -- Ertaklar jadvali
            CREATE TABLE IF NOT EXISTS tales (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                content TEXT,
                audio_file_id TEXT,
                image_file_id TEXT,
                language TEXT DEFAULT 'uz',   -- 'uz', 'en'
                tale_type TEXT DEFAULT 'folk', -- 'folk', 'sleep', 'educational'
                added_date DATETIME DEFAULT CURRENT_TIMESTAMP,
                is_active INTEGER DEFAULT 1
            );

            -- Testlar jadvali
            CREATE TABLE IF NOT EXISTS tests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                book_id INTEGER NOT NULL,
                question TEXT NOT NULL,
                option_a TEXT NOT NULL,
                option_b TEXT NOT NULL,
                option_c TEXT NOT NULL,
                option_d TEXT NOT NULL,
                correct TEXT NOT NULL,  -- 'a', 'b', 'c', 'd'
                FOREIGN KEY (book_id) REFERENCES books(id)
            );

            -- Test natijalari
            CREATE TABLE IF NOT EXISTS test_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                book_id INTEGER NOT NULL,
                score INTEGER NOT NULL,
                total INTEGER NOT NULL,
                passed_date DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id),
                FOREIGN KEY (book_id) REFERENCES books(id)
            );

            -- Sertifikatlar jadvali
            CREATE TABLE IF NOT EXISTS certificates (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                book_id INTEGER NOT NULL,
                score INTEGER NOT NULL,
                cert_id TEXT UNIQUE NOT NULL,  -- Verification ID
                issued_date DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id),
                FOREIGN KEY (book_id) REFERENCES books(id)
            );

            -- Reading timer sessiyalari
            CREATE TABLE IF NOT EXISTS reading_sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                start_time DATETIME,
                end_time DATETIME,
                duration INTEGER DEFAULT 0,  -- daqiqalarda
                FOREIGN KEY (user_id) REFERENCES users(id)
            );

            -- Foydalanuvchi progress (qaysi kitobni o'qiyapti)
            CREATE TABLE IF NOT EXISTS user_progress (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                audio_book_id INTEGER NOT NULL,
                current_part INTEGER DEFAULT 1,
                last_updated DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id),
                FOREIGN KEY (audio_book_id) REFERENCES audio_books(id),
                UNIQUE(user_id, audio_book_id)
            );
        """)
        await db.commit()

        # Default kategoriyalar qo'shish
        await _seed_categories(db)
        logger.info("✅ Barcha jadvallar yaratildi")


async def _seed_categories(db):
    """Default kategoriyalarni qo'shish"""
    check = await db.execute("SELECT COUNT(*) FROM categories")
    count = (await check.fetchone())[0]
    if count == 0:
        categories = [
            ("Dasturlash", "💻", "pdf"),
            ("Biznes", "💼", "pdf"),
            ("Psixologiya", "🧠", "pdf"),
            ("Ingliz tili", "🇬🇧", "pdf"),
            ("Motivatsiya", "🔥", "pdf"),
            ("IT", "🖥️", "pdf"),
            ("Marketing", "📊", "pdf"),
            ("Bolalar kitoblari", "🧒", "pdf"),
            ("Uzbek ertaklari", "🏕️", "tale"),
            ("Inglizcha ertaklar", "🌍", "tale"),
            ("Uyqu oldi", "🌙", "tale"),
            ("Tarbiyaviy", "📖", "tale"),
        ]
        await db.executemany(
            "INSERT INTO categories (name, emoji, book_type) VALUES (?, ?, ?)",
            categories
        )
        await db.commit()


# ─────────────────────────────────────────────
# FOYDALANUVCHI FUNKSIYALARI
# ─────────────────────────────────────────────

async def get_or_create_user(telegram_id: int, fullname: str, username: str = None):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        user = await db.execute(
            "SELECT * FROM users WHERE telegram_id = ?", (telegram_id,)
        )
        user = await user.fetchone()

        if not user:
            await db.execute(
                "INSERT INTO users (telegram_id, fullname, username) VALUES (?, ?, ?)",
                (telegram_id, fullname, username)
            )
            await db.commit()
            user = await db.execute(
                "SELECT * FROM users WHERE telegram_id = ?", (telegram_id,)
            )
            user = await user.fetchone()

        # Kunlik loginni tekshirish va streak yangilash
        today = date.today().isoformat()
        if user["last_login"] != today:
            streak = user["streak"] + 1 if user["last_login"] else 1
            bonus = streak * 5
            await db.execute("""
                UPDATE users SET last_login=?, streak=?, points=points+?+10
                WHERE telegram_id=?
            """, (today, streak, bonus, telegram_id))
            await db.commit()

        return dict(user)


async def get_user(telegram_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            "SELECT * FROM users WHERE telegram_id = ?", (telegram_id,)
        )
        row = await cur.fetchone()
        return dict(row) if row else None


async def add_points(telegram_id: int, points: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE users SET points = points + ? WHERE telegram_id = ?",
            (points, telegram_id)
        )
        await db.commit()


async def add_reading_time(telegram_id: int, minutes: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            UPDATE users SET reading_time = reading_time + ?, points = points + ?
            WHERE telegram_id = ?
        """, (minutes, minutes * 1, telegram_id))
        await db.commit()


async def get_top_users(limit: int = 10):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("""
            SELECT fullname, points, reading_time, books_read, tests_passed, streak
            FROM users WHERE is_banned = 0
            ORDER BY points DESC LIMIT ?
        """, (limit,))
        rows = await cur.fetchall()
        return [dict(r) for r in rows]


async def get_all_users():
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT telegram_id FROM users WHERE is_banned = 0")
        rows = await cur.fetchall()
        return [r[0] for r in rows]


async def ban_user(telegram_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE users SET is_banned = 1 WHERE telegram_id = ?", (telegram_id,)
        )
        await db.commit()


async def get_stats():
    async with aiosqlite.connect(DB_PATH) as db:
        users = (await (await db.execute("SELECT COUNT(*) FROM users")).fetchone())[0]
        books = (await (await db.execute("SELECT COUNT(*) FROM books")).fetchone())[0]
        certs = (await (await db.execute("SELECT COUNT(*) FROM certificates")).fetchone())[0]
        tests = (await (await db.execute("SELECT COUNT(*) FROM test_results")).fetchone())[0]
        return {"users": users, "books": books, "certificates": certs, "tests": tests}


# ─────────────────────────────────────────────
# KITOB FUNKSIYALARI
# ─────────────────────────────────────────────

async def add_book(title, author, description, pdf_file_id, image_file_id, category_id):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT INTO books (title, author, description, pdf_file_id, image_file_id, category_id)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (title, author, description, pdf_file_id, image_file_id, category_id))
        await db.commit()


async def get_books_by_category(category_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("""
            SELECT b.*, c.name as category_name
            FROM books b JOIN categories c ON b.category_id = c.id
            WHERE b.category_id = ? AND b.is_active = 1
            ORDER BY b.added_date DESC
        """, (category_id,))
        rows = await cur.fetchall()
        return [dict(r) for r in rows]


async def get_book(book_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("SELECT * FROM books WHERE id = ?", (book_id,))
        row = await cur.fetchone()
        return dict(row) if row else None


async def increment_downloads(book_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE books SET downloads = downloads + 1 WHERE id = ?", (book_id,)
        )
        await db.commit()


# ─────────────────────────────────────────────
# KATEGORIYA FUNKSIYALARI
# ─────────────────────────────────────────────

async def get_categories(book_type: str = "pdf"):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            "SELECT * FROM categories WHERE book_type = ?", (book_type,)
        )
        rows = await cur.fetchall()
        return [dict(r) for r in rows]


# ─────────────────────────────────────────────
# TEST FUNKSIYALARI
# ─────────────────────────────────────────────

async def add_test_question(book_id, question, a, b, c, d, correct):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT INTO tests (book_id, question, option_a, option_b, option_c, option_d, correct)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (book_id, question, a, b, c, d, correct))
        await db.commit()


async def get_test_questions(book_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            "SELECT * FROM tests WHERE book_id = ? ORDER BY RANDOM() LIMIT 10",
            (book_id,)
        )
        rows = await cur.fetchall()
        return [dict(r) for r in rows]


async def save_test_result(user_id: int, book_id: int, score: int, total: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT INTO test_results (user_id, book_id, score, total) VALUES (?, ?, ?, ?)
        """, (user_id, book_id, score, total))
        await db.execute(
            "UPDATE users SET tests_passed = tests_passed + 1 WHERE id = ?", (user_id,)
        )
        await db.commit()


async def has_passed_test(user_db_id: int, book_id: int):
    """Foydalanuvchi bu kitob testini avval yaxshi topshirganmi?"""
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("""
            SELECT id FROM test_results
            WHERE user_id = ? AND book_id = ? AND score >= 7
        """, (user_db_id, book_id))
        return await cur.fetchone() is not None


# ─────────────────────────────────────────────
# SERTIFIKAT FUNKSIYALARI
# ─────────────────────────────────────────────

async def create_certificate(user_db_id: int, book_id: int, score: int, cert_id: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT INTO certificates (user_id, book_id, score, cert_id) VALUES (?, ?, ?, ?)
        """, (user_db_id, book_id, score, cert_id))
        await db.execute(
            "UPDATE users SET points = points + 150 WHERE id = ?", (user_db_id,)
        )
        await db.commit()


async def get_user_certificates(user_db_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("""
            SELECT c.*, b.title as book_title, b.author as book_author
            FROM certificates c JOIN books b ON c.book_id = b.id
            WHERE c.user_id = ?
            ORDER BY c.issued_date DESC
        """, (user_db_id,))
        rows = await cur.fetchall()
        return [dict(r) for r in rows]


# ─────────────────────────────────────────────
# AUDIO KITOB FUNKSIYALARI
# ─────────────────────────────────────────────

async def add_audio_book(title, author, description, image_file_id, category_id):
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("""
            INSERT INTO audio_books (title, author, description, image_file_id, category_id)
            VALUES (?, ?, ?, ?, ?)
        """, (title, author, description, image_file_id, category_id))
        await db.commit()
        return cur.lastrowid


async def add_audio_part(audio_book_id, part_number, title, audio_file_id, duration=0):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT INTO audio_parts (audio_book_id, part_number, title, audio_file_id, duration)
            VALUES (?, ?, ?, ?, ?)
        """, (audio_book_id, part_number, title, audio_file_id, duration))
        await db.execute(
            "UPDATE audio_books SET total_parts = total_parts + 1 WHERE id = ?",
            (audio_book_id,)
        )
        await db.commit()


async def get_audio_books(category_id: int = None):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        if category_id:
            cur = await db.execute(
                "SELECT * FROM audio_books WHERE category_id=? AND is_active=1", (category_id,)
            )
        else:
            cur = await db.execute("SELECT * FROM audio_books WHERE is_active=1")
        rows = await cur.fetchall()
        return [dict(r) for r in rows]


async def get_audio_part(audio_book_id: int, part_number: int):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("""
            SELECT * FROM audio_parts WHERE audio_book_id=? AND part_number=?
        """, (audio_book_id, part_number))
        row = await cur.fetchone()
        return dict(row) if row else None


async def get_user_progress(user_db_id: int, audio_book_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("""
            SELECT current_part FROM user_progress WHERE user_id=? AND audio_book_id=?
        """, (user_db_id, audio_book_id))
        row = await cur.fetchone()
        return row[0] if row else 1


async def update_user_progress(user_db_id: int, audio_book_id: int, part: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT INTO user_progress (user_id, audio_book_id, current_part)
            VALUES (?, ?, ?)
            ON CONFLICT(user_id, audio_book_id) DO UPDATE SET current_part=?, last_updated=CURRENT_TIMESTAMP
        """, (user_db_id, audio_book_id, part, part))
        await db.commit()


# ─────────────────────────────────────────────
# ERTAK FUNKSIYALARI
# ─────────────────────────────────────────────

async def add_tale(title, content, audio_file_id, image_file_id, language, tale_type):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT INTO tales (title, content, audio_file_id, image_file_id, language, tale_type)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (title, content, audio_file_id, image_file_id, language, tale_type))
        await db.commit()


async def get_tales(tale_type: str = None, language: str = None):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        query = "SELECT * FROM tales WHERE is_active=1"
        params = []
        if tale_type:
            query += " AND tale_type=?"
            params.append(tale_type)
        if language:
            query += " AND language=?"
            params.append(language)
        cur = await db.execute(query, params)
        rows = await cur.fetchall()
        return [dict(r) for r in rows]


async def get_tale(tale_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("SELECT * FROM tales WHERE id=?", (tale_id,))
        row = await cur.fetchone()
        return dict(row) if row else None