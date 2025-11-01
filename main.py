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
daily_tasks = {}

ACHIEVEMENTS = {
    "first_win": {"name": "🥇 Перша перемога", "reward": 50},
    "veteran": {"name": "🎖️ Ветеран", "desc": "10 перемог", "reward": 100},
    "winner_streak_3": {"name": "🔥 Серія 3", "desc": "3 поспіль", "reward": 75},
}

SHOP_ITEMS = {
    "avatar_king": {"name": "👑 Король", "price": 500},
    "avatar_ace": {"name": "🃏 Туз", "price": 300},
}

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
        self.coins = 100
        self.achievements = []
        self.items = []
        self.current_avatar = None
        self.friends_list = []
        self.win_streak = 0
        self.best_streak = 0
    
    def win(self):
        self.wins += 1
        self.games_played += 1
        self.rating += 25
        self.coins += 50
        self.win_streak += 1
        self.best_streak = max(self.best_streak, self.win_streak)
        return self._check_achievements()
    
    def lose(self):
        self.losses += 1
        self.games_played += 1
        self.rating = max(0, self.rating - 15)
        self.coins += 10
        self.win_streak = 0
    
    def _check_achievements(self):
        new = []
        if self.wins == 1 and "first_win" not in self.achievements:
            self.achievements.append("first_win")
            self.coins += 50
            new.append("first_win")
        if self.wins == 10 and "veteran" not in self.achievements:
            self.achievements.append("veteran")
            self.coins += 100
            new.append("veteran")
        if self.win_streak == 3 and "winner_streak_3" not in self.achievements:
            self.achievements.append("winner_streak_3")
            self.coins += 75
            new.append("winner_streak_3")
        return new

class DailyTask:
    def __init__(self, user_id):
        self.user_id = user_id
        self.date = datetime.now().date().isoformat()
        self.tasks = {
            "play_3": {"completed": False, "progress": 0, "target": 3, "reward": 30},
            "win_2": {"completed": False, "progress": 0, "target": 2, "reward": 50},
        }
    
    def update(self, task_name):
        if task_name in self.tasks and not self.tasks[task_name]["completed"]:
            self.tasks[task_name]["progress"] += 1
            if self.tasks[task_name]["progress"] >= self.tasks[task_name]["target"]:
                self.tasks[task_name]["completed"] = True
                return self.tasks[task_name]["reward"]
        return 0

class GameRoom:
    def __init__(self, room_id, creator_id, creator_name):
        self.room_id = room_id
        self.creator_id = creator_id
        self.creator_name = creator_name
        self.player2_id = None
        self.player2_name = None
        self.game = None

class DurakGame:
    def __init__(self, player1_id, player2_id=None, difficulty="medium", player1_name="", player2_name=""):
        self.player1_id = player1_id
        self.player2_id = player2_id
        self.player1_name = player1_name
        self.player2_name = player2_name
        self.difficulty = difficulty
        self.is_multiplayer = player2_id is not None
        self.start_time = datetime.now()
        
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
    
    def get_duration(self):
        return (datetime.now() - self.start_time).seconds
    
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
                    return None
            return "all_defended"

def get_or_create_stats(user_id, username):
    if user_id not in stats:
        stats[user_id] = PlayerStats(user_id, username)
    return stats[user_id]

def get_or_create_daily_tasks(user_id):
    today = datetime.now().date().isoformat()
    if user_id not in daily_tasks or daily_tasks[user_id].date != today:
        daily_tasks[user_id] = DailyTask(user_id)
    return daily_tasks[user_id]

def get_leaderboard():
    return sorted(stats.values(), key=lambda x: x.rating, reverse=True)[:10]

def format_hand(cards):
    return " ".join([str(card) for card in cards])

def format_table(table):
    if not table:
        return "Стіл порожній"
    return "\n".join([f"{a} ← {d}" if d else f"{a} ← ?" for a, d in table])

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
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎮 Бот", callback_data="play_bot"),
         InlineKeyboardButton(text="👥 Друг", callback_data="play_multi")],
        [InlineKeyboardButton(text="📊 Профіль", callback_data="my_stats"),
         InlineKeyboardButton(text="🏆 Рейтинг", callback_data="leaderboard")],
        [InlineKeyboardButton(text="🛒 Магазин", callback_data="shop"),
         InlineKeyboardButton(text="📅 Завдання", callback_data="tasks")],
        [InlineKeyboardButton(text="❓ Правила", callback_data="help")]
    ])

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    user_stats = get_or_create_stats(message.from_user.id, message.from_user.username)
    await message.answer(
        f"🃏 **Дурак**\n\n👤 {user_stats.username}\n⭐ {user_stats.rating}\n💰 {user_stats.coins}",
        reply_markup=get_main_menu(), parse_mode="Markdown"
    )

@dp.message(Command("menu"))
async def cmd_menu(message: types.Message):
    await message.answer("🎮 **Меню:**", reply_markup=get_main_menu(), parse_mode="Markdown")

@dp.callback_query(F.data == "play_bot")
async def handle_play_bot(callback: types.CallbackQuery):
    keyboard = [
        [InlineKeyboardButton(text="🟢 Легкий", callback_data="diff_easy")],
        [InlineKeyboardButton(text="🟡 Середній", callback_data="diff_medium")],
        [InlineKeyboardButton(text="🔴 Важкий", callback_data="diff_hard")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back_menu")]
    ]
    await callback.message.edit_text("🤖 **Складність:**", 
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard), parse_mode="Markdown")
    await callback.answer()

@dp.callback_query(F.data.startswith("diff_"))
async def handle_difficulty(callback: types.CallbackQuery):
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
    keyboard = [[InlineKeyboardButton(text="➕ Створити", callback_data="create_room")],
                [InlineKeyboardButton(text="🔙 Назад", callback_data="back_menu")]]
    await callback.message.edit_text("👥 **Гра з другом:**", 
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard), parse_mode="Markdown")
    await callback.answer()

@dp.callback_query(F.data == "create_room")
async def handle_create_room(callback: types.CallbackQuery):
    room_id = f"{callback.from_user.id}_{int(datetime.now().timestamp())}"
    rooms[room_id] = GameRoom(room_id, callback.from_user.id, callback.from_user.username or "User")
    
    await callback.message.edit_text(
        f"✅ **Кімнату створено!**\n\n📤 `/join_{room_id}`\n\n⏳ Очікування...",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="❌ Скасувати", callback_data="cancel_room")]]),
        parse_mode="Markdown"
    )
    await callback.answer()

@dp.message(F.text.startswith("/join_"))
async def cmd_join_room(message: types.Message):
    room_id = message.text.replace("/join_", "")
    
    if room_id not in rooms:
        await message.answer("❌ Кімната не знайдена")
        return
    
    room = rooms[room_id]
    
    if room.creator_id == message.from_user.id:
        await message.answer("❌ Це ваша кімната!")
        return
    
    room.player2_id = message.from_user.id
    room.player2_name = message.from_user.username or "User"
    
    creator_stats = get_or_create_stats(room.creator_id, room.creator_name)
    joiner_stats = get_or_create_stats(room.player2_id, room.player2_name)
    
    if room.player2_id not in creator_stats.friends_list:
        creator_stats.friends_list.append(room.player2_id)
    if room.creator_id not in joiner_stats.friends_list:
        joiner_stats.friends_list.append(room.creator_id)
    
    room.game = DurakGame(room.creator_id, room.player2_id, player1_name=room.creator_name, player2_name=room.player2_name)
    
    games[room.creator_id] = room.game
    games[room.player2_id] = room.game
    
    try:
        await bot.send_message(room.creator_id, f"✅ {room.player2_name} приєднався!", parse_mode="Markdown")
        await send_game_state_multiplayer(room.creator_id, room.game)
    except:
        pass
    
    await message.answer(f"✅ Приєдналися!", parse_mode="Markdown")
    await send_game_state_multiplayer(room.player2_id, room.game)
    
    del rooms[room_id]

# ПРОДОВЖЕННЯ В НАСТУПНОМУ ФАЙЛІ handlers.py
# ПРОДОВЖЕННЯ main.py - ВСТАВТЕ ПІСЛЯ ПЕРШОЇ ЧАСТИНИ

@dp.callback_query(F.data == "my_stats")
async def handle_my_stats(callback: types.CallbackQuery):
    user_stats = get_or_create_stats(callback.from_user.id, callback.from_user.username)
    winrate = (user_stats.wins / user_stats.games_played * 100) if user_stats.games_played > 0 else 0
    
    text = f"""
{'👤' if not user_stats.current_avatar else user_stats.current_avatar} **Профіль**

👤 {user_stats.username}
🎮 Ігор: {user_stats.games_played}
✅ Перемог: {user_stats.wins}
❌ Поразок: {user_stats.losses}
📈 Winrate: {winrate:.1f}%
⭐ Рейтинг: {user_stats.rating}
💰 Монет: {user_stats.coins}

🔥 Серія: {user_stats.win_streak}
🏆 Краща: {user_stats.best_streak}
"""
    
    keyboard = [[InlineKeyboardButton(text="🔙 Назад", callback_data="back_menu")]]
    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard), parse_mode="Markdown")
    await callback.answer()

@dp.callback_query(F.data == "leaderboard")
async def handle_leaderboard(callback: types.CallbackQuery):
    top = get_leaderboard()
    
    if not top:
        await callback.answer("Рейтинг порожній", show_alert=True)
        return
    
    text = "🏆 **ТОП-10:**\n\n"
    medals = ["🥇", "🥈", "🥉"]
    
    for i, player in enumerate(top):
        medal = medals[i] if i < 3 else f"{i+1}."
        text += f"{medal} {player.username} - ⭐{player.rating}\n"
    
    keyboard = [[InlineKeyboardButton(text="🔙 Назад", callback_data="back_menu")]]
    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard), parse_mode="Markdown")
    await callback.answer()

@dp.callback_query(F.data == "shop")
async def handle_shop(callback: types.CallbackQuery):
    user_stats = get_or_create_stats(callback.from_user.id, callback.from_user.username)
    
    text = f"🛒 **Магазин**\n\n💰 {user_stats.coins}\n\n"
    keyboard = []
    for item_id, item_data in SHOP_ITEMS.items():
        if item_id not in user_stats.items:
            text += f"{item_data['name']} - {item_data['price']}💰\n"
            keyboard.append([InlineKeyboardButton(text=f"Купити {item_data['name']}", callback_data=f"buy_{item_id}")])
    
    keyboard.append([InlineKeyboardButton(text="🔙 Назад", callback_data="back_menu")])
    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard), parse_mode="Markdown")
    await callback.answer()

@dp.callback_query(F.data.startswith("buy_"))
async def handle_buy(callback: types.CallbackQuery):
    item_id = callback.data.replace("buy_", "")
    user_stats = get_or_create_stats(callback.from_user.id, callback.from_user.username)
    
    if item_id not in SHOP_ITEMS or item_id in user_stats.items:
        await callback.answer("❌ Помилка", show_alert=True)
        return
    
    item = SHOP_ITEMS[item_id]
    
    if user_stats.coins < item["price"]:
        await callback.answer(f"❌ Потрібно: {item['price']}💰", show_alert=True)
        return
    
    user_stats.coins -= item["price"]
    user_stats.items.append(item_id)
    user_stats.current_avatar = item["name"].split()[0]
    
    await callback.answer("✅ Куплено!", show_alert=True)
    await handle_shop(callback)

@dp.callback_query(F.data == "tasks")
async def handle_tasks(callback: types.CallbackQuery):
    tasks = get_or_create_daily_tasks(callback.from_user.id)
    
    text = "📅 **Завдання**\n\n"
    task_names = {"play_3": "🎮 Зіграти 3", "win_2": "🏆 Виграти 2"}
    
    for task_name, task_data in tasks.tasks.items():
        status = "✅" if task_data["completed"] else f"{task_data['progress']}/{task_data['target']}"
        text += f"{status} {task_names[task_name]}\n   💰{task_data['reward']}\n\n"
    
    keyboard = [[InlineKeyboardButton(text="🔙 Назад", callback_data="back_menu")]]
    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard), parse_mode="Markdown")
    await callback.answer()

@dp.callback_query(F.data == "help")
async def handle_help(callback: types.CallbackQuery):
    rules = """
🃏 **Правила**

**Мета:** Позбутися карт

• Козирна масть
• Б'ємо старшою або козирем
• Можна підкидати

**Монети:**
+50 перемога
+10 гра

/menu
"""
    keyboard = [[InlineKeyboardButton(text="🔙 Назад", callback_data="back_menu")]]
    await callback.message.edit_text(rules, reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard), parse_mode="Markdown")
    await callback.answer()

@dp.callback_query(F.data == "back_menu")
async def handle_back_menu(callback: types.CallbackQuery):
    await callback.message.edit_text("🃏 **Меню:**", reply_markup=get_main_menu(), parse_mode="Markdown")
    await callback.answer()

@dp.callback_query(F.data == "cancel_room")
async def handle_cancel_room(callback: types.CallbackQuery):
    to_delete = [rid for rid, r in rooms.items() if r.creator_id == callback.from_user.id]
    for rid in to_delete:
        del rooms[rid]
    await callback.message.edit_text("❌ Скасовано", 
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 Назад", callback_data="play_multi")]]),
        parse_mode="Markdown")
    await callback.answer()

async def send_game_state(chat_id, game, message=""):
    diff_emoji = {"easy": "🟢", "medium": "🟡", "hard": "🔴"}
    
    status = f"🃏 **Дурак** {diff_emoji.get(game.difficulty, '')}\n\n"
    status += f"🎴 Козир: {game.trump_card}\n📚 Колода: {len(game.deck)}\n\n"
    status += f"**Стіл:** {format_table(game.table)}\n\n"
    status += f"🤖 Бот: {len(game.player2_hand)}\n👤 Ви: {format_hand(game.player1_hand)}\n\n"
    
    if message:
        status += f"📢 {message}\n\n"
    
    keyboard = None
    is_attacker = game.current_attacker == game.player1_id
    
    if is_attacker and game.stage == "attack":
        status += "⚔️ **Атакуйте!**"
        valid = game.get_valid_attacks(game.player1_hand)
        if valid:
            keyboard = create_card_keyboard(valid, "attack")
            keyboard.inline_keyboard.append([InlineKeyboardButton(text="✅ Завершити", callback_data="end_attack")])
    
    elif not is_attacker and game.stage == "defend":
        status += "🛡️ **Захищайтесь!**"
        for i, (attack, defend) in enumerate(game.table):
            if defend is None:
                valid = [c for c in game.player1_hand if game.can_beat(attack, c)]
                if valid:
                    status += f"\n🎯 Відбийте: {attack}"
                    keyboard = create_card_keyboard(valid, f"defend_{i}")
                kb = keyboard.inline_keyboard if keyboard else []
                kb.append([InlineKeyboardButton(text="❌ Беру", callback_data="take_cards")])
                keyboard = InlineKeyboardMarkup(inline_keyboard=kb)
                break
    
    elif is_attacker and game.stage == "throw_in":
        status += "🎲 **Підкиньте**"
        valid = game.get_valid_attacks(game.player1_hand)
        if valid and len(game.table) < 6:
            keyboard = create_card_keyboard(valid, "throw")
        kb = keyboard.inline_keyboard if keyboard else []
        kb.append([InlineKeyboardButton(text="✅ Закінчити", callback_data="end_throw")])
        keyboard = InlineKeyboardMarkup(inline_keyboard=kb)
    
    await bot.send_message(chat_id, status, reply_markup=keyboard, parse_mode="Markdown")

async def send_game_state_multiplayer(chat_id, game, message=""):
    player_hand = game.get_hand(chat_id)
    opponent_id = game.get_opponent_id(chat_id)
    opponent_hand = game.get_hand(opponent_id)
    opponent_name = game.player2_name if chat_id == game.player1_id else game.player1_name
    
    status = f"🃏 **Дурак**\n\n"
    status += f"🎴 Козир: {game.trump_card}\n📚 Колода: {len(game.deck)}\n\n"
    status += f"**Стіл:** {format_table(game.table)}\n\n"
    status += f"👥 {opponent_name}: {len(opponent_hand)}\n👤 Ви: {format_hand(player_hand)}\n\n"
    
    if message:
        status += f"📢 {message}\n\n"
    
    keyboard = None
    is_attacker = game.current_attacker == chat_id
    
    if is_attacker and game.stage == "attack":
        status += "⚔️ **Атакуйте!**"
        valid = game.get_valid_attacks(player_hand)
        if valid:
            keyboard = create_card_keyboard(valid, "attack")
            keyboard.inline_keyboard.append([InlineKeyboardButton(text="✅ Завершити", callback_data="end_attack")])
    
    elif not is_attacker and game.stage == "defend":
        status += "🛡️ **Захищайтесь!**"
        for i, (attack, defend) in enumerate(game.table):
            if defend is None:
                valid = [c for c in player_hand if game.can_beat(attack, c)]
                if valid:
                    status += f"\n🎯 Відбійте: {attack}"
                    keyboard = create_card_keyboard(valid, f"defend_{i}")
                kb = keyboard.inline_keyboard if keyboard else []
                kb.append([InlineKeyboardButton(text="❌ Беру", callback_data="take_cards")])
                keyboard = InlineKeyboardMarkup(inline_keyboard=kb)
                break
    
    elif is_attacker and game.stage == "throw_in":
        status += "🎲 **Підкиньте**"
        valid = game.get_valid_attacks(player_hand)
        if valid and len(game.table) < 6:
            keyboard = create_card_keyboard(valid, "throw")
        kb = keyboard.inline_keyboard if keyboard else []
        kb.append([InlineKeyboardButton(text="✅ Закінчити", callback_data="end_throw")])
        keyboard = InlineKeyboardMarkup(inline_keyboard=kb)
    else:
        status += "⏳ **Очікування...**"
    
    await bot.send_message(chat_id, status, reply_markup=keyboard, parse_mode="Markdown")

async def bot_move(chat_id, game):
    await asyncio.sleep(1.5)
    
    is_bot_attacker = game.current_attacker != game.player1_id
    
    if is_bot_attacker and game.stage == "attack":
        card = game.make_bot_move_smart(attacker=True)
        if card:
            game.player2_hand.remove(card)
            game.table.append((card, None))
            game.stage = "defend"
            await send_game_state(chat_id, game, f"🤖 Атакує: {card}")
        else:
            await end_round(chat_id, game)
    
    elif not is_bot_attacker and game.stage == "defend":
        result = game.make_bot_move_smart(attacker=False)
        
        if result == "all_defended":
            game.stage = "throw_in"
            game.current_attacker = game.player1_id
            await send_game_state(chat_id, game, "🤖 Відбився!")
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
                await send_game_state(chat_id, game, "🤖 Взяв")
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
            await send_game_state(chat_id, game, f"🤖 Підкинув: {card}")
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
    tasks = get_or_create_daily_tasks(game.player1_id)
    tasks.update("play_3")
    
    if game.is_multiplayer:
        winner_stats = get_or_create_stats(winner_id, "")
        loser_id = game.get_opponent_id(winner_id)
        loser_stats = get_or_create_stats(loser_id, "")
        
        new_ach = winner_stats.win()
        loser_stats.lose()
        
        winner_msg = f"🎉 **Перемога!**\n\n⭐ {winner_stats.rating} (+25)\n💰 +50\n🔥 Серія: {winner_stats.win_streak}"
        
        if new_ach:
            winner_msg += f"\n\n🏅 **Нові:**\n"
            for ach_id in new_ach:
                winner_msg += f"{ACHIEVEMENTS[ach_id]['name']}\n"
        
        loser_msg = f"😔 **Поразка**\n\n⭐ {loser_stats.rating} (-15)\n💰 +10"
        
        keyboard = [[InlineKeyboardButton(text="🏠 Меню", callback_data="back_menu")]]
        
        await bot.send_message(winner_id, winner_msg, reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard), parse_mode="Markdown")
        await bot.send_message(loser_id, loser_msg, reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard), parse_mode="Markdown")
        
        if game.player1_id in games:
            del games[game.player1_id]
        if game.player2_id in games:
            del games[game.player2_id]
    else:
        user_stats = get_or_create_stats(game.player1_id, "")
        
        if winner_id == game.player1_id:
            new_ach = user_stats.win()
            tasks.update("win_2")
            
            message = f"🎉 **Перемога!**\n\n⭐ {user_stats.rating} (+25)\n💰 +50\n🔥 Серія: {user_stats.win_streak}\n"
            
            if new_ach:
                message += f"\n🏅 **Нові:**\n"
                for ach_id in new_ach:
                    message += f"{ACHIEVEMENTS[ach_id]['name']} (+{ACHIEVEMENTS[ach_id]['reward']}💰)\n"
        else:
            user_stats.lose()
            message = f"😔 **Поразка**\n\n⭐ {user_stats.rating} (-15)\n💰 +10"
        
        message += f"\n\n📊 {user_stats.wins}W / {user_stats.losses}L"
        
        keyboard = [
            [InlineKeyboardButton(text="🔄 Ще", callback_data=f"diff_{game.difficulty}")],
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
    player_hand = game.get_hand(callback.from_user.id)
    valid = game.get_valid_attacks(player_hand)
    
    if card_idx < len(valid):
        card = valid[card_idx]
        player_hand.remove(card)
        game.table.append((card, None))
        game.stage = "defend"
        
        await callback.message.delete()
        
        if game.is_multiplayer:
            opponent_id = game.get_opponent_id(callback.from_user.id)
            await send_game_state_multiplayer(callback.from_user.id, game, f"⚔️ Ви: {card}")
            await send_game_state_multiplayer(opponent_id, game, f"⚔️ Атака: {card}")
        else:
            await send_game_state(chat_id, game, f"⚔️ Ви: {card}")
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
    valid = [c for c in player_hand if game.can_beat(attack_card, c)]
    
    if card_idx < len(valid):
        card = valid[card_idx]
        player_hand.remove(card)
        game.table[table_idx] = (attack_card, card)
        
        await callback.message.delete()
        
        all_defended = all(defend is not None for _, defend in game.table)
        if all_defended:
            game.stage = "throw_in"
            
            if game.is_multiplayer:
                opponent_id = game.get_opponent_id(callback.from_user.id)
                await send_game_state_multiplayer(callback.from_user.id, game, f"🛡️ Ви: {card}")
                await send_game_state_multiplayer(opponent_id, game, f"🛡️ Відбито: {card}")
            else:
                await send_game_state(chat_id, game, f"🛡️ Ви: {card}")
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
            await send_game_state_multiplayer(callback.from_user.id, game, "📥 Взяли")
            await send_game_state_multiplayer(opponent_id, game, "✅ Ваш хід!")
        else:
            await send_game_state(chat_id, game, "📥 Взяли")
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
            await send_game_state_multiplayer(callback.from_user.id, game, "Спочатку хід!")
        else:
            await send_game_state(chat_id, game, "Спочатку хід!")
    else:
        game.stage = "defend"
        
        if game.is_multiplayer:
            opponent_id = game.get_opponent_id(callback.from_user.id)
            await send_game_state_multiplayer(callback.from_user.id, game, "⏳ Очікування...")
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
    valid = game.get_valid_attacks(player_hand)
    
    if card_idx < len(valid):
        card = valid[card_idx]
        player_hand.remove(card)
        game.table.append((card, None))
        game.stage = "defend"
        
        await callback.message.delete()
        
        if game.is_multiplayer:
            opponent_id = game.get_opponent_id(callback.from_user.id)
            await send_game_state_multiplayer(callback.from_user.id, game, f"🎲 Ви: {card}")
            await send_game_state_multiplayer(opponent_id, game, f"🎲 Підкинули: {card}")
        else:
            await send_game_state(chat_id, game, f"🎲 Ви: {card}")
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
    print("🤖 Бот 'Дурак' запущено!")
    print("✅ Всі функції активовано")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())