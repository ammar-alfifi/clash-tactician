from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def main_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🗺️ مخطّط الهجوم", callback_data="feature:planner"),
                InlineKeyboardButton(text="👤 ملف اللاعب", callback_data="feature:player"),
            ],
            [
                InlineKeyboardButton(text="⚔️ قيادة الحرب", callback_data="feature:warroom"),
                InlineKeyboardButton(text="🏰 ملف القبيلة", callback_data="feature:clan"),
            ],
            [
                InlineKeyboardButton(text="🎯 أهداف الهجوم", callback_data="feature:targets"),
                InlineKeyboardButton(text="👥 أعضاء القبيلة", callback_data="feature:members"),
            ],
            [InlineKeyboardButton(text="📈 لوحة الصدارة", callback_data="feature:top")],
            [
                InlineKeyboardButton(text="🆘 الدعم والمساعدة", callback_data="ticket:support"),
                InlineKeyboardButton(text="✨ اقترح ميزة", callback_data="ticket:idea"),
            ],
            [InlineKeyboardButton(text="🤖 إعداد الذكاء الاصطناعي", callback_data="page:ai")],
            [InlineKeyboardButton(text="🔐 الخصوصية والسياسة", callback_data="page:privacy")],
        ]
    )
