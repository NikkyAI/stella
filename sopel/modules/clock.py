# coding=utf-8
# Copyright 2008-9, Sean B. Palmer, inamidst.com
# Copyright 2012, Elsie Powell, embolalia.com
# Licensed under the Eiffel Forum License 2.
from __future__ import unicode_literals, absolute_import, print_function, division

from datetime import datetime, timedelta

from pytz import LazySet

from sopel.logger import get_logger
from sopel.tools import Identifier

try:
    import pytz
except ImportError:
    pytz = None

from sopel.module import commands, example, OP, rule, event, intent

from sopel.tools.time import (
    get_timezone, format_time, validate_format, validate_timezone
)
from sopel.config.types import StaticSection, ValidatedAttribute
import dateutil.parser

LOGGER = get_logger(__name__)

common_timezones_set = LazySet([
    'Europe/London',
    'Europe/Berlin',
    'Africa/Cairo',
    'Europe/Moscow',
    'Asia/Dubai',
    'Asia/Tehran',
    'Indian/Maldives',
    'Asia/Kabul',
    'Antarctica/Vostok',
    'Asia/Calcutta',
    'Asia/Bangkok',
    'Asia/Rangoon',
    'Asia/Singapore',
    'Asia/Tokyo',
    'Asia/Pyongyang',
    'Australia/Eucla',
    'Australia/Queensland',
    'Australia/North',
    'Australia/Sydney',
    'Australia/South',
    'Pacific/Wallis',
    'Pacific/Auckland',
    'US/Hawaii',
    'Pacific/Chatham',
    'US/Alaska',
    'Pacific/Marquesas',
    'America/Los_Angeles',
    'America/Phoenix',
    'America/Chicago',
    'America/New_York',
    'Etc/GMT+4',
    'Etc/GMT+3',
    'Canada/Newfoundland',
    'Etc/GMT+2',
    'Etc/GMT+1',
])


class TimeSection(StaticSection):
    tz = ValidatedAttribute(
        'tz',
        parse=validate_timezone,
        serialize=validate_timezone,
        default='UTC'
    )
    """Default time zone (see http://sopel.chat/tz)"""
    time_format = ValidatedAttribute(
        'time_format',
        parse=validate_format,
        default='%Y-%m-%d - %T%Z'
    )
    """Default time format (see http://strftime.net)"""


def configure(config):
    config.define_section('clock', TimeSection)
    config.clock.configure_setting(
        'tz', 'Preferred time zone (http://sopel.chat/tz)')
    config.clock.configure_setting(
        'time_format', 'Preferred time format (http://strftime.net)')


def setup(bot):
    bot.config.define_section('clock', TimeSection)


response_channel = {}


def guess_tz(bot, nick, date_string):
    try:
        date = dateutil.parser.parse(date_string, fuzzy=True)
    except ValueError:
        LOGGER.error('cannot parse {nick}\'s date string {date_string}'.format(**locals()))
        if nick in response_channel:
            bot.say('cannot parse {nick}\'s date string {date_string}'.format(**locals()), response_channel[nick])
        return

    if not date.tzinfo:
        date = pytz.utc.localize(date)
        now = pytz.utc.localize(datetime.utcnow())
        difference = date - now
        minutes = int(round(difference.seconds / 60))
        utc_offset = timedelta(
            days=difference.days,
            minutes=int(round((minutes / 15)) * 15))
    else:
        utc_offset = date.utcoffset()

    name = None
    now = datetime.now()
    for tz in map(pytz.timezone, common_timezones_set):
        if tz.utcoffset(now) == utc_offset:
            name = tz.zone
            break
    if name:
        tz = name
        bot.db.set_nick_value(nick, 'timezone', tz)
        if nick in response_channel:
            bot.say('set timezone of {nick} to {tz}'.format(**locals()), response_channel[nick])
    else:
        if nick in response_channel:
            bot.say('could not find a timezone for utc offset {utc_offset}'.format(**locals()), response_channel[nick])


@rule('.*')
@event('NOTICE')
@intent('TIME')
def receive_notice(bot, trigger):
    datestring = trigger.group()
    LOGGER.info('{trigger.nick}: NOTICE TIME {datestring}'.format(**locals()))
    try:
        user = Identifier(trigger.nick)
        guess_tz(bot, user, datestring)
    except Exception as e:
        LOGGER.error('{e}'.format(**locals()))
        if trigger.nick in response_channel:
            bot.say('cannot parse {nick}\'s date string {date_string}'.format(**locals()), response_channel[trigger.nick])
        return


@rule(r"""\.guesstz
          (?:
            \s+(?P<user>\S+)
            (?:\s+(?P<datestring>.+))?
          )?
       """)
@example('.guesstz')
def guess(bot, trigger):
    user = trigger.group('user')
    if user:
        if not trigger.admin:
            bot.say('admin privileges required')
            return
        user = Identifier(user)
        datestring = trigger.group('datestring')
        if datestring:
            response_channel[user] = trigger.sender
            try:
                guess_tz(bot, user, datestring)
            except Exception as e:
                bot.say('{e}'.format(**locals()))
            return
    user = user or Identifier(trigger.nick)
    response_channel[user] = trigger.sender
    bot.say('sending CTCP TIME to {user}'.format(**locals()))
    bot.say('\001TIME\001', user)


@commands('t', 'time')
@example('.t America/New_York')
def f_time(bot, trigger):
    """Returns the current time."""
    if trigger.group(2):
        zone = get_timezone(bot.db, bot.config, trigger.group(2).strip(), None, None)
        if not zone:
            zone = get_timezone(bot.db, bot.config, None, trigger.nick, trigger.sender)
            if not zone:
                bot.say('Could not find timezone {}.'.format(trigger.group(2).strip()))
            else:
                time = format_time(bot.db, bot.config, zone, trigger.nick, trigger.sender)
                bot.say(time)
                bot.say('{arg} is not a valid timezone '
                        'or {arg} has not used .settz correctly '
                        '\x02\x033.help settz\x0F, '
                        'falling back to channel defaults'
                        .format(arg=trigger.group(2).strip()))
            return
    else:
        zone = get_timezone(bot.db, bot.config, None, trigger.nick,
                            trigger.sender)
    time = format_time(bot.db, bot.config, zone, trigger.nick, trigger.sender)
    bot.say(time)


@commands('settz', 'settimezone')
@example('.settz America/New_York')
def update_user(bot, trigger):
    """
    Set your preferred time zone. Most timezones will work, but it's best to
    use one from http://sopel.chat/tz
    """
    if not pytz:
        bot.reply("Sorry, I don't have timezone support installed.")
    else:
        tz = trigger.group(2)
        if not tz:
            bot.reply("What timezone do you want to set? Try one from "
                      "http://sopel.chat/tz")
            return
        if tz not in pytz.all_timezones:
            bot.reply("I don't know that time zone. Try one from "
                      "http://sopel.chat/tz")
            return

        bot.db.set_nick_value(trigger.nick, 'timezone', tz)
        if len(tz) < 7:
            bot.say("Okay, {}, but you should use one from http://sopel.chat/tz "
                    "if you use DST.".format(trigger.nick))
        else:
            bot.reply('I now have you in the %s time zone.' % tz)


@commands('gettz', 'gettimezone')
@example('.gettz [nick]')
def get_user_tz(bot, trigger):
    """
    Gets a user's preferred time zone, will show yours if no user specified
    """
    if not pytz:
        bot.reply("Sorry, I don't have timezone support installed.")
    else:
        nick = trigger.group(2)
        if not nick:
            nick = trigger.nick

        nick = nick.strip()

        tz = bot.db.get_nick_value(nick, 'timezone')
        if tz:
            bot.say('%s\'s time zone is %s.' % (nick, tz))
        else:
            bot.say('%s has not set their time zone' % nick)


@commands('settimeformat', 'settf')
@example('.settf %Y-%m-%dT%T%z')
def update_user_format(bot, trigger):
    """
    Sets your preferred format for time. Uses the standard strftime format. You
    can use http://strftime.net or your favorite search engine to learn more.
    """
    tformat = trigger.group(2)
    if not tformat:
        bot.reply("What format do you want me to use? Try using"
                  " http://strftime.net to make one.")
        return

    tz = get_timezone(bot.db, bot.config, None, trigger.nick, trigger.sender)

    # Get old format as back-up
    old_format = bot.db.get_nick_value(trigger.nick, 'time_format')

    # Save the new format in the database so we can test it.
    bot.db.set_nick_value(trigger.nick, 'time_format', tformat)

    try:
        timef = format_time(db=bot.db, zone=tz, nick=trigger.nick)
    except:
        bot.reply("That format doesn't work. Try using"
                  " http://strftime.net to make one.")
        # New format doesn't work. Revert save in database.
        bot.db.set_nick_value(trigger.nick, 'time_format', old_format)
        return
    bot.reply("Got it. Your time will now appear as %s. (If the "
              "timezone is wrong, you might try the settz command)"
              % timef)


@commands('gettimeformat', 'gettf')
@example('.gettf [nick]')
def get_user_format(bot, trigger):
    """
    Gets a user's preferred time format, will show yours if no user specified
    """
    nick = trigger.group(2)
    if not nick:
        nick = trigger.nick

    nick = nick.strip()

    # Get old format as back-up
    fmt = bot.db.get_nick_value(nick, 'time_format')

    if fmt:
        bot.say("%s's time format: %s." % (nick, fmt))
    else:
        bot.say("%s hasn't set a custom time format" % nick)


@commands('setchanneltz', 'setctz')
@example('.setctz America/New_York')
def update_channel(bot, trigger):
    """
    Set the preferred time zone for the channel.
    """
    if bot.privileges[trigger.sender][trigger.nick] < OP:
        return
    elif not pytz:
        bot.reply("Sorry, I don't have timezone support installed.")
    else:
        tz = trigger.group(2)
        if not tz:
            bot.reply("What timezone do you want to set? Try one from "
                      "http://sopel.chat/tz")
            return
        if tz not in pytz.all_timezones:
            bot.reply("I don't know that time zone. Try one from "
                      "http://sopel.chat/tz")
            return

        bot.db.set_channel_value(trigger.sender, 'timezone', tz)
        if len(tz) < 7:
            bot.say("Okay, {}, but you should use one from http://sopel.chat/tz "
                    "if you use DST.".format(trigger.nick))
        else:
            bot.reply(
                'I now have {} in the {} time zone.'.format(trigger.sender, tz))


@commands('getchanneltz', 'getctz')
@example('.getctz [channel]')
def get_channel_tz(bot, trigger):
    """
    Gets the preferred channel timezone, or the current channel timezone if no
    channel given.
    """
    if not pytz:
        bot.reply("Sorry, I don't have timezone support installed.")
    else:
        channel = trigger.group(2)
        if not channel:
            channel = trigger.sender

        channel = channel.strip()

        timezone = bot.db.get_channel_value(channel, 'timezone')
        if timezone:
            bot.say('%s\'s timezone: %s' % (channel, timezone))
        else:
            bot.say('%s has no preferred timezone' % channel)


@commands('setchanneltimeformat', 'setctf')
@example('.setctf %Y-%m-%dT%T%z')
def update_channel_format(bot, trigger):
    """
    Sets your preferred format for time. Uses the standard strftime format. You
    can use http://strftime.net or your favorite search engine to learn more.
    """
    if bot.privileges[trigger.sender][trigger.nick] < OP:
        return

    tformat = trigger.group(2)
    if not tformat:
        bot.reply("What format do you want me to use? Try using"
                  " http://strftime.net to make one.")

    tz = get_timezone(bot.db, bot.config, None, None, trigger.sender)

    # Get old format as back-up
    old_format = bot.db.get_channel_value(trigger.sender, 'time_format')

    # Save the new format in the database so we can test it.
    bot.db.set_channel_value(trigger.sender, 'time_format', tformat)

    try:
        timef = format_time(db=bot.db, zone=tz, channel=trigger.sender)
    except:
        bot.reply("That format doesn't work. Try using"
                  " http://strftime.net to make one.")
        # New format doesn't work. Revert save in database.
        bot.db.set_channel_value(trigger.sender, 'time_format', old_format)
        return
    bot.db.set_channel_value(trigger.sender, 'time_format', tformat)
    bot.reply("Got it. Times in this channel  will now appear as %s "
              "unless a user has their own format set. (If the timezone"
              " is wrong, you might try the settz and channeltz "
              "commands)" % timef)


@commands('getchanneltimeformat', 'getctf')
@example('.getctf [channel]')
def get_channel_format(bot, trigger):
    """
    Gets the channel's preferred time format, will return current channel's if
    no channel name is given
    """

    channel = trigger.group(2)
    if not channel:
        channel = trigger.sender

    channel = channel.strip()

    tformat = bot.db.get_channel_value(channel, 'time_format')
    if tformat:
        bot.say('%s\'s time format: %s' % (channel, tformat))
    else:
        bot.say('%s has no preferred time format' % channel)
