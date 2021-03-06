# coding=utf-8
"""
help.py - Sopel Help Module
Copyright 2008, Sean B. Palmer, inamidst.com
Copyright © 2013, Elad Alfassa, <elad@fedoraproject.org>
Licensed under the Eiffel Forum License 2.
http://sopel.chat
"""
from __future__ import unicode_literals, absolute_import, print_function, division

import textwrap
import collections
import json
import subprocess

import requests

from sopel.logger import get_logger
from sopel.module import commands, rule, example, priority

logger = get_logger(__name__)


@rule('$nick' '(?i)(help|doc) +([A-Za-z]+)(?:\?+)?$')
@example('.help tell')
@commands('help', 'commands')
@priority('low')
def f_help(bot, trigger):
    """Shows a command's documentation, and possibly an example."""
    if trigger.group(2):
        name = trigger.group(2)
        name = name.lower()

        # number of lines of help to show
        threshold = 3

        if name in bot.doc:
            if len(bot.doc[name][0]) + (1 if bot.doc[name][1] else 0) > threshold:
                if trigger.nick != trigger.sender:  # don't say that if asked in private
                    bot.reply('The documentation for this command is too long; I\'m sending it to you in a private message.')
                msgfun = lambda l: bot.msg(trigger.nick, l)
            else:
                msgfun = bot.reply

            for line in bot.doc[name][0]:
                msgfun(line)
            if bot.doc[name][1]:
                msgfun('e.g. ' + bot.doc[name][1])
    else:
        # This'll probably catch most cases, without having to spend the time
        # actually creating the list first. Maybe worth storing the link and a
        # heuristic in config, too, so it persists across restarts. Would need a
        # command to regenerate, too...
        if 'command-gist' in bot.memory and bot.memory['command-gist'][0] == len(bot.command_groups):
            url = bot.memory['command-gist'][1]
        else:
            bot.say("Hang on, I'm creating a list.")
            msgs = []

            name_length = max(6, max(len(k) for k in bot.command_groups.keys()))
            for category, cmds in collections.OrderedDict(sorted(bot.command_groups.items())).items():
                category = category.upper().ljust(name_length)
                cmds = '  '.join(cmds)
                msg = category + '  ' + cmds
                indent = ' ' * (name_length + 2)
                # Honestly not sure why this is a list here
                msgs.append('\n'.join(textwrap.wrap(msg, subsequent_indent=indent)))

            url = create_gist(bot, '\n\n'.join(msgs))
            if not url:
                return
            bot.memory['command-gist'] = (len(bot.command_groups), url)
        bot.say("I've posted a list of my commands at {url} - You can see "
                "more info about any of these commands by doing {help_prefix}help "
                "<command> (e.g. {help_prefix}help time)".format(url=url, help_prefix=bot.config.core.help_prefix))


def create_gist(bot, msg):
    payload = {
        'description': 'Command listing for {}@{}'.format(bot.nick, bot.config.core.host),
        'public': 'true',
        'files': {
            'commands.txt': {
                "content": msg,
            },
        },
    }
    try:
        result = requests.post('https://api.github.com/gists',
                               json=payload)
        result.raise_for_status()
    except requests.HTTPError as e:
        bot.say("Sorry! Something went wrong.")
        logger.error("Error %s posting commands gist: %s",
                     e.response.status_code, e.response.text)
        return
    except requests.RequestException:
        bot.say("Sorry! Something went wrong.")
        logger.exception("Error posting commands gist")
        return

    result = result.json().get('files', {}).get('commands.txt', {}).get('raw_url')
    if not result:
        bot.say("Sorry! Something went wrong.")
        logger.error("Invalid result %s", result)
        return
    return result


@rule('$nick' '(?i)(help|doc) +([A-Za-z]+)(?:\?+)?$')
@example('.info')
@commands('info')
@priority('low')
def info(bot, trigger):
    githash = subprocess.check_output(['git', 'rev-list', '--count', 'HEAD'])
    bot.say("Stella - Revision #" + githash.rstrip("\n") + "- A bot created by Sofia, whose development is managed by #sapphire, however all final decisions are made by Princess Vi.")
    bot.say("For a gist of commands, please use: '{help_prefix}commands' with no parameters.".format(help_prefix=bot.config.core.help_prefix))

@commands('version')
def version(bot, trigger):
    githash = subprocess.check_output(['git', 'rev-list', '--count', 'HEAD'])
    bot.say("Stella - Revision #" + githash.rstrip("\n") + "")
