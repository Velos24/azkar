# -*- coding: utf-8 -*-

import telebot
from telebot import types
import sqlite3
import time
import threading
import json
from collections import defaultdict

# ==============================================================================
# إعدادات البوت والثوابت
# ==============================================================================
TOKEN = "8272161809:AAEo9oMiOvBV1lUfANwZbuDvGgAoz1ju8-c"
DEV_ID = 1346665329

# مستويات الرتب
RANK_MEMBER = 0
RANK_DISTINGUISHED = 1
RANK_ADMIN = 2        # مشرفي التيليجرام
RANK_MANAGER = 3      # مدير البوت
RANK_SEC_DEV = 4      # مضيف البوت
RANK_PRI_DEV = 5      # مالك المجموعة

RANK_NAMES = {
    RANK_MEMBER: "عضو",
    RANK_DISTINGUISHED: "عضو مميز",
    RANK_ADMIN: "أدمن",
    RANK_MANAGER: "مدير",
    RANK_SEC_DEV: "مطور ثانوي",
    RANK_PRI_DEV: "مطور أساسي (المالك)"
}

# إعدادات الحماية الافتراضية
DEFAULT_SETTINGS = {
    "lock_links": False,
    "lock_photos": False,
    "lock_video": False,
    "lock_animation": False,
    "lock_stickers": False,
    "lock_bots": False,
    "lock_forward": False,
    "lock_username": False,
    "lock_long_msg": False,
    "lock_flood": True,
    "lock_spam": True,
    "flood_limit": 5,      # عدد الرسائل
    "flood_time": 3,       # خلال ثواني
    "max_msg_len": 3000,   # طول الرسالة
    "max_warnings": 3      # الحد الأقصى للإنذارات قبل العقوبة
}

# ==============================================================================
# إدارة قاعدة البيانات (SQLite) مع الكاش
# ==============================================================================
class DatabaseManager:
    def __init__(self, db_name="bot_database.db"):
        self.db_name = db_name
        self.lock = threading.Lock()
        self.conn = sqlite3.connect(self.db_name, check_same_thread=False)
        self.cursor = self.conn.cursor()
        self.setup_tables()

        # الكاش الداخلي
        self.cache_settings = {}
        self.cache_ranks = {}
        self.cache_replies = {}
        self.cache_users = {}
        self.cache_warnings = {}

    def setup_tables(self):
        with self.lock:
            self.cursor.execute('''CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                first_name TEXT,
                username TEXT
            )''')

            self.cursor.execute('''CREATE TABLE IF NOT EXISTS groups (
                group_id INTEGER PRIMARY KEY,
                title TEXT,
                added_by INTEGER
            )''')

            self.cursor.execute('''CREATE TABLE IF NOT EXISTS group_ranks (
                group_id INTEGER,
                user_id INTEGER,
                rank_level INTEGER,
                PRIMARY KEY (group_id, user_id)
            )''')

            self.cursor.execute('''CREATE TABLE IF NOT EXISTS group_settings (
                group_id INTEGER PRIMARY KEY,
                settings_json TEXT
            )''')

            self.cursor.execute('''CREATE TABLE IF NOT EXISTS custom_replies (
                group_id INTEGER,
                keyword TEXT,
                reply_text TEXT,
                PRIMARY KEY (group_id, keyword)
            )''')

            self.cursor.execute('''CREATE TABLE IF NOT EXISTS warnings (
                group_id INTEGER,
                user_id INTEGER,
                count INTEGER DEFAULT 0,
                PRIMARY KEY (group_id, user_id)
            )''')

            self.conn.commit()

    def get_settings(self, group_id):
        if group_id in self.cache_settings:
            return self.cache_settings[group_id]

        with self.lock:
            self.cursor.execute("SELECT settings_json FROM group_settings WHERE group_id=?", (group_id,))
            res = self.cursor.fetchone()
            if res:
                settings = json.loads(res[0])
                full_settings = DEFAULT_SETTINGS.copy()
                full_settings.update(settings)
                self.cache_settings[group_id] = full_settings
                return full_settings
            else:
                self.cache_settings[group_id] = DEFAULT_SETTINGS.copy()
                return self.cache_settings[group_id]

    def update_setting(self, group_id, key, value):
        settings = self.get_settings(group_id)
        settings[key] = value
        self.cache_settings[group_id] = settings

        with self.lock:
            self.cursor.execute("INSERT OR REPLACE INTO group_settings (group_id, settings_json) VALUES (?, ?)",
                                (group_id, json.dumps(settings)))
            self.conn.commit()

    def get_custom_rank(self, group_id, user_id):
        cache_key = f"{group_id}:{user_id}"
        if cache_key in self.cache_ranks:
            return self.cache_ranks[cache_key]

        with self.lock:
            self.cursor.execute("SELECT rank_level FROM group_ranks WHERE group_id=? AND user_id=?", (group_id, user_id))
            res = self.cursor.fetchone()
            rank = res[0] if res else 0
            self.cache_ranks[cache_key] = rank
            return rank

    def set_custom_rank(self, group_id, user_id, rank_level):
        with self.lock:
            if rank_level == RANK_MEMBER:
                self.cursor.execute("DELETE FROM group_ranks WHERE group_id=? AND user_id=?", (group_id, user_id))
            else:
                self.cursor.execute("INSERT OR REPLACE INTO group_ranks (group_id, user_id, rank_level) VALUES (?, ?, ?)",
                                    (group_id, user_id, rank_level))
            self.conn.commit()

        cache_key = f"{group_id}:{user_id}"
        self.cache_ranks[cache_key] = rank_level

    def get_replies(self, group_id):
        if group_id in self.cache_replies:
            return self.cache_replies[group_id]

        with self.lock:
            self.cursor.execute("SELECT keyword, reply_text FROM custom_replies WHERE group_id=?", (group_id,))
            rows = self.cursor.fetchall()
            replies = {row[0]: row[1] for row in rows}
            self.cache_replies[group_id] = replies
            return replies

    def add_reply(self, group_id, keyword, reply):
        with self.lock:
            self.cursor.execute("INSERT OR REPLACE INTO custom_replies (group_id, keyword, reply_text) VALUES (?, ?, ?)",
                                (group_id, keyword, reply))
            self.conn.commit()
        if group_id in self.cache_replies:
            self.cache_replies[group_id][keyword] = reply
        else:
            self.get_replies(group_id)

    def delete_reply(self, group_id, keyword):
        with self.lock:
            self.cursor.execute("DELETE FROM custom_replies WHERE group_id=? AND keyword=?", (group_id, keyword))
            self.conn.commit()
        if group_id in self.cache_replies and keyword in self.cache_replies[group_id]:
            del self.cache_replies[group_id][keyword]

    def register_user(self, user):
        if user.id in self.cache_users: return
        with self.lock:
            self.cursor.execute("INSERT OR REPLACE INTO users (user_id, first_name, username) VALUES (?, ?, ?)",
                                (user.id, user.first_name, user.username))
            self.conn.commit()
        self.cache_users[user.id] = True

    def register_group(self, chat, added_by_id):
        with self.lock:
            self.cursor.execute("INSERT OR IGNORE INTO groups (group_id, title, added_by) VALUES (?, ?, ?)",
                                (chat.id, chat.title, added_by_id))
            self.conn.commit()

    def get_group_adder(self, group_id):
        with self.lock:
            self.cursor.execute("SELECT added_by FROM groups WHERE group_id=?", (group_id,))
            res = self.cursor.fetchone()
            return res[0] if res else None

    # --- إدارة الإنذارات ---
    def get_warnings(self, group_id, user_id):
        key = f"{group_id}:{user_id}"
        if key in self.cache_warnings:
            return self.cache_warnings[key]
        with self.lock:
            self.cursor.execute("SELECT count FROM warnings WHERE group_id=? AND user_id=?", (group_id, user_id))
            res = self.cursor.fetchone()
            count = res[0] if res else 0
            self.cache_warnings[key] = count
            return count

    def add_warning(self, group_id, user_id):
        count = self.get_warnings(group_id, user_id) + 1
        with self.lock:
            self.cursor.execute("INSERT OR REPLACE INTO warnings (group_id, user_id, count) VALUES (?, ?, ?)",
                                (group_id, user_id, count))
            self.conn.commit()
        self.cache_warnings[f"{group_id}:{user_id}"] = count
        return count

    def reset_warnings(self, group_id, user_id):
        with self.lock:
            self.cursor.execute("DELETE FROM warnings WHERE group_id=? AND user_id=?", (group_id, user_id))
            self.conn.commit()
        self.cache_warnings[f"{group_id}:{user_id}"] = 0


# تهيئة البوت وقاعدة البيانات
bot = telebot.TeleBot(TOKEN, parse_mode='HTML', threaded=True)
db = DatabaseManager()

# ==============================================================================
# إدارة الرتب
# ==============================================================================
admins_cache = {}

def get_chat_admins_cached(chat_id):
    now = time.time()
    if chat_id in admins_cache and (now - admins_cache[chat_id]['timestamp'] < 600):
        return admins_cache[chat_id]
    try:
        admins = bot.get_chat_administrators(chat_id)
        owner_id = next((a.user.id for a in admins if a.status == 'creator'), None)
        admin_ids = [a.user.id for a in admins]
        data = {'owner': owner_id, 'admins': admin_ids, 'timestamp': now}
        admins_cache[chat_id] = data
        return data
    except Exception as e:
        print(f"Error fetching admins for {chat_id}: {e}")
        return {'owner': None, 'admins': [], 'timestamp': 0}

def get_user_rank(user_id, chat_id):
    group_data = get_chat_admins_cached(chat_id)
    if user_id == group_data['owner']:
        return RANK_PRI_DEV
    added_by = db.get_group_adder(chat_id)
    if added_by and user_id == added_by:
        return RANK_SEC_DEV
    custom_rank = db.get_custom_rank(chat_id, user_id)
    if custom_rank == RANK_MANAGER:
        return RANK_MANAGER
    if user_id in group_data['admins']:
        return RANK_ADMIN
    if custom_rank == RANK_DISTINGUISHED:
        return RANK_DISTINGUISHED
    return RANK_MEMBER

def get_rank_name(rank):
    return RANK_NAMES.get(rank, "عضو")

# ==============================================================================
# نظام مكافحة التكرار التدريجي
# ==============================================================================
flood_cache = defaultdict(list)
flood_penalties = {} # {user_id_group_id: level} (1=warned, 2=muted)
last_cleanup = time.time()

def check_flood(user_id, chat_id, settings):
    # تنظيف دوري للذاكرة (كل ساعة)
    global last_cleanup
    if time.time() - last_cleanup > 3600:
        flood_cache.clear()
        flood_penalties.clear()
        last_cleanup = time.time()

    if not settings['lock_flood']: return None

    key = f"{user_id}_{chat_id}"
    now = time.time()
    flood_cache[key] = [t for t in flood_cache[key] if now - t < settings['flood_time']]
    flood_cache[key].append(now)

    if len(flood_cache[key]) > settings['flood_limit']:
        flood_cache[key] = []
        current_level = flood_penalties.get(key, 0)

        if current_level == 0:
            flood_penalties[key] = 1
            return "warn"
        elif current_level == 1:
            flood_penalties[key] = 2
            return "mute"
        else:
            del flood_penalties[key]
            return "kick"

    return None

# ==============================================================================
# لوحة التحكم
# ==============================================================================
def create_control_panel(chat_id, target_id, target_name):
    markup = types.InlineKeyboardMarkup(row_width=2)
    try:
        member = bot.get_chat_member(chat_id, target_id)
        is_muted = not member.can_send_messages if member.status == 'restricted' else False
        is_restricted = False
        if member.status == 'restricted' and member.can_send_messages and not member.can_send_media_messages:
            is_restricted = True
    except:
        is_muted = False
        is_restricted = False

    btns = []

    if is_muted:
        btns.append(types.InlineKeyboardButton("🔊 الغاء كتم", callback_data=f"unmute_{target_id}"))
    else:
        btns.append(types.InlineKeyboardButton("🔇 كتم", callback_data=f"mute_{target_id}"))

    if is_restricted:
        btns.append(types.InlineKeyboardButton("🔓 فك تقييد", callback_data=f"unrestrict_{target_id}"))
    else:
        btns.append(types.InlineKeyboardButton("🚫 تقييد ميديا", callback_data=f"restrict_{target_id}"))

    btns.append(types.InlineKeyboardButton("👢 طرد", callback_data=f"kick_{target_id}"))
    btns.append(types.InlineKeyboardButton("🛑 حظر", callback_data=f"ban_{target_id}"))

    warns = db.get_warnings(chat_id, target_id)
    btns.append(types.InlineKeyboardButton(f"⚠️ إنذار ({warns})", callback_data=f"warn_{target_id}"))
    btns.append(types.InlineKeyboardButton("🔄 تصفير إنذارات", callback_data=f"resetwarn_{target_id}"))

    markup.add(*btns)
    markup.add(types.InlineKeyboardButton("❌ إغلاق", callback_data="close_panel"))

    return markup

# ==============================================================================
# معالجات الأوامر
# ==============================================================================

@bot.message_handler(commands=['start'])
def start_command(message):
    db.register_user(message.from_user)
    if message.chat.type == 'private':
        bot.reply_to(message, "👋 أهلاً بك! أضفني إلى مجموعتك وارفعني مشرفاً.")

@bot.message_handler(commands=['help', 'الاوامر'])
def help_command(message):
    help_text = """
🛡 **أوامر الحماية والإدارة:**

👮‍♂️ **للإداريين:**
- `قفل/فتح [الروابط|الصور|الفيديو|الخ]`
- `تحكم` (بالرد)
- `كشف` (بالرد)
- `رفع/تنزيل مميز`
- `رفع/تنزيل مدير`
- `اضف/حذف رد`
- `الردود` (لعرض الردود)

🎮 **أخرى:**
- `ايدي`
    """
    bot.reply_to(message, help_text, parse_mode='Markdown')

@bot.my_chat_member_handler()
def on_bot_added(message: types.ChatMemberUpdated):
    new_status = message.new_chat_member.status
    if new_status in ['member', 'administrator']:
        db.register_group(message.chat, message.from_user.id)
        if message.chat.id in admins_cache:
            del admins_cache[message.chat.id]

LOCK_TYPES = {
    "الروابط": "lock_links", "الصور": "lock_photos", "الفيديو": "lock_video",
    "المتحركات": "lock_animation", "الملصقات": "lock_stickers", "البوتات": "lock_bots",
    "التوجيه": "lock_forward", "المعرفات": "lock_username", "اليوزر": "lock_username",
    "الرسائل الطويلة": "lock_long_msg", "التكرار": "lock_flood", "السبام": "lock_spam"
}

@bot.message_handler(func=lambda m: m.text and (m.text.startswith("قفل ") or m.text.startswith("فتح ")) and m.chat.type in ['group', 'supergroup'])
def handle_locks(message):
    if get_user_rank(message.from_user.id, message.chat.id) < RANK_ADMIN:
        bot.reply_to(message, "⚠️ للمشرفين فقط.")
        return

    command, target = message.text.split(maxsplit=1)
    target = target.strip()

    if target == "الكل":
        val = True if command == "قفل" else False
        for k in LOCK_TYPES.values():
            db.update_setting(message.chat.id, k, val)
        bot.reply_to(message, f"✅ تم {command} الكل.")
        return

    if target in LOCK_TYPES:
        setting_key = LOCK_TYPES[target]
        new_val = True if command == "قفل" else False
        db.update_setting(message.chat.id, setting_key, new_val)
        bot.reply_to(message, f"✅ تم {command} {target}.")
    else:
        bot.reply_to(message, f"❌ غير معروف. المتاح: {', '.join(LOCK_TYPES.keys())}")

@bot.message_handler(func=lambda m: m.text and m.text.startswith(("رفع", "تنزيل")) and m.chat.type in ['group', 'supergroup'])
def handle_promotions(message):
    if not message.reply_to_message:
        bot.reply_to(message, "⚠️ رد على العضو.")
        return

    args = message.text.split()
    action = args[0]
    role_req = args[1] if len(args) > 1 else ""

    chat_id = message.chat.id
    target_id = message.reply_to_message.from_user.id
    actor_id = message.from_user.id
    actor_rank = get_user_rank(actor_id, chat_id)
    target_rank = get_user_rank(target_id, chat_id)

    if actor_rank <= target_rank and actor_rank != RANK_PRI_DEV:
        bot.reply_to(message, "⛔️ رتبتك لا تسمح.")
        return

    target_role = RANK_MEMBER
    required_rank = RANK_ADMIN
    if "مدير" in role_req:
        target_role = RANK_MANAGER
        required_rank = RANK_SEC_DEV
    elif "مميز" in role_req:
        target_role = RANK_DISTINGUISHED
        required_rank = RANK_ADMIN
    else:
        target_role = RANK_DISTINGUISHED

    if actor_rank < required_rank:
        bot.reply_to(message, "⚠️ رتبتك لا تسمح.")
        return

    if action == "رفع":
        db.set_custom_rank(chat_id, target_id, target_role)
        bot.reply_to(message, f"✅ تم الرفع.")
    elif action == "تنزيل":
        db.set_custom_rank(chat_id, target_id, RANK_MEMBER)
        bot.reply_to(message, "✅ تم التنزيل.")

@bot.message_handler(func=lambda m: m.text == "تحكم" and m.chat.type in ['group', 'supergroup'])
def control_panel_cmd(message):
    if not message.reply_to_message: return

    actor_rank = get_user_rank(message.from_user.id, message.chat.id)
    target_rank = get_user_rank(message.reply_to_message.from_user.id, message.chat.id)

    if actor_rank < RANK_ADMIN: return
    if actor_rank <= target_rank:
        bot.reply_to(message, "⛔️ لا تملك صلاحية.")
        return

    markup = create_control_panel(message.chat.id, message.reply_to_message.from_user.id, message.reply_to_message.from_user.first_name)
    bot.reply_to(message, f"🔧 تحكم: {message.reply_to_message.from_user.first_name}", reply_markup=markup)

@bot.message_handler(func=lambda m: m.text == "كشف" and m.chat.type in ['group', 'supergroup'])
def reveal_cmd(message):
    if not message.reply_to_message: return
    target = message.reply_to_message.from_user
    rank = get_user_rank(target.id, message.chat.id)
    bot.reply_to(message, f"👤 {target.first_name}\n🏅 {get_rank_name(rank)}", parse_mode='Markdown')

@bot.message_handler(func=lambda m: m.text and m.text.startswith("اضف رد") and m.chat.type in ['group', 'supergroup'])
def add_reply_cmd(message):
    if get_user_rank(message.from_user.id, message.chat.id) < RANK_ADMIN: return
    try:
        parts = message.text.split(maxsplit=2)
        db.add_reply(message.chat.id, parts[1], parts[2])
        bot.reply_to(message, "✅ تم الإضافة.")
    except: pass

@bot.message_handler(func=lambda m: m.text and m.text.startswith("حذف رد") and m.chat.type in ['group', 'supergroup'])
def del_reply_cmd(message):
    if get_user_rank(message.from_user.id, message.chat.id) < RANK_ADMIN: return
    try:
        db.delete_reply(message.chat.id, message.text.split(maxsplit=1)[1])
        bot.reply_to(message, "✅ تم الحذف.")
    except: pass

@bot.message_handler(func=lambda m: m.text == "الردود" and m.chat.type in ['group', 'supergroup'])
def list_replies_cmd(message):
    if get_user_rank(message.from_user.id, message.chat.id) < RANK_ADMIN: return
    replies = db.get_replies(message.chat.id)
    if not replies:
        bot.reply_to(message, "لا توجد ردود مخصصة.")
        return
    text = "📝 **الردود المخصصة:**\n"
    for k, v in replies.items():
        text += f"- `{k}` : {v}\n"
    bot.reply_to(message, text, parse_mode='Markdown')

# ==============================================================================
# Callback Query
# ==============================================================================
@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    if call.data == "close_panel":
        bot.delete_message(call.message.chat.id, call.message.message_id)
        return
    try:
        action, target_id = call.data.split('_')
        target_id = int(target_id)
    except: return

    chat_id = call.message.chat.id
    actor_rank = get_user_rank(call.from_user.id, chat_id)
    target_rank = get_user_rank(target_id, chat_id)

    if actor_rank <= target_rank:
        bot.answer_callback_query(call.id, "⛔️ ليس لديك صلاحية.", show_alert=True)
        return

    try:
        msg = ""
        if action == "mute":
            bot.restrict_chat_member(chat_id, target_id, can_send_messages=False)
            msg = "تم الكتم"
        elif action == "unmute":
            bot.restrict_chat_member(chat_id, target_id, can_send_messages=True, can_send_media_messages=True, can_send_other_messages=True)
            msg = "تم الغاء الكتم"
        elif action == "kick":
            bot.ban_chat_member(chat_id, target_id)
            bot.unban_chat_member(chat_id, target_id)
            msg = "تم الطرد"
        elif action == "ban":
            bot.ban_chat_member(chat_id, target_id)
            msg = "تم الحظر"
        elif action == "restrict":
            bot.restrict_chat_member(chat_id, target_id, can_send_messages=True, can_send_media_messages=False)
            msg = "تم التقييد"
        elif action == "unrestrict":
            bot.restrict_chat_member(chat_id, target_id, can_send_messages=True, can_send_media_messages=True, can_send_other_messages=True)
            msg = "تم الغاء التقييد"
        elif action == "warn":
            count = db.add_warning(chat_id, target_id)
            msg = f"تم التحذير ({count})"
            if count >= 3:
                bot.restrict_chat_member(chat_id, target_id, until_date=time.time()+3600)
                db.reset_warnings(chat_id, target_id)
                bot.send_message(chat_id, f"🛑 تجاوز {target_id} حد الإنذارات وتم كتمه لساعة.")
        elif action == "resetwarn":
            db.reset_warnings(chat_id, target_id)
            msg = "تم تصفير الإنذارات"

        bot.answer_callback_query(call.id, msg)
        new_markup = create_control_panel(chat_id, target_id, "")
        bot.edit_message_reply_markup(chat_id, call.message.message_id, reply_markup=new_markup)
    except Exception as e:
        bot.answer_callback_query(call.id, f"خطأ: {e}", show_alert=True)

# ==============================================================================
# فلترة الرسائل
# ==============================================================================
DEFAULT_REPLIES = {
    "هلو": "أهلاً وسهلاً 🌸", "هلا": "هلا بيك 👋", "مرحبا": "نورت ✨",
    "باي": "في أمان الله 🤍", "خاص": "الخاص مفتوح 📩"
}

@bot.message_handler(func=lambda m: True, content_types=['text', 'photo', 'video', 'sticker', 'animation', 'document', 'new_chat_members'])
def global_message_handler(message):
    if message.chat.type == 'private': return
    chat_id = message.chat.id
    user_id = message.from_user.id
    db.register_user(message.from_user)

    rank = get_user_rank(user_id, chat_id)
    is_immune = rank >= RANK_ADMIN
    is_distinguished = rank >= RANK_DISTINGUISHED

    if not is_immune:
        settings = db.get_settings(chat_id)

        # Anti-Flood تدريجي
        if not is_distinguished:
            flood_action = check_flood(user_id, chat_id, settings)
            if flood_action:
                bot.delete_message(chat_id, message.message_id)
                if flood_action == "warn":
                    bot.send_message(chat_id, f"⚠️ {message.from_user.first_name}، توقف عن التكرار! (تحذير)")
                elif flood_action == "mute":
                    try:
                        bot.restrict_chat_member(chat_id, user_id, until_date=time.time()+300)
                        bot.send_message(chat_id, f"🤐 تم كتم {message.from_user.first_name} 5 دقائق للتكرار.")
                    except: pass
                elif flood_action == "kick":
                    try:
                        bot.ban_chat_member(chat_id, user_id)
                        bot.unban_chat_member(chat_id, user_id)
                        bot.send_message(chat_id, f"👢 تم طرد {message.from_user.first_name} للتكرار المستمر.")
                    except: pass
                return

        should_delete = False

        # فحص طول الرسالة (يستثنى منه المميز)
        if settings['lock_long_msg'] and message.text and len(message.text) > settings['max_msg_len']:
            if not is_distinguished:
                should_delete = True

        # فحص السبام (تكرار نفس الرسالة - بسيط)
        # هنا نحتاج كاش لآخر رسالة، لكن للتبسيط سنعتمد على التكرار الزمني (Anti-Flood)
        # أو يمكننا إضافة فحص سريع هنا إذا كان المحتوى مطابق تماما للسابق (يتطلب كاش إضافي)
        # سنكتفي بالAnti-Flood القوي الذي يغطي السبام الزمني.

        if settings['lock_links'] and message.entities:
            for ent in message.entities:
                if ent.type in ['url', 'text_link']: should_delete = True

        if settings['lock_photos'] and message.photo: should_delete = True
        if settings['lock_video'] and message.video: should_delete = True
        if settings['lock_animation'] and message.animation: should_delete = True
        if settings['lock_stickers'] and message.sticker: should_delete = True
        if settings['lock_forward'] and (message.forward_from or message.forward_from_chat): should_delete = True
        if settings['lock_username'] and message.text and "@" in message.text: should_delete = True

        if settings['lock_bots'] and message.new_chat_members:
            for m in message.new_chat_members:
                if m.is_bot:
                    try: bot.kick_chat_member(chat_id, m.id)
                    except: pass

        if should_delete:
            try: bot.delete_message(chat_id, message.message_id)
            except: pass
            return

    if message.text:
        custom_replies = db.get_replies(chat_id)
        for key, reply in custom_replies.items():
            if key in message.text:
                bot.reply_to(message, reply)
                return
        for key, reply in DEFAULT_REPLIES.items():
            if key in message.text:
                bot.reply_to(message, reply)
                return

if __name__ == "__main__":
    bot.infinity_polling(timeout=10, long_polling_timeout=5)
