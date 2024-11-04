from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

admin_menu = InlineKeyboardMarkup(
    inline_keyboard=[
        [
            InlineKeyboardButton(text="📬Broadcast", callback_data="broadcast"),
        ],
        [InlineKeyboardButton(text="✖️Close", callback_data="close")],
    ]
)


support_menu = InlineKeyboardMarkup(
    inline_keyboard=[
        [
            InlineKeyboardButton(
                text="🆘Support",
                url="https://t.me/username",
            )
        ],
    ]
)


def cancel_menu(arg="cancel"):
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✖️Cancel" if arg == "cancel" else "✖️Close",
                    callback_data="cancel",
                )
            ]
        ]
    )


back_admin = InlineKeyboardMarkup(
    inline_keyboard=[[InlineKeyboardButton(text="🔙Back", callback_data="back_admin")]]
)


choose_menu = InlineKeyboardMarkup(
    inline_keyboard=[
        [
            InlineKeyboardButton(text="✔️Yes", callback_data="yes"),
        ],
        [InlineKeyboardButton(text="🔙Back", callback_data="back_admin")],
    ]
)
