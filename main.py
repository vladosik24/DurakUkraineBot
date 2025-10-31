"""
Telegram бот для гри "Дурак" - МАКСИМАЛЬНА ВЕРСІЯ
Усі функції: турніри, історія, досягнення, магазин, друзі, щоденні завдання
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
tournaments = {}
daily_tasks = {}
game_history = {}

ACHIEVEMENTS = {
    "first_win": {"name": "🥇 Перша перемога", "reward": 50},
    "veteran": {"name": "🎖️ Ветеран", "desc": "10 перемог", "reward": 100},
    "master": {"name": "👑 Майстер", "desc": "50 перемог", "reward": 250},
    "legend": {"name": "⭐ Легенда", "desc": "100 перемог", "reward": 500},
    "winner_streak_3": {"name": "🔥 Серія 3", "desc": "3 перемоги поспіль", "reward": 75},
    "winner_streak_5": {"name": "🔥🔥 Серія 5", "desc": "5 перемог поспіль", "reward": 150},
    "high_rated": {"name": "💎 Висока ліга", "desc": "Рейтинг 1500+", "reward": 200},
    "pro_rated": {"name": "🏆 Про гравець", "desc": "Рейтинг 2000+", "reward": 500},
    "daily_player": {"name": "📅 Щоденний гравець", "desc": "7 днів поспіль", "reward": 100},
    "tournament_winner": {"name": "🎯 Переможець турніру", "reward": 300},
}

SHOP_ITEMS = {
    "avatar_king": {"name": "👑 Король", "price": 500, "type": "avatar"},
    "avatar_ace": {"name": "🃏 Туз", "price": 300, "type": "avatar"},
    "avatar_joker": {"name": "🤡 Джокер", "price": 400, "type": "avatar"},
    "avatar_diamond": {"name": "💎 Діамант", "price": 1000, "type": "avatar"},
    "theme_gold": {"name": "✨ Золота тема", "price": 800, "type": "theme"},
}

class Card:
    def __init__(self, rank, suit):
        self.rank = rank
        self.suit = suit
        self.value = RANK_VALUES[rank]
    
    def __str__(self):
        return f"{self.rank}{self.suit}"

class GameHistory:
    def __init__(self, player1_id, player2_id, winner_id, duration, mode):
        self.player1_id = player1_id
        self.player2_id = player2_id
        self.winner_id = winner_id
        self.duration = duration
        self.mode = mode
        self.timestamp = datetime.now().isoformat()

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
        self.last_played = None
        self.daily_streak = 0
    
    def win(self):
        self.wins += 1
        self.games_played += 1
        self.rating += 25
        self.coins += 50
        self.win_streak += 1
        self.best_streak = max(self.best_streak, self.win_streak)
        self.last_played = datetime.now().isoformat()
        return self._check_achievements()
    
    def lose(self):
        self.losses += 1
        self.games_played += 1
        self.rating = max(0, self.rating - 15)
        self.coins += 10
        self.win_streak = 0
        self.last_played = datetime.now().isoformat()
    
    def _check_achievements(self):
        new_achievements = []
        
        if self.wins == 1 and "first_win" not in self.achievements:
            self.achievements.append("first_win")
            self.coins += ACHIEVEMENTS["first_win"]["reward"]
            new_achievements.append("first_win")
        
        if self.wins == 10 and "veteran" not in self.achievements:
            self.achievements.append("veteran")
            self.coins += ACHIEVEMENTS["veteran"]["reward"]
            new_achievements.append("veteran")
        
        if self.wins == 50 and "master" not in self.achievements:
            self.achievements.append("master")
            self.coins += ACHIEVEMENTS["master"]["reward"]
            new_achievements.append("master")
        
        if self.wins == 100 and "legend" not in self.achievements:
            self.achievements.append("legend")
            self.coins += ACHIEVEMENTS["legend"]["reward"]
            new_achievements.append("legend")
        
        if self.win_streak == 3 and "winner_streak_3" not in self.achievements:
            self.achievements.append("winner_streak_3")
            self.coins += ACHIEVEMENTS["winner_streak_3"]["reward"]
            new_achievements.append("winner_streak_3")
        
        if self.win_streak == 5 and "winner_streak_5" not in self.achievements:
            self.achievements.append("winner_streak_5")
            self.coins += ACHIEVEMENTS["winner_streak_5"]["reward"]
            new_achievements.append("winner_streak_5")
        
        if self.rating >= 1500 and "high_rated" not in self.achievements:
            self.achievements.append("high_rated")
            self.coins += ACHIEVEMENTS["high_rated"]["reward"]
            new_achievements.append("high_rated")
        
        if self.rating >= 2000 and "pro_rated" not in self.achievements:
            self.achievements.append("pro_rated")
            self.coins += ACHIEVEMENTS["pro_rated"]["reward"]
            new_achievements.append("pro_rated")
        
        return new_achievements
    
    def check_daily_streak(self):
        if self.last_played:
            last = datetime.fromisoformat(self.last_played)
            now = datetime.now()
            days_diff = (now - last).days
            
            if days_diff == 1:
                self.daily_streak += 1
            elif days_diff > 1:
                self.daily_streak = 1
        else:
            self.daily_streak = 1
        
        if self.daily_streak == 7 and "daily_player" not in self.achievements:
            self.achievements.append("daily_player")
            self.coins += ACHIEVEMENTS["daily_player"]["reward"]
            return True
        return False

class DailyTask:
    def __init__(self, user_id):
        self.user_id = user_id
        self.date = datetime.now().date().isoformat()
        self.tasks = {
            "play_3_games": {"completed": False, "progress": 0, "target": 3, "reward": 30},
            "win_2_games": {"completed": False, "progress": 0, "target": 2, "reward": 50},
            "win_vs_hard": {"completed": False, "progress": 0, "target": 1, "reward": 100},
        }
    
    def update_task(self, task_name, progress=1):
        if task_name in self.tasks and not self.tasks[task_name]["completed"]:
            self.tasks[task_name]["progress"] += progress
            if self.tasks[task_name]["progress"] >= self.tasks[task_name]["target"]:
                self.tasks[task_name]["completed"] = True
                return self.tasks[task_name]["reward"]
        return 0

class Tournament:
    def __init__(self, tournament_id, name, creator_id):
        self.tournament_id = tournament_id
        self.name = name
        self.creator_id = creator_id
        self.players = []
        self.status = "waiting"
        self.bracket = {}
        self.current_round = 0
        self.created_at = datetime.now().isoformat()
    
    def add_player(self, player_id, username):
        if len(self.players) < 8:
            self.players.append({"id": player_id, "name": username})
            return True
        return False

class GameRoom:
    def __init__(self, room_id, creator_id, creator_name, mode="podkidnoy"):
        self.room_id = room_id
        self.creator_id = creator_id
        self.creator_name = creator_name
        self.player2_id = None
        self.player2_name = None
        self.mode = mode
        self.game = None

class DurakGame:
    def __init__(self, player1_id, player2_id=None, mode="podkidnoy", difficulty="medium", 
                 player1_name="", player2_name="", cards_count=36):
        self.player1_id = player1_id
        self.player2_id = player2_id
        self.player1_name = player1_name
        self.player2_name = player2_name
        self.mode = mode
        self.difficulty = difficulty
        self.is_multiplayer = player2_id is not None
        self.start_time = datetime.now()
        
        if cards_count == 24:
            ranks_to_use = ['9', '10', 'В', 'Д', 'К', 'Т']
        else:
            ranks_to_use = RANKS
        
        self.deck = [Card(r, s) for s in SUITS for r in ranks_to_use]
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
            elif self.difficulty == "medium":
                non_trumps = [c for c in valid if c.suit != self.trump_suit]
                return min(non_trumps, key=lambda x: x.value) if non_trumps else min(valid, key=lambda x: x.value)
            else:
                opponent_count = len(self.player1_hand)
                if opponent_count <= 3:
                    return max(valid, key=lambda x: x.value)
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

def get_or_create_daily_tasks(user_id):
    today = datetime.now().date().isoformat()
    if user_id not in daily_tasks or daily_tasks[user_id].date != today:
        daily_tasks[user_id] = DailyTask(user_id)
    return daily_tasks[user_id]

def get_leaderboard():
    return sorted(stats.values(), key=lambda x: x.rating, reverse=True)[:10]

def add_game_history(player1_id, player2_id, winner_id, duration, mode):
    if player1_id not in game_history:
        game_history[player1_id] = []
    if player2_id and player2_id not in game_history:
        game_history[player2_id] = []
    
    history = GameHistory(player1_id, player2_id, winner_id, duration, mode)
    game_history[player1_id].append(history)
    if player2_id:
        game_history[player2_id].append(history)
    
    if len(game_history[player1_id]) > 20:
        game_history[player1_id] = game_history[player1_id][-20:]
    if player2_id and len(game_history[player2_id]) > 20:
        game_history[player2_id] = game_history[player2_id][-20:]

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
            InlineKeyboardButton(text="🎯 Турніри", callback_data="tournaments_menu"),
            InlineKeyboardButton(text="📅 Завдання", callback_data="daily_tasks_menu")
        ],
        [
            InlineKeyboardButton(text="📊 Профіль", callback_data="my_stats"),
            InlineKeyboardButton(text="🏆 Рейтинг", callback_data="leaderboard")
        ],
        [
            InlineKeyboardButton(text="🛒 Магазин", callback_data="shop_menu"),
            InlineKeyboardButton(text="👫 Друзі", callback_data="friends_menu")
        ],
        [
            InlineKeyboardButton(text="📜 Історія", callback_data="game_history"),
            InlineKeyboardButton(text="❓ Правила", callback_data="help")
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    user_stats = get_or_create_stats(message.from_user.id, message.from_user.username)
    user_stats.check_daily_streak()
    
    await message.answer(
        f"🃏 **Вітаю в грі 'Дурак'!**\n\n"
        f"👤 {user_stats.username}\n"
        f"⭐ Рейтинг: {user_stats.rating}\n"
        f"💰 Монет: {user_stats.coins}\n"
        f"🏅 Досягнень: {len(user_stats.achievements)}\n\n"
        f"Оберіть режим:",
        reply_markup=get_main_menu(),
        parse_mode="Markdown"
    )

@dp.message(Command("menu"))
async def cmd_menu(message: types.Message):
    await message.answer("🎮 **Головне меню:**", reply_markup=get_main_menu(), parse_mode="Markdown")

@dp.callback_query(F.data == "play_bot")
async def handle_play_bot(callback: types.CallbackQuery):
    keyboard = [
        [InlineKeyboardButton(text="🟢 Легкий", callback_data="diff_easy")],
        [InlineKeyboardButton(text="🟡 Середній", callback_data="diff_medium")],
        [InlineKeyboardButton(text="🔴 Важкий", callback_data="diff_hard")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back_menu")]
    ]
    await callback.message.edit_text(
        "🤖 **Оберіть складність:**",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard),
        parse_mode="Markdown"
    )
    await callback.answer()

@dp.callback_query(F.data.startswith("diff_"))
async def handle_difficulty(callback: types.CallbackQuery):
    difficulty = callback.data.split("_")[1]
    
    keyboard = [
        [
            InlineKeyboardButton(text="🎴 Підкидний", callback_data=f"mode_podkidnoy_{difficulty}"),
            InlineKeyboardButton(text="🎯 Класичний", callback_data=f"mode_classic_{difficulty}")
        ],
        [
            InlineKeyboardButton(text="⚡ Швидка (24)", callback_data=f"mode_quick_{difficulty}")
        ],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="play_bot")]
    ]
    
    await callback.message.edit_text(
        "🎮 **Оберіть режим:**",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard),
        parse_mode="Markdown"
    )
    await callback.answer()

@dp.callback_query(F.data.startswith("mode_"))
async def handle_game_mode(callback: types.CallbackQuery):
    parts = callback.data.split("_")
    mode = parts[1]
    difficulty = parts[2]
    
    cards_count = 24 if mode == "quick" else 36
    actual_mode = "podkidnoy" if mode == "quick" else mode
    
    chat_id = callback.message.chat.id
    games[chat_id] = DurakGame(
        player1_id=callback.from_user.id,
        mode=actual_mode,
        difficulty=difficulty,
        player1_name=callback.from_user.username or "Ви",
        player2_name="🤖 Бот",
        cards_count=cards_count
    )
    
    await callback.message.delete()
    await send_game_state(chat_id, games[chat_id])
    await callback.answer()

@dp.callback_query(F.data == "play_multi")
async def handle_play_multi(callback: types.CallbackQuery):
    keyboard = [
        [InlineKeyboardButton(text="➕ Створити кімнату", callback_data="create_room")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back_menu")]
    ]
    
    await callback.message.edit_text(
        "👥 **Гра з другом:**\n\nСтворіть кімнату!",
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
    
    keyboard = [[InlineKeyboardButton(text="❌ Скасувати", callback_data="cancel_room")]]
    
    await callback.message.edit_text(
        f"✅ **Кімнату створено!**\n\n"
        f"🔑 Код: `{room_id}`\n\n"
        f"📤 Команда:\n`{join_command}`\n\n"
        f"⏳ Очікування...",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard),
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
    
    if room.player2_id is not None:
        await message.answer("❌ Кімната зайнята!")
        return
    
    room.player2_id = message.from_user.id
    room.player2_name = message.from_user.username or f"User{message.from_user.id}"
    
    creator_stats = get_or_create_stats(room.creator_id, room.creator_name)
    joiner_stats = get_or_create_stats(room.player2_id, room.player2_name)
    
    if room.player2_id not in creator_stats.friends_list:
        creator_stats.friends_list.append(room.player2_id)
    if room.creator_id not in joiner_stats.friends_list:
        joiner_stats.friends_list.append(room.creator_id)
    
    room.game = DurakGame(
        player1_id=room.creator_id,
        player2_id=room.player2_id,
        player1_name=room.creator_name,
        player2_name=room.player2_name
    )
    
    games[room.creator_id] = room.game
    games[room.player2_id] = room.game
    
    try:
        await bot.send_message(room.creator_id, f"✅ **{room.player2_name}** приєднався!", parse_mode="Markdown")
        await send_game_state_multiplayer(room.creator_id, room.game)
    except:
        pass
    
    await message.answer(f"✅ Приєдналися до **{room.creator_name}**!", parse_mode="Markdown")
    await send_game_state_multiplayer(room.player2_id, room.game)
    
    del rooms[room_id]

@dp.callback_query(F.data == "cancel_room")
async def handle_cancel_room(callback: types.CallbackQuery):
    to_delete = [rid for rid, r in rooms.items() if r.creator_id == callback.from_user.id]
    for rid in to_delete:
        del rooms[rid]
    
    await callback.message.edit_text(
        "❌ Скасовано",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 Назад", callback_data="play_multi")]]),
        parse_mode="Markdown"
    )
    await callback.answer()

@dp.callback_query(F.data == "my_stats")
async def handle_my_stats(callback: types.CallbackQuery):
    user_stats = get_or_create_stats(callback.from_user.id, callback.from_user.username)
    
    winrate = (user_stats.wins / user_stats.games_played * 100) if user_stats.games_played > 0 else 0
    avatar = user_stats.current_avatar if user_stats.current_avatar else "👤"
    
    achievements_text = ""
    for ach_id in user_stats.achievements[:5]:
        if ach_id in ACHIEVEMENTS:
            achievements_text += f"{ACHIEVEMENTS[ach_id]['name']}\n"
    
    if not achievements_text:
        achievements_text = "Поки немає"
    
    text = f"""
{avatar} **Профіль**

👤 {user_stats.username}
🎮 Ігор: {user_stats.games_played}
✅ Перемог: {user_stats.wins}
❌ Поразок: {user_stats.losses}
📈 Winrate: {winrate:.1f}%
⭐ Рейтинг: {user_stats.rating}
💰 Монет: {user_stats.coins}

🔥 Серія: {user_stats.win_streak}
🏆 Краща: {user_stats.best_streak}
📅 Днів: {user_stats.daily_streak}

🏅 **Досягнення:**
{achievements_text}
"""
    
    keyboard = [
        [InlineKeyboardButton(text="🏅 Всі досягнення", callback_data="all_achievements")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back_menu")]
    ]
    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard), parse_mode="Markdown")
    await callback.answer()

@dp.callback_query(F.data == "all_achievements")
async def handle_all_achievements(callback: types.CallbackQuery):
    user_stats = get_or_create_stats(callback.from_user.id, callback.from_user.username)
    
    text = "🏅 **Всі досягнення:**\n\n"
    
    for ach_id, ach_data in ACHIEVEMENTS.items():
        status = "✅" if ach_id in user_stats.achievements else "⬜"
        desc = ach_data.get("desc", "")
        reward = ach_data["reward"]
        text += f"{status} {ach_data['name']}\n"
        if desc:
            text += f"   {desc}\n"
        text += f"   💰 {reward}\n\n"
    
    keyboard = [[InlineKeyboardButton(text="🔙 Назад", callback_data="my_stats")]]
    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard), parse_mode="Markdown")
    await callback.answer()

@dp.callback_query(F.data == "leaderboard")
async def handle_leaderboard(callback: types.CallbackQuery):
    top_players = get_leaderboard()
    
    if not top_players