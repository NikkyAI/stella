# coding=utf-8
"""
this module adds quoting and retrieving quotes

# Copyright 2016, Niklas B, nikky.moe

"""

# from __future__ import unicode_literals
import re

import pickle

from sopel.config import StaticSection
from sopel.config.types import FilenameAttribute
from sopel.logger import get_logger
from sopel.tools import Identifier, SopelMemory
from sopel.module import rule, priority, commands, require_chanmsg, example, require_privmsg
from datetime import datetime
import sqlite3

LOGGER = get_logger(__name__)

log_key = 'quote_lines'
memory_key = 'quote_memory'
memory_size = 10
importer = None


class QuoteSection(StaticSection):
    filename = FilenameAttribute(
        'filename',
        default="quotes.db"
    )
    """file location of the sqlite database"""


def configure(config):
    config.define_section('quote', QuoteSection)
    config.quote.configure_setting(
        'filename', 'where tosave the quotes db')


def setup(bot):
    bot.config.define_section('quote', QuoteSection)
    bot.memory[log_key] = SopelMemory()
    bot.memory[memory_key] = list()


@rule('.*')
@priority('low')
def collect_lines(bot, trigger):
    """Create a temporary log of what people say"""

    # Don't log things in PM
    if trigger.is_privmsg:
        return

    # Add a log for the channel and nick, if there isn't already one
    if trigger.sender not in bot.memory[log_key]:
        bot.memory[log_key][trigger.sender] = SopelMemory()
    if Identifier(trigger.nick) not in bot.memory[log_key][trigger.sender]:
        bot.memory[log_key][trigger.sender][Identifier(trigger.nick)] = list()

    # Create a temporary list of the user's lines in a channel
    templist = bot.memory[log_key][trigger.sender][Identifier(trigger.nick)]
    line = trigger.group()
    if line.startswith("s/") or line.startswith(bot.config.core.help_prefix):
        # Don't remember substitutions or commands
        return
    elif line.startswith("\x01ACTION"):  # For /me messages
        line = line[:-1]
        templist.append(line)
    else:
        templist.append(line)

    del templist[:-10]  # Keep the log to 10 lines per person

    bot.memory[log_key][trigger.sender][Identifier(trigger.nick)] = templist


def isquote(bot, nick, channel, quote):
    # TODO grey out _ matched text
    search_dict = bot.memory[log_key]
    regex = re.sub('(?!\[|\]|_).', lambda m: re.escape(m.group()), quote)
    LOGGER.debug(regex)
    regex = re.sub('_', '(.*)', regex)
    LOGGER.debug(regex)
    regex = re.sub('(?:\\\ )?\[(.+)\](?:\\\ )?', '\s?(\g<1>)?\s?', regex)
    LOGGER.debug(regex)
    pattern = r'\b' + regex + r'\b'

    found_quote = None
    me = False
    if channel in search_dict and nick in search_dict[channel]:
        for line in reversed(search_dict[channel][nick]):
            if line.startswith("\x01ACTION"):
                me = True  # /me command
                line = line[8:]
            else:
                me = False
            match = re.match(pattern, line)
            if match:
                found_quote = line
                break

        if found_quote is not None:
            return True, found_quote, me
    return False, None, False


def get_data_provider(bot):
    filename = bot.config.quote.filename

    data_provider = SqliteQuotedataProvider(filename)
    return data_provider


@rule(r"""\.quote\srandom
          (?:
            \s+(?P<user>\S+)           # nick
          )?
       """)
@require_chanmsg()
@priority('high')
@example('.quote random Vi')
@commands('quote random')
def random(bot, trigger):
    user = trigger.group('user')
    data_provider = get_data_provider(bot)
    if user:
        output = data_provider.get_random_by_user(Identifier(user))
    else:
        output = data_provider.get_random()
    bot.say(output)


@rule(r"""\.quote\slist
          (?:
            \s+(?P<user>\S+)           # nick
          )?
       """)
@require_chanmsg()
@priority('high')
@example('.quote list Vi')
@commands('quote list')
def f_list(bot, trigger):
    user = trigger.group('user')
    data_provider = get_data_provider(bot)
    if user:
        output = data_provider.list_by_user(Identifier(user))
    else:
        output = data_provider.list()
    if isinstance(output, list):
        output = ', '.join([str(q) for q in output])
    bot.say(output)


@rule(r"""\.quote\sadd
          (?:
            \s+(?P<user>\S+)           # nick
          [:,]?)?                 # Followed by colon/comma and whitespace, if given
          \s+(?P<quote>.+)
          """)
@priority('low')
@require_chanmsg()
@example('.quote add Skye: Nikky, are you a goddess?')
@commands('quote add')
def add(bot, trigger):
    user = Identifier(trigger.group('user') or trigger.nick)
    quote = trigger.group('quote')
    channel = trigger.sender
    valid, realtext, me = isquote(bot, user, channel, quote)
    if not valid:
        bot.say('i cannot validate {} said {}'.format(user, quote))
        return
    data_provider = get_data_provider(bot)
    output = data_provider.add(user, channel, quote, realtext, trigger.nick, datetime.now())
    bot.say(output)


@rule(r"""\.quote\sforceadd
          (?:
            \s+(?P<user>\S+)           # nick
          [:,]?)?                 # Followed by colon/comma and whitespace, if given
          \s+(?P<quote>.+)
          """)
@priority('low')
@require_chanmsg()
@example('.quote forceadd RX14: .blame maxpowa')
@commands('quote forceadd')
def add(bot, trigger):
    if not trigger.admin:
        return
    user = Identifier(trigger.group('user') or trigger.nick)
    quote = trigger.group('quote')
    data_provider = get_data_provider(bot)
    channel = trigger.sender
    output = data_provider.add(user, channel, quote, quote, trigger.nick, datetime.now())
    bot.say(output)


@rule(r"""\.quote\s(?:delete|remove)\s+
          (?:
            (?P<user>\S+)           # nick
          [:,]\s+)?                 # Followed by colon/comma and whitespace, if given
          (?P<idx>.+)
          """)
@priority('low')
@require_chanmsg()
@example('.quote delete 69')
@commands('quote delete')
def delete(bot, trigger):
    identifier = int(trigger.group('idx'))
    data_provider = get_data_provider(bot)
    output = data_provider.remove(identifier)
    bot.say(output)


@rule(r"""\.quote\sshow\s+
          (?:
            (?P<user>\S+)           # nick
          [:,]\s+)?                 # Followed by colon/comma and whitespace, if given
          (?P<idx>.+)
          """)
@priority('low')
@require_chanmsg()
@example('.quote show 43')
@commands('quote show')
def show(bot, trigger):
    identifier = int(trigger.group('idx'))
    data_provider = get_data_provider(bot)
    output = data_provider.get_by_id(identifier)
    bot.say(output)


@rule(r"""\.quote\s(?:find|search)
          (?:
            (?P<user>\S+)           # nick
          [:,]\s+)?         # Followed by colon/comma and whitespace, if given
          (?P<search>\d+)     # One or more non-slashes or escaped slashes
          """)
@require_chanmsg()
@priority('high')
@example('.quote find lewd')
@commands('quote find')
def find(bot, trigger):
    search = trigger.group('search')
    data_provider = get_data_provider(bot)
    output = data_provider.search(search)
    bot.say(output)


@rule(r"""\.quote\sinfo\s+
          (?P<idx>.+)
          """)
@priority('low')
@require_chanmsg()
@example('.quote show 43')
@commands('quote show')
def info(bot, trigger):
    identifier = int(trigger.group('idx'))
    data_provider = get_data_provider(bot)
    output = data_provider.get_by_id(identifier)
    bot.say(output)
    raise NotImplementedError('Should have implemented this.')


@rule(r"""\.quote\sexportlistto
          (?:
            \s+(?P<receiver>\S+)           # nick
          )?
       """)
@require_privmsg()
@priority('high')
@commands('quote exportlistto')
def export_list(bot, trigger):
    data_provider = get_data_provider(bot)
    receiver = Identifier(trigger.group('receiver') or trigger.sender)
    output = data_provider.list()
    if isinstance(output, list):
        for quote in output:
            pickle = cPickle.dumps(quote).replace('\n', '\\n')
            bot.say('.quote import {}'.format(pickle), receiver)
            LOGGER.debug(pickle)
        bot.say('.quote importdone', receiver)


@rule(r"""\.quote\simport
            \s+(?P<pickle>.+)           # picked data
       """)
@require_privmsg()
@priority('high')
def f_import(bot, trigger):
    global importer
    if importer and not Identifier(trigger.nick) == importer:
        bot.say('{} is not a importer'.format(trigger.nick))
        LOGGER.warn('{} is not a importer'.format(trigger.nick))
        return
    pickle = trigger.group('pickle')
    data_provider = get_data_provider(bot)
    quote = cPickle.loads(str(pickle.replace('\\n', '\n')))
    data_provider.add(quote.user, quote.channel, quote.quote, quote.realtext, quote.submitter, quote.date)


@rule(r"""\.quote\simportfrom
            \s+(?P<user>\S+)
       """)
@priority('high')
@commands('quote importfrom')
def inport_from(bot, trigger):
    if not trigger.admin:
        return
    global importer
    importer = Identifier(trigger.group('user'))
    bot.say('.quote exportlistto {}'.format(bot.config.core.nick), importer)


@rule(r"""\.quote\simportdone
       """)
@require_privmsg()
@priority('high')
def f_import_done(bot, trigger):
    global importer
    if importer and not Identifier(trigger.nick) == importer:
        bot.say('{} is not a importer'.format(trigger.nick))
        return
    LOGGER.info('[{}] import done'.format(importer))
    importer = None


class Quote(object):
    def __init__(self, idx, user, channel, quote, realtext, submitter, date):
        self.idx = idx
        self.user = user
        self.channel = channel
        self.quote = quote
        self.realtext = realtext
        self.submitter = submitter
        self.date = date

    def __str__(self):
        return '[{self.idx}] {self.quote}'.format(**locals())

    def __repr__(self):
        return self.__str__()

    def decode(self, encoding):
        return self.__str__()


class QuotedataProvider    (object):
    def __init__(self, filename):
        self.filename = filename

    def get_random(self):
        raise NotImplementedError('Should have implemented this.')

    def get_random_by_user(self, user):
        raise NotImplementedError('Should have implemented this.')

    def list(self):
        raise NotImplementedError('Should have implemented this.')

    def list_by_user(self, user):
        raise NotImplementedError('Should have implemented this.')

    def search(self, data):
        raise NotImplementedError('Should have implemented this.')

    def add(self, user, channel, quote, realtext, submitter, date):
        raise NotImplementedError('Should have implemented this.')

    def remove(self, quote_id):
        raise NotImplementedError('Should have implemented this.')

    def get_by_id(self, quote_id):
        raise NotImplementedError('Should have implemented this.')


def quote_factory(cursor, row):
    d = {}
    for idx, col in enumerate(cursor.description):
        d[col[0]] = row[idx]
    return Quote(**d)


class SqliteQuotedataProvider    (QuotedataProvider):

    def __init__(self, filename):
        QuotedataProvider    .__init__(self, filename)

        # check if tables exist and create as necessary
        self.conn = sqlite3.connect(filename, detect_types=sqlite3.PARSE_DECLTYPES)
        self.conn.row_factory = quote_factory
        self.dbcursor = self.conn.cursor()
        self.dbcursor.execute('''
            create table if not exists quotes (idx integer primary key, user text not null, channel text not null, quote text not null, realtext text not null, submitter text not null, date timestamp)
        ''')
        self.conn.commit()

    def get_random(self):
        self.dbcursor.execute('''
            select * from quotes order by random() limit 1
        ''')
        msg = None
        quotes = self.dbcursor.fetchmany(1)
        self.conn.close()
        if len(quotes) == 0:
            msg = 'there are no quotes in the database.'
        return msg or quotes[0]

    def get_random_by_user(self, user):
        self.dbcursor.execute('''
            select * from quotes where user = ? order by random()  limit 1
        ''', (user,))
        msg = None
        quotes = self.dbcursor.fetchmany(1)
        self.conn.close()
        if len(quotes) == 0:
            msg = 'there are no quotes in the database.'
        return msg or quotes[0]

    def list(self):
        self.dbcursor.execute('''
            select * from quotes
        ''')
        msg = None
        quote_list = []
        quotes = self.dbcursor.fetchall()
        self.conn.close()
        if len(quotes) == 0:
            msg = 'there are no quotes in the database.'
        for quote in quotes:
            quote_list.append(quote)
        return msg or quote_list

    def list_by_user(self, user):
        self.dbcursor.execute('''
            select *, date from quotes where user = ?
        ''', (user,))
        msg = None
        quote_list = []
        quotes = self.dbcursor.fetchall()
        self.conn.close()
        if len(quotes) == 0:
            msg = 'there are no quotes from %s in the database.' % user
        for quote in quotes:
            quote_list.append(quote)
        return msg or quote_list

    def search(self, text):
        self.dbcursor.execute('''
            select * from quotes where quote like ? or realtext like ? order by random() limit 1
        ''', ('%' + text + '%',))
        quote = None
        quotes = self.dbcursor.fetchall()
        # if len(quotes) == 0:
        #     msg = 'there are no quotes in the database that match pattern = %s.' % (data)
        for quote in quotes:
            break
        self.conn.close()
        return quote

    def get_by_id(self, quote_id):
        self.dbcursor.execute('''
            select * from quotes where idx = ?
        ''', (quote_id,))
        msg = None
        quotes = self.dbcursor.fetchmany(1)
        self.conn.close()
        if len(quotes) == 0:
            msg = 'there is no id %s in the database.' % quote_id
        return msg or quotes[0]

    def add(self,  user, channel, quote, realtext, submitter, date):
        self.dbcursor.execute('''
            insert into quotes (user, channel, quote, realtext, submitter, date) values (?, ?, ?, ?,  ?, ?)
        ''', (user, channel, quote, realtext, submitter, date))
        self.conn.commit()
        self.conn.close()

        msg = 'quote added: %s.' % quote
        return msg

    def remove(self, quote_id):
        self.dbcursor.execute('''
            delete from quotes where idx = ?
        ''', (quote_id,))
        self.conn.commit()
        self.conn.close()

        msg = 'deleted quote #%d.' % quote_id
        return msg
