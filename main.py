from flask import Flask, request, jsonify
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from dateutil.parser import parse as parsedate
from pprint import pprint
import requests
import pytz

BOT_NAME = 'reminderbot'
TIMEZONE = pytz.timezone('Australia/Melbourne')
TIME_FORMAT = '%-I:%M%P'
DATE_FORMAT = '%a %-d %b'

DATETIME_FORMAT = f'{DATE_FORMAT} at {TIME_FORMAT}'
TIMEDATE_FORMAT = f'{TIME_FORMAT} on {DATE_FORMAT}'

jobstores = {
  'default': SQLAlchemyJobStore(url='sqlite:///jobs.sqlite'),
}
scheduler = BackgroundScheduler(jobstores=jobstores)
scheduler.start()

app = Flask(__name__)

def depersonalise(text):
  """
  Convert text from the first-person to the third-person.
  """
  replacements = {
    'my': 'your',
    'I': 'you',
  }

  return ' '.join(replacements.get(word, word) for word in text.split())

def answer(text, room=None, author=BOT_NAME):
  """
  Prepare a JSON response to send to NeCSuS
  """
  response = {'text': text, 'author': author}
  if room:
    response['room'] = room
  return jsonify(response)

def numbertoword(num):
  """
  Convert a number to its corresponding word using the NCSS Convert API
  """
  response = requests.get(f'https://apis.ncss.cloud/convert/number?value={num}')
  return response.text if response.ok else str(num)

def send_reminder(what, room):
  """
  Send a reminder message to a NeCSuS chatroom
  """
  requests.post(
     'https://chat.ncss.cloud/api/actions/message',
    json={
      'author': BOT_NAME,
      'room': room,
      'text': f'Remember to {depersonalise(what)}!',
    }
  )

@app.route('/remove', methods=['POST'])
def remove_reminder():
  """
  Remove a scheduled reminder from the list.
  """
  data = request.get_json()
  task = data['params']['task']

  pprint(task)

  job = scheduler.get_job(task)

  pprint(job)

  if not job:
    return answer('I can\'t find that reminder')

  job.remove()

  pprint(job)

  return answer(f'Okay, I won\'t remind you to {depersonalise(job.name)} at {job.next_run_time.strftime(TIMEDATE_FORMAT)}.')

@app.route('/clear', methods=['POST'])
def clear_schedule():
  """
  Clear the full list of scheduled reminders, removing them from memory.
  """
  count = 0

  for job in scheduler.get_jobs():
    job.remove()
    count += 1

  return answer(
    f'Okay, I\'ve removed all {numbertoword(count)} reminders.'
  )

@app.route('/list', methods=['POST'])
def list_reminders():
  """
  Display the full list of scheduled reminders.
  """
  jobs = scheduler.get_jobs()

  if not jobs:
    return answer( 'You don\'t have any reminders.')

  return answer('Here are your reminders:<ul><li>' +
    '</li><li>'.join(f'{depersonalise(job.name)} at {job.next_run_time.strftime(TIMEDATE_FORMAT)}' for job in jobs) + '</ul></li>')

@app.route('/schedule', methods=['POST'])
def schedule_reminder():
  """
  Schedule a reminder at a specified time.
  """
  data = request.get_json()
  room = data['room']
  pprint(data)

  what = data['params']['task']
  when = parsedate(data['params']['datetime'], fuzzy=True)

  when = TIMEZONE.localize(when)

  job = scheduler.add_job(
    send_reminder, args=(what, room),
    trigger='date', run_date=when,
    id=what, name=what
  )

  print(job)

  return answer(f'''Okay, I will remind you to {depersonalise(what)}
    at {when.strftime(TIMEDATE_FORMAT)}''')

app.run(host='0.0.0.0', port=8080)