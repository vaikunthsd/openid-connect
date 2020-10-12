import os
import datetime
import json
import pytz
import uuid
import random
import base64

import requests


from flask import Flask, render_template, redirect
from flask import request
from flask import jsonify
from flask import send_from_directory, make_response

from google.cloud import datastore
import libs.bcrypt as bcrypt

app = Flask(__name__)
datastore_client = datastore.Client()

CLIENT_SECRET = datastore_client.get(datastore_client.key('secret', 'oidc'))['client-secret']
CLIENT_ID = '723969041295-1unte4gk7ee80ubqglcicb9dsf1b5dld.apps.googleusercontent.com'

"""
Path to serve the favicon
"""
@app.route('/favicon.ico')
def favicon():
    return send_from_directory(os.path.join(app.root_path, 'static'),
                               'favicon.ico')

"""
Root path of the server

Returns:
    static index.html file from the static directory
"""
@app.route('/')
def root():
    return send_from_directory('static', 'index.html')


"""
Stores an event into datastore

Args:
    dt (datetime): the datetime of the event
    name (str): the name of the event
    recurring(Boolean): when the date is sent without an year
Returns:
    None
"""
def store_event(dt, name, user_id = None, recurring = False):
    if user_id:
        user_key = datastore_client.key("user", user_id)
        entity = datastore.Entity(key=datastore_client.key('event', parent=user_key))
    else:
        entity = datastore.Entity(key=datastore_client.key('event'))
    entity.update({
        'time': dt,
        'name': name,
        'recurring': recurring
    })

    datastore_client.put(entity)

"""
fetch all the users

Args:
    None
Returns:
    list of all the user entities
"""
def fetch_users():
    query = datastore_client.query(kind='user')
    users = query.fetch()
    return list(users)

"""
fetches the user having the passed id

Args:
    user_id: user's id
Returns:
    return user
"""
def fetch_user_by_id(user_id):
    user_key = datastore_client.key('user', int(user_id))
    user = datastore_client.get(user_key)
    return user

"""
fetches the user having the passed username

Args:
    username: user's username
Returns:
    return user
"""
def fetch_user_by_username(username):
    query = datastore_client.query(kind='user')
    query.add_filter('name', '=', username)
    user = query.fetch()
    user = list(user)
    return user[0] if user else None


"""
stores the session for the user

Args:
    user_id: user's id
    random_number: random session id
Returns:
    return user
"""
def store_session_id_for_user(user_id, random_number):
    session_entity = datastore.Entity(key=datastore_client.key('session'))
    session_entity.update({
        'user_id': user_id,
        'hash': random_number,
        'expiry': datetime.datetime.now() + datetime.timedelta(minutes=60)
    })
    datastore_client.put(session_entity)

"""
checks for session with the id

Args:
    session_id: session random string
Returns:
    return session entity or None
"""
def get_session_by_id(session_id):
    query = datastore_client.query(kind='session')
    query.add_filter('hash', '=', session_id)
    session = query.fetch()
    session = list(session)
    return session[0] if session else None

"""
login path

Returns:
    static login.html file from the static directory
"""
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'GET':
        res = make_response(send_from_directory('static', 'login.html'))
        res.set_cookie('oidc_state', str(uuid.uuid4()))
        return res
    elif request.method == 'POST':
        request_json = request.get_json()
        username = request_json['username']
        password = request_json['password']
        user = fetch_user_by_username(username)
        if user:
            hashed_password = user['password']
            input_hashed = bcrypt.hashpw(password, hashed_password)
            if input_hashed == hashed_password:
                response = make_response(redirect('/'), 302)
                session_id = str(random.randint(100000000000,999999999999))
                store_session_id_for_user(user.key.id, session_id)
                response.set_cookie('session_id', session_id, max_age = 3600) #setting session cookie expiry in 1 hour
                return response
            else:
                return {'data': 'failure'}, 401
        else:
            return {'data': 'user does not exist!!'}, 401

"""
logout path

Returns:
    deletes session and redirects user back to the login page
"""
@app.route('/logout')
def logout():
    session_id = request.cookies.get('session_id')
    query = datastore_client.query(kind='session')
    query.add_filter('hash', '=', session_id)
    session = query.fetch()
    session = list(session)
    complete_key = datastore_client.key('session', int(session[0].key.id))
    res = datastore_client.delete(complete_key)
    response = make_response(redirect('/login'), 302)
    return response
"""
get the oath params

Args:
    
Returns:
    json containing client_id, redirect_uri and nonce
"""
@app.route('/get_oauth_login_url_params')
def get_oauth_login_url_params():
    # client_id = '723969041295-6n3haeib451keji7737uors83gb3om57.apps.googleusercontent.com'
    redirect_uri = '/oidcauth'
    nonce = str(uuid.uuid4())
    oauth_url = 'https://accounts.google.com/o/oauth2/v2/auth?response_type=code&client_id={0}&scope=openid%20email&redirect_uri={1}&state={2}&nonce={3}'.format('723969041295-6n3haeib451keji7737uors83gb3om57.apps.googleusercontent.com',
        'http://127.0.0.1:8090/oidcauth',
        str(uuid.uuid4()),
        str(uuid.uuid4()))
    return {'data': {'client_id': CLIENT_ID,'redirect_uri': redirect_uri, 'nonce': nonce}}, 200


"""
hanlding redirect from the oauth

Args:
    
Returns:
    checks for received state with state cookie,
    makes post request to get token and if user doesnt exist creates a user or else logins the existing user
"""
@app.route('/oidcauth')
def oidcauth():
    try:
        redirect_uri = 'https://burnished-core-289201.ue.r.appspot.com/oidcauth'
        code = request.args['code']
        state = request.args['state']
        state_cookie = request.cookies.get('oidc_state')
        if state_cookie == state:
            response = requests.post('https://www.googleapis.com/oauth2/v4/token' ,{'code': code,'client_id': CLIENT_ID,'client_secret': CLIENT_SECRET,'redirect_uri': redirect_uri,'grant_type': 'authorization_code'})
            id_token = response.json()['id_token']
            _, body, _ = id_token.split('.')
            body += '=' * (-len(body) % 4)
            claims = json.loads(base64.urlsafe_b64decode(body.encode('utf-8')))
            sub = str(claims['sub'][0:7])
            user = fetch_user_by_username(sub)
            session_id = str(random.randint(100000000000,999999999999))
            if not user: # Create new user
                user_id = add_user(sub, None)
                store_session_id_for_user(user_id, session_id)
            else:
                store_session_id_for_user(user.key.id, session_id)
            # login
            response = make_response(redirect('/'), 302)
            response.set_cookie('session_id', session_id, max_age = 3600) #setting session cookie expiry in 1 hour
            return response
    except Exception as e:
        return {'error': str(e), 'sub': sub}

"""
add the user entity

Args:
    username:(str) user's name
    hashed_password:(str) hashed password
Returns:
    key id of the user entity created
"""
def add_user(username, hashed_password):
    user_entity = datastore.Entity(key=datastore_client.key('user'))
    user_entity.update({
        'name': username,
        'password': hashed_password if hashed_password else None,
    })
    datastore_client.put(user_entity)
    return user_entity.key.id

"""
signup path

Returns:
    static signup.html file from the static directory
"""
@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'GET':
        return send_from_directory('static', 'signup.html')
    elif request.method == 'POST':
        request_json = request.get_json()
        username = request_json['username']
        password = request_json['password']
        hashed_password = bcrypt.hashpw(password, bcrypt.gensalt())
        user = fetch_user_by_username(username)
        if user:
            return {'data': 'user already exists!'}, 409
        else:
            user_id = add_user(username, hashed_password)
            status_response = jsonify({'data': 'user signed up'})
            response = make_response(status_response)
            session_id = str(random.randint(100000000000,999999999999))
            store_session_id_for_user(user_id, session_id)
            response.set_cookie('session_id', session_id, max_age = 3600) #setting session cookie expiry in 1 hour
            return response

# @app.route('/delete_users')
# def delete_users():
#     users = fetch_users()
#     for user in users:
#         complete_key = datastore_client.key('user', int(user.key.id))
#         datastore_client.delete(complete_key)
#     return 'completed!!'

@app.route('/users', methods=['GET', 'POST'])
def users():
    if request.method == 'GET':
        query = datastore_client.query(kind='user')
        users = query.fetch()
        users = list(users)
        dicts = []
        for user in users:
            dicts.append({'id': user.key.id, 'name': user['name'], 'password': user['password']})
        return json.dumps(dicts)


@app.route('/sessions')
def sessions():
    query = datastore_client.query(kind='session')
    all_sessions = query.fetch()
    all_sessions = list(all_sessions)
    dicts = []
    for session in all_sessions:
        dicts.append({'id': session.key.id, 'session_id': session['user_id']})
    return json.dumps(dicts)


# @app.route('/user/<user_id>', methods=['GET', 'POST'])
# def user(user_id):
#     if request.method == 'GET':
#         user = fetch_user_by_id(user_id)
#         if user:
#             return json.dumps({'id': user.key.id, 'name': user['name'], 'password': user['password']})
#         else:
#             return json.dumps({'error': 'no user found'})



# @app.route('/user_by_name/<user_name>', methods=['GET', 'POST'])
# def user_by_name(user_name):
#     if request.method == 'GET':
#         user = fetch_user_by_username(user_name)
#         if user:
#             return json.dumps({'id': user.key.id, 'name': user['name'], 'password': user['password']})
#         else:
#             return json.dumps({'error': 'no user found'})

"""
Returns all the created events in ascending order of time

Args:
    None
Returns:
    list of events
"""
def fetch_events(user = None):
    if user:
        query = datastore_client.query(kind='event', ancestor=user.key)
    else:
        query = datastore_client.query(kind='event')
    query.order = ['time']
    events = query.fetch()
    return list(events)

"""
Cron job to delete the past events(runs every minute)
"""
@app.route('/tasks/delete_past_events')
def delete_past_events():
    try:
        events = fetch_events()
        current_time = datetime.datetime.now()
        past_events = filter(lambda x: pytz.utc.localize(current_time) >  x['time'], events)
        for past_event in past_events:
            complete_key = datastore_client.key('event', int(past_event.key.id))
            datastore_client.delete(complete_key)
        return 'completed!!'    
    except Exception as e:
        return str(e)

"""
Cron job to delete expired session ids
"""
@app.route('/tasks/delete_expired_sessions')
def delete_expired_sessions():
    try:
        query = datastore_client.query(kind='session')
        sessions = query.fetch()
        sessions = list(sessions)
        current_time = datetime.datetime.now()
        for session in sessions:
            try:
                if pytz.utc.localize(current_time) > session['expiry']:
                    complete_key = datastore_client.key('session', int(session.key.id))
                    datastore_client.delete(complete_key)
            except Exception as e:
                continue
        return {'data': 'all sessions deleted'}, 200
        
    except Exception as e:
        return str(e)



"""
Path to delete an event based on the event_id
Args:
    even_id: id of event
Returns:
    status: whether the delete event succeed 
"""
@app.route('/event/<event_id>', methods=["DELETE"])
def event(event_id):
    try:
        session_id = request.cookies.get('session_id')
        session = get_session_by_id(str(session_id))
        if session:
            user_id = session['user_id']
            user_key = datastore_client.key("user", int(user_id))
            complete_key = datastore_client.key('event', int(event_id), parent = user_key)
            datastore_client.delete(complete_key)
            return json.dumps({'status': 'deleted: ' + event_id})
    except Exception as e:
        return str(e)


@app.route('/migrate_events_to_user/<user_id>')
def migrate_events_to_user(user_id):
    events = fetch_events()
    events_without_user = list(filter(lambda event: event.key.parent == None ,events))
    user = fetch_user_by_id(user_id)
    if user:
        for event_without_user in events_without_user:
            user_key = datastore_client.key("user", int(user_id))
            print('Migrating: ', event_without_user['name'])
            store_event(event_without_user['time'], event_without_user['name'], int(user_id)) #create new entity assigning the user
            first_event_key = datastore_client.key('event', int(event_without_user.key.id))
            datastore_client.delete(first_event_key) #delete existing entity without user parent
        return {'data': 'all events migrated to user with username {0}'.format(user['name'])}, 201
    else:
        return {'data': 'no such user'}, 401

    
"""
path to fetch events and create an event

GET /events will return all the events
Returns:
    return the json of events

POST /events will create a new event
Returns:
    return the json of the created event
"""
@app.route('/events', methods=['GET', 'POST'])
def events():
    if request.method == 'GET':
        try:
            session_id = request.cookies.get('session_id')
            session = get_session_by_id(str(session_id))
            if session:
                user_id = session['user_id']
                user = fetch_user_by_id(str(user_id))
                if user:
                    events = fetch_events(user)
                    dicts = []
                    for event in events:
                        dicts.append({'time': event['time'].timestamp(),'name': event['name'], 'recurring': event['recurring'], 'id': event.key.id, 'parent_id': event.key.parent.id_or_name if event.key.parent else None})
                    return json.dumps(dicts)
                else:
                    return {'data': 'please logins' ,'user_id': str(user_id)}, 401
            else:
                return {'data': 'please login'}, 401
        except Exception as e:
            return str(e)
    else:
        try:
            session_id = request.cookies.get('session_id')
            session = get_session_by_id(session_id)
            if session:
                user_id = session['user_id']
                event_name = request.form['event_name']
                month = int(request.form['event_month'])
                day = int(request.form['event_day'])

                if request.form['event_year'] != '':
                    year = int(request.form['event_year'])
                    dt = datetime.datetime(year, month, day)
                    store_event(dt, event_name, user_id)
                    return {'time': dt, 'name': event_name}
                else:
                    for x in range(2020,2040):
                        dt = datetime.datetime(x, month, day)
                        store_event(dt, event_name, user_id, True)
                    return {'status': 'stored 20 events'}
            else:
                return {'data': 'please login'}, 401

        except Exception as e:
            return 'ERROR: {0}'.format(str(e))

if __name__ == '__main__':
    app.run(host='127.0.0.1', port=8090, debug=True)




