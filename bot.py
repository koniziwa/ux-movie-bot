import telebot
import json
import os
from datetime import *
from time import *
import schedule
import threading


from bot_token import *
from constants import *


bot = telebot.TeleBot(token)


@bot.message_handler(commands=['start'])
def start(message):
    end(message)
    with open('assets/start_photo.jpg', 'rb') as file:
        bot.send_photo(message.chat.id, file, start_text, parse_mode='HTML')


@bot.message_handler(commands=['new'])
def createNewSession(message):
    end(message)
    sent = bot.send_message(
        message.chat.id, select_film_text, parse_mode='HTML')
    bot.register_next_step_handler(sent, saveName)


def saveName(message):
    createDB(message.text, message.from_user.username, message.date,
             message.from_user.first_name, message.from_user.last_name)
    bot.send_message(message.chat.id, write_comms_text, parse_mode='HTML')


def createDB(session_name, userID, start_date, first_name, last_name):
    with open(f'data/{userID}-{session_name.replace(" ", "-")}.json', 'w') as db:
        db.write(json.dumps({
            'username': userID,
            'session_name': session_name,
            'start_date': start_date,
            'first_name': first_name,
            'last_name': last_name,
        }))


@bot.message_handler(commands=['end'], func=lambda message: message.from_user.username in [path.split('-')[0] for path in os.listdir('data')])
def end(message):
    try:
        if len(os.listdir('data')) > 0:
            for path in os.listdir('data'):
                if message.from_user.username == path.split('-')[0]:
                    bot.send_message(
                        message.chat.id, end_text, parse_mode='HTML')
                    bot.send_document(
                        message.chat.id, open(f'data/{path}', 'rb'))
                    os.remove(f'data/{path}')
                    break
    except Exception as e:
        print('ERROR!', e)


@bot.message_handler(func=lambda message: message.from_user.username in [path.split('-')[0] for path in os.listdir('data')])
def writeDB(message):
    for path in os.listdir('data'):
        if path.split('-')[0] == message.from_user.username:
            with open(f'data/{path}') as db:
                db_content = db.read()
                to_db = dict(json.loads(db_content))

            if 'comms' not in list(to_db.keys()):
                to_db['comms'] = [{
                    'text': message.text,
                    'time': message.date - int(to_db['start_date']),
                    'active': True,
                }]
            else:
                to_db['comms'].append({
                    'text': message.text,
                    'time': message.date - int(to_db['start_date']),
                    'active': True,
                })

            with open(f'data/{path}', 'w') as db:
                db.write(json.dumps(to_db))

            break


@bot.message_handler(content_types=['document'])
def loadFile(message):
    end(message)
    file_name = str(message.document.file_name)
    file_info = bot.get_file(message.document.file_id)
    downloaded_file = bot.download_file(file_info.file_path)
    with open(f'loaded/{file_name}', 'wb') as new_file:
        new_file.write(downloaded_file)

    with open(f'loaded/{file_name}') as db:
        db_content = db.read()
        to_db = dict(json.loads(db_content))
        to_db['viewer_id'] = message.chat.id

    with open(f'loaded/{file_name.replace("-", f"-{message.from_user.username}-", 1)}', 'w') as db:
        db.write(json.dumps(to_db))

    bot.send_message(message.chat.id, start_from_file_text, parse_mode='HTML')


@bot.message_handler(commands=['start_from_file'])
def startFromFileSession(message):
    for path in [path for path in os.listdir('loaded') if '-active' not in path and '-ended' not in path and path.split('-')[1] == message.from_user.username]:
        with open(f'loaded/{path}', 'r') as db_raw:
            db = dict(json.load(db_raw))
            if db['viewer_id'] == message.chat.id:
                db['view_start_time'] = message.date
                last_name = db["last_name"] if db["last_name"] else ""
                bot.send_message(
                    message.chat.id, f'Вы будете смотреть \"{db["session_name"]}\" с комментариями от {db["first_name"]} {last_name}')

        with open(f'loaded/{path.replace(".json", "-active.json")}', 'w') as file:
            file.write(json.dumps(db))
            os.remove(f'loaded/{path}')

        break


def job():
    paths = os.listdir('loaded')
    if len(paths) > 0:
        for path in paths:
            if '-active' in path:
                max_comments = 0
                false_comments = 0
                chat_id = 0
                with open(f'loaded/{path}', 'r+') as file:
                    data = json.load(file)
                    dt = int(time()) - int(data['view_start_time'])
                    max_comments = len(data['comms'])
                    chat_id = data['viewer_id']
                    for comment in data['comms']:
                        if dt >= int(comment['time']) and comment['active'] == True:
                            comment['active'] = False
                            file.seek(0)
                            json.dump(data, file, indent=4)
                            file.truncate()
                            last_name = data["last_name"] if data["last_name"] else ""
                            bot.send_message(
                                data['viewer_id'], f'[{timedelta(seconds=int(comment["time"]))}] {data["first_name"]} {last_name}: {comment["text"]}')

                        elif comment['active'] == False:
                            false_comments += 1

                if false_comments == max_comments:
                    bot.send_message(
                        int(chat_id), '<b><i>Комментарии закончились</i></b>', parse_mode='HTML')
                    os.rename(
                        f'loaded/{path}', f'loaded/{path.replace("-active", "-ended")}')

def startBot():
    bot.polling(none_stop=True, interval=0)

def startScheduler():
    schedule.every(3).seconds.do(job)
    while True:
        schedule.run_pending()
        sleep(1)

if __name__ == "__main__":
    t1 = threading.Thread(target=startBot)
    t2 = threading.Thread(target=startScheduler)
    t1.start() 
    t2.start()