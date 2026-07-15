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

    conn.commit()
    conn.close()


# ------------------ add user ------------------


def add_user(user_id, username, full_name):

    print("ADD USER:", user_id, username, full_name)

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


# ------------------ set last subscription ------------------


def set_last_subscription(user_id, subscription_url):

    conn = get_connection()
    cur = conn.cursor()

    cur.execute(
        """
        UPDATE users
        SET last_subscription = ?
        WHERE user_id = ?
        """,
        (subscription_url, user_id),
    )

    conn.commit()
    conn.close()


# ------------------ get last subscribtion ------------------


def get_last_subscription(user_id):

    conn = get_connection()
    cur = conn.cursor()

    cur.execute(
        """
        SELECT last_subscription
        FROM users
        WHERE user_id = ?
        """,
        (user_id,),
    )

    row = cur.fetchone()

    conn.close()

    if row:
        return row["last_subscription"]

    return None
