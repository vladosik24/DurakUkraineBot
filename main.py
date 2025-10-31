"""
Telegram бот для гри "Дурак" - МАКСИМАЛЬНА ВЕРСІЯ
Усі функції: турніри, історія, досягнення, магазин, друзі, щоденні завдання
"""

import logging
import random
import os
import json
from datetime import datetime, timedelta
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
friends = {}

# Досягнення
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

# Магазин аватарів
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
        self.current_avatar =     text = f"""
{avatar} **Профіль гравця**

👤 {user_stats.username}
🎮 Ігор: {user_stats.games_played}
✅ Перемог: {user_stats.wins}
❌ Поразок: {user_stats.losses}
📈 Winrate: {winrate:.1f}%
⭐ Рейтинг: {user_stats.rating}
💰 Монет: {user_stats.coins}

🔥 Поточна серія: {user_stats.win_streak}
🏆 Краща серія: {user_stats.best_streak}
📅 Днів поспіль: {user_stats.daily_streak}

🏅 **Досягнення ({len(user_stats.achievements)}):**
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
        text += f"   💰 Нагорода: {reward} монет\n\n"
    
    keyboard = [[InlineKeyboardButton(text="🔙 Назад", callback_data="my_stats")]]
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
    
    user_id = callback.from_user.id
    user_position = None
    
    for i, player in enumerate(top_players):
        medal = medals[i] if i < 3 else f"{i+1}."
        winrate = (player.wins / player.games_played * 100) if player.games_played > 0 else 0
        
        name = player.username
        if player.user_id == user_id:
            name = f"**{name}** ⬅️"
            user_position = i + 1
        
        text += f"{medal} {name}\n"
        text += f"   ⭐ {player.rating} | {player.wins}W/{player.losses}L ({winrate:.0f}%)\n\n"
    
    if user_position:
        text += f"\n📍 **Ваша позиція: #{user_position}**"
    
    keyboard = [[InlineKeyboardButton(text="🔙 Назад", callback_data="back_menu")]]
    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard), parse_mode="Markdown")
    await callback.answer()

@dp.callback_query(F.data == "shop_menu")
async def handle_shop_menu(callback: types.CallbackQuery):
    user_stats = get_or_create_stats(callback.from_user.id, callback.from_user.username)
    
    text = f"🛒 **Магазин**\n\n💰 Ваші монети: {user_stats.coins}\n\n"
    text += "**Доступні товари:**\n\n"
    
    keyboard = []
    for item_id, item_data in SHOP_ITEMS.items():
        if item_id not in user_stats.items:
            text += f"{item_data['name']} - 💰 {item_data['price']}\n"
            keyboard.append([InlineKeyboardButton(
                text=f"Купити {item_data['name']}",
                callback_data=f"buy_{item_id}"
            )])
    
    keyboard.append([InlineKeyboardButton(text="🔙 Назад", callback_data="back_menu")])
    
    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard), parse_mode="Markdown")
    await callback.answer()

@dp.callback_query(F.data.startswith("buy_"))
async def handle_buy_item(callback: types.CallbackQuery):
    item_id = callback.data.replace("buy_", "")
    user_stats = get_or_create_stats(callback.from_user.id, callback.from_user.username)
    
    if item_id not in SHOP_ITEMS:
        await callback.answer("❌ Товар не знайдено", show_alert=True)
        return
    
    item = SHOP_ITEMS[item_id]
    
    if item_id in user_stats.items:
        await callback.answer("❌ Ви вже маєте цей товар", show_alert=True)
        return
    
    if user_stats.coins < item["price"]:
        await callback.answer(f"❌ Недостатньо монет! Потрібно: {item['price']}", show_alert=True)
        return
    
    user_stats.coins -= item["price"]
    user_stats.items.append(item_id)
    
    if item["type"] == "avatar":
        user_stats.current_avatar = item["name"].split()[0]
    
    await callback.answer(f"✅ Куплено: {item['name']}!", show_alert=True)
    await handle_shop_menu(callback)

@dp.callback_query(F.data == "daily_tasks_menu")
async def handle_daily_tasks(callback: types.CallbackQuery):
    user_stats = get_or_create_stats(callback.from_user.id, callback.from_user.username)
    tasks = get_or_create_daily_tasks(callback.from_user.id)
    
    text = "📅 **Щоденні завдання**\n\n"
    
    for task_name, task_data in tasks.tasks.items():
        status = "✅" if task_data["completed"] else f"{task_data['progress']}/{task_data['target']}"
        
        task_names = {
            "play_3_games": "🎮 Зіграти 3 гри",
            "win_2_games": "🏆 Виграти 2 гри",
            "win_vs_hard": "💪 Перемогти важкого бота"
        }
        
        text += f"{status} {task_names[task_name]}\n"
        text += f"   💰 Нагорода: {task_data['reward']} монет\n\n"
    
    keyboard = [[InlineKeyboardButton(text="🔙 Назад", callback_data="back_menu")]]
    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard), parse_mode="Markdown")
    await callback.answer()

@dp.callback_query(F.data == "friends_menu")
async def handle_friends_menu(callback: types.CallbackQuery):
    user_stats = get_or_create_stats(callback.from_user.id, callback.from_user.username)
    
    text = f"👫 **Друзі ({len(user_stats.friends_list)})**\n\n"
    
    if user_stats.friends_list:
        for friend_id in user_stats.friends_list[:10]:
            if friend_id in stats:
                friend = stats[friend_id]
                text += f"👤 {friend.username} (⭐ {friend.rating})\n"
    else:
        text += "У вас поки немає друзів.\nГрайте з іншими гравцями щоб додати їх!"
    
    keyboard = [[InlineKeyboardButton(text="🔙 Назад", callback_data="back_menu")]]
    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard), parse_mode="Markdown")
    await callback.answer()

@dp.callback_query(F.data == "game_history")
async def handle_game_history(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    
    if user_id not in game_history or not game_history[user_id]:
        await callback.answer("У вас поки немає історії ігор", show_alert=True)
        return
    
    text = "📜 **Історія ігор (останні 10):**\n\n"
    
    for game in reversed(game_history[user_id][-10:]):
        result = "✅ Перемога" if game.winner_id == user_id else "❌ Поразка"
        opponent_id = game.player2_id if game.player1_id == user_id else game.player1_id
        opponent_name = "Бот" if opponent_id is None else (stats[opponent_id].username if opponent_id in stats else "Гравець")
        
        minutes = game.duration // 60
        seconds = game.duration % 60
        
        text += f"{result} проти {opponent_name}\n"
        text += f"   ⏱️ {minutes}:{seconds:02d} | Режим: {game.mode}\n\n"
    
    keyboard = [[InlineKeyboardButton(text="🔙 Назад", callback_data="back_menu")]]
    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard), parse_mode="Markdown")
    await callback.answer()

@dp.callback_query(F.data == "tournaments_menu")
async def handle_tournaments_menu(callback: types.CallbackQuery):
    text = "🎯 **Турніри**\n\n"
    
    active_tournaments = [t for t in tournaments.values() if t.status == "waiting"]
    
    if active_tournaments:
        text += "**Активні турніри:**\n"
        for t in active_tournaments:
            text += f"🏆 {t.name}\n"
            text += f"   👥 Гравців: {len(t.players)}/8\n\n"
    else:
        text += "Немає активних турнірів.\nСтворіть свій!"
    
    keyboard = [
        [InlineKeyboardButton(text="➕ Створити турнір", callback_data="create_tournament")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back_menu")]
    ]
    
    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard), parse_mode="Markdown")
    await callback.answer()

@dp.callback_query(F.data == "create_tournament")
async def handle_create_tournament(callback: types.CallbackQuery):
    tournament_id = f"t_{callback.from_user.id}_{int(datetime.now().timestamp())}"
    tournament_name = f"Турнір {callback.from_user.username}"
    
    tournaments[tournament_id] = Tournament(tournament_id, tournament_name, callback.from_user.id)
    tournaments[tournament_id].add_player(callback.from_user.id, callback.from_user.username)
    
    text = f"✅ **Турнір створено!**\n\n"
    text += f"🏆 {tournament_name}\n"
    text += f"👥 Гравців: 1/8\n\n"
    text += f"Код для приєднання:\n`/join_tournament_{tournament_id}`"
    
    keyboard = [
        [InlineKeyboardButton(text="▶️ Почати турнір", callback_data=f"start_tournament_{tournament_id}")],
        [InlineKeyboardButton(text="❌ Скасувати", callback_data="cancel_tournament")]
    ]
    
    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard), parse_mode="Markdown")
    await callback.answer("Турнір створено!")

@dp.callback_query(F.data == "help")
async def handle_help(callback: types.CallbackQuery):
    rules = """
🃏 **Правила гри 'Дурак'**

**Мета:** Позбутися всіх карт.

**Правила:**
• Колода: 36 або 24 карти
• Козирна масть
• Атакуючий кладе карту
• Захисник бʼє старшою або козирем
• Можна підкидати карти

**Режими:**
🎴 **Підкидний** - можна підкидати
🎯 **Класичний** - тільки атака/захист
⚡ **Швидка гра** - 24 карти

**Складність ботів:**
🟢 **Легкий** - випадкові ходи
🟡 **Середній** - економить карти
🔴 **Важкий** - використовує стратегію

**Як заробляти монети:**
• +50 за перемогу
• +10 за гру
• Досягнення
• Щоденні завдання

**Команди:**
/menu - головне меню
/stats - статистика
"""
    keyboard = [[InlineKeyboardButton(text="🔙 Назад", callback_data="back_menu")]]
    await callback.message.edit_text(rules, reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard), parse_mode="Markdown")
    await callback.answer()

@dp.callback_query(F.data == "back_menu")
async def handle_back_menu(callback: types.CallbackQuery):
    await callback.message.edit_text("🃏 **Головне меню:**", reply_markup=get_main_menu(), parse_mode="Markdown")
    await callback.answer()

async def send_game_state(chat_id, game, message=""):
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
        status += "🛡️ **Захищайтесь!**"
        undefended = None
        for i, (attack, defend) in enumerate(game.table):
            if defend is None:
                undefended = (i, attack)
                break
        
        if undefended:
            idx, attack_card = undefended
            valid_defends = [c for c in player_hand if game.can_beat(attack_card, c)]
            if valid_defends:
                status += f"\n🎯 Відбійте: {attack_card}"
                keyboard = create_card_keyboard(valid_defends, f"defend_{idx}")
            
            keyboard_buttons = keyboard.inline_keyboard if keyboard else []
            keyboard_buttons.append([InlineKeyboardButton(text="❌ Беру", callback_data="take_cards")])
            keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
    
    elif is_attacker and game.stage == "throw_in":
        status += "🎲 **Можете підкинути**"
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
    await asyncio.sleep(1.5)
    
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
    duration = game.get_duration()
    
    # Оновлення щоденних завдань
    tasks = get_or_create_daily_tasks(game.player1_id)
    tasks.update_task("play_3_games")
    
    if game.is_multiplayer:
        winner_stats = get_or_create_stats(winner_id, "")
        loser_id = game.get_opponent_id(winner_id)
        loser_stats = get_or_create_stats(loser_id, "")
        
        winner_stats.win()
        loser_stats.lose()
        
        # Історія гри
        add_game_history(game.player1_id, game.player2_id, winner_id, duration, game.mode)
        
        # Щоденні завдання
        winner_tasks = get_or_create_daily_tasks(winner_id)
        winner_tasks.update_task("win_2_games")
        
        winner_name = game.player1_name if winner_id == game.player1_id else game.player2_name
        loser_name = game.player2_name if winner_id == game.player1_id else game.player1_name
        
        winner_msg = f"🎉 **Перемога над {loser_name}!**\n\n"
        winner_msg += f"⭐ Рейтинг: {winner_stats.rating} (+25)\n"
        winner_msg += f"💰 Монет: +50\n"
        winner_msg += f"🔥 Серія: {winner_stats.win_streak}"
        
        # Перевірка нових досягнень
        new_achievements = winner_stats._check_achievements()
        if new_achievements:
            winner_msg += f"\n\n🏅 **Нові досягнення:**\n"
            for ach_id in new_achievements:
                winner_msg += f"{ACHIEVEMENTS[ach_id]['name']}\n"
        
        loser_msg = f"😔 **Поразка від {winner_name}**\n\n⭐ Рейтинг: {loser_stats.rating} (-15)\n💰 Монет: +10"
        
        keyboard = [
            [InlineKeyboardButton(text="📊 Профіль", callback_data="my_stats")],
            [InlineKeyboardButton(text="🏠 Меню", callback_data="back_menu")]
        ]
        
        await bot.send_message(winner_id, winner_msg, reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard), parse_mode="Markdown")
        await bot.send_message(loser_id, loser_msg, reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard), parse_mode="Markdown")
        
        if game.player1_id in games:
            del games[game.player1_id]
        if game.player2_id in games:
            del games[game.player2_id]
    else:
        user_stats = get_or_create_stats(game.player1_id, "")
        
        if winner_id == game.player1_id:
            user_stats.win()
            
            # Щоденні завдання
            tasks.update_task("win_2_games")
            if game.difficulty == "hard":
                reward = tasks.update_task("win_vs_hard")
                if reward > 0:
                    user_stats.coins += reward
            
            message = f"🎉 **Вітаємо! Перемога!**\n\n"
            message += f"⭐ Рейтинг: {user_stats.rating} (+25)\n"
            message += f"💰 Монет: +50\n"
            message += f"🔥 Серія: {user_stats.win_streak}\n"
            
            # Нові досягнення
            new_achievements = user_stats._check_achievements()
            if new_achievements:
                message += f"\n🏅 **Нові досягнення:**\n"
                for ach_id in new_achievements:
                    ach = ACHIEVEMENTS[ach_id]
                    message += f"{ach['name']} (+{ach['reward']} 💰)\n"
        else:
            user_stats.lose()
            message = f"😔 **Поразка**\n\n⭐ Рейтинг: {user_stats.rating} (-15)\n💰 Монет: +10"
        
        # Історія
        add_game_history(game.player1_id, None, winner_id, duration, game.mode)
        
        message += f"\n\n📊 Загально: {user_stats.wins}W / {user_stats.losses}L"
        
        keyboard = [
            [InlineKeyboardButton(text="🔄 Нова гра", callback_data=f"diff_{game.difficulty}")],
            [InlineKeyboardButton(text="📊 Профіль", callback_data="my_stats")],
            [InlineKeyboardButton(text="🏠 Меню", callback_data="back_menu")]
        ]
        
        await bot.send_message(chat_id, message, reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard), parse_mode="Markdown")
        del games[chat_id]

# Обробники ходів
@dp.callback_query(F.data.startswith("attack_"))
async def handle_attack(callback: types.CallbackQuery):
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
            await send_game_state_multiplayer(opponent_id, game, "✅ Противник взяв. Ваш хід!")
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
    print("🤖 МАКСИМАЛЬНА версія бота 'Дурак' запущена!")
    print("✅ Функції: статистика, рейтинг, досягнення, multiplayer, турніри")
    print("✅ Щоденні завдання, магазин, друзі, історія ігор, 3 складності")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
        self.friends_list = []
        self.win_streak = 0
        self.best_streak = 0
        self.last_played = None
        self.daily_streak = 0
        self.total_playtime = 0
    
    def win(self):
        self.wins += 1
        self.games_played += 1
        self.rating += 25
        self.coins += 50
        self.win_streak += 1
        self.best_streak = max(self.best_streak, self.win_streak)
        self.last_played = datetime.now().isoformat()
        self._check_achievements()
    
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
    
    def start_tournament(self):
        if len(self.players) >= 4:
            random.shuffle(self.players)
            self.status = "active"
            self._create_bracket()
            return True
        return False
    
    def _create_bracket(self):
        self.bracket = {}
        for i in range(0, len(self.players), 2):
            match_id = i // 2
            self.bracket[match_id] = {
                "player1": self.players[i],
                "player2": self.players[i+1] if i+1 < len(self.players) else None,
                "winner": None
            }

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
        
        # Вибір колоди
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
            else:  # hard
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
    
    # Тримаємо тільки останні 20 ігор
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
            InlineKeyboardButton(text="📅 Щоденні завдання", callback_data="daily_tasks_menu")
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
            InlineKeyboardButton(text="📜 Історія ігор", callback_data="game_history"),
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
            InlineKeyboardButton(text="⚡ Швидка гра (24 карти)", callback_data=f"mode_quick_{difficulty}")
        ],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="play_bot")]
    ]
    
    await callback.message.edit_text(
        "🎮 **Оберіть режим гри:**",
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
        [InlineKeyboardButton(text="👫 Запросити друга", callback_data="invite_friend")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back_menu")]
    ]
    
    await callback.message.edit_text(
        "👥 **Гра з другом:**\n\nСтворіть кімнату та поділіться кодом!",
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
        f"📤 Поділіться командою:\n`{join_command}`\n\n"
        f"⏳ Очікування гравця...",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard),
        parse_mode="Markdown"
    )
    await callback.answer("Кімнату створено!")

@dp.message(F.text.startswith("/join_"))
async def cmd_join_room(message: types.Message):
    room_id = message.text.replace("/join_", "")
    
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
    
    # Додаємо один одного в друзі
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
        await bot.send_message(
            room.creator_id,
            f"✅ **{room.player2_name}** приєднався!\n\nГра починається!",
            parse_mode="Markdown"
        )
        await send_game_state_multiplayer(room.creator_id, room.game)
    except:
        pass
    
    await message.answer(
        f"✅ Ви приєдналися до **{room.creator_name}**!\n\nГра починається!",
        parse_mode="Markdown"
    )
    await send_game_state_multiplayer(room.player2_id, room.game)
    
    del rooms[room_id]

@dp.callback_query(F.data == "cancel_room")
async def handle_cancel_room(callback: types.CallbackQuery):
    to_delete = [rid for rid, r in rooms.items() if r.creator_id == callback.from_user.id]
    for rid in to_delete:
        del rooms[rid]
    
    await callback.message.edit_text(
        "❌ Кімнату скасовано",
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
{avatar} **Профіль гравця**

👤 {user_stats.username}
🎮 Ігор: {user_stats.games_played}
✅ Перемог: {user_stats.wins}