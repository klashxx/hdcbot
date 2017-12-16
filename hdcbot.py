"""
HDC Bot
"""
import logging

import tweepy
from decouple import config



def get_logger():
    logger = logging.getLogger('hdcbot')
    fmt = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    ch = logging.StreamHandler()
    logger.setLevel(logging.DEBUG)
    ch.setLevel(logging.DEBUG)
    ch.setFormatter(fmt)
    logger.addHandler(ch)

    return logger

def get_friends(api):
    for friend in tweepy.Cursor(api.friends).items():
        print (friend.screen_name)

def get_api(logger):
    api_key = config('API_KEY')
    api_secret = config('API_SECRET')
    token = config('TOKEN')
    token_secret = config('TOKEN_SECRET')

    logger.debug('API_KEY: %s', api_key)
    logger.debug('API_SECRET: %s', api_secret)
    auth = tweepy.OAuthHandler(api_key, api_secret)
    auth.set_access_token(token, token_secret)

    return tweepy.API(
        auth,
        wait_on_rate_limit=True,
        wait_on_rate_limit_notify=True
    )

def main():
    logger = get_logger()
    api = get_api(logger)

    try:
        get_friends(api)
    except tweepy.error.RateLimitError:
        logger.error('rate limit exceed')

if __name__ == '__main__':
    main()
