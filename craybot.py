#!/usr/bin/env python
##########################################
##
##    Craybot - a multipurpose Internet Relay Chat bot
##    Copyright (C) 2009 Michael Aboff
##                       
##    This program and all software included with this distribution is free software: you can redistribute it and/or modify
##    it under the terms of the GNU General Public License as published by
##    the Free Software Foundation, either version 3 of the License, or
##    (at your option) any later version.
##
##    This program is distributed in the hope that it will be useful,
##    but WITHOUT ANY WARRANTY; without even the implied warranty of
##    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
##    GNU General Public License for more details.
##
##    You should have received a copy of the GNU General Public License
##    along with this program.  If not, see <http://www.gnu.org/licenses/>.
##
##########################################
# Misc imports
import time, sys, urllib, pickle, random, re, os, shelve, math, httplib, datetime, hashlib

# Craybot imports
import commands.regcmds as regcmd
import commands.opcmds as opcmd
import commands.settings as settings
import startup.craybot_initdata as data
import commands.chanprotection as protect

# Twisted imports
import twisted
from twisted.words.protocols import irc
from twisted.internet import reactor, protocol, task, defer

# Modules
for term in data.modules:
    try:
        exec("import %s as %s" % ('modules.'+term[0], term[0]))
        print("importing special module: modules.%s" %(term[0]))
    except ImportError:
        print("ERROR: %s module not found!!" % (term[0].upper()))

# Debug & server variables
global debug, server, chans
server = data.server
debug = False
if debug:
    chans = '#craybot'
    print("#################### DEBUG MODE ####################")
else:
    chans = data.channels

# Code
class Bot(irc.IRCClient):

    def __init__(self):
        if debug:
            deb = 'DEBUG MODE'
        else:
            deb = ''
        self.version = "2.1.0 %s" % deb
        self.nickname = data.nickname
        self.realname = 'Craybot v%s by Michael Aboff' % self.version
        self.username = 'Craybot
        self.password = data.password
        self.trigger = data.trigger
        self.ubertrigger = data.ubertrigger
        self.Owner = data.owner.lower()
        
        self.defaultpass = hashlib.sha1('pass').hexdigest()
        
        self.versionName = "Craybot"
        self.versionNum = self.version
        self.versionEnv = "Twisted %s - Python %s" % (twisted.version.short(), sys.version.split()[0])
        
        # Spam variables
        self.cap_ratio = 0.65
        self.special_ratio = 0.59
        self.min_sent_len = 45
        self.max_reps = 10
        self.floodmax = 6
        self.floodtime = 11
        
        self.userhost_defer = {}
    
    def printer(self, message):
        lt = time.localtime()
        date = "%d/%d/%d %d:%d.%d" % (lt[1],lt[2],lt[0],lt[3],lt[4],lt[5])
        data.log.write("[%s] %s\n" % (date, message))
        data.log.flush()
        
    def debugprint(self, message):
        if debug:
            self.printer(message)
    
    def connectionMade(self):
        irc.IRCClient.connectionMade(self)
    
    def connectionLost(self, reason):
        self.printer("!!! ERROR: LOST CONNECTION! REASON:  %s" % reason)
        irc.IRCClient.connectionLost(self, reason)
    
    def signedOn(self):
        self.join(self.factory.channel)
        self.mode(self.nickname, True, '+B', limit=None, user=self.nickname)
        print('!!! CONNECT: %s as %s. Version %s' % (data.server, self.nickname, self.version))
        for op in data.authlevels:
            data.authlevels[op]['logged in'] = False
        for user in data.usersettings:
            if len(data.usersettings[user]['messages']) > 0:
                data.usersettings[user]['toldofmessages'] = False
            else:
                data.usersettings[user]['toldofmessages'] = True
        for chan in data.channelsettings:
            data.channelsettings[chan]['userlist'] = []
        
    def joined(self, channel):
        self.printer('!!! JOIN: %s' %(channel))
        self.setchansettings(channel)
        data.channelsettings[channel.lower()]['floodwatcher'] = {}
        data.channelsettings[channel.lower()]['hilighted'] = False
    
    def noticed(self, user, channel, msg):
        user = user.split('!', 1)[0]
        if user.lower() == 'nickserv':
            if "recognized" not in msg.lower() and "accepted" not in msg.lower() and "not" not in msg.lower() and "registered" not in msg.lower():
                self.msg('nickserv', 'identify '+self.password)
                self.printer("!!! IDENTIFYING with nickserv")
        if 'foonetic' not in user and 'Chanserv' not in user:
            self.printer("<<< NOTICE: (%s) <%s> %s" % (channel, user, msg))
    
    def irc_RPL_NAMREPLY(self, prefix, params):    #we want to create a working userlist
        for name in params[3].split(' '):
            if name != '' and name != self.nickname:
                name = name.strip('+').strip('&').strip('@').strip('%').strip('~')
                data.channelsettings[params[2].lower()]['userlist'].append(name)
                data.channelsettings[params[2].lower()]['floodwatcher'][name.lower()] = []
                if name.lower() not in data.channelsettings[params[2].lower()]['strikes']:
                    data.channelsettings[params[2].lower()]['strikes'][name.lower()] = 0
                self.setusersettings(name)
    
    def irc_RPL_USERHOST(self, prefix, params):
        self.debugprint(prefix)
        self.debugprint(params)
        nick,hostname = params[1].strip().split('=')
        nick = nick.rstrip('*')
        hostname = hostname.lstrip('+-')
        username, host = hostname.split('@')
        if nick in self.userhost_defer:
            self.userhost_defer[nick].callback((nick, username, hostname))
            del self.userhost_defer[nick]
    
    def getUserhost(self, nick):
        if nick not in self.userhost_defer:
            self.sendLine("USERHOST %s" % nick)
            self.userhost_defer[nick] = defer.Deferred()
        return self.userhost_defer[nick]
        
    def modeChanged(self, user, channel, set, modes, args):
        self.setchansettings(channel)
        if args == () and 'm' in modes:
            if set == True:
                data.channelsettings[channel.lower()]['guard'] = False
                self.printer("!!! MODE CHANGE: Turning off guard in %s because the channel went +m" % (channel))
            elif set == False:
                data.channelsettings[channel.lower()]['guard'] = True
                self.printer("!!! MODE CHANGE: Turning on guard in %s because the channel went -m" % (channel))
    
    def ctcpQuery_VERSION(self, user, channel, data):
        user = user.split('!')[0]
        self.ctcpMakeReply(user, [('VERSION', '%s v%s [%s]' % (self.versionName, self.versionNum, self.versionEnv))])
    
    def userJoined(self, user, channel):
        user = user.split('!', 1)[0]
        self.printer("!!! USER JOINED: %s has joined %s" % (user, channel))
        self.setusersettings(user)
        welcomewagonmessage = ["O_O","O_o","x_x",">_>","I was going to eat that pudding! %s has to die."%(random.choice(data.channelsettings[channel]['userlist'])), "Hola %s"%(user),"Hey, what's up %s?" % (user), "WHAT ARE YOU LOOKING AT, %s?"%(user.upper()),"\x01ACTION has quit (Quit: OH SHIT %s is here)\x01"%(user),"Welcome to %s, %s!"%(channel,user),".__.","WTF ARE YOU DOING HERE, %s!??!?!!"%(user.upper()),"What's up, %s"%(user),"Hey, %s"%(user.upper()),"Guten Tag, %s"%(user),"\x01ACTION shoots %s in the head with Crayboff's flamethrower\x01"%(user),"\x01ACTION throws a %s at %s\x01"%(random.choice(data.channelsettings[channel]['userlist']),user),"OMG, it's %s!"%(user),"sup %s"%(user),"OH LOOK EVERYONE. LOOK WHO DECIDED TO FINALLY SHOW UP."]
        data.channelsettings[channel.lower()]['userlist'].append(user)
        data.channelsettings[channel.lower()]['floodwatcher'][user.lower()] = []
        if random.randint(0,100) < data.usersettings[user.lower()]['welcomewagonpercentage'] and data.channelsettings[channel.lower()]['welcomewagon']:
            self.say(channel, random.choice(welcomewagonmessage))
        if data.usersettings[user.lower()]['toldofmessages'] and len(data.usersettings[user.lower()]['messages']) > 0:
            data.usersettings[user.lower()]['toldofmessages'] = False
        if user.lower() not in data.channelsettings[channel.lower()]['strikes']:
            data.channelsettings[channel.lower()]['strikes'][user.lower()] = 0
        
    def userRenamed(self, oldname, newname):
        self.printer("!!! USER RENAMED: %s has changed their name to %s" % (oldname, newname))
        self.setusersettings(newname)
        if newname in data.authlevels:
            data.authlevels[newname]['logged in'] = False
        if oldname in data.authlevels:
            data.authlevels[oldname]['logged in'] = False
        for channel in data.channelsettings:
            if oldname in data.channelsettings[channel]['userlist']:
                data.channelsettings[channel]['userlist'].remove(oldname)
                data.channelsettings[channel]['userlist'].append(newname)
                data.channelsettings[channel]['userlist'].sort()
    
    def userKicked(self, kickee, channel, kicker, message):
        self.printer("!!! USER KICKED: %s kicked from %s by %s [%s]" %(kickee, channel, kicker, message))
        data.channelsettings[channel.lower()]['userlist'].remove(kickee)
    
    def userLeft(self, user, channel):
        user = user.split('!', 1)[0]
        self.printer("!!! USER PARTED: %s has left %s" % (user, channel))
        data.channelsettings[channel.lower()]['userlist'].remove(user)
        notinany = True
        for chan in data.channelsettings:
            if user in data.channelsettings[chan]['userlist']:
                notinany = False
        if notinany and user.lower() in data.authlevels:
            if data.authlevels[user.lower()]['logged in']:
                data.authlevels[user.lower()]['logged in'] = False
        
    def userQuit(self, user, quitMessage):
        user = user.split('!', 1)[0]
        if user in data.authlevels:
            data.authlevels[user]['logged in'] = False
        for channel in data.channelsettings:
            if user in data.channelsettings[channel.lower()]['userlist']:
                data.channelsettings[channel.lower()]['userlist'].remove(user)
        self.printer("!!! USER QUIT: %s quit" % user)
    
    # Message parsing
    def action(self, user, channel, msg):
        realuser = user.split('!',1)[0]
        hostmask = user.split('!',1)[1]
        user = user.split('!',1)[0]
        self.printer("<<< ACTION: (%s) *%s %s" % (channel, user, msg))
        protect.checkSpam(self, user, realuser, hostmask, channel, msg)
        for module in data.modules:
            exec("%s.%s" % (module[0], module[1]))
    
    def privmsg(self, user, channel, msg):
        realuser = user.split('!',1)[1].split('@',1)[0]
        hostmask = user.split('!',1)[1].split('@',1)[1]
        user = user.split('!',1)[0]
        if data.usersettings[user.lower()]['ignore']:
            self.printer("<<< PRIVMSG: -IGNORED- (%s) <%s> %s" % (channel, user, msg))
            protect.checkSpam(self, user, realuser, hostmask, channel, msg)
            return
        if msg.lower().startswith('auth'):
            self.printer("<<< PRIVMSG: (%s) <%s> ******* PASSWORD *****" % (channel, user))
        else:
            self.printer("<<< PRIVMSG: (%s) <%s> %s" % (channel, user, msg))
        if not data.usersettings[user.lower()]['toldofmessages']:
            regcmd.messageNotify(self, user)
        if not protect.checkSpam(self, user, realuser, hostmask, channel, msg):
            if not data.usersettings[user.lower()]['bot']:
                if channel.lower() == self.nickname.lower():
                    if msg.startswith(self.ubertrigger):
                        self.uberCommandParser(user, channel, msg)
                    else:
                        self.commandParser(user, realuser, hostmask, user, msg)
                elif msg.startswith(self.trigger):
                    self.commandParser(user, realuser, hostmask, channel, msg)
                elif msg.startswith(self.ubertrigger):
                    self.uberCommandParser(user, channel, msg)
                elif '++' in msg or '--' in msg:
                    regcmd.karmaAddMinus(self, user, channel, msg)
        for module in data.modules:
            exec("%s.%s" % (module[0], module[1]))
    
    def commandParser(self, user, realuser, hostmask, channel, msg):
        """
        Ok this is really, really ugly. It's just how I did things when
        I first started programming, and I haven't really used this at all 
        since.
        """
        command = msg.lstrip(self.trigger)
        cmd = command.lower()
        if cmd == 'test':
            regcmd.test(self, user, channel)
            
        # HELP
        elif cmd.startswith('version'):
            self.respond(user, "Emybot version %s" % self.version)
        elif cmd == 'docs' or cmd == 'help':
            regcmd.docPrinter(self, user)
        elif cmd.startswith('help'):
            regcmd.helpPrinter(self, user, command)
            
        # USER SETTINGS
        elif cmd.startswith('settings'):
            settings.settingsParser(self, user, channel, command)
        
        # SEARCH COMMANDS
        elif cmd.startswith('google'):
            regcmd.searchGoogle(self, user, command)
        elif cmd.startswith('wiki'):
            regcmd.searchWikipedia(self, user, command)
        elif cmd.startswith('songza'):
            regcmd.searchSongza(self, user, command)
        elif cmd.startswith('youtube'):
            regcmd.searchYoutube(self, user, command)
               
        # MISC COMMANDS
        elif cmd.startswith('calc'):
            regcmd.googleCalc(self, user, command)
        elif cmd.startswith('timer'):
            regcmd.timer(self, channel, user, command)
        elif cmd.startswith('message'):
            regcmd.messageParser(self, user, command)
        elif cmd.startswith('karma'):
            regcmd.karmaPrinter(self, user, channel, command)
        elif cmd.startswith('gender'):
            regcmd.genderPrinter(self, user, channel, command)
        elif cmd == 'op.print':
            regcmd.opPrinter(self, user)
        elif cmd == 'hilight.mass' or cmd == 'highlight.mass':
            opcmd.hilightMass(self, user, channel)     
        elif cmd.startswith('choose'):
            regcmd.chooser(self, user, channel, command)
        elif cmd == 'botlist.print':
            regcmd.botListPrinter(self, user)
        elif cmd == 'ignore.print':
            regcmd.ignorePrinter(self, user)
        elif cmd == 'specignore.print':
            regcmd.specignorePrinter(self, user)
        
        # OP COMMANDS
        elif cmd.startswith('auth'):
            opcmd.auth(self, user, channel, command)
        elif cmd.startswith('deauth'):
            opcmd.deauth(self, user)
        elif cmd.startswith('join'):
            opcmd.joinChan(self, user, command)
        elif cmd.startswith('part'):
            opcmd.partChan(self, user, msg)
        elif cmd.startswith('op.add'):
            opcmd.opAdd(self, user, command)
        elif cmd.startswith('op.del'):
            opcmd.opDel(self, user, command)
        elif cmd.startswith('say'):
            opcmd.saySomething(self, user, command)
        elif cmd.startswith('do'):
            opcmd.doSomething(self, user, command)
        elif cmd.startswith('chansettings'):
            settings.chansettingsParser(self, user, command)
        elif cmd.startswith('botlist'):
            opcmd.botListParse(self, user, command)
        elif cmd.startswith('ban'):
            opcmd.banner(self, user, realuser, hostmask, channel, command)
        elif cmd.startswith('mute'):
            opcmd.muter(self, user, realuser, hostmask, channel, command)
        elif cmd.startswith('ignore'):
            opcmd.ignore(self, user, command)
        elif cmd.startswith('specignore'):
            opcmd.specignore(self, user, command)
    
    
    
    ##############################
    # BOT OWNER POWERS
    #
    # WARNING: Do not use these commands UNLESS YOU KNOW WHAT YOU ARE DOING!
    ##############################
    def uberCommandParser(self, user, channel, msg):
        command = msg.lstrip(self.ubertrigger)
        if command.startswith('exec'):
            opcmd.execute(self, user, command)
        elif command.startswith('eval'):
            opcmd.evaluate(self, user, command)
        
        
        
    ##############################
    # HELPER COMMANDS
    ##############################
    def setusersettings(self, user):
        if user.lower() not in data.usersettings:
            data.usersettings[user.lower()] = {'reply':'PRIVMSG', 'welcomewagonpercentage': 50, 'messageblock':[], 'ignore':False, 'specignore':False, 'bot':False, 'messages':[], 'toldofmessages':True, 'karma':0, 'gender':''}
            data.saveFile('usersettings')
            self.printer("!!! CREATE: user settings for %s" % (user))
    
    def setchansettings(self, channel):
        if channel.lower() not in data.channelsettings:
            data.channelsettings[channel.lower()] = {'welcomewagon':True, 'guard':False, 'shutup':False, 'listen':True, 'hilightoptout':[], 'optoutable':True, 'userlist':[], 'hilightable':False, 'hilighted':False, 'floodwatcher':{}, 'stopword':[],'chanops':[],'strikes':{},'chanops':{}}
            data.saveFile('channelsettings')
            self.printer("!!! CREATE: channel settings for %s" % (channel))
    
    def say(self, channel, astring, splitat=' '):
        if channel.startswith('#'):
            if len(astring) < data.charlimit:
                if channel in data.channelsettings:
                    if not data.channelsettings[channel]['shutup']:
                        self.printer(">>> SAY: (%s) %s" % (channel, astring))
                        self.msg(channel, astring)
                    else:
                        self.printer("!!! ERROR: SAY failed because bot is muted in %s. Attempted message: %s" % (channel, astring))
            elif len(astring) >= data.charlimit:
                count=0
                while astring[(data.charlimit-count)] != splitat and count < data.charlimit:
                    self.debugprint(str(count)+' '+astring[(data.charlimit-count)])
                    count += 1
                if count <= data.charlimit:
                    self.say(channel, astring[:(data.charlimit-count)])
                    self.say(channel, astring[(data.charlimit-count):])    
        else:
            self.setusersettings(channel)
            self.respond(channel, astring)
    
    def do(self, channel, astring):
        if channel in data.channelsettings:
            if not data.channelsettings[channel]['shutup']:
                self.printer(">>> DO: (%s) %s" % (channel, astring))
                self.me(channel, astring)
            else:
                self.printer("!!! ERROR: DO failed because bot is muted in %s. Attempted message: %s" % (channel, astring))
    
    def respond(self, user, message, splitat=' '):
        self.setusersettings(user)
        if len(message) < data.charlimit:
            if data.usersettings[user.lower()]['reply'] == 'NOTICE':
                self.printer(">>> RESPOND: -NOTICE- (%s) %s" % (user, message))
                self.notice(user, message)
            else:
                self.printer(">>> RESPOND: -PRIVMSG- (%s) %s" % (user, message))
                self.msg(user, message)
        elif len(message) >= data.charlimit:
            count=0
            while message[(data.charlimit-count)] != splitat and count < data.charlimit:
                self.debugprint(str(count)+' '+message[(data.charlimit-count)])
                count += 1
            if count <= data.charlimit:
                self.respond(user, message[:(data.charlimit-count)])
                self.respond(user, message[(data.charlimit-count):])
    
    def isop(self, user, level, channel):
        if user.lower() in data.authlevels:
            if data.authlevels[user.lower()]['logged in']:
                if (channel.lower() in data.authlevels[user.lower()]['channels'] or channel == '***') or user.lower() == self.Owner:
                    if user.lower() == self.Owner:
                        return True
                    else:
                        if channel == '***':
                            return True
                        elif data.authlevels[user.lower()]['channels'][channel.lower()] >= level:
                            return True
                        else:
                            self.notop(user, level, channel)
                            return False
                else:
                    self.respond(user, "Insufficient privileges for %s." % channel)
                    return False
            else:
                self.respond(user, "You are not logged in!")
                return False
        else:
            self.notop(user, level,channel)
            return False
        
    def notop(self, user, level, channel):
        if user.lower() not in data.authlevels:
            userlvl = 0
        else:
            userlvl = data.authlevels[user.lower()]['channels'][channel.lower()]
        self.respond(user, "Insufficient access level. Required level: %d  Your level: %d" % (level,userlvl))
        self.printer("!!! INSUFFICIENT ACCESS: %s attempted to use restricted command. Required level: %d  User level: %d" % (user, level, userlvl))
        
    def timeParser(self, timeamount):
        digits = ['1','2','3','4','5','6','7','8','9','0']
        time = {'h': [0], 'm': [0], 's': [0]}
        curdigits = ''
        for char in timeamount:
            if char in digits:
                curdigits += str(char)
            elif char in time.keys():
                time[char].append(int(curdigits))
                curdigits = ''
        try:
            extrasec = int(curdigits)
        except:
            extrasec = 0
        totalhour,totalmin,totalsec = 0,0,0
        for numb in time['h']:
            totalhour += numb
        for numb in time['m']:
            totalmin += numb
        for numb in time['s']:
            totalsec += numb
        final_count_in_seconds = (totalhour*3600) + (totalmin*60) + totalsec + extrasec
        return final_count_in_seconds
        
class KomurinFactory(protocol.ClientFactory):       #A 'factory' for the bot.

    protocol = Bot

    def __init__(self, channel):
        self.channel = channel

    def clientConnectionLost(self, connector, reason):      #We got disconnected, reconnect.
        connector.connect()
        
    def clientConnectionFailed(self, connector, reason):
        print("!!! ERROR: connection failed: %s" % (reason))
        reactor.stop()

if __name__ == '__main__':                              #Check if we ran it, not imported it.
    f = KomurinFactory(chans)
    reactor.connectTCP(data.server, 6667, f)
    reactor.run()
    #Code here that gets run after the reactor is shut down.
    
