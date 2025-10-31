import os import random import telebot from telebot import types

============================================

DURAK UKRAINE BOT (v2) - MULTI ATTACK MODE

============================================

🇺🇦 Гра ДУРАК ПІДКИДНИЙ для 2-4 гравців

Формат: підкидання кількома гравцями, черговість, завершення раунду.

Використовує pyTelegramBotAPI (polling mode, сумісний із Render.com)

--------------------------------------------

ФАЙЛИ:

- main.py (цей файл)

- requirements.txt → pyTelegramBotAPI==4.20.0

- Procfile → worker: python main.py

--------------------------------------------

Перед деплоєм: додайте у Render Environment variable BOT_TOKEN

============================================

BOT_TOKEN = os.getenv("BOT_TOKEN") or "PLACE_YOUR_TOKEN_HERE" bot = telebot.TeleBot(BOT_TOKEN)

=== Ігрові дані ===

games = {}  # chat_id: {players, deck, trump, field, hands, attacker_index, defender_index, status}

suits = ['♠', '♥', '♦', '♣'] ranks = ['6', '7', '8', '9', '10', 'J', 'Q', 'K', 'A']

=== Генерація колоди ===

def create_deck(): return [f"{r}{s}" for s in suits for r in ranks]

=== Роздача ===

def deal_cards(deck, count=6): hand = [] for _ in range(count): if deck: hand.append(deck.pop()) return hand

=== Початок гри ===

@bot.message_handler(commands=['start']) def start_cmd(msg): bot.send_message(msg.chat.id, "🎴 Вітаю у Дурак Україна!\nНатисни /join щоб приєднатися до гри.", parse_mode="Markdown")

@bot.message_handler(commands=['join']) def join_cmd(msg): chat_id = msg.chat.id user = msg.from_user.first_name

if chat_id not in games:
    games[chat_id] = {
        'players': [],
        'deck': [],
        'trump': None,
        'field': [],
        'hands': {},
        'attacker_index': 0,
        'defender_index': 1,
        'status': 'waiting'
    }

game = games[chat_id]
if user not in game['players']:
    game['players'].append(user)
    bot.send_message(chat_id, f"👤 {user} приєднався до гри.")

if len(game['players']) >= 2:
    btn = types.InlineKeyboardButton("🎮 Почати гру", callback_data="begin_game")
    bot.send_message(chat_id, "Готові?", reply_markup=types.InlineKeyboardMarkup([[btn]]))

@bot.callback_query_handler(func=lambda c: c.data == 'begin_game') def begin_game(call): chat_id = call.message.chat.id game = games.get(chat_id) if not game: return

game['deck'] = create_deck()
random.shuffle(game['deck'])
game['trump'] = game['deck'][-1][-1]  # остання карта визначає козир

for player in game['players']:
    game['hands'][player] = deal_cards(game['deck'])

game['status'] = 'active'
attacker = game['players'][game['attacker_index']]
defender = game['players'][game['defender_index']]

bot.send_message(chat_id, f"🃏 Гра почалася! Козир: {game['trump']}\nАтакує: {attacker}\nОбороняється: {defender}")
show_hand(chat_id, attacker)

=== Показати руку ===

@bot.message_handler(commands=['hand']) def show_hand_cmd(msg): show_hand(msg.chat.id, msg.from_user.first_name)

def show_hand(chat_id, player): game = games.get(chat_id) if not game: return hand = game['hands'].get(player, []) bot.send_message(chat_id, f"{player}, твої карти: {', '.join(hand)}")

=== Ходи через кнопки ===

def make_turn_kb(attacker, defender): kb = types.InlineKeyboardMarkup() kb.add( types.InlineKeyboardButton("🗡️ Підкинути", callback_data=f"attack_{attacker}"), types.InlineKeyboardButton("🛡️ Захиститись", callback_data=f"defend_{defender}"), types.InlineKeyboardButton("🙅‍♂️ Взяти", callback_data=f"take_{defender}"), types.InlineKeyboardButton("✅ Завершити хід", callback_data="end_turn") ) return kb

=== Обробка підкидання ===

@bot.callback_query_handler(func=lambda c: c.data.startswith('attack_')) def attack_cb(call): chat_id = call.message.chat.id player = call.data.split('_')[1] game = games.get(chat_id) if not game or game['status'] != 'active': return

if player not in game['players']:
    bot.answer_callback_query(call.id, "Ти не у грі!")
    return

if player == game['players'][game['defender_index']]:
    bot.answer_callback_query(call.id, "Ти обороняєшся!")
    return

show_hand(chat_id, player)
bot.send_message(chat_id, f"{player}, яку карту хочеш підкинути? Напиши назву (наприклад 9♠)")

=== Введення карти ===

@bot.message_handler(func=lambda m: any(s in m.text for s in suits)) def handle_card_input(msg): chat_id = msg.chat.id player = msg.from_user.first_name game = games.get(chat_id) if not game or game['status'] != 'active': return

card = msg.text.strip()
if card not in game['hands'].get(player, []):
    bot.send_message(chat_id, "У тебе немає такої карти!")
    return

game['hands'][player].remove(card)
game['field'].append({'player': player, 'card': card})
bot.send_message(chat_id, f"{player} підкинув {card}.")

=== Завершення ходу ===

@bot.callback_query_handler(func=lambda c: c.data == 'end_turn') def end_turn(call): chat_id = call.message.chat.id game = games.get(chat_id) if not game: return

bot.send_message(chat_id, f"Хід завершено. Поле: {', '.join([x['card'] for x in game['field']])}")

# очищення поля, перехід ролей
game['field'] = []
game['attacker_index'] = (game['attacker_index'] + 1) % len(game['players'])
game['defender_index'] = (game['attacker_index'] + 1) % len(game['players'])

next_attacker = game['players'][game['attacker_index']]
next_defender = game['players'][game['defender_index']]

bot.send_message(chat_id, f"➡️ Наступний хід: атакує {next_attacker}, обороняється {next_defender}")

bot.infinity_polling()