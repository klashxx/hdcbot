"""
HDCBot
"""
import logging
import time

import tweepy
import yaml
from decouple import config

CONFIG = './config.yml'

class StreamListener(tweepy.StreamListener):
    def __init__(self, api, logger):
        self.logger = logger
        super(StreamListener, self).__init__(api=api)

    def on_status(self, status):
        tweet_processor(self.api, status)

    def on_error(self, status_code):
        if status_code == 420:
            return False

def get_config(config_file):
    with open(config_file) as stream:
        return yaml.load(stream)

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


def tweet_processor(api, tweet):
    logger = logging.getLogger('hdcbot')
    logger.info('processing tweet: %d', tweet.id)
    logger.debug(
        'retweeted: %s (%d) favorited: %s (%d)',
        str(tweet.retweeted),
        tweet.retweet_count,
        str(tweet.favorited),
        tweet.favorite_count
    )

    if not tweet.retweeted and tweet.retweet_count > 5:
        try:
            api.retweet(tweet.id)
        except tweepy.TweepError:
            logger.error('unable to retweet')
        else:
            logger.info('retweeted!')

    if not tweet.favorited:
        try:
            api.create_favorite(tweet.id)
        except tweepy.TweepError:
            logger.debug('unable to favor')
        else:
            logger.info('tweet favorited!')

    return True

def process_wath_list(api, watch_list):
    logger = logging.getLogger('hdcbot')

    for screen_name in watch_list:
        logger.info('processing watch user: %s', screen_name)
        try:
            last_tweets = api.user_timeline(screen_name=screen_name, count=3)
        except tweepy.TweepError:
            logger.error('unable to get user timeline')
            continue

        for tweet in last_tweets:
            tweet_processor(api, tweet)



def process_followers(api, last_count=0):
    logger = logging.getLogger('hdcbot')

    followers_count = api.me().followers_count
    logger.info('followers count: %d', followers_count)
    if followers_count <= last_count:
        return followers_count

    for follower in tweepy.Cursor(api.followers).items():
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
        try:
            last_tweets = api.user_timeline(user_id=follower.id, count=3)
        except tweepy.TweepError:
            continue

        for tweet in last_tweets:
            tweet_processor(api, tweet)


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
    config_file = get_config(CONFIG)
    api = get_api(logger)

    process_wath_list(api, config_file['watch'])

    track = config('TRACK').split(',')

    logger.info('tracking: %s', str(track))

    stream = tweepy.Stream(auth=api.auth, listener=StreamListener(api, logger))
    stream.filter(track=track, async=True)

    while True:
        num_followers = process_followers(api, last_count=num_followers)
        time.sleep(60 * 60)

    return None

if __name__ == '__main__':
    main()
