"""
WolframAlpha Module
"""

import xml.etree.ElementTree as ET, sys, sopel.module, urllib


@sopel.module.commands("wa","wolfram")
def wa(bot, trigger):
	q = trigger.group(2)
	if not q:
		return bot.reply('No trigger recieved.')

	query = urllib.quote(q.encode('utf-8'))

	uri = 'http://api.wolframalpha.com/v2/query?appid=3YKPRR-HVW54Y3QTY&input='
	print(uri + query)
	r = ET.fromstring(urllib.urlopen(uri + query).read())
	if r is not None and r.get("success")[:1] is "t":
		result = list(r.iter("plaintext"))[1].text
		if result:
			lines = result[:450].split("\n")
			for line in lines:
				bot.reply(line)
	else:
		bot.reply("I'm sorry, I'm afraid I can't do that.")
