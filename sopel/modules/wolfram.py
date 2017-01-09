"""
WolframAlpha Module
"""
try:
    from future.moves.urllib.parse import urlparse, urlencode, quote
    from future.moves.urllib.request import urlopen, Request
    from future.moves.urllib.error import HTTPError
except ImportError:
    from urllib import urlencode, urlopen, quote
    
import xml.etree.ElementTree as ET, sys, sopel.module


@sopel.module.commands("wa", "wolfram")
def wa(bot, trigger):
    q = trigger.group(2)
    if not q:
        return bot.reply('No trigger recieved.')

    query = quote(q.encode('utf-8'))

    uri = 'http://api.wolframalpha.com/v2/query?appid=3YKPRR-HVW54Y3QTY&input='
    print(uri + query)
    r = ET.fromstring(urlopen(uri + query).read())
    if r is not None and r.get("success")[:1] is "t":
        result = list(r.iter("plaintext"))[1].text
        if result:
            lines = result[:450].split("\n")
            for line in lines:
                bot.reply(line)
    else:
        bot.reply("I'm sorry, I'm afraid I can't do that.")
