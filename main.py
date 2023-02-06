from collections import deque
import dateutil.parser
import requests
import datetime
import sqlite3
import threading
import json
import sys
import jwt

EPOCH = datetime.datetime(1970, 1, 1, tzinfo=datetime.timezone.utc)

REFRESH_TOKEN = 'eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJmcmVzaCI6ZmFsc2UsImlhdCI6MTY3NTU2MTkzNywianRpIjoiM2Q2NGU2ODEtODQ4YS00MmQ5LThkMGYtYWMzY2U4MjM5NTZlIiwidHlwZSI6InJlZnJlc2giLCJzdWIiOjcwNTE2OSwibmJmIjoxNjc1NTYxOTM3LCJjc3JmIjoiOWI4NWRkYjYtNTMxZi00OGYwLTg2YTItMjc4ZjViYzViODBiIiwiZXhwIjoxNjc4MTUzOTM3LCJhY3QiOm51bGx9.aDVHOJBa6fpvZ3HzeLt7ClI0L_YS8rhOq94_YoeBUys'


def make_database() -> sqlite3.Connection:
    database = sqlite3.connect('.sqlite')
    database.execute('''
    create table if not exists CLIENT_MANAGER (
        CLIENT_MANAGER_ID integer primary key,
        CLIENT_MANAGER_EMAIL text,
        CLIENT_MANAGER_NAME text
    )
    ''')
    database.execute('''
    create table if not exists IMAGE (
        IMAGE_ID integer primary key,
        IMAGE_URL text,
        IMAGE_TYPE integer,
        COMPANY_ID integer references COMPANY
    )
    ''')
    database.execute('''
    create table if not exists COMPANY (
        COMPANY_ID integer primary key,
        COMPANY_NAME text,
        COMPANY_PUBLIC_ID text,
        COMPANY_AMOUNT_OF_EMPLOYEES text,
        COMPANY_LAST_ACTIVE integer,
        COMPANY_RESPONSIVENESS text,
    	CLIENT_MANAGER_ID integer references CLIENT_MANAGER
    )
    ''')
    database.execute('''
    create table if not exists RECRUITER (
        RECRUITER_ID integer primary key,
        RECRUITER_EMAIL text,
        RECRUITER_NAME text,
        COMPANY_ID integer references COMPANY
    )
    ''')
    database.execute('''
    create table if not exists EVENTS (
        EVENT_ID integer primary key,
        EVENT_PUBLIC_ID integer,

        EVENT_NAME text,
        EVENT_LOCATION text,
        EVENT_CHECK_IN_CODE text,
        EVENT_INSTRUCTIONS_TO_JOIN text,

        EVENT_CREATE_DATE integer,
        EVENT_START_DATE integer,
        EVENT_END_DATE integer,
        EVENT_TIME_ZONE text,

        EVENT_TYPE integer,
        EVENT_COVER_IMAGE_URL text,
        EVENT_RSVP_LIMIT integer,
    	COMPANY_ID integer references COMPANY
    )
    ''')
    database.execute('''
    create table if not exists APPLICATIONS (
        APPLICATION_ID integer primary key,
        APPLICATION_PUBLIC_ID text,
        APPLICATION_CREATE_DATE integer,
        APPLICATION_STATUS integer,
        APPLICATION_TYPE text,
        EVENT_ID references EVENTS
    )
    ''')
    database.commit()
    return database


def get_access_token(tok: str = REFRESH_TOKEN) -> str:
    tok_dec = jwt.decode(
        tok, algorithms=['HS256'],
        options={'verify_signature': False},
    )

    headers = {
        'authority': 'app.ripplematch.com',
        'origin': 'https://app.ripplematch.com',
        'referer': 'https://app.ripplematch.com/v2/student/recommendations',
        'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/104.0.5112.81 Safari/537.36',
        'x-csrf-token': tok_dec['csrf'],
    }

    set_cookie = requests.post(
        'https://app.ripplematch.com/api/v2/auth/token/refresh',
        json={}, cookies={'refresh_token': tok},
        headers=headers,
    ).headers['Set-Cookie']

    beg = set_cookie.index('access_token=')
    end = set_cookie.index(';', beg)
    return set_cookie[beg + 13:end]


def get_entry(iden: int, tok: str | None = None) -> requests.Response:
    if not tok:
        tok = get_access_token()
    tok_dec = jwt.decode(
        tok, algorithms=['HS256'],
        options={'verify_signature': False},
    )

    headers = {
        'origin': 'https://app.ripplematch.com',
        'referer': 'https://app.ripplematch.com/v2/student/recommendations',
        'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/104.0.5112.81 Safari/537.36',
        'x-csrf-token': tok_dec['csrf'],
    }

    return requests.put(
        f'https://app.ripplematch.com/api/v2/rsvps/{iden}/mark-interested',
        json={'from_page': 'unRSVPModal'}, cookies={'access_token': tok},
        headers=headers,
    )


def check_in_data(database: sqlite3.Connection, i: int) -> bool:
    record = database.execute(f'''
    select exists(
        select 1 from APPLICATIONS where APPLICATION_ID={i} limit 1
    )
    ''').fetchone()
    return record[0] == 1


def get_min(database: sqlite3.Connection) -> bool:
    record = database.execute(f'''
        select APPLICATION_ID as I from APPLICATIONS order by I asc limit 1
    ''').fetchone()
    return record[0]


def try_entry(database: sqlite3.Connection, i: int, tok: str) -> tuple[dict | None, str]:
    # if check_in_data(database, i):
    # return (None, tok)

    while True:
        entry = get_entry(i, tok)
        if entry.status_code == 401:
            tok = get_access_token()
            print(f'Error at (id={i})')
            continue
        break

    try:
        j: dict = entry.json()
        msg_not_found = f'Record (id={i}) of type Application not found.'
        if j.get('message', '') == msg_not_found:
            raise Exception
        return (j, tok)

    except Exception:
        return (None, tok)


def search(database: sqlite3.Connection, attrs: dict[str], queue: deque[tuple[int, dict | None]], start: int, incr: int) -> None:
    tok = get_access_token()
    # for i in range(start, sys.maxsize, incr):
    for i in range(start, 0, -incr):
        if i < attrs['min']:
            if attrs['halt']:
                attrs['threads'] -= 1
                return
            attrs['min'] = i
        entry, tok = try_entry(database, i, tok)
        queue.append((i, entry))


def convert_datetime(date: str) -> float:
    return (dateutil.parser.parse(date) - EPOCH).total_seconds()


def blank_data(database: sqlite3.Connection, i: int) -> None:
    database.execute(f'''
        insert or replace into APPLICATIONS (
            APPLICATION_ID
        )
        VALUES (?)
        ''', (i,)
    )


def add_to_data(database: sqlite3.Connection, data: dict) -> None:
    event = data['event']
    role_info = event['event_role_info']
    company = event['company']
    company_page = company['company_page']

    database.execute(f'''
    insert or replace into CLIENT_MANAGER (
        CLIENT_MANAGER_ID,
        CLIENT_MANAGER_EMAIL,
        CLIENT_MANAGER_NAME
    )
    VALUES (?, ?, ?)
    ''', (
        company['client_manager_id'],
        company['client_manager_email'],
        company['client_manager_name'],
    ))

    database.executemany('''
    insert or replace into IMAGE (
        IMAGE_ID,
        IMAGE_URL,
        IMAGE_TYPE,
        COMPANY_ID
    )
    VALUES (?, ?, ?, ?)
    ''', ((
        img['id'],
        img['url'],
        img['image_type'],
        company['id'],
    )
        for img in company_page['images']
    ))

    database.execute(f'''
    insert or replace into COMPANY (
        COMPANY_ID,
        COMPANY_NAME,
        COMPANY_PUBLIC_ID,
        COMPANY_AMOUNT_OF_EMPLOYEES,
        COMPANY_LAST_ACTIVE,
        COMPANY_RESPONSIVENESS,
    	CLIENT_MANAGER_ID
    )
    VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (
        company['id'],
        company['name'],
        company['url'],
        company_page['amount_of_employees'],
        convert_datetime(company['company_badges'][0]['last_active_on']),
        company['company_badges'][0]['type'],
        company['client_manager_id'],
    ))

    database.execute(f'''
    insert or replace into RECRUITER (
        RECRUITER_ID,
        RECRUITER_EMAIL,
        RECRUITER_NAME,
        COMPANY_ID
    )
    VALUES (?, ?, ?, ?)
    ''', (
        event['default_recruiter_id'],
        data['default_recruiter_email'],
        data['default_recruiter_name'],
        company['id'],
    ))

    database.execute(f'''
    insert or replace into EVENTS (
        EVENT_ID,
        EVENT_PUBLIC_ID,
        EVENT_NAME,
        EVENT_LOCATION,
        EVENT_CHECK_IN_CODE,
        EVENT_INSTRUCTIONS_TO_JOIN,
        EVENT_CREATE_DATE,
        EVENT_START_DATE,
        EVENT_END_DATE,
        EVENT_TIME_ZONE,
        EVENT_TYPE,
        EVENT_COVER_IMAGE_URL,
        EVENT_RSVP_LIMIT,
        COMPANY_ID
    )
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        event['id'],
        event['public_id'],
        event['name'],
        role_info['location'],
        role_info['checkin_code'],
        role_info['instructions_to_join'],
        convert_datetime(event['create_date']),
        convert_datetime(role_info['start_date']),
        convert_datetime(role_info['end_date']),
        role_info['time_zone'],
        role_info['type'],
        role_info['cover_image_url'],
        role_info['rsvp_limit'],
        company['id'],
    ))

    database.execute(f'''
    insert or replace into APPLICATIONS (
        APPLICATION_ID,
        APPLICATION_PUBLIC_ID,
        APPLICATION_CREATE_DATE,
        APPLICATION_STATUS,
        APPLICATION_TYPE,
        EVENT_ID
    )
    VALUES (?, ?, ?, ?, ?, ?)
    ''', (
        data['application_id'],
        data['application_public_id'],
        convert_datetime(data['application_create_date']),
        data['application_status'],
        data['application_type'],
        event['id'],
    ))


if __name__ == '__main__':
    database = make_database()
    try:
        start = get_min(database) - 1
    except Exception:
        start = 16909635

    th_count = 13
    attrs = {'min': start, 'halt': False, 'threads': th_count}
    queue = deque[tuple[int, dict | None]]()
    ths = [
        threading.Thread(target=search, args=(database, attrs, queue, start - o, th_count))
        for o in range(th_count)
    ]
    for t in ths:
        t.start()

    try:
        while True:
            while len(queue) == 0:
                pass
            i, e = queue.pop()
            if e:
                add_to_data(database, e)
            else:
                blank_data(database, i)
            database.commit()
            print(i)

    except KeyboardInterrupt:
        attrs['halt'] = True
        while attrs['threads'] > 0:
            pass
