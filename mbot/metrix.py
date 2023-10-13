# -*- coding: utf-8 -*-
"""
MetrixBot for Telegram
A Telegram bot for blood pressure and pulse metrix.
by Eugene Kolonsky ekolonsky@gmail.com 2018 - 2023

"""

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

import configparser, codecs
import datetime

import nest_asyncio
nest_asyncio.apply()

# get configuration data from .ini file
config = configparser.ConfigParser()
def read_ini(filename):
   config.read_file(codecs.open(filename, encoding='cp1251'))

read_ini("metrix.ini")

TOKEN = config["TELEGRAM"]["TOKEN"]

MAX_BP    = int(config['LIMITS']['MAX_BP'])  # blood pressure figures over max are incorrect
MIN_BP    = int(config['LIMITS']['MIN_BP']) # figures lower min are incorrect
MAX_PULSE = int(config['LIMITS']['MAX_PULSE'])  # pulse figures over max are incorrect
MIN_PULSE = int(config['LIMITS']['MIN_PULSE'])  # pulse pressure figures over max are incorrect

def get_filename(user):
    filename = f'{user.id}.txt'
    return filename

def get_records(user):
    try: 
        records = open(get_filename(user)).readlines()
    except:
        records = []
    return records  

# writing data to text file
async def write_data(user, vad, nad, pulse=None, comment=None):
    date_time = datetime.datetime.now().strftime("%Y.%m.%d %H:%M")
    record = f'{date_time}\t{vad}\t{nad}\t{pulse}\t{comment}\n'
    filename = get_filename(user)
    print(filename, record)
    with open(filename,'a') as f:
        f.write(record)

async def save(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user

    #store_user_action(user, '/save', 'command')
    
    records = get_records(user)
    num = len(records)
    if num == 0:
        update.message.reply_html('No yet records to save.') 
    else:
        doc_file = open(get_filename(user), 'rb')
        await context.bot.send_document(
        chat_id = update.message.chat_id,
        document=doc_file,
        caption="My blood pressure records"
        )
    return

# delete last point
async def del_last(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    #store_user_action(user, '/del', 'command')
    #username = "%s_%s [id:%d]"%(user.first_name, user.last_name, user.id)
    # do we have some records?
    records = get_records(user)
    if len(records) > 0: # yes, we have a point(s) to delete
       filename = get_filename(user)
       print(filename, records[-1])
       print('\n'.join(records[:-1]))
       with open(filename,'w') as f:
          f.write('\n'.join(records[:-1]))

       last = records[-1]
       fields = last.split('\t')
       VAD, NAD = fields[1], fields[2]
       text = 'Record {}/{} deleted.'.format(VAD, NAD)
    else:                # new user
           text = 'No yet records to delete.'
    await update.message.reply_html(text)

# Define a few command handlers. These usually take the two arguments update and
# context.
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a message when the command /start is issued."""
    user = update.effective_user
    records = get_records(user)
    num = len(records)
    if num >0: # returning user
        reply = config['DIALOG']['Welcome returning'].format(num)
    else:             # new user
        reply = config['DIALOG']['Welcome first'].format(user.mention_html())
    await update.message.reply_html(reply,
        #reply_markup=ForceReply(selective=True),
    )
    
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a message when the command /help is issued."""
    reply = config['DIALOG']['Help']
    await update.message.reply_text(reply)
    
   
# проверка и разбор входящей строки
# хорошая строка содержит два или три целых числа
# из которых первое и второе - показатели давления
# третье - пульс (опицонально)     
# все остальное считается текстовым комментарием
def parse(message):  
    vad, nad, pulse = None, None, None
    words = message.split(' ')
    error_code = 0
    
    values = []
    others = []
    for word in words:
      if word.isdigit():
          values.append(int(word))
      else:
          others.append(word)
    if len(values) == 0: # just talk? ok
        error_code = -1
    elif len(values) == 1:
        error_code = 1  # ":( Sorry.. What is '%d'? Feed me 2 or 3 values"
    elif len(values) >= 2:
        vad, nad = values[0], values[1]
        if  MAX_BP > values[0] > values[1] > MIN_BP: # check correctness
            error_code = 0
        else:
            error_code = 1 # Is it blood pressure?
    if len(values) >= 3:
        if  MAX_PULSE > values[2] > MIN_PULSE: # check correctness
            pulse = values[2]
            
    return vad, nad, pulse, error_code, ' '.join(others)

# talk with user if no digital data given
async def talk(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    # try to find intent
    # hello intent
    #  help intent
    # others, we do not understand yet
    user = update.message.from_user
    message = update.message.text
    
    words = message.lower().strip('!:),*;-').split(' ')
    for word in words:
        if word in config['DICTIONARY']['Hello']:
          reply = config['DIALOG']['Hello'].format(user.first_name)
          await update.message.reply_text(reply)
          return
        elif word in config['DICTIONARY']['Help']:
          await help_command()
          return
    reply = config['DIALOG']['Nocomprene']
    await update.message.reply_text(reply)
    return

# main conversation cycle
async def conversation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.message.from_user
    message = update.message.text

    vad, nad, pulse, error_code, comment = parse(message)
    if error_code == 0: # all checks passed, data accepted
        await write_data(user, vad, nad, pulse, comment)
        if pulse == None: #pulse is optional
            reply = config['DIALOG']['Gotit2'].format(vad, nad)
        else:
            reply = config['DIALOG']['Gotit3'].format(vad, nad, pulse)
        #store_user_action(user, message, 'data_accepted') # for later analysis
    elif error_code == 1: # check not passed
        reply = config['DIALOG']['Check fail'].format(vad, nad)
        #store_user_action(user, message, 'data_rejected') # for later analysis
    else: # no digits, just a talk
        await talk(Update)
        #store_user_action(user, message, 'talk') # for later analysis
        return   
    await update.message.reply_text(reply)


def main() -> None:
    """Start the bot."""
    # Create the Application and pass it your bot's token.
    application = Application.builder().token(TOKEN).build()

    # on different commands - answer in Telegram
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("save", save))
    application.add_handler(CommandHandler("del", del_last))
    
    # on non command i.e message - start dialogue
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, conversation))

    # Run the bot until the user presses Ctrl-C
    application.run_polling(allowed_updates=Update.ALL_TYPES)



if __name__ == "__main__":
    print('Start bot polling..')
    main()
