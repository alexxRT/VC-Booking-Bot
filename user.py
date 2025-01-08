import telebot
from telebot import types
import data_base as db
from datetime import datetime
import configparser
from enum import Enum

SECONDS_IN_HOUR = 3600

class Authority(Enum):
    ADMIN = 1,
    USER  = 2

class User:
    user_id         : int
    username        : str
    authority       : Authority
    data_base       : db.data_base
    is_launched     : bool
    vc_inuse        : bool
    num_bookings    : int
    max_book_a_day  : int
    book_table      : dict
    book_interval   : int
    active_bookings : set[str]

    def __init__(self, user_id: int, username: str, authority: int, cfg_path: str):
        self.data_base = db.data_base("users.sql")
        self.user_id   = user_id
        self.username  = username
        self.authority = authority

        self.is_launched     = False
        self.num_bookings    = 0
        self.vc_inuse        = False
        self.active_bookings = set()

        self.init_from_config(cfg_path)

    def lookup(self):
        return self.data_base.select_user(f"usrid = {self.user_id}")

    def add_new(self):
        self.data_base.add_new_user(self.username, self.user_id)

    def init_from_config(self, cfg_path : str):
        cfg_parser   = configparser.ConfigParser()
        cfg_parser.read(cfg_path)

        # stores duration of one booking
        self.book_interval = int(cfg_parser["User"]["book_time_interval"])
        self.max_book_a_day = int(cfg_parser["User"]["max_book_a_day"])
        earliest_hour = int(cfg_parser["User"]["earliest_book_time"].split(":")[0])
        earliest_minutes = str(cfg_parser["User"]["earliest_book_time"].split(":")[1])
        latest_hour   = int(cfg_parser["User"]["latest_book_time"].split(":")[0])
        self.book_table = {}
        for hour in range(earliest_hour, latest_hour + 1, self.book_interval):
            book_time = f"{hour}:{earliest_minutes}"
            self.book_table[hour] = book_time

    def get_menu(self, msg : str = "Choose one of the actions below"):
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True)

        buttons = []
        buttons.append(types.KeyboardButton("status"))
        buttons.append(types.KeyboardButton("book"))
        buttons.append(types.KeyboardButton("my bookings"))

        if self.authority == Authority.ADMIN:
            buttons.append(types.KeyboardButton("show users"))
            buttons.append(types.KeyboardButton("start bot"))
            buttons.append(types.KeyboardButton("stop bot"))

        markup.add(*buttons, row_width=3)
        return {
            "chat_id" : self.user_id,
            "text"    : msg,
            "reply_markup" : markup
        }

    def finish_rent(self, time : str) -> dict:
        if not self.vc_inuse:
            return {
                "chat_id" : self.user_id,
                "text"    : "Start rent first!"
            }
        if time not in self.active_bookings:
            return {
                "chat_id" : self.user_id,
                "text"    : "You can not finish rent you haven't started!"
            }

        self.vc_inuse = False
        self.active_bookings.remove(time)

        return {
            "chat_id" : self.user_id,
            "text"    : "Rent finished successfuly!"
        }

    def start_rent(self, time : str) -> bool:
        if time not in self.active_bookings:
            return {
                "chat_id" : self.user_id,
                "text"    : "Book before starting the rent!"
            }

        time_now = datetime.now()
        hours_before_rent = (datetime.strptime(f"{time_now.year}-{time_now.month}-{time_now.day} {time}", "%Y-%m-%d %H:%M") \
                            - time_now).total_seconds() / SECONDS_IN_HOUR

        if hours_before_rent > 0:
            return {
                "chat_id" : self.user_id,
                "text"    : f"Its not your time to start the rent! Wait until {time}"
            }
        elif abs(hours_before_rent) > self.book_interval:
            self.active_bookings.remove(time)
            return {
                "chat_id" : self.user_id,
                "text"    : f"Your booking has expired! Create new booking!"
            }

        self.vc_inuse = True
        return {
            "chat_id" : self.user_id,
            "text"    : "Rent Started Successfuly!"
        }

    def get_book_info(self, booked_times : list[str]) -> dict:
        available_times = [time for time in self.book_table.values() if time not in booked_times]
        markup = types.InlineKeyboardMarkup()
        buttons_list = []

        for time in available_times:
            button = types.InlineKeyboardButton(time, callback_data=time)
            buttons_list.append(button)

        markup.add(*buttons_list, row_width=2)
        return {
            "chat_id" : self.user_id,
            "text"    : "Availabe times:",
            "reply_markup" : markup
        }

    def get_active_bookings(self):
        if not self.active_bookings:
            return self.get_menu("You do not have active bookings!")

        markup = types.ReplyKeyboardMarkup(resize_keyboard=True)

        for time in self.active_bookings:
            markup.add(types.KeyboardButton(time))
        markup.add(types.KeyboardButton("exit"))

        return {
            "chat_id"      : self.user_id,
            "text"         : "Your available bookings:",
            "reply_markup" : markup
        }

    def try_book(self, time: str) -> tuple[dict, bool]:
        if self.num_bookings < self.max_book_a_day:
            self.active_bookings.add(time)
            self.num_bookings += 1
            return {
                "chat_id" : self.user_id,
                "text"    : "Successfully booked!",
            }, True
        return self.get_menu(f"You have no more than {self.max_book_a_day} books a day! Return tommorow!"), False

    def get_confirmation(self, time: str):
        markup = types.InlineKeyboardMarkup()
        approve = types.InlineKeyboardButton("approve", callback_data=f"approve {time}")
        back    = types.InlineKeyboardButton("back", callback_data="back")
        markup.row(approve, back)

        return {
            "chat_id"      : self.user_id,
            "text"         : f"Book at {time}?",
            "reply_markup" : markup
        }

    def get_book_actions(self) :
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        buttons = [types.KeyboardButton("start"), types.KeyboardButton("finish"), types.KeyboardButton("exit")]
        markup.add(*buttons, row_width=1)

        return {
            "chat_id"      : self.user_id,
            "text"         : "Choose action to manage your book:",
            "reply_markup" : markup
        }

