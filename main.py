"""
Telegram бот для гри "Дурак" - ПОВНА ВЕРСІЯ
Функції: статистика, рейтинг, multiplayer, 3 рівні складності
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
rooms = {}

class Card:
    def __init__(self, rank, suit):
        self.rank = rank
        self.suit = suit
        self.value = RANK_VALUES[rank]
    
    def __str__(self):
        return f"{self.rank}{self.suit}"

class PlayerStats:
    def __init__(self, user_id, username):
        self.user_id = user_id
        self.username = username or f"User{user_id}"
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

class GameRoom:
    def __init__(self, room_id, creator_id, creator_name):
        self.room_id = room_id
        self.creator_id = creator_id
        self.creator_name = creator_name
        self.player2_id = None
        self.player2_name = None
        self.game = None

class DurakGame:
    def __init__(self, player1_id, player2_id=None, mode="podkidnoy", difficulty="medium", player1_name="", player2_name=""):
        self.player1_id = player1_id
        self.player2_id = player2_id
        self.player1_name = player1_name
        self.player2_name = player2_name
        self.mode = mode
        self.difficulty = difficulty
        self.is_multiplayer = player2_id is not None
        
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
    
    def get_hand(self, player_id):
        return self.player1_hand if player_id == self.player1_id else self.player2_hand
    
    def get_opponent_id(self, player_id):
        return self.player2_id if player_id == self.player1_id else self.player1_id
    
    def refill_hands(self):
        attacker_hand = self.get_hand(self.current_attacker)
        defender_id = self.get_opponent_id(self.current_attacker)
        defender_hand = self.get_hand(defender_id)
        
        while len(attacker_hand) < 6 and self.deck:
            attacker_hand.append(self.deck.pop())
        
        while len(defender_hand) < 6 and self.deck:
            defender_hand.append(self.deck.pop())
    
    def game_over(self):
        if not self.deck:
            if not self.player1_hand:
                return self.player1_id
            if not self.player2_hand:
                return self.player2_id
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
        stats[user_id] = PlayerStats(user_id, username)
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
            InlineKeyboardButton(text="👥 З другом", callback_data="play_multi")
        ],
        [
            InlineKeyboardButton(text="📊 Статистика", callback_data="my_stats"),
            InlineKeyboardButton(text="🏆 Рейтинг", callback_data="leaderboard")
        ],
        [
            InlineKeyboardButton(text="❓ Правила", callback_data="help")
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    get_or_create_stats(message.from_user.id, message.from_user.username)
    await message.answer(
        "🃏 **Вітаю в грі 'Дурак'!**\n\nОберіть режим:",
        reply_markup=get_main_menu(),
        parse_mode="Markdown"
    )

@dp.message(Command("menu"))
async def cmd_menu(message: types.Message):
    await message.answer("🎮 **Головне меню:**", reply_markup=get_main_menu(), parse_mode="Markdown")

@dp.message(Command("stats"))
async def cmd_stats(message: types.Message):
    await handle_my_stats_message(message)

async def handle_my_stats_message(message):
    user_stats = get_or_create_stats(message.from_user.id, message.from_user.username)
    
    winrate = (user_stats.wins / user_stats.games_played * 100) if user_stats.games_played > 0 else 0
    
    text = f"""
📊 **Ваша статистика:**

👤 {user_stats.username}
🎮 Ігор: {user_stats.games_played}
✅ Перемог: {user_stats.wins}
❌ Поразок: {user_stats.losses}
📈 Winrate: {winrate:.1f}%
⭐ Рейтинг: {user_stats.rating}

🏅 Досягнень: {len(user_stats.achievements)}
"""
    
    await message.answer(text, parse_mode="Markdown")

@dp.callback_query(F.data == "play_bot")
async def handle_play_bot(callback: types.CallbackQuery):
    keyboard = [
        [InlineKeyboardButton(text="🟢 Легкий", callback_data="bot_easy")],
        [InlineKeyboardButton(text="🟡 Середній", callback_data="bot_medium")],
        [InlineKeyboardButton(text="🔴 Важкий", callback_data="bot_hard")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back_menu")]
    ]
    await callback.message.edit_text(
        "🤖 **Оберіть складність бота:**",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard),
        parse_mode="Markdown"
    )
    await callback.answer()

@dp.callback_query(F.data.startswith("bot_"))
async def handle_bot_difficulty(callback: types.CallbackQuery):
    difficulty = callback.data.split("_")[1]
    
    chat_id = callback.message.chat.id
    games[chat_id] = DurakGame(
        player1_id=callback.from_user.id,
        difficulty=difficulty,
        player1_name=callback.from_user.username or "Ви",
        player2_name="🤖 Бот"
    )
    
    await callback.message.delete()
    await send_game_state(chat_id, games[chat_id])
    await callback.answer()

@dp.callback_query(F.data == "play_multi")
async def handle_play_multi(callback: types.CallbackQuery):
    keyboard = [
        [InlineKeyboardButton(text="➕ Створити кімнату", callback_data="create_room")],
        [InlineKeyboardButton(text="🔍 Мої кімнати", callback_data="my_rooms")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back_menu")]
    ]
    
    await callback.message.edit_text(
        "👥 **Гра з другом:**\n\n"
        "Створіть кімнату та поділіться кодом з другом!",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard),
        parse_mode="Markdown"
    )
    await callback.answer()

@dp.callback_query(F.data == "create_room")
async def handle_create_room(callback: types.CallbackQuery):
    room_id = f"{callback.from_user.id}_{int(datetime.now().timestamp())}"
    rooms[room_id] = GameRoom(
        room_id,
        callback.from_user.id,
        callback.from_user.username or f"User{callback.from_user.id}"
    )
    
    join_command = f"/join_{room_id}"
    
    keyboard = [
        [InlineKeyboardButton(text="❌ Скасувати", callback_data="cancel_room")]
    ]
    
    await callback.message.edit_text(
        f"✅ **Кімнату створено!**\n\n"
        f"🔑 Код кімнати: `{room_id}`\n\n"
        f"📤 Поділіться цією командою з другом:\n"
        f"`{join_command}`\n\n"
        f"⏳ Очікування гравця...",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard),
        parse_mode="Markdown"
    )
    await callback.answer("Кімнату створено! Поділіться командою з другом")

@dp.message(Command(startswith="join_"))
async def cmd_join_room(message: types.Message):
    room_id = message.text.split("_", 1)[1]
    
    if room_id not in rooms:
        await message.answer("❌ Кімната не знайдена або вже зайнята")
        return
    
    room = rooms[room_id]
    
    if room.creator_id == message.from_user.id:
        await message.answer("❌ Ви не можете приєднатись до своєї кімнати!")
        return
    
    if room.player2_id is not None:
        await message.answer("❌ Кімната вже зайнята!")
        return
    
    room.player2_id = message.from_user.id
    room.player2_name = message.from_user.username or f"User{message.from_user.id}"
    
    # Створюємо гру
    room.game = DurakGame(
        player1_id=room.creator_id,
        player2_id=room.player2_id,
        player1_name=room.creator_name,
        player2_name=room.player2_name
    )
    
    # Додаємо гру для обох гравців
    games[room.creator_id] = room.game
    games[room.player2_id] = room.game
    
    # Повідомляємо створювача
    try:
        await bot.send_message(
            room.creator_id,
            f"✅ **{room.player2_name}** приєднався до гри!\n\nГра починається!",
            parse_mode="Markdown"
        )
        await send_game_state_multiplayer(room.creator_id, room.game)
    except:
        pass
    
    # Повідомляємо того хто приєднався
    await message.answer(
        f"✅ Ви приєдналися до гри з **{room.creator_name}**!\n\nГра починається!",
        parse_mode="Markdown"
    )
    await send_game_state_multiplayer(room.player2_id, room.game)
    
    # Видаляємо кімнату
    del rooms[room_id]

@dp.callback_query(F.data == "cancel_room")
async def handle_cancel_room(callback: types.CallbackQuery):
    # Видаляємо всі кімнати створені цим користувачем
    to_delete = [rid for rid, r in rooms.items() if r.creator_id == callback.from_user.id]
    for rid in to_delete:
        del rooms[rid]
    
    await callback.message.edit_text(
        "❌ Кімнату скасовано",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Назад", callback_data="play_multi")]
        ]),
        parse_mode="Markdown"
    )
    await callback.answer()

@dp.callback_query(F.data == "my_rooms")
async def handle_my_rooms(callback: types.CallbackQuery):
    user_rooms = [r for r in rooms.values() if r.creator_id == callback.from_user.id]
    
    if not user_rooms:
        await callback.answer("У вас немає активних кімнат", show_alert=True)
        return
    
    text = "🏠 **Ваші кімнати:**\n\n"
    for room in user_rooms:
        text += f"🔑 `{room.room_id}`\n"
    
    keyboard = [[InlineKeyboardButton(text="🔙 Назад", callback_data="play_multi")]]
    
    await callback.message.edit_text(
        text,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard),
        parse_mode="Markdown"
    )
    await callback.answer()

@dp.callback_query(F.data == "my_stats")
async def handle_my_stats(callback: types.CallbackQuery):
    user_stats = get_or_create_stats(callback.from_user.id, callback.from_user.username)
    
    winrate = (user_stats.wins / user_stats.games_played * 100) if user_stats.games_played > 0 else 0
    
    achievements_text = ""
    if "first_win" in user_stats.achievements:
        achievements_text += "🥇 Перша перемога\n"
    if "veteran" in user_stats.achievements:
        achievements_text += "🎖️ Ветеран (10 побід)\n"
    if "master" in user_stats.achievements:
        achievements_text += "👑 Майстер (50 побід)\n"
    
    if not achievements_text:
        achievements_text = "Поки немає досягнень"
    
    text = f"""
📊 **Ваша статистика:**

👤 {user_stats.username}
🎮 Ігор: {user_stats.games_played}
✅ Перемог: {user_stats.wins}
❌ Поразок: {user_stats.losses}
📈 Winrate: {winrate:.1f}%
⭐ Рейтинг: {user_stats.rating}

🏅 **Досягнення:**
{achievements_text}
"""
    
    keyboard = [[InlineKeyboardButton(text="🔙 Назад", callback_data="back_menu")]]
    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard), parse_mode="Markdown")
    await callback.answer()

@dp.callback_query(F.data == "leaderboard")
async def handle_leaderboard(callback: types.CallbackQuery):
    top_players = get_leaderboard()
    
    if not top_players:
        await callback.answer("Рейтинг порожній. Зіграйте першу гру!", show_alert=True)
        return
    
    text = "🏆 **ТОП-10 ГРАВЦІВ:**\n\n"
    medals = ["🥇", "🥈", "🥉"]
    for i, player in enumerate(top_players):
        medal = medals[i] if i < 3 else f"{i+1}."
        winrate = (player.wins / player.games_played * 100) if player.games_played > 0 else 0
        text += f"{medal} **{player.username}** - {player.rating} ⭐\n   {player.wins}W / {player.losses}L ({winrate:.0f}%)\n\n"
    
    keyboard = [[InlineKeyboardButton(text="🔙 Назад", callback_data="back_menu")]]
    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard), parse_mode="Markdown")
    await callback.answer()

@dp.callback_query(F.data == "help")
async def handle_help(callback: types.CallbackQuery):
    rules = """
🃏 **Правила гри 'Дурак'**

**Мета:** Позбутися всіх карт.

**Правила:**
• Колода: 36 карт (6-Т)
• Визначається козирна масть
• Атакуючий кладе карту
• Захисник бʼє старшою або козирем
• Можна підкидати карти того ж номіналу
• Хто залишився з картами - програв

**Режими:**
🎮 **З ботом** - 3 рівні складності
👥 **З другом** - створіть кімнату

**Команди:**
/menu - головне меню
/stats - ваша статистика
"""
    keyboard = [[InlineKeyboardButton(text="🔙 Назад", callback_data="back_menu")]]
    await callback.message.edit_text(rules, reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard), parse_mode="Markdown")
    await callback.answer()

@dp.callback_query(F.data == "back_menu")
async def handle_back_menu(callback: types.CallbackQuery):
    await callback.message.edit_text("🃏 **Головне меню:**", reply_markup=get_main_menu(), parse_mode="Markdown")
    await callback.answer()

async def send_game_state(chat_id, game, message=""):
    """Для гри з ботом"""
    difficulty_emoji = {"easy": "🟢", "medium": "🟡", "hard": "🔴"}
    
    status = f"🃏 **Гра 'Дурак'**\n"
    status += f"🤖 Складність: {difficulty_emoji.get(game.difficulty, '')} {game.difficulty.upper()}\n\n"
    status += f"🎴 Козир: {game.trump_card}\n"
    status += f"📚 Карт у колоді: {len(game.deck)}\n\n"
    status += f"**На столі:**\n{format_table(game.table)}\n\n"
    status += f"🤖 Карт у бота: {len(game.player2_hand)}\n"
    status += f"👤 Ваші карти: {format_hand(game.player1_hand)}\n\n"
    
    if message:
        status += f"📢 {message}\n\n"
    
    keyboard = None
    is_attacker = game.current_attacker == game.player1_id
    
    if is_attacker and game.stage == "attack":
        status += "⚔️ **Ваш хід - атакуйте!**"
        valid_cards = game.get_valid_attacks(game.player1_hand)
        if valid_cards:
            keyboard = create_card_keyboard(valid_cards, "attack")
            keyboard.inline_keyboard.append([InlineKeyboardButton(text="✅ Завершити хід", callback_data="end_attack")])
    
    elif not is_attacker and game.stage == "defend":
        status += "🛡️ **Захищайтесь!**"
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
        status += "🎲 **Можете підкинути**"
        valid_cards = game.get_valid_attacks(game.player1_hand)
        if valid_cards and len(game.table) < 6:
            keyboard = create_card_keyboard(valid_cards, "throw")
        
        keyboard_buttons = keyboard.inline_keyboard if keyboard else []
        keyboard_buttons.append([InlineKeyboardButton(text="✅ Закінчити підкидання", callback_data="end_throw")])
        keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
    
    await bot.send_message(chat_id, status, reply_markup=keyboard, parse_mode="Markdown")

async def send_game_state_multiplayer(chat_id, game, message=""):
    """Для multiplayer гри"""
    player_hand = game.get_hand(chat_id)
    opponent_id = game.get_opponent_id(chat_id)
    opponent_hand = game.get_hand(opponent_id)
    opponent_name = game.player2_name if chat_id == game.player1_id else game.player1_name
    
    status = f"🃏 **Гра 'Дурак'** (з другом)\n\n"
    status += f"🎴 Козир: {game.trump_card}\n"
    status += f"📚 Карт у колоді: {len(game.deck)}\n\n"
    status += f"**На столі:**\n{format_table(game.table)}\n\n"
    status += f"👥 {opponent_name}: {len(opponent_hand)} карт\n"
    status += f"👤 Ваші карти: {format_hand(player_hand)}\n\n"
    
    if message:
        status += f"📢 {message}\n\n"
    
    keyboard = None
    is_attacker = game.current_attacker == chat_id
    
    if is_attacker and game.stage == "attack":
        status += "⚔️ **Ваш хід - атакуйте!**"
        valid_cards = game.get_valid_attacks(player_hand)
        if valid_cards:
            keyboard = create_card_keyboard(valid_cards, "attack")
            keyboard.inline_keyboard.append([InlineKeyboardButton(text="✅ Завершити хід", callback_data="end_attack")])
    
    elif not is_attacker and game.stage == "defend":
        status += "🛡️ **Ваш хід - захищайтесь!**"
        undefended = None
        for i, (attack, defend) in enumerate(game.table):
            if defend is None:
                undefended = (i, attack)
                break
        
        if undefended:
            idx, attack_card = undefended
            valid_defends = [c for c in player_hand if game.can_beat(attack_card, c)]
            if valid_defends:
                status += f"\n🎯 Відбийте: {attack_card}"
                keyboard = create_card_keyboard(valid_defends, f"defend_{idx}")
            
            keyboard_buttons = keyboard.inline_keyboard if keyboard else []
            keyboard_buttons.append([InlineKeyboardButton(text="❌ Беру", callback_data="take_cards")])
            keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
    
    elif is_attacker and game.stage == "throw_in":
        status += "🎲 **Можете підкінути**"
        valid_cards = game.get_valid_attacks(player_hand)
        if valid_cards and len(game.table) < 6:
            keyboard = create_card_keyboard(valid_cards, "throw")
        
        keyboard_buttons = keyboard.inline_keyboard if keyboard else []
        keyboard_buttons.append([InlineKeyboardButton(text="✅ Закінчити підкидання", callback_data="end_throw")])
        keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
    else:
        status += "⏳ **Очікування ходу суперника...**"
    
    await bot.send_message(chat_id, status, reply_markup=keyboard, parse_mode="Markdown")

async def bot_move(chat_id, game):
    await asyncio.sleep(1)
    
    is_bot_attacker = game.current_attacker != game.player1_id
    
    if is_bot_attacker and game.stage == "attack":
        card = game.make_bot_move_smart(attacker=True)
        if card:
            game.player2_hand.remove(card)
            game.table.append((card, None))
            game.stage = "defend"
            await send_game_state(chat_id, game, f"🤖 Бот атакує: {card}")
        else:
            await end_round(chat_id, game)
    
    elif not is_bot_attacker and game.stage == "defend":
        result = game.make_bot_move_smart(attacker=False)
        
        if result == "all_defended":
            game.stage = "throw_in"
            game.current_attacker = game.player1_id
            await send_game_state(chat_id, game, "🤖 Бот відбився!")
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
            game.stage = "defend"
            await send_game_state(chat_id, game, f"🤖 Бот підкинув: {card}")
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
        
        if game.is_multiplayer:
            await send_game_state_multiplayer(game.player1_id, game, "✅ Раунд завершено")
            await send_game_state_multiplayer(game.player2_id, game, "✅ Раунд завершено")
        else:
            await send_game_state(chat_id, game, "✅ Раунд завершено")
            if game.current_attacker != game.player1_id:
                await bot_move(chat_id, game)

async def handle_game_over(chat_id, game, winner_id):
    if game.is_multiplayer:
        # Multiplayer завершення
        winner_stats = get_or_create_stats(winner_id, "")
        loser_id = game.get_opponent_id(winner_id)
        loser_stats = get_or_create_stats(loser_id, "")
        
        winner_stats.win()
        loser_stats.lose()
        
        winner_name = game.player1_name if winner_id == game.player1_id else game.player2_name
        loser_name = game.player2_name if winner_id == game.player1_id else game.player1_name
        
        winner_msg = f"🎉 **Ви перемогли {loser_name}!**\n\n⭐ Рейтинг: {winner_stats.rating} (+25)"
        loser_msg = f"😔 **Ви програли {winner_name}**\n\n⭐ Рейтинг: {loser_stats.rating} (-15)"
        
        keyboard = [
            [InlineKeyboardButton(text="📊 Статистика", callback_data="my_stats")],
            [InlineKeyboardButton(text="🏠 Меню", callback_data="back_menu")]
        ]
        
        await bot.send_message(winner_id, winner_msg, reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard), parse_mode="Markdown")
        await bot.send_message(loser_id, loser_msg, reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard), parse_mode="Markdown")
        
        if game.player1_id in games:
            del games[game.player1_id]
        if game.player2_id in games:
            del games[game.player2_id]
    else:
        # Гра з ботом
        user_stats = get_or_create_stats(game.player1_id, "")
        
        if winner_id == game.player1_id:
            user_stats.win()
            message = f"🎉 **Вітаємо! Ви перемогли!**\n\n⭐ Рейтинг: {user_stats.rating} (+25)\n"
            if user_stats.wins == 1:
                message += "\n🏅 **Нове досягнення:** Перша перемога!"
            elif user_stats.wins == 10:
                message += "\n🏅 **Нове досягнення:** Ветеран!"
            elif user_stats.wins == 50:
                message += "\n🏅 **Нове досягнення:** Майстер!"
        else:
            user_stats.lose()
            message = f"😔 **Ви програли.**\n\n⭐ Рейтинг: {user_stats.rating} (-15)\n"
        
        message += f"\n📊 Статистика: {user_stats.wins}W / {user_stats.losses}L"
        
        keyboard = [
            [InlineKeyboardButton(text="🔄 Нова гра", callback_data=f"bot_{game.difficulty}")],
            [InlineKeyboardButton(text="📊 Статистика", callback_data="my_stats")],
            [InlineKeyboardButton(text="🏠 Меню", callback_data="back_menu")]
        ]
        
        await bot.send_message(chat_id, message, reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard), parse_mode="Markdown")
        del games[chat_id]

@dp.callback_query(F.data.startswith("attack_"))
async def handle_attack(callback: types.CallbackQuery):
    chat_id = callback.message.chat.id
    
    # Перевірка чи є гра
    if chat_id not in games:
        await callback.answer("Гра не знайдена")
        return
    
    game = games[chat_id]
    card_idx = int(callback.data.split("_")[1])
    player_hand = game.get_hand(callback.from_user.id)
    valid_cards = game.get_valid_attacks(player_hand)
    
    if card_idx < len(valid_cards):
        card = valid_cards[card_idx]
        player_hand.remove(card)
        game.table.append((card, None))
        game.stage = "defend"
        
        await callback.message.delete()
        
        if game.is_multiplayer:
            opponent_id = game.get_opponent_id(callback.from_user.id)
            await send_game_state_multiplayer(callback.from_user.id, game, f"⚔️ Ви атакували: {card}")
            await send_game_state_multiplayer(opponent_id, game, f"⚔️ Противник атакує: {card}")
        else:
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
    
    player_hand = game.get_hand(callback.from_user.id)
    attack_card = game.table[table_idx][0]
    valid_defends = [c for c in player_hand if game.can_beat(attack_card, c)]
    
    if card_idx < len(valid_defends):
        card = valid_defends[card_idx]
        player_hand.remove(card)
        game.table[table_idx] = (attack_card, card)
        
        await callback.message.delete()
        
        all_defended = all(defend is not None for _, defend in game.table)
        if all_defended:
            game.stage = "throw_in"
            
            if game.is_multiplayer:
                opponent_id = game.get_opponent_id(callback.from_user.id)
                await send_game_state_multiplayer(callback.from_user.id, game, f"🛡️ Ви відбилися: {card}")
                await send_game_state_multiplayer(opponent_id, game, f"🛡️ Противник відбився: {card}")
            else:
                await send_game_state(chat_id, game, f"🛡️ Ви відбилися: {card}")
                await bot_move(chat_id, game)
        else:
            if game.is_multiplayer:
                await send_game_state_multiplayer(callback.from_user.id, game, f"🛡️ Відбито: {card}")
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
    player_hand = game.get_hand(callback.from_user.id)
    
    for attack, defend in game.table:
        player_hand.append(attack)
        if defend:
            player_hand.append(defend)
    
    game.table = []
    opponent_id = game.get_opponent_id(callback.from_user.id)
    game.current_attacker = opponent_id
    game.stage = "attack"
    game.refill_hands()
    
    await callback.message.delete()
    
    winner = game.game_over()
    if winner:
        await handle_game_over(chat_id, game, winner)
    else:
        if game.is_multiplayer:
            await send_game_state_multiplayer(callback.from_user.id, game, "📥 Ви взяли карти")
            await send_game_state_multiplayer(opponent_id, game, "✅ Противник взяв карти. Ваш хід!")
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
        if game.is_multiplayer:
            await send_game_state_multiplayer(callback.from_user.id, game, "Спочатку зробіть хід!")
        else:
            await send_game_state(chat_id, game, "Спочатку зробіть хід!")
    else:
        game.stage = "defend"
        
        if game.is_multiplayer:
            opponent_id = game.get_opponent_id(callback.from_user.id)
            await send_game_state_multiplayer(callback.from_user.id, game, "⏳ Очікування ходу противника...")
            await send_game_state_multiplayer(opponent_id, game)
        else:
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
    player_hand = game.get_hand(callback.from_user.id)
    valid_cards = game.get_valid_attacks(player_hand)
    
    if card_idx < len(valid_cards):
        card = valid_cards[card_idx]
        player_hand.remove(card)
        game.table.append((card, None))
        game.stage = "defend"
        
        await callback.message.delete()
        
        if game.is_multiplayer:
            opponent_id = game.get_opponent_id(callback.from_user.id)
            await send_game_state_multiplayer(callback.from_user.id, game, f"🎲 Ви підкинули: {card}")
            await send_game_state_multiplayer(opponent_id, game, f"🎲 Противник підкинув: {card}")
        else:
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
    print("✅ Функції: статистика, рейтинг, досягнення, multiplayer, 3 рівні складності")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())