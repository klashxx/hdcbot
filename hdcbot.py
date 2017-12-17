#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""hdcbot ...just another tweeter bot.

Usage:
  hdcbot.py [options]

Options:
  --non-daemon         avoid daemonized execution
  --unfollow           unfollows non followers
  --followers          followers proccesor
  --version            show program's version number and exit
  -h, --help           show this help message and exit

"""

import logging
import os
import time

import tweepy
import yaml
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


def tweet_processor(api, status, words=None):
    logger = logging.getLogger('hdcbot')

    try:
        possibly_sensitive = status.possibly_sensitive
    except AttributeError:
        possibly_sensitive = False

    logger.info(
        'processing tweet: %d location: %s', status.id, status.user.location
    )

    if possibly_sensitive:
        logger.debug('sensitive tweet')
        return True

    logger.debug(
        'retweeted: %s (%d) favorited: %s (%d)',
        str(status.retweeted),
        status.retweet_count,
        str(status.favorited),
        status.favorite_count
    )


    text = status.text.splitlines()
    logger.debug('text: %s,', str(text))

    if words is not None:
        tweet_words = ' '.join(text).split()
        logger.debug('text: %s,', str(tweet_words))

        try:
            look = words['look']
        except:
            look = None

        try:
            block = words['block']
        except:
            block = None

        if isinstance(look, list):
            if not any(w in tweet_words for w in look):
                return True

        if isinstance(block, list):
            if any(w in tweet_words for w in block):
                logger.debug('tweet blocked')
                return True

    if (not status.retweeted and
            status.retweet_count > 10 and
            status.user.followers_count > 70):

        try:
            api.retweet(status.id)
        except tweepy.TweepError as error:
            try:
                error_code = error.args[0][0]['code']
            except TypeError:
                logger.error('%s, sleeping for %d minutes', error, MIN_SLEEP)
                time.sleep(60 * MIN_SLEEP)
            else:
                if error_code != 327:
                    logger.error('unable to retweet: %s', error)
                else:
                    logger.debug('already retweeted')
        else:
            logger.debug('retweeted!')

    if not status.favorited:
        try:
            api.create_favorite(status.id)
        except tweepy.TweepError as error:
            try:
                error_code = error.args[0][0]['code']
            except TypeError:
                logger.error('%s, sleeping for %d minutes', error, MIN_SLEEP)
                time.sleep(60 * MIN_SLEEP)
            else:
                if error_code != 139:
                    logger.error('unable to favor tweet %s', error)
                else:
                    logger.debug('already favorited')
        else:
            logger.debug('tweet favorited!')

    return True


def unfollower(api, config_file):
    logger = logging.getLogger('hdcbot')

    try:
        omit = [f['user_id'] for f in config_file['omit']]
    except:
        omit = []

    logger.debug('white list: %s', str(omit))

    friends_ids = api.friends_ids()

    my_id = api.me().id

    for friend_id in friends_ids:
        friendship = api.show_friendship(
            source_id=my_id,
            target_id=friend_id
        )[1]
        if not friendship.following and friend_id not in omit:
            try:
                api.destroy_friendship(friend_id)
            except tweepy.TweepError:
                pass
            else:
                logger.info('user: %s unfollowed!', friendship.screen_name)

    return None

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
    auth = tweepy.OAuthHandler(os.environ['API_KEY'], os.environ['API_SECRET'])
    auth.set_access_token(os.environ['TOKEN'], os.environ['TOKEN_SECRET'])

    return tweepy.API(
        auth,
        wait_on_rate_limit=True,
        wait_on_rate_limit_notify=True,
        compression=True
    )


def daemon(api, config_file):
    logger = logging.getLogger('hdcbot')

    track = config_file['track']
    words = config_file['words']
    follow = config_file['follow']

    logger.info('tracking: %s', str(track))
    logger.info('words: %s', str(words))
    logger.info('follow: %s', str(follow))

    logger.info('stream_tracker launched')
    stream_tracker = tweepy.Stream(
        auth=api.auth,
        listener=StreamListener(api, logger, words=None)
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
    non_daemon = arguments['--non-daemon']
    unfollow = arguments['--unfollow']
    followers = arguments['--followers']

    num_followers = 0
    logger = get_logger()
    config_file = get_config(CONFIG)

    api = get_api(logger)

    if unfollow:
        unfollower(api, config_file)

    if not non_daemon:
        daemon(api, config_file)

    if followers:
        while True:
            num_followers = followers_processor(api, last_count=num_followers)
            time.sleep(60 * MIN_SLEEP * 4)

    return None

if __name__ == '__main__':
    main(docopt(__doc__, version='0.1'))
