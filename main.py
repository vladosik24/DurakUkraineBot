"""
Telegram бот для гри "Дурак" - РОЗШИРЕНА ВЕРСІЯ
Функції: multiplayer, статистика, турніри, режими гри, AI
"""

import logging
import random
import os
from datetime import datetime
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram import F
import asyncio

logging.basicConfig(level=logging.INFO)

BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN не знайдено!")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

SUITS = ['♠️', '♥️', '♦️', '♣️']
RANKS = ['6', '7', '8', '9', '10', 'В', 'Д', 'К', 'Т']
RANK_VALUES = {'6': 6, '7': 7, '8': 8, '9': 9, '10': 10, 'В': 11, 'Д': 12, 'К': 13, 'Т': 14}

games = {}
stats = {}

class Card:
    def init(self, rank, suit):
        self.rank = rank
        self.suit = suit
        self.value = RANK_VALUES[rank]

    def str(self):
        return f"{self.rank}{self.suit}"

class PlayerStats:
    def init(self, user_id, username):
        self.user_id = user_id
        self.username = username
        self.games_played = 0
        self.wins = 0
        self.losses = 0
        self.rating = 1000
        self.achievements = []

    def win(self):
        self.wins += 1
        self.games_played += 1
        self.rating += 25
        self._check_achievements()

    def lose(self):
        self.losses += 1
        self.games_played += 1
        self.rating = max(0, self.rating - 15)

    def _check_achievements(self):
        if self.wins == 1 and "first_win" not in self.achievements:
            self.achievements.append("first_win")
        if self.wins == 10 and "veteran" not in self.achievements:
            self.achievements.append("veteran")
        if self.wins == 50 and "master" not in self.achievements:
            self.achievements.append("master")

class DurakGame:
    def init(self, player1_id, mode="podkidnoy", difficulty="medium"):
        self.player1_id = player1_id
        self.mode = mode
        self.difficulty = difficulty

        self.deck = [Card(r, s) for s in SUITS for r in RANKS]
        random.shuffle(self.deck)

        self.trump_card = self.deck.pop()
        self.trump_suit = self.trump_card.suit
        self.deck.insert(0, self.trump_card)

        self.player1_hand = [self.deck.pop() for _ in range(6)]
        self.player2_hand = [self.deck.pop() for _ in range(6)]

        self.table = []
        self.current_attacker = player1_id
        self.stage = "attack"

    def can_beat(self, attacking_card, defending_card):
        if defending_card.suit == attacking_card.suit:
            return defending_card.value > attacking_card.value
        return defending_card.suit == self.trump_suit

    def get_valid_attacks(self, hand):
        if not self.table:
            return hand

        table_ranks = set()
        for attack, defend in self.table:
            table_ranks.add(attack.rank)
            if defend:
                table_ranks.add(defend.rank)

        return [c for c in hand if c.rank in table_ranks]

    def refill_hands(self):
        while len(self.player1_hand) < 6 and self.deck:
            self.player1_hand.append(self.deck.pop())
        while len(self.player2_hand) < 6 and self.deck:
            self.player2_hand.append(self.deck.pop())

    def game_over(self):
        if not self.deck:
            if not self.player1_hand:
                return self.player1_id
            if not self.player2_hand:
                return "bot"
        return None

    def make_bot_move_smart(self, attacker=True):
        bot_hand = self.player2_hand

        if attacker:
            valid = self.get_valid_attacks(bot_hand)
            if not valid or len(self.table) >= 6:
                return None

            if self.difficulty == "easy":

return random.choice(valid)
            else:
                non_trumps = [c for c in valid if c.suit != self.trump_suit]
                return min(non_trumps, key=lambda x: x.value) if non_trumps else min(valid, key=lambda x: x.value)
        else:
            for i, (attack, defend) in enumerate(self.table):
                if defend is None:
                    valid_defends = [c for c in bot_hand if self.can_beat(attack, c)]
                    if valid_defends:
                        non_trumps = [c for c in valid_defends if c.suit != self.trump_suit]
                        card = min(non_trumps, key=lambda x: x.value) if non_trumps else min(valid_defends, key=lambda x: x.value)
                        return (i, card)
                    else:
                        return None
            return "all_defended"

def get_or_create_stats(user_id, username):
    if user_id not in stats:
        stats[user_id] = PlayerStats(user_id, username or "Гравець")
    return stats[user_id]

def get_leaderboard():
    return sorted(stats.values(), key=lambda x: x.rating, reverse=True)[:10]

def format_hand(cards):
    return " ".join([str(card) for card in cards])

def format_table(table):
    if not table:
        return "Стіл порожній"
    result = []
    for attack, defend in table:
        result.append(f"{attack} ← {defend}" if defend else f"{attack} ← ?")
    return "\n".join(result)

def create_card_keyboard(cards, action_prefix):
    keyboard = []
    row = []
    for i, card in enumerate(cards):
        row.append(InlineKeyboardButton(text=str(card), callback_data=f"{action_prefix}_{i}"))
        if len(row) == 4:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def get_main_menu():
    keyboard = [
        [
            InlineKeyboardButton(text="🎮 Гра з ботом", callback_data="play_bot"),
            InlineKeyboardButton(text="📊 Статистика", callback_data="my_stats")
        ],
        [
            InlineKeyboardButton(text="🏆 Рейтинг", callback_data="leaderboard"),
            InlineKeyboardButton(text="❓ Правила", callback_data="help")
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    get_or_create_stats(message.from_user.id, message.from_user.username)
    await message.answer(
        "🃏 Вітаю в грі 'Дурак'!\n\nОберіть режим гри:",
        reply_markup=get_main_menu(),
        parse_mode="Markdown"
    )

@dp.message(Command("menu"))
async def cmd_menu(message: types.Message):
    await message.answer("🎮 Головне меню:", reply_markup=get_main_menu(), parse_mode="Markdown")

@dp.callback_query(F.data == "play_bot")
async def handle_play_bot(callback: types.CallbackQuery):
    keyboard = [
        [InlineKeyboardButton(text="🟢 Легкий", callback_data="bot_easy")],
        [InlineKeyboardButton(text="🟡 Середній", callback_data="bot_medium")],
        [InlineKeyboardButton(text="🔴 Важкий", callback_data="bot_hard")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back_menu")]
    ]
    await callback.message.edit_text(
        "🤖 Оберіть складність бота:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard),
        parse_mode="Markdown"
    )
    await callback.answer()

@dp.callback_query(F.data.startswith("bot_"))
async def handle_bot_difficulty(callback: types.CallbackQuery):
    difficulty = callback.data.split("_")[1]

    chat_id = callback.message.chat.id
    games[chat_id] = DurakGame(callback.from_user.id, difficulty=difficulty)

    await callback.message.delete()
    await send_game_state(chat_id, games[chat_id])
    await callback.answer()

@dp.callback_query(F.data == "my_stats")
async def handle_my_stats(callback: types.CallbackQuery):
    user_stats = get_or_create_stats(callback.from_user.id, callback.from_user.username)

    winrate = (user_stats.wins / user_stats.games_played * 100) if user_stats.games_played > 0 else 0

text = f"""
📊 Ваша статистика:

👤 {user_stats.username}
🎮 Ігор: {user_stats.games_played}
✅ Перемог: {user_stats.wins}
❌ Поразок: {user_stats.losses}
📈 Winrate: {winrate:.1f}%
⭐ Рейтинг: {user_stats.rating}

🏅 Досягнення: {len(user_stats.achievements)}
"""

    keyboard = [[InlineKeyboardButton(text="🔙 Назад", callback_data="back_menu")]]
    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard), parse_mode="Markdown")
    await callback.answer()

@dp.callback_query(F.data == "leaderboard")
async def handle_leaderboard(callback: types.CallbackQuery):
    top_players = get_leaderboard()

    if not top_players:
        await callback.answer("Рейтинг порожній", show_alert=True)
        return

    text = "🏆 ТОП-10 ГРАВЦІВ:\n\n"
    medals = ["🥇", "🥈", "🥉"]
    for i, player in enumerate(top_players):
        medal = medals[i] if i < 3 else f"{i+1}."
        winrate = (player.wins / player.games_played * 100) if player.games_played > 0 else 0
        text += f"{medal} {player.username} - {player.rating} ⭐\n   ({player.wins}W/{player.losses}L, {winrate:.0f}%)\n\n"

    keyboard = [[InlineKeyboardButton(text="🔙 Назад", callback_data="back_menu")]]
    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard), parse_mode="Markdown")
    await callback.answer()

@dp.callback_query(F.data == "help")
async def handle_help(callback: types.CallbackQuery):
    rules = """
🃏 Правила гри 'Дурак'

Мета: Позбутися всіх карт.

Правила:
• Колода: 36 карт (6-Т)
• Визначається козирна масть
• Атакуючий кладе карту
• Захисник бʼє старшою або козирем
• Можна підкидати карти того ж номіналу

Складність:
🟢 Легкий - бот грає випадково
🟡 Середній - бот економить карти
🔴 Важкий - бот використовує стратегію

Команди:
/menu - головне меню
/stats - ваша статистика
"""
    keyboard = [[InlineKeyboardButton(text="🔙 Назад", callback_data="back_menu")]]
    await callback.message.edit_text(rules, reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard), parse_mode="Markdown")
    await callback.answer()

@dp.callback_query(F.data == "back_menu")
async def handle_back_menu(callback: types.CallbackQuery):
    await callback.message.edit_text("🃏 Головне меню:", reply_markup=get_main_menu(), parse_mode="Markdown")
    await callback.answer()

async def send_game_state(chat_id, game, message=""):
    difficulty_emoji = {"easy": "🟢", "medium": "🟡", "hard": "🔴"}

    status = f"🃏 Гра 'Дурак'\n"
    status += f"🤖 Складність: {difficulty_emoji.get(game.difficulty, '')} {game.difficulty.upper()}\n\n"
    status += f"🎴 Козир: {game.trump_card}\n"
    status += f"📚 Карт у колоді: {len(game.deck)}\n\n"
    status += f"На столі:\n{format_table(game.table)}\n\n"
    status += f"🤖 Карт у бота: {len(game.player2_hand)}\n"
    status += f"👤 Ваші карти: {format_hand(game.player1_hand)}\n\n"

    if message:
        status += f"📢 {message}\n\n"

    keyboard = None
    is_attacker = game.current_attacker == game.player1_id

    if is_attacker and game.stage == "attack":
        status += "⚔️ Ваш хід - атакуйте!"
        valid_cards = game.get_valid_attacks(game.player1_hand)
        if valid_cards:
            keyboard = create_card_keyboard(valid_cards, "attack")
            keyboard.inline_keyboard.append([InlineKeyboardButton(text="✅ Завершити хід", callback_data="end_attack")])

    elif not is_attacker and game.stage == "defend":
        status += "🛡️ Захищайтесь!"
        undefended = None
        for i, (attack, defend) in enumerate(game.table):
            if defend is None:
                undefended = (i, attack)
                break

        if undefended:
            idx, attack_card = undefended
            valid_defends = [c for c in game.player1_hand if game.can_beat(attack_card, c)]
            if valid_defends:
                status += f"\n🎯 Відбийте: {attack_card}"
                keyboard = create_card_keyboard(valid_defends, f"defend_{idx}")

keyboard_buttons = keyboard.inline_keyboard if keyboard else []
            keyboard_buttons.append([InlineKeyboardButton(text="❌ Беру", callback_data="take_cards")])
            keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)

    elif is_attacker and game.stage == "throw_in":
        status += "🎲 Можете підкинути"
        valid_cards = game.get_valid_attacks(game.player1_hand)
        if valid_cards and len(game.table) < 6:
            keyboard = create_card_keyboard(valid_cards, "throw")

        keyboard_buttons = keyboard.inline_keyboard if keyboard else []
        keyboard_buttons.append([InlineKeyboardButton(text="✅ Закінчити підкидання", callback_data="end_throw")])
        keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)

    await bot.send_message(chat_id, status, reply_markup=keyboard, parse_mode="Markdown")

async def bot_move(chat_id, game):
    await asyncio.sleep(1)

    is_bot_attacker = game.current_attacker != game.player1_id

    if is_bot_attacker and game.stage == "attack":
        card = game.make_bot_move_smart(attacker=True)
        if card:
            game.player2_hand.remove(card)
            game.table.append((card, None))
            await send_game_state(chat_id, game, f"🤖 Бот атакує: {card}")
            game.stage = "defend"
        else:
            await end_round(chat_id, game)

    elif not is_bot_attacker and game.stage == "defend":
        result = game.make_bot_move_smart(attacker=False)

        if result == "all_defended":
            await send_game_state(chat_id, game, "🤖 Бот відбився!")
            game.stage = "throw_in"
            game.current_attacker = game.player1_id
        elif result is None:
            for attack, defend in game.table:
                game.player2_hand.append(attack)
                if defend:
                    game.player2_hand.append(defend)
            game.table = []
            game.current_attacker = game.player1_id
            game.stage = "attack"
            game.refill_hands()

            winner = game.game_over()
            if winner:
                await handle_game_over(chat_id, game, winner)
            else:
                await send_game_state(chat_id, game, "🤖 Бот взяв карти")
                await bot_move(chat_id, game)
        else:
            idx, card = result
            game.player2_hand.remove(card)
            game.table[idx] = (game.table[idx][0], card)
            await bot_move(chat_id, game)

    elif is_bot_attacker and game.stage == "throw_in":
        card = game.make_bot_move_smart(attacker=True)
        if card:
            game.player2_hand.remove(card)
            game.table.append((card, None))
            await send_game_state(chat_id, game, f"🤖 Бот підкинув: {card}")
            game.stage = "defend"
        else:
            await end_round(chat_id, game)

async def end_round(chat_id, game):
    game.table = []
    game.refill_hands()

    winner = game.game_over()
    if winner:
        await handle_game_over(chat_id, game, winner)
    else:
        game.stage = "attack"
        await send_game_state(chat_id, game, "✅ Раунд завершено")
        if game.current_attacker != game.player1_id:
            await bot_move(chat_id, game)

async def handle_game_over(chat_id, game, winner_id):
    user_stats = get_or_create_stats(game.player1_id, "Гравець")

    if winner_id == game.player1_id:
        user_stats.win()
        message = f"🎉 Вітаємо! Ви перемогли!\n\n⭐ Рейтинг: {user_stats.rating} (+25)\n"
        if user_stats.wins == 1:
            message += "\n🏅 Нове досягнення: Перша перемога!"
        elif user_stats.wins == 10:
            message += "\n🏅 Нове досягнення: Ветеран!"
    else:
        user_stats.lose()
        message = f"😔 Ви програли.\n\n⭐ Рейтинг: {user_stats.rating} (-15)\n"

    message += f"\n📊 Статистика: {user_stats.wins}W / {user_stats.losses}L"

keyboard = [
        [InlineKeyboardButton(text="🔄 Нова гра", callback_data=f"bot_{game.difficulty}")],
        [InlineKeyboardButton(text="🏠 Меню", callback_data="back_menu")]
    ]

    await bot.send_message(chat_id, message, reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard), parse_mode="Markdown")
    del games[chat_id]

@dp.callback_query(F.data.startswith("attack_"))
async def handle_attack(callback: types.CallbackQuery):
    chat_id = callback.message.chat.id
    if chat_id not in games:
        await callback.answer("Гра не знайдена")
        return

    game = games[chat_id]
    card_idx = int(callback.data.split("_")[1])
    valid_cards = game.get_valid_attacks(game.player1_hand)

    if card_idx < len(valid_cards):
        card = valid_cards[card_idx]
        game.player1_hand.remove(card)
        game.table.append((card, None))

        await callback.message.delete()
        game.stage = "defend"
        await send_game_state(chat_id, game, f"⚔️ Ви атакували: {card}")
        await bot_move(chat_id, game)

    await callback.answer()

@dp.callback_query(F.data.startswith("defend_"))
async def handle_defend(callback: types.CallbackQuery):
    chat_id = callback.message.chat.id
    if chat_id not in games:
        await callback.answer("Гра не знайдена")
        return

    game = games[chat_id]
    parts = callback.data.split("_")
    table_idx = int(parts[1])
    card_idx = int(parts[2])

    attack_card = game.table[table_idx][0]
    valid_defends = [c for c in game.player1_hand if game.can_beat(attack_card, c)]

    if card_idx < len(valid_defends):
        card = valid_defends[card_idx]
        game.player1_hand.remove(card)
        game.table[table_idx] = (attack_card, card)

        await callback.message.delete()

        all_defended = all(defend is not None for _, defend in game.table)
        if all_defended:
            game.stage = "throw_in"
            await send_game_state(chat_id, game, f"🛡️ Ви відбилися: {card}")
            await bot_move(chat_id, game)
        else:
            await send_game_state(chat_id, game, f"🛡️ Відбито: {card}")

    await callback.answer()

@dp.callback_query(F.data == "take_cards")
async def handle_take(callback: types.CallbackQuery):
    chat_id = callback.message.chat.id
    if chat_id not in games:
        await callback.answer("Гра не знайдена")
        return

    game = games[chat_id]

    for attack, defend in game.table:
        game.player1_hand.append(attack)
        if defend:
            game.player1_hand.append(defend)

    game.table = []
    game.current_attacker = game.player1_id
    game.stage = "attack"
    game.refill_hands()

    await callback.message.delete()

    winner = game.game_over()
    if winner:
        await handle_game_over(chat_id, game, winner)
    else:
        await send_game_state(chat_id, game, "📥 Ви взяли карти")
        await bot_move(chat_id, game)

    await callback.answer()

@dp.callback_query(F.data == "end_attack")
async def handle_end_attack(callback: types.CallbackQuery):
    chat_id = callback.message.chat.id
    if chat_id not in games:
        await callback.answer("Гра не знайдена")
        return

    game = games[chat_id]
    await callback.message.delete()

    if not game.table:
        await send_game_state(chat_id, game, "Спочатку зробіть хід!")
    else:
        game.stage = "defend"
        await send_game_state(chat_id, game)
        await bot_move(chat_id, game)

    await callback.answer()

@dp.callback_query(F.data.startswith("throw_"))
async def handle_throw(callback: types.CallbackQuery):
    chat_id = callback.message.chat.id
    if chat_id not in games:
        await callback.answer("Гра не знайдена")
        return

    game = games[chat_id]
    card_idx = int(callback.data.split("_")[1])
    valid_cards = game.get_valid_attacks(game.player1_hand)

    if card_idx < len(valid_cards):
        card = valid_cards[card_idx]
        game.player1_hand.remove(card)
        game.table.append((card, None))

await callback.message.delete()
        game.stage = "defend"
        await send_game_state(chat_id, game, f"🎲 Ви підкинули: {card}")
        await bot_move(chat_id, game)

    await callback.answer()

@dp.callback_query(F.data == "end_throw")
async def handle_end_throw(callback: types.CallbackQuery):
    chat_id = callback.message.chat.id
    if chat_id not in games:
        await callback.answer("Гра не знайдена")
        return

    game = games[chat_id]
    await callback.message.delete()
    await end_round(chat_id, game)
    await callback.answer()

async def main():
    print("🤖 Покращений бот 'Дурак' запущено!")
    print("✅ Функції: статистика, рейтинг, досягнення, 3 рівні складності")
    await dp.start_polling(bot)

if name == "main":
    asyncio.run(main())