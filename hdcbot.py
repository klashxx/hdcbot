#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""hdcbot ...just another tweeter bot.

Usage:
  hdcbot.py [CNF] [options]

Arguments:
  CNF                        config file [default: config.yml]

Options:
  --daemon                   daemonized execution
  --unfollow                 unfollows non followers
  --followers=<screen_name>  followers proccesor (<me> = my account)
  --getid screen_name        id for a given screen name
  --version                  show program's version number and exit
  -h, --help                 show this help message and exit

"""

import logging
import os
import time
from random import randint
from threading import Thread

import tweepy
import yaml
from docopt import docopt
from tweepy.models import Status
from tweepy.utils import import_simplejson

json = import_simplejson()

CONFIG = './config.yml'


class StreamListener(tweepy.StreamListener):
    def __init__(self, api, logger, words=None, retweet=False):
        self.logger = logger
        self.words = words
        self.retweet = retweet
        super(StreamListener, self).__init__(api=api)

    def on_status(self, status):
        thread = Thread(
            target=tweet_processor,
            args=(self.api, status,),
            kwargs={'words': self.words, 'retweet': self.retweet}
        )
        thread.start()

    def on_data(self, raw_data):
        data = json.loads(raw_data)
        self.logger.debug('raw_data: %s', str(raw_data))

        if 'in_reply_to_status_id' in data:
            status = Status.parse(self.api, data)
            if self.on_status(status) is False:
                return False
        elif 'delete' in data:
            delete = data['delete']['status']
            if self.on_delete(delete['id'], delete['user_id']) is False:
                return False
        elif 'event' in data:
            status = Status.parse(self.api, data)
            if self.on_event(status) is False:
                return False
        elif 'direct_message' in data:
            status = Status.parse(self.api, data)
            if self.on_direct_message(status) is False:
                return False
        elif 'friends' in data:
            if self.on_friends(data['friends']) is False:
                return False
        elif 'limit' in data:
            if self.on_limit(data['limit']['track']) is False:
                return False
        elif 'disconnect' in data:
            if self.on_disconnect(data['disconnect']) is False:
                return False
        elif 'warning' in data:
            if self.on_warning(data['warning']) is False:
                return False
        else:
            self.logger.error('Unknown message type: %s', str(raw_data))

    def on_error(self, status_code):
        if status_code == 420:
            return False


def get_config(config_file):
    with open(config_file) as stream:
        return yaml.load(stream)


def get_logger():
    logger = logging.getLogger('hdcbot')
    fmt = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    handler = logging.StreamHandler()
    logger.setLevel(logging.DEBUG)
    handler.setLevel(logging.DEBUG)
    handler.setFormatter(fmt)
    logger.addHandler(handler)

    return logger

def tweet_processor(api, status, words=None, retweet=False):
    logger = logging.getLogger('hdcbot')

    try:
        possibly_sensitive = status.possibly_sensitive
    except AttributeError:
        possibly_sensitive = False

    logger.info(
        'processing tweet: %d screen_name: %s location: %s',
        status.id,
        status.user.screen_name,
        status.user.location
    )

    try:
        retweeted_status = status.retweeted_status
    except AttributeError:
        is_retweet = False
    else:
        is_retweet = True
        logger.debug('retweet detected')

    if possibly_sensitive:
        logger.debug('sensitive tweet')
        return True

    if status.in_reply_to_screen_name is not None:
        logger.debug('reply tweet')
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
            if not any(w.lower() in [tw.lower() for tw in tweet_words]
                       for w in look):
                return True

        if isinstance(block, list):
            if any(w.lower() in [tw.lower() for tw in tweet_words]
                   for w in block):
                logger.debug('tweet blocked: %d', status.id)
                return True

    if (not status.retweeted and not is_retweet and (
            status.retweet_count > params['min_retweet_count'] and
            status.user.followers_count > params['min_followers_count'])
            or retweet):

        seconds_to_wait = randint(randint(10, 30), 60 * 3)
        logger.debug(
            'waiting to retweet id: %d for %d seconds',
            status.id,
            seconds_to_wait
        )
        time.sleep(seconds_to_wait)

        try:
            api.retweet(status.id)
        except tweepy.TweepError as error:
            try:
                error_code = error.args[0][0]['code']
            except TypeError:
                logger.error(
                    '%s, sleeping for %d minutes',
                    error,
                    params['mins_sleep']
                )
                time.sleep(60 * params['mins_sleep'])
            else:
                if error_code != 327:
                    logger.error(
                        'unable to retweet %d: %s', status.id, error
                    )
                else:
                    logger.debug('already retweeted, id: %d', status.id)
        else:
            logger.debug('id: %d retweeted!', status.id)

    if not status.favorited:
        seconds_to_wait = randint(randint(10, 30), 60 * 2)
        logger.debug(
            'waiting to favor id: %d for %d seconds',
            status.id,
            seconds_to_wait
        )
        time.sleep(seconds_to_wait)

        try:
            api.create_favorite(status.id)
        except tweepy.TweepError as error:
            try:
                error_code = error.args[0][0]['code']
            except TypeError:
                logger.error(
                    '%s, sleeping for %d minutes',
                    error,
                    params['mins_sleep'])
                time.sleep(60 * params['mins_sleep'])
            else:
                if error_code != 139:
                    logger.error(
                        'unable to favor tweet %d: %s', status.id, error
                    )
                else:
                    logger.debug('already favorited, id: %d', status.id)
        else:
            logger.debug('id: %d favorited!', status.id)

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

def followers_processor(api, screen_name=None, items_number=5000):
    logger = logging.getLogger('hdcbot')
    batch_count = 0

    if screen_name is None or screen_name == 'me':
        ref_user = api.me()
    else:
        ref_user = get_user(api, screen_name)

    if ref_user is None:
        logger.error('unable to get user for follower processor')
        return None

    logger.info(
        'processing followers for user: %s (%d)',
        ref_user.screen_name,
        ref_user.followers_count
    )

    for follower in tweepy.Cursor(
        api.followers,
        id=ref_user.id).items(items_number):

        if follower.following:
            logger.debug('%s already followed', follower.screen_name )
            continue

        if follower.followers_count < params['min_followers_count']:
            logger.debug(
                '%d: not enough followers for %s',
                follower.followers_count,
                follower.screen_name
            )
            continue

        if (follower.followers_count + params['add_followers_count'] <
            follower.friends_count):
            logger.debug(
                '%d: not enough friends for %s',
                follower.friends_count,
                follower.screen_name
            )
            continue

        batch_count += 1
        logger.info(
            'processing follower: %s batch number: %d',
            follower.screen_name,
            batch_count
        )

        if batch_count % params['max_batch'] == 0:
            seconds_to_wait = 60 * params['mins_sleep'] * 2
            logger.debug('batch pause for %d seconds', seconds_to_wait)
            time.sleep(seconds_to_wait)

        try:
            follower.follow()
        except tweepy.TweepError:
            logger.error('unable to follow: %s', follower.screen_name)
            continue

        logger.info('%s followed!', follower.screen_name)

        try:
            last_tweets = api.user_timeline(user_id=follower.id, count=3)
        except tweepy.TweepError:
            continue

        for status in last_tweets:
            tweet_processor(api, status)

    return None


def get_api(logger):
    auth = tweepy.OAuthHandler(os.environ['API_KEY'], os.environ['API_SECRET'])
    auth.set_access_token(os.environ['TOKEN'], os.environ['TOKEN_SECRET'])

    return tweepy.API(
        auth,
        wait_on_rate_limit=True,
        wait_on_rate_limit_notify=True,
        compression=True
    )


def daemon_thread(api, config_file):
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
        listener=StreamListener(
            api,
            logger,
            words=words,
            retweet=params['retweet_tracker']
        )
    )
    stream_tracker.filter(languages=['es'], track=track, async=True)

    logger.info('stream_watcher launched')
    stream_watcher = tweepy.Stream(
        auth=api.auth,
        listener=StreamListener(
            api,
            logger,
            words=None,
            retweet=params['retweet_follow']
        )
    )
    stream_watcher.filter(
        follow=[str(f['user_id']) for f in follow],
        async=True
    )

def get_user(api, screen_name):
    logger = logging.getLogger('hdcbot')

    try:
        user = api.get_user(screen_name)
    except tweepy.TweepError as error:
        logger.error('unable to get %s id: %s', screen_name, error)
        return None

    logger.info('user id for %s: %d', screen_name, user.id)

    return user

def main(arguments):
    config = arguments['CNF'] if arguments['CNF'] is not None else CONFIG
    daemon = arguments['--daemon']
    unfollow = arguments['--unfollow']
    followers = arguments['--followers']
    screen_name = arguments['--getid']

    try:
        config_file = get_config(config)
    except FileNotFoundError:
        print('unable to open file: {0}'.format(config))
        return None

    global params
    params = config_file['params']

    api = get_api(get_logger())

    if screen_name is not None:
        get_user(api, screen_name)

    if unfollow:
        unfollower(api, config_file)

    if daemon:
        daemon_thread(api, config_file)

    if followers is not None:
        followers_processor(api, screen_name=followers)

    return None

if __name__ == '__main__':
     main(docopt(__doc__, version='0.1'))
