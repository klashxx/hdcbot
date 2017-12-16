"""
HDCBot
"""
import logging

import tweepy
from decouple import config

class StreamListener(tweepy.StreamListener):
    def __init__(self, api, logger):
        self.logger = logger
        super(StreamListener, self).__init__(api=api)

    def on_status(self, status):
        try:
            new_favorite = self.api.create_favorite(status.id)
        except tweepy.TweepError:
            self.logger.debug('unable to like tweet: %d', status.id)
        else:
            self.logger.info('tweet favorited: %d', new_favorite.id)


    def on_error(self, status_code):
        if status_code == 420:
            return False


def get_logger():
    logger = logging.getLogger('hdcbot')
    fmt = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    handler = logging.StreamHandler()
    logger.setLevel(logging.DEBUG)
    handler.setLevel(logging.DEBUG)
    handler.setFormatter(fmt)
    logger.addHandler(handler)

    return logger


def process_followers(api, logger, last_count=0):
    followers_count = api.me().followers_count
    logger.info('followers count: %d', followers_count)
    if followers_count <= last_count:
        return followers_count

    for follower in tweepy.Cursor(api.followers, screen_name='HijosDelCid').items(5):
        logger.info('processing follower: %s', follower.screen_name)

        if not follower.following and (
                follower.followers_count > 50 and
                follower.followers_count + 50 > follower.friends_count):
            try:
                follower.follow()
            except tweepy.TweepError:
                logger.error('unable to follow')
            else:
                logger.info('followed!')


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
        wait_on_rate_limit_notify=True,
        compression=True
    )


def main():
    num_followers = 0
    logger = get_logger()
    api = get_api(logger)

    num_followers = process_followers(api, logger, last_count=num_followers)

    logger.debug(api.rate_limit_status())

    track = config('TRACK').split(',')

    logger.info('tracking: %s', str(track))

    stream = tweepy.Stream(auth=api.auth, listener=StreamListener(api, logger))
    stream.filter(track=track, async=True)

    return None

if __name__ == '__main__':
    main()
