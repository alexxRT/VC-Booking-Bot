import bot as tb
import datetime

if __name__ == "__main__":
    # # this while starts bot exactly at 23:59 so all booking tables will be updated properly
    # wait_to_launch = True
    # while wait_to_launch:
    #     date = datetime.datetime.now()

    #     if (date.hour == 3):
    #         wait_to_launch = False
    bot = tb.Bot("data/config.cfg")
    bot.bot.infinity_polling()

