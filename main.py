"""
Telegram бот для гри "Дурак" (Підкидний)
Для Render.com
"""

import logging
import random
import os
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram import F
import asyncio

# Налаштування логування
logging.basicConfig(level=logging.INFO)

# Отримання токену з змінних оточення
BOT_TOKEN = os.getenv("BOT_TOKEN")

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN не знайдено! Додайте його в Environment Variables на Render")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# Масті та номінали карт
SUITS = ['♠️', '♥️', '♦️', '♣️']
RANKS = ['6', '7', '8', '9', '10', 'В', 'Д', 'К', 'Т']
RANK_VALUES = {'6': 6, '7': 7, '8': 8, '9': 9, '10': 10, 'В': 11, 'Д': 12, 'К': 13, 'Т': 14}

# Зберігання активних ігор
games = {}

class Card:
    def __init__(self, rank, suit):
        self.rank = rank
        self.suit = suit
        self.value = RANK_VALUES[rank]
    
    def __str__(self):
        return f"{self.rank}{self.suit}"
    
    def __repr__(self):
        return self.__str__()

class DurakGame:
    def __init__(self, player_id):
        self.player_id = player_id
        self.deck = self.create_deck()
        random.shuffle(self.deck)
        
        # Козирна карта
        self.trump_card = self.deck.pop()
        self.trump_suit = self.trump_card.suit
        self.deck.insert(0, self.trump_card)
        
        # Роздача карт
        self.player_hand = [self.deck.pop() for _ in range(6)]
        self.bot_hand = [self.deck.pop() for _ in range(6)]
        
        # Стіл (карти в грі)
        self.table = []  # [(атакуюча_карта, захисна_карта або None)]
        
        # Черга ходу
        self.player_turn = self.who_starts()
        self.stage = "attack"  # attack, defend, throw_in
        self.attacker_can_throw = False
        
    def create_deck(self):
        """Створює колоду з 36 карт"""
        return [Card(rank, suit) for suit in SUITS for rank in RANKS]
    
    def who_starts(self):
        """Визначає хто ходить першим (у кого менший козир)"""
        player_trumps = [c for c in self.player_hand if c.suit == self.trump_suit]
        bot_trumps = [c for c in self.bot_hand if c.suit == self.trump_suit]
        
        if not player_trumps and not bot_trumps:
            return True  # Гравець починає
        elif not bot_trumps:
            return True
        elif not player_trumps:
            return False
        
        return min(player_trumps, key=lambda x: x.value).value < min(bot_trumps, key=lambda x: x.value).value
    
    def can_beat(self, attacking_card, defending_card):
        """Чи може захисна карта побити атакуючу"""
        if defending_card.suit == attacking_card.suit:
            return defending_card.value > attacking_card.value
        return defending_card.suit == self.trump_suit
    
    def get_valid_attacks(self, hand):
        """Отримати валідні карти для атаки/підкидання"""
        if not self.table:
            return hand  # Перший хід - будь-яка карта
        
        # Можна підкидати карти того ж номіналу, що є на столі
        table_ranks = set()
        for attack, defend in self.table:
            table_ranks.add(attack.rank)
            if defend:
                table_ranks.add(defend.rank)
        
        return [c for c in hand if c.rank in table_ranks]
    
    def refill_hands(self):
        """Поповнення рук після раунду"""
        # Спочатку атакуючий
        attacker_hand = self.player_hand if self.player_turn else self.bot_hand
        defender_hand = self.bot_hand if self.player_turn else self.player_hand
        
        while len(attacker_hand) < 6 and self.deck:
            attacker_hand.append(self.deck.pop())
        
        while len(defender_hand) < 6 and self.deck:
            defender_hand.append(self.deck.pop())
    
    def game_over(self):
        """Перевірка закінчення гри"""
        if not self.deck:
            if not self.player_hand:
                return "player_win"
            if not self.bot_hand:
                return "bot_win"
        return None

def format_hand(cards):
    """Форматує карти в руці"""
    return " ".join([str(card) for card in cards])

def format_table(table):
    """Форматує карти на столі"""
    if not table:
        return "Стіл порожній"
    
    result = []
    for i, (attack, defend) in enumerate(table, 1):
        if defend:
            result.append(f"{attack} ← {defend}")
        else:
            result.append(f"{attack} ← ?")
    return "\n".join(result)

def create_card_keyboard(cards, action_prefix):
    """Створює клавіатуру з картами"""
    keyboard = []
    row = []
    for i, card in enumerate(cards):
        row.append(InlineKeyboardButton(
            text=str(card),
            callback_data=f"{action_prefix}_{i}"
        ))
        if len(row) == 4:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

async def send_game_state(chat_id, game, message=""):
    """Відправляє поточний стан гри"""
    status = f"🃏 **Гра 'Дурак'**\n\n"
    status += f"🎴 Козир: {game.trump_card}\n"
    status += f"📚 Карт у колоді: {len(game.deck)}\n\n"
    status += f"**На столі:**\n{format_table(game.table)}\n\n"
    status += f"🤖 Карт у бота: {len(game.bot_hand)}\n"
    status += f"👤 Ваші карти: {format_hand(game.player_hand)}\n\n"
    
    if message:
        status += f"📢 {message}\n\n"
    
    # Визначаємо дії
    keyboard = None
    
    if game.player_turn and game.stage == "attack":
        status += "⚔️ **Ваш хід - атакуйте!**"
        valid_cards = game.get_valid_attacks(game.player_hand)
        if valid_cards:
            keyboard = create_card_keyboard(valid_cards, "attack")
            keyboard.inline_keyboard.append([
                InlineKeyboardButton(text="✅ Завершити хід", callback_data="end_attack")
            ])
    
    elif not game.player_turn and game.stage == "defend":
        status += "🛡️ **Ваш хід - захищайтесь!**"
        # Знаходимо першу незахищену карту
        undefended = None
        for i, (attack, defend) in enumerate(game.table):
            if defend is None:
                undefended = (i, attack)
                break
        
        if undefended:
            idx, attack_card = undefended
            valid_defends = [c for c in game.player_hand if game.can_beat(attack_card, c)]
            if valid_defends:
                status += f"\n🎯 Відбийте: {attack_card}"
                keyboard = create_card_keyboard(valid_defends, f"defend_{idx}")
            
            keyboard_buttons = keyboard.inline_keyboard if keyboard else []
            keyboard_buttons.append([
                InlineKeyboardButton(text="❌ Беру", callback_data="take_cards")
            ])
            keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
    
    elif game.player_turn and game.stage == "throw_in":
        status += "🎲 **Можете підкинути карти**"
        valid_cards = game.get_valid_attacks(game.player_hand)
        if valid_cards and len(game.table) < 6:
            keyboard = create_card_keyboard(valid_cards, "throw")
        
        keyboard_buttons = keyboard.inline_keyboard if keyboard else []
        keyboard_buttons.append([
            InlineKeyboardButton(text="✅ Закінчити підкидання", callback_data="end_throw")
        ])
        keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
    
    await bot.send_message(chat_id, status, reply_markup=keyboard, parse_mode="Markdown")

async def bot_move(chat_id, game):
    """Хід бота (простий AI)"""
    await asyncio.sleep(1)  # Пауза для реалістичності
    
    if not game.player_turn and game.stage == "attack":
        # Бот атакує
        valid_attacks = game.get_valid_attacks(game.bot_hand)
        if valid_attacks and len(game.table) < len(game.player_hand):
            # Обираємо найслабшу карту
            card = min(valid_attacks, key=lambda x: (x.suit != game.trump_suit, x.value))
            game.bot_hand.remove(card)
            game.table.append((card, None))
            await send_game_state(chat_id, game, f"🤖 Бот атакує: {card}")
            
            game.stage = "defend"
            await bot_move(chat_id, game)
        else:
            # Бот завершує атаку
            game.stage = "end_round"
            await end_round(chat_id, game)
    
    elif game.player_turn and game.stage == "defend":
        # Бот захищається
        can_defend = True
        for i, (attack, defend) in enumerate(game.table):
            if defend is None:
                valid_defends = [c for c in game.bot_hand if game.can_beat(attack, c)]
                if valid_defends:
                    # Обираємо найслабшу підходящу карту
                    card = min(valid_defends, key=lambda x: (x.suit != game.trump_suit, x.value))
                    game.bot_hand.remove(card)
                    game.table[i] = (attack, card)
                else:
                    can_defend = False
                    break
        
        if can_defend:
            await send_game_state(chat_id, game, "🤖 Бот відбився!")
            game.stage = "throw_in"
            game.player_turn = True
        else:
            # Бот бере карти
            for attack, defend in game.table:
                game.bot_hand.append(attack)
                if defend:
                    game.bot_hand.append(defend)
            game.table = []
            game.player_turn = False
            game.stage = "attack"
            game.refill_hands()
            
            result = game.game_over()
            if result:
                await handle_game_over(chat_id, game, result)
            else:
                await send_game_state(chat_id, game, "🤖 Бот взяв карти")
                await bot_move(chat_id, game)

async def end_round(chat_id, game):
    """Завершення раунду"""
    game.table = []
    game.refill_hands()
    
    result = game.game_over()
    if result:
        await handle_game_over(chat_id, game, result)
    else:
        game.stage = "attack"
        if game.player_turn:
            await send_game_state(chat_id, game, "✅ Раунд завершено. Ваш хід!")
        else:
            await send_game_state(chat_id, game, "✅ Раунд завершено.")
            await bot_move(chat_id, game)

async def handle_game_over(chat_id, game, result):
    """Обробка закінчення гри"""
    if result == "player_win":
        message = "🎉 **Вітаємо! Ви перемогли!**\n\nХочете зіграти ще раз? /newgame"
    else:
        message = "😔 **Ви програли. Бот переміг!**\n\nСпробуйте ще раз! /newgame"
    
    await bot.send_message(chat_id, message, parse_mode="Markdown")
    del games[chat_id]

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    """Привітання"""
    await message.answer(
        "🃏 Вітаю в грі **Дурак**!\n\n"
        "Використовуйте /newgame для початку нової гри\n"
        "/help - правила гри",
        parse_mode="Markdown"
    )

@dp.message(Command("help"))
async def cmd_help(message: types.Message):
    """Правила гри"""
    rules = """
🃏 **Правила гри 'Дурак'**

**Мета:** Позбутися всіх карт. Хто залишиться з картами - програв (дурак).

**Правила:**
• Гра йде колодою в 36 карт (від 6 до туза)
• Визначається козирна масть
• Атакуючий кладе карту, захисник повинен побити її
• Карта б'ється старшою картою тієї ж масті або козирем
• Можна підкидати карти того ж номіналу
• Якщо захисник не може відбитися - бере всі карти зі столу

**Команди:**
/newgame - нова гра
/help - ці правила
"""
    await message.answer(rules, parse_mode="Markdown")

@dp.message(Command("newgame"))
async def cmd_new_game(message: types.Message):
    """Початок нової гри"""
    chat_id = message.chat.id
    games[chat_id] = DurakGame(message.from_user.id)
    game = games[chat_id]
    
    await send_game_state(chat_id, game, "🎮 Нова гра розпочата!")
    
    if not game.player_turn:
        await bot_move(chat_id, game)

@dp.callback_query(F.data.startswith("attack_"))
async def handle_attack(callback: types.CallbackQuery):
    """Обробка атаки гравця"""
    chat_id = callback.message.chat.id
    if chat_id not in games:
        await callback.answer("Гра не знайдена. Використайте /newgame")
        return
    
    game = games[chat_id]
    card_idx = int(callback.data.split("_")[1])
    valid_cards = game.get_valid_attacks(game.player_hand)
    
    if card_idx < len(valid_cards):
        card = valid_cards[card_idx]
        game.player_hand.remove(card)
        game.table.append((card, None))
        
        await callback.message.delete()
        game.stage = "defend"
        game.player_turn = False
        await send_game_state(chat_id, game, f"⚔️ Ви атакували: {card}")
        await bot_move(chat_id, game)
    
    await callback.answer()

@dp.callback_query(F.data.startswith("defend_"))
async def handle_defend(callback: types.CallbackQuery):
    """Обробка захисту гравця"""
    chat_id = callback.message.chat.id
    if chat_id not in games:
        await callback.answer("Гра не знайдена")
        return
    
    game = games[chat_id]
    parts = callback.data.split("_")
    table_idx = int(parts[1])
    card_idx = int(parts[2])
    
    attack_card = game.table[table_idx][0]
    valid_defends = [c for c in game.player_hand if game.can_beat(attack_card, c)]
    
    if card_idx < len(valid_defends):
        card = valid_defends[card_idx]
        game.player_hand.remove(card)
        game.table[table_idx] = (attack_card, card)
        
        await callback.message.delete()
        
        # Перевіряємо чи всі карти відбиті
        all_defended = all(defend is not None for _, defend in game.table)
        if all_defended:
            game.stage = "throw_in"
            game.player_turn = False
            await send_game_state(chat_id, game, f"🛡️ Ви відбилися: {card}")
            await bot_move(chat_id, game)
        else:
            await send_game_state(chat_id, game, f"🛡️ Відбито: {card}")
    
    await callback.answer()

@dp.callback_query(F.data == "take_cards")
async def handle_take(callback: types.CallbackQuery):
    """Гравець бере карти"""
    chat_id = callback.message.chat.id
    if chat_id not in games:
        await callback.answer("Гра не знайдена")
        return
    
    game = games[chat_id]
    
    for attack, defend in game.table:
        game.player_hand.append(attack)
        if defend:
            game.player_hand.append(defend)
    
    game.table = []
    game.player_turn = True
    game.stage = "attack"
    game.refill_hands()
    
    await callback.message.delete()
    
    result = game.game_over()
    if result:
        await handle_game_over(chat_id, game, result)
    else:
        await send_game_state(chat_id, game, "📥 Ви взяли карти")
    
    await callback.answer()

@dp.callback_query(F.data == "end_attack")
async def handle_end_attack(callback: types.CallbackQuery):
    """Завершення атаки"""
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
        game.player_turn = False
        await send_game_state(chat_id, game)
        await bot_move(chat_id, game)
    
    await callback.answer()

@dp.callback_query(F.data.startswith("throw_"))
async def handle_throw(callback: types.CallbackQuery):
    """Підкидання карт"""
    chat_id = callback.message.chat.id
    if chat_id not in games:
        await callback.answer("Гра не знайдена")
        return
    
    game = games[chat_id]
    card_idx = int(callback.data.split("_")[1])
    valid_cards = game.get_valid_attacks(game.player_hand)
    
    if card_idx < len(valid_cards):
        card = valid_cards[card_idx]
        game.player_hand.remove(card)
        game.table.append((card, None))
        
        await callback.message.delete()
        game.player_turn = False
        await send_game_state(chat_id, game, f"🎲 Ви підкинули: {card}")
        await bot_move(chat_id, game)
    
    await callback.answer()

@dp.callback_query(F.data == "end_throw")
async def handle_end_throw(callback: types.CallbackQuery):
    """Завершення підкідання"""
    chat_id = callback.message.chat.id
    if chat_id not in games:
        await callback.answer("Гра не знайдена")
        return
    
    game = games[chat_id]
    await callback.message.delete()
    await end_round(chat_id, game)
    await callback.answer()

async def main():
    """Запуск бота"""
    print("🤖 Бот запущено на Render.com!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())