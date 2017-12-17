#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""hdcbot ...just another tweeter bot.

Usage:
  hdcbot.py [options]

Options:
  --not-daemon         avoid daemonized execution.
  --version            show program's version number and exit
  -h, --help           show this help message and exit

"""

import logging
import time

import tweepy
import yaml
from decouple import config
from docopt import docopt

CONFIG = './config.yml'
MIN_SLEEP = 15

class StreamListener(tweepy.StreamListener):
    def __init__(self, api, logger, words=None):
        self.logger = logger
        self.words = words
        super(StreamListener, self).__init__(api=api)

    def on_status(self, status):
        tweet_processor(self.api, status, words=self.words)

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


def tweet_processor(api, tweet, words=None):
    logger = logging.getLogger('hdcbot')

    try:
        possibly_sensitive = tweet.possibly_sensitive
    except AttributeError:
        possibly_sensitive = False

    logger.info('processing tweet: %d location: %s', tweet.id, tweet.user.location)

    if possibly_sensitive:
        logger.debug('sensitive tweet')
        return True

    logger.debug(
        'retweeted: %s (%d) favorited: %s (%d)',
        str(tweet.retweeted),
        tweet.retweet_count,
        str(tweet.favorited),
        tweet.favorite_count
    )

    text = tweet.text.splitlines()
    logger.debug('text: %s,', str(text))

    if isinstance(words, list):
        tweet_words = ' '.join(text).split()
        logger.debug('text: %s,', str(tweet_words))
        if not any(w in tweet_words for w in words):
            return True

    if not tweet.retweeted and tweet.user.followers_count > 70:
        try:
            api.retweet(tweet.id)
        except tweepy.TweepError as error:
            try:
                error_code = error.args[0][0]['code']
            except TypeError:
                logger.error('%s , sleeping for %d minutes', error, MIN_SLEEP)
                time.sleep(60 * MIN_SLEEP)
            else:
                if error_code != 327:
                   logger.error('unable to retweet: %s', error)
                else:
                    logger.debug('already retweeted')
        else:
            logger.debug('retweeted!')

    if not tweet.favorited:
        try:
            api.create_favorite(tweet.id)
        except tweepy.TweepError as error:
            try:
                error_code = error.args[0][0]['code']
            except TypeError:
                logger.error('%s , sleeping for %d minutes', error, MIN_SLEEP)
                time.sleep(60 * MIN_SLEEP)
            else:
                if error_code != 139:
                    logger.error('unable to favor tweet %s', error)
                else:
                    logger.debug('already favorited')
        else:
            logger.debug('tweet favorited!')

    return True


def followers_processor(api, last_count=0):
    logger = logging.getLogger('hdcbot')

    followers_count = api.me().followers_count
    logger.info('followers count: %d', followers_count)
    if last_count is None:
        last_count = 0
    if followers_count == last_count:
        return followers_count

    for follower in tweepy.Cursor(api.followers).items():
        logger.info('processing follower: %s', follower.screen_name)

        if not follower.following and (
                follower.followers_count > 90 and
                follower.followers_count + 300 > follower.friends_count):
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

    return followers_count


def get_api(logger):
    auth = tweepy.OAuthHandler(config('API_KEY'), config('API_SECRET'))
    auth.set_access_token(config('TOKEN'), config('TOKEN_SECRET'))

    return tweepy.API(
        auth,
        wait_on_rate_limit=True,
        wait_on_rate_limit_notify=True,
        compression=True
    )


def daemon(api):
    logger = logging.getLogger('hdcbot')

    config_file = get_config(CONFIG)
    track = config_file['track']
    words = config_file['words']
    follow = config_file['follow']

    logger.info('tracking: %s', str(track))
    logger.info('words: %s', str(words))
    logger.info('follow: %s', str(follow))

    logger.info('stream_tracker launched')
    stream_tracker = tweepy.Stream(
        auth=api.auth,
        listener=StreamListener(api, logger, words=words)
    )
    stream_tracker.filter(track=track, async=True)

    logger.info('stream_watcher launched')
    stream_watcher = tweepy.Stream(
        auth=api.auth,
        listener=StreamListener(api, logger, words=None)
    )
    stream_watcher.filter(
        follow=[str(f['user_id']) for f in follow],
        async=True
    )


def main(arguments):
    not_daemon = arguments['--not-daemon']
    num_followers = 0

    logger = get_logger()

    api = get_api(logger)

    if not not_daemon:
        daemon(api)

    while True:
        num_followers = followers_processor(api, last_count=num_followers)
        time.sleep(60 * MIN_SLEEP * 4)

    return None

if __name__ == '__main__':
    main(docopt(__doc__, version='0.1'))
