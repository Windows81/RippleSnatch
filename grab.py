import dateutil.parser
import datetime
import requests
import jwt

# Expires on 2023-03-07T01:52:17Z.
REFRESH_TOKEN = 'eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJmcmVzaCI6ZmFsc2UsImlhdCI6MTY3NTU2MTkzNywianRpIjoiM2Q2NGU2ODEtODQ4YS00MmQ5LThkMGYtYWMzY2U4MjM5NTZlIiwidHlwZSI6InJlZnJlc2giLCJzdWIiOjcwNTE2OSwibmJmIjoxNjc1NTYxOTM3LCJjc3JmIjoiOWI4NWRkYjYtNTMxZi00OGYwLTg2YTItMjc4ZjViYzViODBiIiwiZXhwIjoxNjc4MTUzOTM3LCJhY3QiOm51bGx9.aDVHOJBa6fpvZ3HzeLt7ClI0L_YS8rhOq94_YoeBUys'


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


ACCESS_TOKEN = get_access_token()


def get_response(iden: int, tok: str = ACCESS_TOKEN) -> requests.Response:
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


def is_past_max(i: int, e: dict) -> bool:
    cr_date = e['application_create_date']
    delta = (datetime.datetime.now(tz=datetime.timezone.utc) - dateutil.parser.parse(cr_date))
    return delta.total_seconds() < 1337


def try_entry(i: int) -> dict | None:
    # if check_in_data(database, i):
    # return

    global ACCESS_TOKEN
    while True:
        res = get_response(i, ACCESS_TOKEN)
        if res.status_code == 401:
            ACCESS_TOKEN = get_access_token()
            print(f'Error at (id={i})')
            continue
        break

    try:
        j: dict = res.json()
        msg_not_found = f'Record (id={i}) of type Application not found.'
        if j.get('message', '') == msg_not_found:
            raise Exception
        return j

    except Exception:
        return
