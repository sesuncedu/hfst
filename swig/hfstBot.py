"""
hfst-bot

If someone says the bot's name in the channel followed by a ': ' and a string,
e.g.

  <foo> hfstbot: koira

the bot will perform a lookup on the first word in the string and return the
results:

  <hfstbot> foo: koira<N><Sg><Nom><cap>

Run this script with three arguments: the irc server the bot should
connect to, the channel it should join and the file to use for analysis, e.g.:

  $ python hfstbot.py chat.freenode.net hfst /home/sam/ircbot/omorfi.hfstol

If the file $IRCSERVER-$CHANNELNAME-$TRANSDUCERFILE-misses.txt is writeable,
hfstbot will append to it words that it wasn't able to return any analyses for.
"""

# twisted imports
from twisted.words.protocols import irc
from twisted.internet import reactor, protocol
#from twisted.python import log

# system imports
import sys

import libhfst
from itertools import ifilterfalse as ffilter

logfilename = sys.argv[1] + "-" + sys.argv[2].replace('#','') + "-" + \
    sys.argv[3].split('/')[-1] + "-misses.txt"

class MorphologicalAnalyzer:
    """
    Class for morphological analysis
    """
    def __init__(self, filename):
        self.istr = libhfst.HfstInputStream(filename)
        self.transducer = libhfst.HfstTransducer(self.istr)

    def process_result_vector(self, rvector):
        results = []
        for entry in rvector:
            if len(entry) < 2:
                continue
            weight = entry[0]
            string = ''.join(
                ffilter(libhfst.FdOperation.is_diacritic, entry[1]))
            results.append(string)
        return results

    def analyze(self, message):
        """Return analyses"""
        results = self.transducer.lookup_fd(message)
        vresults = libhfst.vectorize(results)
        return self.process_result_vector(vresults)

    def close(self):
        pass
#        self.istr.close()

class HfstBot(irc.IRCClient):
    """Hfst-utilizing bot"""
    
    nickname = "hfstbot"
    
    def connectionMade(self):
        irc.IRCClient.connectionMade(self)
        self.analyzer = MorphologicalAnalyzer(self.factory.filename)

    def connectionLost(self, reason):
        irc.IRCClient.connectionLost(self, reason)
        if self.logfilehandle != None:
            self.logfilehandle.close()
        self.analyzer.close()

    # callbacks for events

    def signedOn(self):
        """Called when bot has succesfully signed on to server."""
        self.join(self.factory.channel)

    def joined(self, channel):
        """This will get called when the bot joins the channel."""
        print logfilename
        try:
            self.logfilehandle = open(logfilename, 'a')
        except IOError:
            self.logfilehandle = None

    def privmsg(self, user, channel, msg):
        """This will get called when the bot receives a message."""
        # Check to see if they're sending me a private message
        if channel == self.nickname:
            print "Got private message:"
            print "user: %s\nchannel: %s \nmsg:%s" %(user, channel, msg)
            #            self.msg(user, self.analyzer.analyze()
            return

        try:
            user = user.split('!', 1)[0]
            if ':' in msg:
                divpos = msg.index(':')
            elif ',' in msg:
                divpos = msg.index(',')
        except:
            print "Failed to parse message"
            print "user: %s\nchannel: %s \nmsg:%s" %(user, channel, msg)
            return
        
        # Otherwise check to see if it is a message directed at me
        if msg.startswith(self.nickname):
            msg = msg[divpos + 1:].strip().split(' ')[0].strip()
            replyprefix = "%s: " % user
            analysis_results = self.analyzer.analyze(msg)
            if len(analysis_results) == 0:
                self.notice(user, "I don't know that word!")
                if self.logfilehandle != None:
                    self.logfilehandle.write(msg + '\n')
            else:
                for result in analysis_results:
                    self.msg(channel, replyprefix + result)

    def action(self, user, channel, msg):
        """This will get called when the bot sees someone do an action."""
        pass
#        user = user.split('!', 1)[0]
#        self.logger.log("* %s %s" % (user, msg))

    # irc callbacks

    def irc_NICK(self, prefix, params):
        """Called when an IRC user changes their nickname."""
        pass
#        old_nick = prefix.split('!')[0]
#        new_nick = params[0]
#        self.logger.log("%s is now known as %s" % (old_nick, new_nick))


class HfstBotFactory(protocol.ClientFactory):
    """A factory for LogBots.

    A new protocol instance will be created each time we connect to the server.
    """

    # the class of the protocol to build when new connection is made
    protocol = HfstBot

    def __init__(self, channel, filename):
        self.channel = channel
        self.filename = filename

    def clientConnectionLost(self, connector, reason):
        """If we get disconnected, reconnect to server."""
        connector.connect()

    def clientConnectionFailed(self, connector, reason):
        print "connection failed:", reason
        reactor.stop()


if __name__ == '__main__':
    
    # create factory protocol and application
    f = HfstBotFactory(sys.argv[2], sys.argv[3])

    # connect factory to this host and port
    reactor.connectTCP(sys.argv[1], 6667, f)

    # run bot
    reactor.run()