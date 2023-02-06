import dateutil.parser
import datetime
import sqlite3

EPOCH = datetime.datetime(1970, 1, 1, tzinfo=datetime.timezone.utc)


def convert_datetime(date: str) -> float:
    return (dateutil.parser.parse(date) - EPOCH).total_seconds()


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
    create table if not exists EVENT (
        EVENT_ID integer primary key,
        EVENT_PUBLIC_ID integer,

        EVENT_NAME text,
        EVENT_DESCRIPTION text,
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
    create table if not exists APPLICATION (
        APPLICATION_ID integer primary key,
        APPLICATION_PUBLIC_ID text,
        APPLICATION_CREATE_DATE integer,
        APPLICATION_STATUS integer,
        APPLICATION_TYPE text,
        EVENT_ID references EVENT
    )
    ''')
    database.execute('''
    create view if not exists EVENT_VIEW as
    select
        EVENT_ID,
        EVENT_PUBLIC_ID,
        EVENT_NAME,
        COMPANY_ID,
        COMPANY_NAME,
        EVENT_LOCATION,
        EVENT_CHECK_IN_CODE,
        EVENT_DESCRIPTION,
        EVENT_INSTRUCTIONS_TO_JOIN,
        datetime(EVENT_CREATE_DATE, 'unixepoch') as EVENT_CREATE_DATE,
        datetime(EVENT_START_DATE, 'unixepoch') as EVENT_START_DATE,
        datetime(EVENT_END_DATE, 'unixepoch') as EVENT_END_DATE,
        EVENT_TIME_ZONE,
        EVENT_TYPE,
        EVENT_COVER_IMAGE_URL
    from EVENT natural join COMPANY order by EVENT_START_DATE asc
    ''')
    database.execute('''
    create view if not exists EVENT_LINK_VIEW as
    select
        EVENT_ID,
        "https://app.ripplematch.com/event/" || COMPANY_PUBLIC_ID || "/" || EVENT_PUBLIC_ID as EVENT_URL,
        datetime(EVENT_START_DATE, 'unixepoch') as EVENT_START_DATE,
        datetime(EVENT_END_DATE, 'unixepoch') as EVENT_END_DATE
    from EVENT natural join COMPANY order by EVENT_START_DATE asc
    ''')
    database.commit()
    return database


DATABASE = make_database()


def add_to_data(i: int, data: dict | None) -> None:
    if not data:
        DATABASE.execute(f'''
            insert or replace into APPLICATION (
                APPLICATION_ID
            )
            VALUES (?)
            ''', (i,)
        )
        DATABASE.commit()
        return

    event = data['event']
    role_info = event['event_role_info']
    company = event['company']
    company_page = company['company_page']

    DATABASE.execute(f'''
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
    DATABASE.executemany('''
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
    DATABASE.execute(f'''
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
    DATABASE.execute(f'''
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
    DATABASE.execute(f'''
    insert or replace into EVENT (
        EVENT_ID,
        EVENT_PUBLIC_ID,
        EVENT_NAME,
        EVENT_DESCRIPTION,
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
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        event['id'],
        event['public_id'],
        event['name'],
        event['desc'],
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
    DATABASE.execute(f'''
    insert or replace into APPLICATION (
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
    DATABASE.commit()


def check_in_data(i: int) -> bool:
    record = DATABASE.execute(f'''
    select exists(
        select 1 from APPLICATION where APPLICATION_ID={i} limit 1
    )
    ''').fetchone()
    return record[0] == 1


def get_min() -> bool:
    record = DATABASE.execute(f'''
        select APPLICATION_ID as I from APPLICATION order by I asc limit 1
    ''').fetchone()
    return record[0]


def get_max() -> bool:
    record = DATABASE.execute(f'''
        select APPLICATION_ID as I from APPLICATION order by I desc limit 1
    ''').fetchone()
    return record[0]
