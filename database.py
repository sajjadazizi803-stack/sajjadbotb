import sqlite3

DB_NAME = "database.db"


def get_connection():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn


# ------------------ init database ------------------


def init_db():

    conn = get_connection()
    cursor = conn.cursor()

    # جدول کاربران
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        username TEXT,
        full_name TEXT,
        balance INTEGER DEFAULT 0,
        last_subscription TEXT DEFAULT NULL,
        trial_received INTEGER DEFAULT 0,
        joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # جدول زیرمجموعه‌ها
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS referrals (
        user_id INTEGER PRIMARY KEY,
        inviter_id INTEGER,
        reward_paid INTEGER DEFAULT 0,
        FOREIGN KEY(user_id) REFERENCES users(user_id),
        FOREIGN KEY(inviter_id) REFERENCES users(user_id)
    )
    """)

    # جدول سرویس‌های کاربران
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS user_services (
        service_id TEXT PRIMARY KEY,
        user_id INTEGER NOT NULL,
        service_name TEXT NOT NULL,
        subscription_url TEXT NOT NULL,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(user_id) REFERENCES users(user_id)
    )
    """)

    # جدول اخبار راهبردی
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS strategic_news (
    key TEXT PRIMARY KEY,
    content TEXT,
    photo TEXT
)
    """)

    conn.commit()
    conn.close()

    add_region_column()
    add_configs_column()
    add_news_photo_column()


# ------------------ add user ------------------


def add_user(user_id, username, full_name):

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        INSERT OR IGNORE INTO users (
            user_id,
            username,
            full_name,
            balance
        )
        VALUES (?, ?, ?, ?)
        """,
        (
            user_id,
            username,
            full_name,
            5000,
        ),
    )

    conn.commit()
    conn.close()


# ------------------ get users ------------------


def get_users():

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT user_id FROM users")

    users = [row["user_id"] for row in cursor.fetchall()]

    conn.close()

    return users


# ------------------ get users count ------------------


def get_users_count():

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM users")

    count = cursor.fetchone()[0]

    conn.close()

    return count


# ------------------ get balance ------------------


def get_balance(user_id):

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT balance FROM users WHERE user_id=?",
        (user_id,),
    )

    row = cursor.fetchone()

    conn.close()

    if row:
        return row["balance"]

    return 0


# ------------------ get join date ------------------


def get_join_date(user_id):

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT joined_at
        FROM users
        WHERE user_id=?
        """,
        (user_id,),
    )

    row = cursor.fetchone()

    conn.close()

    if row:
        return row["joined_at"]

    return None


# ------------------ add balance ------------------


def add_balance(user_id, amount):

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        UPDATE users
        SET balance = balance + ?
        WHERE user_id=?
        """,
        (
            amount,
            user_id,
        ),
    )

    conn.commit()
    conn.close()


# ------------------ deduct balance ------------------


def deduct_balance(user_id, amount):

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        UPDATE users
        SET balance = balance - ?
        WHERE user_id=?
        """,
        (
            amount,
            user_id,
        ),
    )

    conn.commit()
    conn.close()


# ------------------ save referral ------------------


def save_referral(user_id, inviter_id):

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS referrals(
        user_id INTEGER PRIMARY KEY,
        inviter_id INTEGER,
        reward_paid INTEGER DEFAULT 0
    )
""")

    cursor.execute(
        """
        INSERT OR IGNORE INTO referrals(
            user_id,
            inviter_id
        )
        VALUES(?,?)
    """,
        (user_id, inviter_id),
    )

    conn.commit()
    conn.close()


# ------------------ get referrals count ------------------


def get_referrals_count(inviter_id):

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT COUNT(*)
        FROM referrals
        WHERE inviter_id=?
    """,
        (inviter_id,),
    )

    count = cursor.fetchone()[0]

    conn.close()

    return count


# ------------------ total referral earnings ------------------


def get_referral_earnings(user_id):

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT COUNT(*)
        FROM referrals
        WHERE inviter_id = ?
        AND reward_paid = 1
        """,
        (user_id,),
    )

    count = cursor.fetchone()[0]

    conn.close()

    return count * 10000


# ------------------ has referral ------------------


def has_referral(user_id):

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT 1 FROM referrals WHERE user_id=?", (user_id,))

    row = cursor.fetchone()

    conn.close()

    return row is not None


# ------------------ reward already paid ------------------


def reward_already_paid(user_id):

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT reward_paid
        FROM referrals
        WHERE user_id=?
        """,
        (user_id,),
    )

    row = cursor.fetchone()

    conn.close()

    if row:
        return bool(row["reward_paid"])

    return False


# ------------------ mark reward paid ------------------


def mark_reward_paid(user_id):

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        UPDATE referrals
        SET reward_paid=1
        WHERE user_id=?
        """,
        (user_id,),
    )

    conn.commit()
    conn.close()


# ------------------ get inviter ------------------


def get_inviter(user_id):

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT inviter_id
        FROM referrals
        WHERE user_id=?
        """,
        (user_id,),
    )

    row = cursor.fetchone()

    conn.close()

    if row:
        return row["inviter_id"]

    return None


# ------------------ get referrals ------------------


def get_referrals(inviter_id):

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT
            users.full_name,
            referrals.reward_paid
        FROM referrals
        JOIN users
        ON referrals.user_id = users.user_id
        WHERE referrals.inviter_id = ?
        ORDER BY users.joined_at DESC
        """,
        (inviter_id,),
    )

    rows = cursor.fetchall()

    conn.close()

    return rows


# ------------------ save user service ------------------


def save_user_service(user_id, service_id):

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        INSERT OR REPLACE INTO user_services (service_id, user_id)
        VALUES (?, ?)
        """,
        (service_id, user_id),
    )

    conn.commit()
    conn.close()


# ------------------ get user service ids ------------------


def get_user_service_ids(user_id):

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT service_id
        FROM user_services
        WHERE user_id = ?
        """,
        (user_id,),
    )

    rows = cursor.fetchall()

    conn.close()

    return [row[0] for row in rows]


# ------------------ save user service ------------------


def save_user_service(service_id, user_id, service_name, subscription_url):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    cursor.execute(
        """
        INSERT OR REPLACE INTO user_services
        (service_id, user_id, service_name, subscription_url)
        VALUES (?, ?, ?, ?)
    """,
        (service_id, user_id, service_name, subscription_url),
    )

    conn.commit()
    conn.close()


# ------------------ get subscription by service ------------------


def get_subscription_by_service(service_id):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT subscription_url
        FROM user_services
        WHERE service_id=?
    """,
        (service_id,),
    )

    row = cursor.fetchone()

    conn.close()

    return row[0] if row else None


# ------------------ get service by nabe ------------------


def get_service_by_name(service_name):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT service_id, subscription_url
        FROM user_services
        WHERE service_name=?
    """,
        (service_name,),
    )

    row = cursor.fetchone()

    conn.close()

    return row


# ------------------ get subscription by service name ------------------


def get_subscription_by_service_name(service_name):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT subscription_url
        FROM user_services
        WHERE service_name=?
    """,
        (service_name,),
    )

    row = cursor.fetchone()

    conn.close()

    return row[0] if row else None


# ------------------ get user service ------------------


def get_user_services(user_id):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT service_id, service_name, subscription_url
        FROM user_services
        WHERE user_id=?
        ORDER BY created_at DESC
    """,
        (user_id,),
    )

    rows = cursor.fetchall()

    conn.close()

    return rows


# ------------------ update service name ------------------


def update_service_name(service_id, new_name):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        UPDATE user_services
        SET service_name=?
        WHERE service_id=?
        """,
        (new_name, service_id),
    )

    conn.commit()
    conn.close()


# ------------------ add region column ------------------


def add_region_column():
    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("ALTER TABLE user_services ADD COLUMN region TEXT DEFAULT '🌐'")
        conn.commit()
    except Exception:
        pass

    conn.close()


# ------------------ update service region ------------------


def update_service_region(service_id, region):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        UPDATE user_services
        SET region=?
        WHERE service_id=?
        """,
        (region, service_id),
    )

    conn.commit()
    conn.close()


# ------------------ get service region ------------------


def get_service_region(service_id):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT configs, region
        FROM user_services
        WHERE service_id=?
        """,
        (service_id,),
    )

    row = cursor.fetchone()

    conn.close()

    if not row:
        return "🌐"

    configs = row[0] or ""
    saved_region = row[1] or "🌐"

    if not configs.strip():
        return saved_region

    regions = []
    seen = set()

    for line in configs.splitlines():
        line = line.strip()

        if "#" not in line:
            continue

        region = line.split("#", 1)[1].split("|", 1)[0].strip()

        if region and region not in seen:
            seen.add(region)
            regions.append(region)

    if regions:
        return "\n".join(regions)

    return saved_region


# ------------------ add configs column ------------------


def add_configs_column():
    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("ALTER TABLE user_services ADD COLUMN configs TEXT DEFAULT ''")
        conn.commit()
    except Exception:
        pass

    conn.close()


# ------------------ add configs column ------------------


def add_news_photo_column():
    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("ALTER TABLE strategic_news ADD COLUMN photo TEXT")
    except:
        pass

    conn.commit()
    conn.close()


# ------------------ update service configs ------------------


def update_service_configs(service_id, configs):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        UPDATE user_services
        SET configs=?
        WHERE service_id=?
        """,
        ("\n".join(configs), service_id),
    )

    conn.commit()
    conn.close()


# ------------------ get service configs db ------------------


def get_service_configs_db(service_id):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT configs
        FROM user_services
        WHERE service_id=?
        """,
        (service_id,),
    )

    row = cursor.fetchone()

    conn.close()

    if not row or not row[0]:
        return []

    return row[0].split("\n")


# ------------------ set news ------------------


def set_news(key, content):

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        INSERT INTO strategic_news(key, content)
        VALUES(?, ?)
        ON CONFLICT(key)
        DO UPDATE SET content = excluded.content
        """,
        (key, content),
    )

    conn.commit()
    conn.close()


# ------------------ get news ------------------


def get_news(key):

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT content
        FROM strategic_news
        WHERE key=?
        """,
        (key,),
    )

    row = cursor.fetchone()

    conn.close()

    if row:
        return row[0] or ""

    return ""
