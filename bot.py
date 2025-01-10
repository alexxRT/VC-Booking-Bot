import telebot
from telebot import types
import configparser
import re
import logging
from apscheduler.schedulers.background import BackgroundScheduler
from user import Authority, User

TIME_PATTERN     = re.compile(r"([0-1]?[0-9]|2[0-3]):[0-5][0-9]$")
APPROVE_PATTERN  = re.compile(r"approve (([0-1]?[0-9]|2[0-3]):[0-5][0-9])$")
BAD_REQUEST_RESPONSE = "Unknown command! Next time be more precise!"

logging.basicConfig(level=logging.WARNING)
log = logging.getLogger("vcBot")

class Bot:
    bot            : telebot.TeleBot
    admins         : list[str]
    booked_times   : list[str]
    communications : dict[User]
    online_admins  : list[User]
    scheduler      : BackgroundScheduler
    is_launched    : bool
    greet_msg      : str
    config_path    : str

    def __init__(self, cfg_path: str):
        self.is_launched    = False
        self.booked_times   = []
        self.online_admins  = []
        self.communications = {}
        self.config_path    = cfg_path
        self.init_from_config(self.config_path)

        self.scheduler = BackgroundScheduler()

        @self.bot.message_handler(commands=["start"])
        def polling(message: types.Message):
            # say hello on start and provide user with rules!
            self.bot.send_message(**self.accept_menu(message, self.greet_msg))
            self.bot.register_next_step_handler(message, self.on_register)
            start_handle = self.bot.callback_query_handler(func=lambda call : True)
            start_handle(self.on_button)

    def on_register(self, message: types.Message):
        if message.text is None or message.text.strip() != "accept":
            self.bot.send_message(**self.accept_menu(message, "Please accept rules! Otherwise, see you :("))
            self.bot.register_next_step_handler(message, self.on_register)
            log.warning(f"User {message.from_user.username} does not accept rules")
            return

         # some users might not have usernames, but admins should have conntacts with them anyway
        if message.from_user.username is None:
            self.bot.send_message(message.from_user.id, "Please create username in settings and return!")
            self.bot.register_next_step_handler(message, self.on_register)
            log.warning("User does not have @username on_register")
            return

        username = f"@{message.from_user.username}"
        user_id = message.from_user.id

        if username in self.admins:
            new_user = self.add_communication(user_id, username, Authority.ADMIN)
            self.bot.send_message(**new_user.get_menu("Hello admin! We all have been waiting for you!"))
            self.online_admins.append(new_user)
        else:
            new_user = self.add_communication(user_id, username, Authority.USER)
            if new_user.lookup() is not None:
                self.bot.send_message(**new_user.get_menu(f"Hello {new_user.username}, welcome back!"))
            else:
                self.bot.send_message(**new_user.get_menu("Hello unknown! We will remember you soon..."))
                new_user.add_new()

        # start operating requests when success
        self.bot.register_next_step_handler(message, self.on_type)

    def on_type(self, message: types.Message, time: str = None):
        if message.text is None:
            self.bot.send_message(message.from_user.id, BAD_REQUEST_RESPONSE)
            self.bot.register_next_step_handler(message, self.on_type)
            log.warning("Text message is None on_type")
            return
        user = self.communications[message.from_user.id]
        if not self.is_launched and user.authority == Authority.USER:
            self.bot.send_message(message.from_user.id, "Bot is unaivalable for users! Please contact admins!")
            self.bot.register_next_step_handler(message, self.on_type)
            return

        handlers = {
            "status" : self.handle_status,
            "book"   : self.handle_book,
            "finish" : self.handle_finish,
            "start"  : self.handle_start,
            "exit"   : self.handle_exit,
            "my bookings" : self.handle_manage_book,
            "show users" : self.handle_show_users,
            "start bot" : self.handle_launch,
            "stop bot"  : self.handle_reset,
        }

        if (time_match := re.match(TIME_PATTERN, message.text)) is not None:
            user = self.communications[message.from_user.id]
            time = str(time_match[0])
            self.bot.send_message(**user.get_book_actions())
            self.bot.register_next_step_handler(message, self.on_type, time)
            return

        handler = handlers.get(message.text)
        if handler:
            self.bot.send_message(**handler(user=user, time=time))
        else:
            self.bot.send_message(**user.get_menu(BAD_REQUEST_RESPONSE))
            log.warning(f"Unknown command on_type {message.text}")
        self.bot.register_next_step_handler(message, self.on_type)

    def on_button(self, call):
        if call.data is None:
            self.bot.send_message(call.message.chat.id, BAD_REQUEST_RESPONSE)
            log.warning("call data is None on_button")
            return

        user = self.communications[call.message.chat.id]
        if (time_match := re.match(TIME_PATTERN, call.data)) is not None:
            print(f"Call data when choosing booking: {call.data}")
            self.bot.delete_message(call.message.chat.id, call.message.id)
            self.bot.send_message(**user.get_confirmation(str(time_match[0])))
            return
        if "approve" in call.data:
            self.handle_approve(call)
        elif "back" in call.data:
            self.handle_back(call)
        else:
            self.bot.send_message(user.user_id, BAD_REQUEST_RESPONSE)
            log.warning(f"Unknown command on_button {call.data}")


    #----------------------------------- IMPLEMENTATION --------------------------------------#
    def notify_admins(self, msg : str):
        for admin in self.online_admins:
            self.bot.send_message(admin.user_id, msg)

    def handle_status(self, **kwargs) -> dict:
        user = kwargs["user"]
        if (busy_user := self.check_vc_available()) is None:
            return user.get_menu( "Vacume cleaner is available!")
        return user.get_menu(f"Vacum cleaner is in use, please contact: {busy_user.username}")

    def handle_book(self, **kwargs) -> dict:
        user = kwargs["user"]
        self.bot.send_message(**user.get_book_info(self.booked_times))
        return user.get_menu("Choose available time above")

    def handle_start(self, **kwargs) -> dict:
        user = kwargs["user"]
        time = kwargs["time"]
        if (busy_user := self.check_vc_available()) is None:
            self.bot.send_message(**user.start_rent(time))
        else:
            self.bot.send_message(user.user_id, f"Vacum cleaner is in use, please contact: {busy_user.username}")
        return user.get_menu()

    def handle_finish(self, **kwargs) -> dict:
        user = kwargs["user"]
        time = kwargs["time"]
        self.bot.send_message(**user.finish_rent(time))
        self.booked_times.remove(time)
        return user.get_menu()

    def handle_exit(self, **kwargs) -> dict:
        user = kwargs["user"]
        return user.get_menu()

    def handle_manage_book(self, **kwargs) -> dict:
        user = kwargs["user"]
        return user.get_active_bookings()

    def handle_show_users(self, **kwargs) -> dict:
        user = kwargs["user"]
        if user.authority == Authority.USER:
            return user.get_menu(BAD_REQUEST_RESPONSE)

        users = list(filter(lambda user : True if user.authority == Authority.USER else False, self.communications.values()))
        if not users:
            self.bot.send_message(user.user_id, "No users use bot currently!")
            return user.get_menu()

        msg = "Users using service:\n"
        for active in users:
            msg += f"{active.username}\n"
        return user.get_menu(msg)

    def handle_approve(self, call):
        user = self.communications[call.message.chat.id]
        self.bot.delete_message(user.user_id, call.message.id)
        time = str(re.match(APPROVE_PATTERN, call.data)[1])

        if time in self.booked_times:
            self.bot.send_message(user.user_id, "Somebody has stolen your time interval! Book Failed!")
            return

        book, book_status = user.try_book(time)
        if book_status:
            self.booked_times.append(time)
            self.notify_admins(f"New book! Time: {time} User: {user.username}")
        self.bot.send_message(**book)

    def handle_back(self, call):
        user = self.communications[call.message.chat.id]
        self.bot.delete_message(user.user_id, call.message.id)
        self.bot.send_message(**user.get_book_info(self.booked_times))

 # ------------------------------------ EVERYDAY UPDATE ------------------------------------#
    def handle_launch(self, **kwargs):
        user = kwargs["user"]
        if user.authority == Authority.USER:
            return user.get_menu(BAD_REQUEST_RESPONSE)

        if self.is_launched:
            return user.get_menu("Bot already launched and updates everyday!")

        self.scheduler.add_job(self.new_day, 'interval', days=1)
        self.scheduler.start()
        self.is_launched = True

        return user.get_menu("Bot launched! Bot will update every day since now!")

    def handle_reset(self, **kwargs):
        user = kwargs["user"]
        if user.authority == Authority.USER:
            return user.get_menu(BAD_REQUEST_RESPONSE)

        if self.is_launched:
            self.scheduler.shutdown(wait=False)
            self.is_launched = False
            self.new_day()
        return user.get_menu("Bot stopped! Now its not available for users!")

    def new_day(self):
        self.booked_times = []
        for user in self.communications.values():
            user.vc_inuse = False
            user.num_bookings = 0
            user.active_bookings = set()

 # -------------------------------- HELPER FUNCTIONS --------------------------------------#
    def accept_menu(self, message: types.Message, msg: str):
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        markup.add(types.KeyboardButton("accept"))

        return {
            "chat_id" : message.from_user.id,
            "text"    : msg,
            "reply_markup" : markup,
            "parse_mode" : "html"
        }

    def check_vc_available(self):
        for user in self.communications.values():
            if user.vc_inuse:
                return user
        return None

    def add_communication(self, user_id: int, username: str, authority) -> User:
        if user_id not in self.communications.keys():
            new_user = User(user_id, username, authority, self.config_path)
            self.communications[user_id] = new_user
            return new_user

        return self.communications[user_id]

    def init_from_config(self, cfg_path: str):
        cfg_parser = configparser.ConfigParser()
        cfg_parser.read(cfg_path)

        token          = cfg_parser["Credentials"]["bot_token"]
        self.bot       = telebot.TeleBot(token)
        self.admins    = cfg_parser["Admins"]["admin_ids"]
        self.greet_msg = cfg_parser["General"]["greeting"]

        log.debug(f"token: {token}")
        log.debug(f"admins ids: {self.admins}")
