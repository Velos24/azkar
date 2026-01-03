# -*- coding: utf-8 -*-

import telebot
from telebot import types
import sqlite3
import os
import json
import random
import time

# ===============================================
# المتغيرات - قم بتعديلها بنفسك
# ===============================================
TOKEN = "YOUR_BOT_TOKEN"  # ضع توكن البوت الخاص بك هنا
DEV_ID = 123456789  # ضع معرف المطور الأساسي هنا
# ===============================================

# إعداد البوت
bot = telebot.TeleBot(TOKEN)

# دالة لإنشاء والاتصال بقاعدة البيانات
def setup_database():
    """
    تقوم هذه الدالة بإنشاء قاعدة بيانات SQLite والجداول اللازمة إذا لم تكن موجودة.
    """
    if os.path.exists("telegram_bot.db"):
        print("Database already exists.")
        return

    conn = sqlite3.connect('telegram_bot.db')
    cursor = conn.cursor()

    # إنشاء جدول المجموعات
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS groups (
        group_id INTEGER PRIMARY KEY,
        group_title TEXT,
        settings TEXT
    )
    ''')

    # إنشاء جدول المستخدمين
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        first_name TEXT,
        username TEXT
    )
    ''')

    # إنشاء جدول الرتب
    # rank: 0=member, 1=admin, 2=manager, 3=secondary_dev, 4=primary_dev
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS ranks (
        user_id INTEGER,
        group_id INTEGER,
        rank INTEGER DEFAULT 0,
        message_count INTEGER DEFAULT 0,
        PRIMARY KEY (user_id, group_id)
    )
    ''')

    print("Database and tables created successfully.")

    conn.commit()
    conn.close()

# رسالة عند بدء تشغيل البوت في الكونسول
print("Bot is starting...")

# استدعاء دالة إعداد قاعدة البيانات عند بدء التشغيل
setup_database()

# ===============================================
# تعريف الرتب
# ===============================================
MEMBER = 0
ADMIN = 1
MANAGER = 2
SECONDARY_DEV = 3
PRIMARY_DEV = 4

# ===============================================
# دوال مساعدة
# ===============================================

def get_user_rank(user_id, group_id):
    """
    تجلب رتبة المستخدم في مجموعة معينة.
    """
    conn = sqlite3.connect('telegram_bot.db')
    cursor = conn.cursor()

    # المطور الأساسي له أعلى رتبة في كل المجموعات
    if user_id == DEV_ID:
        return PRIMARY_DEV

    # التحقق من رتبة المستخدم في قاعدة البيانات
    cursor.execute("SELECT rank FROM ranks WHERE user_id = ? AND group_id = ?", (user_id, group_id))
    result = cursor.fetchone()

    if result:
        rank = result[0]
    else:
        # إذا لم يكن المستخدم في قاعدة البيانات، تحقق مما إذا كان مشرفًا في المجموعة
        try:
            chat_member = bot.get_chat_member(group_id, user_id)
            if chat_member.status in ['administrator', 'creator']:
                rank = ADMIN
            else:
                rank = MEMBER
        except Exception as e:
            print(f"Error checking chat member status: {e}")
            rank = MEMBER

        # إضافة المستخدم الجديد إلى قاعدة البيانات بالرتبة الافتراضية
        cursor.execute("INSERT OR IGNORE INTO ranks (user_id, group_id, rank, message_count) VALUES (?, ?, ?, 0)", (user_id, group_id, rank))
        conn.commit()

    conn.close()
    return rank

def update_user_info(message):
    """
    تحديث معلومات المستخدم في قاعدة البيانات.
    """
    user = message.from_user
    conn = sqlite3.connect('telegram_bot.db')
    cursor = conn.cursor()
    cursor.execute("INSERT OR REPLACE INTO users (user_id, first_name, username) VALUES (?, ?, ?)",
                   (user.id, user.first_name, user.username))
    conn.commit()
    conn.close()

def add_group_info(message):
    """
    إضافة معلومات المجموعة إلى قاعدة البيانات.
    """
    chat = message.chat
    conn = sqlite3.connect('telegram_bot.db')
    cursor = conn.cursor()
    # Initialize with default settings if not present
    default_settings = json.dumps({
        'lock_links': False, 'lock_photos': False, 'lock_videos': False,
        'lock_stickers': False, 'lock_bots': False
    })
    cursor.execute("INSERT OR IGNORE INTO groups (group_id, group_title, settings) VALUES (?, ?, ?)",
                   (chat.id, chat.title, default_settings))
    conn.commit()
    conn.close()

# ===============================================
# إعدادات المجموعة المتقدمة
# ===============================================

def get_group_settings(group_id):
    """
    تجلب إعدادات المجموعة من قاعدة البيانات.
    """
    conn = sqlite3.connect('telegram_bot.db')
    cursor = conn.cursor()
    cursor.execute("SELECT settings FROM groups WHERE group_id = ?", (group_id,))
    result = cursor.fetchone()
    conn.close()
    if result and result[0]:
        return json.loads(result[0])
    return {}

def set_group_settings(group_id, settings):
    """
    تحفظ إعدادات المجموعة في قاعدة البيانات.
    """
    conn = sqlite3.connect('telegram_bot.db')
    cursor = conn.cursor()
    cursor.execute("UPDATE groups SET settings = ? WHERE group_id = ?", (json.dumps(settings), group_id))
    conn.commit()
    conn.close()

LOCK_MAP = {
    "الروابط": "lock_links",
    "الصور": "lock_photos",
    "الفيديو": "lock_videos",
    "الملصقات": "lock_stickers",
    "البوتات": "lock_bots"
}

@bot.message_handler(commands=['قفل', 'فتح'])
def handle_lock_commands(message):
    if message.chat.type not in ['group', 'supergroup']:
        bot.reply_to(message, "هذا الأمر يعمل في المجموعات فقط.")
        return

    admin_id = message.from_user.id
    chat_id = message.chat.id

    admin_rank = get_user_rank(admin_id, chat_id)
    if admin_rank < MANAGER: # فقط المدير فأعلى يمكنهم القفل والفتح
        bot.reply_to(message, "ليس لديك الصلاحية لاستخدام هذا الأمر. (مدير فأعلى)")
        return

    command = message.text.split()[0].replace('/', '')
    try:
        item_to_lock = message.text.split(maxsplit=1)[1]
    except IndexError:
        bot.reply_to(message, f"الرجاء تحديد ما تريد {command}ه. (مثال: /قفل الروابط)")
        return

    if item_to_lock not in LOCK_MAP:
        bot.reply_to(message, "الخيار المحدد غير صالح. الخيارات المتاحة: " + ", ".join(LOCK_MAP.keys()))
        return

    settings = get_group_settings(chat_id)
    lock_key = LOCK_MAP[item_to_lock]

    if command == 'قفل':
        settings[lock_key] = True
        set_group_settings(chat_id, settings)
        bot.reply_to(message, f"✅ تم قفل {item_to_lock} بنجاح.")
    elif command == 'فتح':
        settings[lock_key] = False
        set_group_settings(chat_id, settings)
        bot.reply_to(message, f"✅ تم فتح {item_to_lock} بنجاح.")


# ===============================================
# لوحة التحكم وأوامر الحماية
# ===============================================

def create_control_panel(target_user_id):
    """
    تنشئ لوحة التحكم مع أزرار الإجراءات.
    """
    markup = types.InlineKeyboardMarkup(row_width=2)
    mute_btn = types.InlineKeyboardButton("كتم", callback_data=f"mute_{target_user_id}")
    unmute_btn = types.InlineKeyboardButton("الغاء الكتم", callback_data=f"unmute_{target_user_id}")
    kick_btn = types.InlineKeyboardButton("طرد", callback_data=f"kick_{target_user_id}")
    restrict_btn = types.InlineKeyboardButton("تقييد", callback_data=f"restrict_{target_user_id}")
    unrestrict_btn = types.InlineKeyboardButton("الغاء التقييد", callback_data=f"unrestrict_{target_user_id}")

    markup.add(mute_btn, unmute_btn, kick_btn, restrict_btn, unrestrict_btn)
    return markup

@bot.message_handler(func=lambda message: message.text == "تحكم")
def show_control_panel(message):
    if message.chat.type not in ['group', 'supergroup']:
        bot.reply_to(message, "هذا الأمر يعمل في المجموعات فقط.")
        return

    if not message.reply_to_message:
        bot.reply_to(message, "يجب استخدام هذا الأمر بالرد على رسالة المستخدم.")
        return

    chat_id = message.chat.id
    admin_id = message.from_user.id
    target_id = message.reply_to_message.from_user.id
    target_name = message.reply_to_message.from_user.first_name

    admin_rank = get_user_rank(admin_id, chat_id)
    target_rank = get_user_rank(target_id, chat_id)

    if admin_rank <= target_rank:
        bot.reply_to(message, "لا يمكنك التحكم في شخص لديه رتبة مساوية لك أو أعلى منك.")
        return

    if admin_rank >= ADMIN:
        markup = create_control_panel(target_id)
        bot.reply_to(message, f"لوحة التحكم للمستخدم {target_name}:", reply_markup=markup)
    else:
        bot.reply_to(message, "ليس لديك الصلاحية لاستخدام هذا الأمر.")

def check_xo_winner(board):
    # Check rows, columns, and diagonals
    lines = board + list(zip(*board)) + [[board[i][i] for i in range(3)], [board[i][2-i] for i in range(3)]]
    for line in lines:
        if line[0] == line[1] == line[2] and line[0] != " ":
            return line[0]
    # Check for draw
    if all(cell != " " for row in board for cell in row):
        return "Draw"
    return None

@bot.callback_query_handler(func=lambda call: True)
def handle_callback_query(call):
    # --- XO Game Logic ---
    if call.data.startswith('xo_'):
        parts = call.data.split('_')
        game_id, r, c = int(parts[1]), int(parts[2]), int(parts[3])

        if game_id not in xo_games:
            bot.answer_callback_query(call.id, "انتهت هذه اللعبة أو لم تعد موجودة.")
            bot.edit_message_text("لعبة XO غير صالحة.", call.message.chat.id, call.message.message_id)
            return

        game = xo_games[game_id]
        player_id = call.from_user.id
        current_player_symbol = game['turn']

        # Assign second player (O)
        if 'O' not in game['players'] and player_id != game['players'].get('X'):
            game['players']['O'] = player_id

        # Check if it's the player's turn
        if player_id != game['players'].get(current_player_symbol):
            bot.answer_callback_query(call.id, "ليس دورك للعب.")
            return

        if game['board'][r][c] == " ":
            game['board'][r][c] = current_player_symbol
            winner = check_xo_winner(game['board'])

            if winner:
                player_name = call.from_user.first_name
                end_message = f"انتهت لعبة XO!\nالفائز هو {player_name} ({winner})! 🏆" if winner != "Draw" else "انتهت لعبة XO بالتعادل!"
                bot.edit_message_text(end_message, game_id, call.message.message_id)
                del xo_games[game_id]
                return

            game['turn'] = 'O' if current_player_symbol == 'X' else 'X'
            keyboard = get_xo_keyboard(game_id)
            bot.edit_message_reply_markup(game_id, call.message.message_id, reply_markup=keyboard)
            bot.answer_callback_query(call.id)
        else:
            bot.answer_callback_query(call.id, "هذا المربع مشغول بالفعل.")
        return

    # --- Control Panel Logic ---
    admin_id = call.from_user.id
    chat_id = call.message.chat.id

    admin_rank = get_user_rank(admin_id, chat_id)
    if admin_rank < ADMIN:
        bot.answer_callback_query(call.id, "ليس لديك الصلاحية الكافية.", show_alert=True)
        return

    try:
        action, target_id_str = call.data.split('_')
        target_id = int(target_id_str)
    except (ValueError, IndexError):
        # This will catch errors if the callback data is not in the expected format (e.g., from XO)
        # We can safely ignore these or log them if needed.
        return

    target_rank = get_user_rank(target_id, chat_id)
    if admin_rank <= target_rank:
        bot.answer_callback_query(call.id, "لا يمكنك التحكم في شخص لديه رتبة مساوية لك أو أعلى منك.", show_alert=True)
        return

    # ... (rest of the control panel logic remains the same)
    try:
        if action == 'mute':
            bot.restrict_chat_member(chat_id, target_id, can_send_messages=False)
            bot.answer_callback_query(call.id, "تم كتم العضو بنجاح.")
            bot.edit_message_text("✅ تم كتم العضو.", chat_id, call.message.message_id)
        elif action == 'unmute':
            bot.restrict_chat_member(chat_id, target_id,
                                     can_send_messages=True,
                                     can_send_media_messages=True,
                                     can_send_other_messages=True,
                                     can_add_web_page_previews=True)
            bot.answer_callback_query(call.id, "تم الغاء كتم العضو بنجاح.")
            bot.edit_message_text("✅ تم الغاء كتم العضو.", chat_id, call.message.message_id)
        elif action == 'kick':
            bot.kick_chat_member(chat_id, target_id)
            bot.unban_chat_member(chat_id, target_id)
            bot.answer_callback_query(call.id, "تم طرد العضو بنجاح.")
            bot.edit_message_text("✅ تم طرد العضو.", chat_id, call.message.message_id)
        elif action == 'restrict':
            bot.restrict_chat_member(chat_id, target_id,
                                     can_send_messages=True,
                                     can_send_media_messages=False,
                                     can_send_other_messages=False,
                                     can_add_web_page_previews=False)
            bot.answer_callback_query(call.id, "تم تقييد العضو بنجاح.")
            bot.edit_message_text("✅ تم تقييد العضو (منع الوسائط والروابط).", chat_id, call.message.message_id)
        elif action == 'unrestrict':
            bot.restrict_chat_member(chat_id, target_id,
                                     can_send_messages=True,
                                     can_send_media_messages=True,
                                     can_send_other_messages=True,
                                     can_add_web_page_previews=True)
            bot.answer_callback_query(call.id, "تم الغاء تقييد العضو بنجاح.")
            bot.edit_message_text("✅ تم الغاء تقييد العضو.", chat_id, call.message.message_id)

    except Exception as e:
        print(f"Error in callback handler: {e}")
        bot.answer_callback_query(call.id, f"حدث خطأ. قد لا يمتلك البوت صلاحيات كافية.", show_alert=True)


# ===============================================
# أوامر الرتب
# ===============================================

@bot.message_handler(commands=['رفع', 'تنزيل', 'تك'])
def handle_rank_commands(message):
    if not message.reply_to_message:
        bot.reply_to(message, "يجب استخدام هذا الأمر بالرد على رسالة المستخدم.")
        return

    chat_id = message.chat.id
    promoter_id = message.from_user.id
    target_id = message.reply_to_message.from_user.id
    target_name = message.reply_to_message.from_user.first_name

    promoter_rank = get_user_rank(promoter_id, chat_id)
    target_rank = get_user_rank(target_id, chat_id)

    command = message.text.split()[0].replace('/', '')

    # أمر "تك"
    if command == 'تك':
        if promoter_rank >= ADMIN:
            if promoter_rank > target_rank:
                conn = sqlite3.connect('telegram_bot.db')
                cursor = conn.cursor()
                cursor.execute("UPDATE ranks SET rank = ? WHERE user_id = ? AND group_id = ?", (MEMBER, target_id, chat_id))
                conn.commit()
                conn.close()
                bot.reply_to(message, f"تم تنزيل {target_name} من جميع الرتب.")
            else:
                bot.reply_to(message, "لا يمكنك التحكم في شخص لديه رتبة مساوية لك أو أعلى منك.")
        else:
            bot.reply_to(message, "ليس لديك الصلاحية لاستخدام هذا الأمر.")
        return

    # أوامر الرفع والتنزيل
    if promoter_rank <= target_rank:
        bot.reply_to(message, "لا يمكنك التحكم في شخص لديه رتبة مساوية لك أو أعلى منك.")
        return

    if command == 'رفع':
        new_rank = -1
        rank_name = ""
        if 'مدير' in message.text and promoter_rank >= SECONDARY_DEV:
            new_rank = MANAGER
            rank_name = "مدير"
        elif 'ادمن' in message.text and promoter_rank >= MANAGER:
            new_rank = ADMIN
            rank_name = "ادمن"
        elif 'مطور ثانوي' in message.text and promoter_rank == PRIMARY_DEV:
            new_rank = SECONDARY_DEV
            rank_name = "مطور ثانوي"
        else:
            bot.reply_to(message, "الرتبة المحددة غير صالحة أو ليس لديك الصلاحية لرفعها.")
            return

        if new_rank < promoter_rank:
            conn = sqlite3.connect('telegram_bot.db')
            cursor = conn.cursor()
            cursor.execute("INSERT OR REPLACE INTO ranks (user_id, group_id, rank) VALUES (?, ?, ?)", (target_id, chat_id, new_rank))
            conn.commit()
            conn.close()
            bot.reply_to(message, f"تم رفع {target_name} إلى رتبة {rank_name}.")
        else:
            bot.reply_to(message, "لا يمكنك رفع شخص لرتبة أعلى من رتبتك أو مساوية لها.")


    elif command == 'تنزيل':
        if target_rank > MEMBER:
            conn = sqlite3.connect('telegram_bot.db')
            cursor = conn.cursor()
            cursor.execute("UPDATE ranks SET rank = ? WHERE user_id = ? AND group_id = ?", (MEMBER, target_id, chat_id))
            conn.commit()
            conn.close()
            bot.reply_to(message, f"تم تنزيل {target_name} من رتبته.")
        else:
            bot.reply_to(message, f"{target_name} ليس لديه رتبة ليتم تنزيلها.")


def increment_message_count(user_id, group_id):
    """
    زيادة عدد رسائل المستخدم في مجموعة معينة.
    """
    conn = sqlite3.connect('telegram_bot.db')
    cursor = conn.cursor()
    cursor.execute("UPDATE ranks SET message_count = message_count + 1 WHERE user_id = ? AND group_id = ?", (user_id, group_id))
    conn.commit()
    conn.close()

# ===============================================
# الأوامر التفاعلية والردود
# ===============================================

RANK_NAMES = {
    MEMBER: "عضو",
    ADMIN: "مشرف",
    MANAGER: "مدير",
    SECONDARY_DEV: "مطور ثانوي",
    PRIMARY_DEV: "المطور الأساسي"
}

def get_message_count(user_id, group_id):
    """
    تجلب عدد رسائل المستخدم من قاعدة البيانات.
    """
    conn = sqlite3.connect('telegram_bot.db')
    cursor = conn.cursor()
    cursor.execute("SELECT message_count FROM ranks WHERE user_id = ? AND group_id = ?", (user_id, group_id))
    result = cursor.fetchone()
    conn.close()
    return result[0] if result else 0

@bot.message_handler(commands=['ايدي', 'ا', 'كشف'])
def handle_id_command(message):
    user_to_check = message.reply_to_message.from_user if message.reply_to_message else message.from_user
    chat_id = message.chat.id

    user_rank_code = get_user_rank(user_to_check.id, chat_id)
    user_rank_name = RANK_NAMES.get(user_rank_code, "غير معروف")
    message_count = get_message_count(user_to_check.id, chat_id)

    user_info = (
        f"👤 **الاسم:** {user_to_check.first_name}\n"
        f"🔖 **المعرف:** `{user_to_check.id}`\n"
        f"✒️ **المعرف (يوزر):** @{user_to_check.username or 'لا يوجد'}\n"
        f"🎖 **الرتبة:** {user_rank_name}\n"
        f"✉️ **عدد الرسائل:** {message_count}"
    )

    bot.reply_to(message, user_info, parse_mode='Markdown')

# قاموس الردود التلقائية
AUTO_REPLIES = {
    ("هلو", "هلا", "مرحبا"): ["أهلاً بك!", "يا هلا فيك", "مرحبتين 🌷"],
    ("باي", "مع السلامة"): ["الله معك", "في أمان الله", "نشوفك على خير"],
    ("خاص"): ["تفضل خاص 💌", "تعال خاص نتفاهم 😉", "الخاص مفتوح دائمًا لك."]
}

def handle_auto_replies(message):
    # Check if message.text is not None and is a string
    if not isinstance(message.text, str):
        return False

    for keywords, replies in AUTO_REPLIES.items():
        for keyword in keywords:
            # Use lower() for case-insensitive matching
            if keyword in message.text.lower():
                bot.reply_to(message, random.choice(replies))
                return True # Replied
    return False # No keyword found

# ===============================================
# الألعاب
# ===============================================

# --- لعبة XO ---
xo_games = {}

def create_xo_board(game_id):
    board = [[" ", " ", " "], [" ", " ", " "], [" ", " ", " "]]
    xo_games[game_id] = {'board': board, 'turn': 'X', 'players': {}}
    return board

def get_xo_keyboard(game_id):
    board = xo_games[game_id]['board']
    markup = types.InlineKeyboardMarkup()
    for r_idx, row in enumerate(board):
        row_btns = [types.InlineKeyboardButton(cell, callback_data=f"xo_{game_id}_{r_idx}_{c_idx}") for c_idx, cell in enumerate(row)]
        markup.add(*row_btns)
    return markup

@bot.message_handler(commands=['xo'])
def start_xo_game(message):
    game_id = message.chat.id
    if game_id in xo_games:
        bot.reply_to(message, "هناك لعبة XO جارية بالفعل في هذه المجموعة.")
        return
    create_xo_board(game_id)
    xo_games[game_id]['players']['X'] = message.from_user.id
    keyboard = get_xo_keyboard(game_id)
    bot.send_message(message.chat.id, f"بدأت لعبة XO!\nاللاعب {message.from_user.first_name} هو X.\nننتظر لاعب O للانضمام.", reply_markup=keyboard)

# --- لعبة أسئle ---
QUESTIONS = {
    "ما هي عاصمة العراق؟": "بغداد",
    "كم عدد قارات العالم؟": "7",
    "ما هو أطول نهر في العالم؟": "النيل"
}
active_questions = {}

@bot.message_handler(commands=['سؤال'])
def ask_question(message):
    chat_id = message.chat.id
    if chat_id in active_questions:
        bot.reply_to(message, "يوجد سؤال فعال بالفعل. الرجاء الإجابة عليه أولاً.")
        return
    question, answer = random.choice(list(QUESTIONS.items()))
    active_questions[chat_id] = answer.lower()
    bot.send_message(chat_id, f"سؤال جديد:\n\n{question}")

# --- لعبة أسرع كاتب ---
fastest_writer_games = {}

@bot.message_handler(commands=['اسرع'])
def fastest_writer_game(message):
    chat_id = message.chat.id
    if chat_id in fastest_writer_games:
        bot.reply_to(message, "هناك لعبة 'أسرع كاتب' جارية بالفعل.")
        return
    word = random.choice(["تليجرام", "بوت", "حماية", "برمجة"])
    shuffled_word = " ".join(random.sample(word, len(word)))
    fastest_writer_games[chat_id] = word
    bot.send_message(chat_id, f"أسرع شخص يكتب الكلمة التالية بشكل صحيح:\n\n`{shuffled_word}`")

# --- معالجات الألعاب ---
def check_game_answers(message):
    chat_id = message.chat.id
    # التحقق من إجابات الأسئلة
    if chat_id in active_questions:
        if message.text.lower() == active_questions[chat_id]:
            bot.reply_to(message, f"إجابة صحيحة! 🎉 أحسنت يا {message.from_user.first_name}.")
            del active_questions[chat_id]
            return True
    # التحقق من إجابات أسرع كاتب
    if chat_id in fastest_writer_games:
        if message.text == fastest_writer_games[chat_id]:
            bot.reply_to(message, f"أنت الأسرع! 🏆 فاز {message.from_user.first_name}.")
            del fastest_writer_games[chat_id]
            return True
    return False

# ===============================================
# نظام مكافحة التكرار (Anti-Flood)
# ===============================================
user_message_times = {}
FLOOD_LIMIT = 5  # عدد الرسائل
FLOOD_WINDOW = 3  # خلال كم ثانية

def check_for_flood(message):
    """
    التحقق من تكرار الرسائل من قبل المستخدم.
    """
    # لا تطبق القاعدة على المشرفين
    if get_user_rank(message.from_user.id, message.chat.id) >= ADMIN:
        return False

    user_id = message.from_user.id
    current_time = time.time()

    if user_id not in user_message_times:
        user_message_times[user_id] = []

    user_message_times[user_id].append(current_time)
    user_message_times[user_id] = [t for t in user_message_times[user_id] if current_time - t < FLOOD_WINDOW]

    if len(user_message_times[user_id]) > FLOOD_LIMIT:
        try:
            bot.restrict_chat_member(message.chat.id, user_id, until_date=time.time() + 60)
            bot.send_message(message.chat.id, f"تم تقييد {message.from_user.first_name} لمدة 60 ثانية بسبب التكرار.")
            user_message_times[user_id] = []
            return True
        except Exception as e:
            print(f"Failed to restrict user for flooding: {e}")
    return False

# معالج الرسائل العام لتطبيق القواعد والردود والألعاب
@bot.message_handler(func=lambda message: True, content_types=['text', 'photo', 'video', 'sticker', 'document', 'new_chat_members', 'left_chat_member'])
def handle_all_messages(message):
    if message.from_user and message.chat:
        # 1. Anti-Flood Check
        if check_for_flood(message):
            return

        # 2. Game Answer Check
        if message.text and check_game_answers(message):
            increment_message_count(message.from_user.id, message.chat.id) # Count game answers as messages
            return

        # 3. Auto-Replies
        if handle_auto_replies(message):
            increment_message_count(message.from_user.id, message.chat.id) # Count auto-replied messages
            return

        # 4. Standard message processing
        update_user_info(message)
        if message.chat.type in ['group', 'supergroup']:
            add_group_info(message)
            increment_message_count(message.from_user.id, message.chat.id)

            user_rank = get_user_rank(message.from_user.id, message.chat.id)
            if user_rank >= ADMIN:
                return # Admins are exempt from content locks

            # 5. Content Locks
            settings = get_group_settings(message.chat.id)
            if settings.get('lock_links') and message.entities:
                for entity in message.entities:
                    if entity.type in ['url', 'text_link']:
                        bot.delete_message(message.chat.id, message.message_id)
                        return
            if settings.get('lock_photos') and message.photo:
                bot.delete_message(message.chat.id, message.message_id)
                return
            if settings.get('lock_videos') and message.video:
                bot.delete_message(message.chat.id, message.message_id)
                return
            if settings.get('lock_stickers') and message.sticker:
                bot.delete_message(message.chat.id, message.message_id)
                return
            if settings.get('lock_bots') and message.new_chat_members:
                for new_member in message.new_chat_members:
                    if new_member.is_bot:
                        bot.kick_chat_member(message.chat.id, new_member.id)
                        bot.send_message(message.chat.id, f"تم طرد البوت {new_member.first_name} لأن إضافة البوتات مقفولة.")
                        return


# بدء تشغيل البوت
if __name__ == '__main__':
    bot.polling(none_stop=True)
