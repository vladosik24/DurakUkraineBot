""" DurakUkraineBot — main.py

Потрібні файли та інструкції (вклади у репозиторій):

requirements.txt: pyTelegramBotAPI==4.20.0

Procfile: worker: python main.py


Перед деплоєм на Render.com додайте в Environment variables:

BOT_TOKEN = <токен від @BotFather>


--- Короткий опис --- Цей файл реалізує Telegram-бота для гри "Дурак (підкидний)" з підтримкою:

режимів: 1 на 1 та мульти (2-4 гравці)

інлайн-кнопок для гри (показ руки, підкидання, захист, взяти)

повідомленнями українською

карти як текст: '10♠', 'A♥' і т.д.


--- Обмеження/Примітки ---

Правила спрощені для зрозумілості: у ходу атакує тільки один гравець; інші гравці (окрім захисника) не підкидають одночасно.

Повна ідеальна симуляція підкидного (коли кілька атакуючих підкидають в один хід) може бути додана в наступному оновленні.


"""

import os import random import logging import telebot from telebot import types

Налаштування логування

logging.basicConfig(level=logging.INFO) logger = logging.getLogger(name)

Токен з ENV

BOT_TOKEN = os.getenv('BOT_TOKEN', 'YOUR_TELEGRAM_BOT_TOKEN') bot = telebot.TeleBot(BOT_TOKEN, parse_mode=None)

Карти

SUITS = ['♠', '♥', '♦', '♣'] RANKS = ['6', '7', '8', '9', '10', 'J', 'Q', 'K', 'A'] MAX_HAND = 6

Ігри зберігаються по chat_id

games = {}

--- Утиліти для карт ---

def create_deck(): return [r + s for s in SUITS for r in RANKS]

def card_rank(card): # повертає індекс рангу r = card[:-1] return RANKS.index(r)

def card_suit(card): return card[-1]

--- Клас гри ---

class DurakGame: def init(self, chat_id, max_players=2): self.chat_id = chat_id self.players = []  # список dict: {id, name, hand} self.max_players = max_players self.deck = [] self.trump = None self.trump_card = None self.attacker_idx = 0 self.defender_idx = 1 self.table = []  # список пар (attack_card, defend_card_or_None) self.started = False

def add_player(self, user):
    if self.started:
        return False, 'Гра вже почалась'
    if any(p['id'] == user.id for p in self.players):
        return False, 'Ти вже в лобі'
    if len(self.players) >= self.max_players:
        return False, 'Лобі повне'
    self.players.append({'id': user.id, 'name': user.first_name, 'hand': []})
    return True, 'Додано'

def remove_player(self, user_id):
    self.players = [p for p in self.players if p['id'] != user_id]

def start(self):
    # старт гри — тасує, роздає, встановлює козир
    self.deck = create_deck()
    random.shuffle(self.deck)
    # остання карта визначає козир (виберемо останню)
    self.trump_card = self.deck[-1]
    self.trump = card_suit(self.trump_card)

    # роздати по MAX_HAND
    for _ in range(MAX_HAND):
        for p in self.players:
            if self.deck:
                p['hand'].append(self.deck.pop(0))
    self.started = True
    self.attacker_idx = 0
    self.defender_idx = 1 % len(self.players)
    self.table = []

def get_player_by_id(self, user_id):
    for p in self.players:
        if p['id'] == user_id:
            return p
    return None

def deal_to_player(self, p):
    while len(p['hand']) < MAX_HAND and self.deck:
        p['hand'].append(self.deck.pop(0))

def refill_all(self):
    # після ходу, кожному по черзі добираємо до 6
    order = list(range(self.attacker_idx, self.attacker_idx + len(self.players)))
    for i in order:
        idx = i % len(self.players)
        self.deal_to_player(self.players[idx])

def next_turn(self):
    # пересунути індекси
    self.attacker_idx = (self.attacker_idx + 1) % len(self.players)
    self.defender_idx = (self.attacker_idx + 1) % len(self.players)
    self.table = []

def is_player_turn_attacker(self, user_id):
    return self.players[self.attacker_idx]['id'] == user_id

def is_player_turn_defender(self, user_id):
    return self.players[self.defender_idx]['id'] == user_id

def play_attack(self, user_id, card):
    # атакувати — додаємо карту на стіл
    p = self.get_player_by_id(user_id)
    if not p:
        return False, 'Ти не в грі'
    if not self.is_player_turn_attacker(user_id):
        return False, 'Не твій хід атакувати'
    if card not in p['hand']:
        return False, 'У тебе немає такої карти'
    # обмеження: кількість атак не більше MAX_HAND та не більше ніж у захисника
    if len(self.table) >= MAX_HAND:
        return False, 'Максимум атак досягнуто'
    p['hand'].remove(card)
    self.table.append([card, None])
    return True, 'Зіграно'

def play_defend(self, user_id, attack_card, defend_card):
    # захисник намагається побити конкретну карту
    if not self.is_player_turn_defender(user_id):
        return False, 'Ти не захисник'
    p = self.get_player_by_id(user_id)
    if defend_card not in p['hand']:
        return False, 'У тебе немає такої карти'
    # знайти відповідний рядок у таблиці
    for row in self.table:
        if row[0] == attack_card and row[1] is None:
            # можна побити: якщо та ж масть і більший ранг або козир проти некозирки
            if can_beat(attack_card, defend_card, self.trump):
                p['hand'].remove(defend_card)
                row[1] = defend_card
                return True, 'Побито'
            else:
                return False, 'Ця карта не б'є'
    return False, 'На столі немає такої атаки або вона вже побита'

def take_cards(self, user_id):
    # захисник бере всі карти зі столу
    if not self.is_player_turn_defender(user_id):
        return False, 'Ти не захисник'
    p = self.get_player_by_id(user_id)
    # забираємо всі карти, які наразі на столі (атакуючі і оборонні)
    for a, d in self.table:
        p['hand'].append(a)
        if d:
            p['hand'].append(d)
    self.table = []
    # захисник добирає після взяття (разом з іншими гравцями — після завершення ходу викликається refill)
    return True, 'Взяв карти'

def all_attacks_beaten(self):
    # перевірити чи всі атаковані карти побиті
    if not self.table:
        return True
    return all(d is not None for a, d in self.table)

def get_table_text(self):
    if not self.table:
        return 'Порожній стіл.'
    rows = []
    for a, d in self.table:
        if d:
            rows.append(f"{a} → {d}")
        else:
            rows.append(f"{a} → _")
    return '\n'.join(rows)

--- Логіка бою карт ---

def can_beat(attack_card, defend_card, trump): # повертає True якщо defend_card б'є attack_card a_rank = card_rank(attack_card) d_rank = card_rank(defend_card) a_suit = card_suit(attack_card) d_suit = card_suit(defend_card) if d_suit == a_suit and d_rank > a_rank: return True # якщо захисник козир і атакуючий не козир if d_suit == trump and a_suit != trump: return True return False

--- Хелпери для UI ---

def hand_keyboard(player): kb = types.InlineKeyboardMarkup() # кожна карта — окрема кнопка buttons = [types.InlineKeyboardButton(text=c, callback_data=f'card:{c}') for c in player['hand']] # розбити на рядки по 4 row = [] for i, b in enumerate(buttons, 1): row.append(b) if i % 4 == 0: kb.row(*row) row = [] if row: kb.row(*row) return kb

def action_keyboard(game: DurakGame, user_id): kb = types.InlineKeyboardMarkup() # Доступні дії залежать від ролі if game.is_player_turn_attacker(user_id): kb.add(types.InlineKeyboardButton('Підкинути карту', callback_data='action:attack')) kb.add(types.InlineKeyboardButton('Завершити хід', callback_data='action:end_attack')) elif game.is_player_turn_defender(user_id): kb.add(types.InlineKeyboardButton('Захищатись (вибрати карту)', callback_data='action:defend')) kb.add(types.InlineKeyboardButton('Взяти карти', callback_data='action:take')) else: kb.add(types.InlineKeyboardButton('Дивитись свою руку', callback_data='action:hand')) return kb

--- Команди ---

@bot.message_handler(commands=['start']) def cmd_start(message): chat_id = message.chat.id # створити нову гру-лобі з дефолтним макс гравців =2 (будемо давати вибір) games[chat_id] = DurakGame(chat_id, max_players=2) bot.send_message(chat_id, '🃏 Лобі створено!\nНапишіть /join щоб приєднатись.\n\nЯкщо хочете гру до 4 гравців - використайте /setmode 4')

@bot.message_handler(commands=['setmode']) def cmd_setmode(message): chat_id = message.chat.id args = message.text.split() if len(args) < 2: bot.send_message(chat_id, 'Вкажіть кількість гравців: /setmode 2 або /setmode 4') return try: n = int(args[1]) if n not in (2, 3, 4): raise ValueError except: bot.send_message(chat_id, 'Допустимі значення: 2, 3, 4') return g = games.get(chat_id) if not g: g = DurakGame(chat_id, max_players=n) games[chat_id] = g else: if g.started: bot.send_message(chat_id, 'Гра вже почалась — не можна міняти режим') return g.max_players = n bot.send_message(chat_id, f'Режим встановлено: до {n} гравців')

@bot.message_handler(commands=['join']) def cmd_join(message): chat_id = message.chat.id user = message.from_user g = games.get(chat_id) if not g: g = DurakGame(chat_id, max_players=2) games[chat_id] = g ok, msg = g.add_player(user) if not ok: bot.send_message(chat_id, msg) return bot.send_message(chat_id, f'✅ {user.first_name} приєднався. ({len(g.players)}/{g.max_players})') if len(g.players) == g.max_players: bot.send_message(chat_id, 'Лобі повне — використайте /begin щоб розпочати гру або чекати поки хтось інший не підключиться')

@bot.message_handler(commands=['leave']) def cmd_leave(message): chat_id = message.chat.id user = message.from_user g = games.get(chat_id) if not g: bot.send_message(chat_id, 'Немає активного лобі') return g.remove_player(user.id) bot.send_message(chat_id, f'{user.first_name} вийшов з лобі')

@bot.message_handler(commands=['begin']) def cmd_begin(message): chat_id = message.chat.id g = games.get(chat_id) if not g: bot.send_message(chat_id, 'Спочатку створіть лобі /start') return if len(g.players) < 2: bot.send_message(chat_id, 'Потрібно щонайменше 2 гравці щоб почати') return g.start() # повідомити чат bot.send_message(chat_id, f"🎮 Гра почалась! Козир: {g.trump_card}.\nАтакує: {g.players[g.attacker_idx]['name']} — Захисник: {g.players[g.defender_idx]['name']}") # розіслати руки приватно for p in g.players: try: bot.send_message(p['id'], f"🃏 Твоя рука: {', '.join(p['hand'])}") bot.send_message(p['id'], 'Вибери дію:', reply_markup=action_keyboard(g, p['id'])) except Exception as e: logger.exception('Не вдалося надіслати приватне повідомлення')

@bot.message_handler(commands=['hand']) def cmd_hand(message): # показати руку гравцю (приватне повідомлення) user = message.from_user for g in games.values(): p = g.get_player_by_id(user.id) if p: try: bot.send_message(user.id, f"🃏 Твоя рука: {', '.join(p['hand'])}", reply_markup=hand_keyboard(p)) except: bot.send_message(message.chat.id, 'Не вдалось надіслати особисте повідомлення — запустіть чат зі мною і натисніть Start') return bot.send_message(message.chat.id, 'Ти не в грі')

--- Обробка callback (інлайн кнопок) ---

@bot.callback_query_handler(func=lambda c: True) def callback_handler(call: types.CallbackQuery): data = call.data user = call.from_user chat_id = call.message.chat.id

# знайти гру, в якій бере участь цей користувач
game = None
for g in games.values():
    if g.get_player_by_id(user.id):
        game = g
        break
if not game:
    bot.answer_callback_query(call.id, 'Ти не в грі або сесія закінчена')
    return

try:
    if data.startswith('card:'):
        card = data.split(':', 1)[1]
        # залежно від ролі — або атакуємо або захищаємо
        if game.is_player_turn_attacker(user.id):
            ok, msg = game.play_attack(user.id, card)
            bot.answer_callback_query(call.id, msg)
            # оновити повідомлення в чаті
            bot.send_message(game.chat_id, f"🟢 {user.first_name} атакував картою {card}\n\nСтіл:\n{game.get_table_text()}")
            # повідомити всіх учасників
            notify_players_after_action(game)
        elif game.is_player_turn_defender(user.id):
            # якщо натиснув карту під час захисту — треба вказати яку атаку б'ємо
            # якщо є незакриті атаки — дозволимо бити першу незакриту
            pending = None
            for a, d in game.table:
                if d is None:
                    pending = a
                    break
            if not pending:
                bot.answer_callback_query(call.id, 'Немає відкритих атак для побиття')
                return
            ok, msg = game.play_defend(user.id, pending, card)
            bot.answer_callback_query(call.id, msg)
            if ok:
                bot.send_message(game.chat_id, f"🛡️ {user.first_name} побив {pending} картoю {card}\n\nСтіл:\n{game.get_table_text()}")
                notify_players_after_action(game)
            else:
                # Нічого не змінюємо
                pass
        else:
            bot.answer_callback_query(call.id, 'Зараз не твоя дія для цієї кнопки')

    elif data.startswith('action:'):
        action = data.split(':', 1)[1]
        if action == 'attack':
            # показати руку атакуючому для вибору карти
            p = game.get_player_by_id(user.id)
            bot.answer_callback_query(call.id, 'Оберіть карту для атаки')
            bot.send_message(user.id, f"🃏 Оберіть карту для атаки: {', '.join(p['hand'])}", reply_markup=hand_keyboard(p))
        elif action == 'defend':
            p = game.get_player_by_id(user.id)
            bot.answer_callback_query(call.id, 'Оберіть карту для захисту')
            bot.send_message(user.id, f"🃏 Оберіть карту для захисту: {', '.join(p['hand'])}", reply_markup=hand_keyboard(p))
        elif action == 'take':
            ok, msg = game.take_cards(user.id)
            bot.answer_callback_query(call.id, msg)
            if ok:
                bot.send_message(game.chat_id, f"🟠 {user.first_name} взяв(ла) карти зі столу.")
                # після взяття — добираємо карти і переходимо до наступного ходу
                game.refill_all()
                game.next_turn()
                notify_players_after_action(game)
        elif action == 'end_attack':
            # завершення атаки — якщо всі карти побиті, переходимо; інакше — захисник має вибір
            if game.all_attacks_beaten():
                bot.answer_callback_query(call.id, 'Хід завершено — всі атаки побиті')
                bot.send_message(game.chat_id, 'Хід завершено — всі атаки побиті. Добір карт...')
                game.refill_all()
                game.next_turn()
                notify_players_after_action(game)
            else:
                bot.answer_callback_query(call.id, 'Не всі атаки побиті — захисник може брати або добивати')
        elif action == 'hand':
            p = game.get_player_by_id(user.id)
            bot.answer_callback_query(call.id, 'Відкриваю руку')
            bot.send_message(user.id, f"🃏 Твоя рука: {', '.join(p['hand'])}", reply_markup=hand_keyboard(p))
        else:
            bot.answer_callback_query(call.id, 'Невідома дія')

except Exception as e:
    logger.exception('Помилка в callback')
    bot.answer_callback_query(call.id, 'Виникла помилка')

def notify_players_after_action(game: DurakGame): # Оновити всім приватні повідомлення про руку і основне повідомлення у чаті try: # основний статус у групі status = f"Стіл:\n{game.get_table_text()}\n\nКозир: {game.trump_card}\nАтакує: {game.players[game.attacker_idx]['name']}\nЗахисник: {game.players[game.defender_idx]['name']}" bot.send_message(game.chat_id, status) except Exception: pass

for p in game.players:
    try:
        hand_txt = f"🃏 Твоя рука: {', '.join(p['hand'])}\n\nСтіл:\n{game.get_table_text()}"
        bot.send_message(p['id'], hand_txt, reply_markup=action_keyboard(game, p['id']))
    except Exception:
        # якщо не вдалося надіслати приватне — ігноруємо
        pass

Запуск

if name == 'main': logger.info('Бот запущено (polling)') try: bot.infinity_polling(timeout=60, long_polling_timeout=60) except KeyboardInterrupt: logger.info('Зупинка користувачем') except Exception: logger.exception('Критична помилка')