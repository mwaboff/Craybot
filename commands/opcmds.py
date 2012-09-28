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
# system imports
import time, sys, urllib, pickle, random, re, os, shelve, math, httplib, datetime, hashlib
from datetime import datetime

# Twisted imports
from twisted.words.protocols import irc
from twisted.internet import reactor, protocol, task, defer

# Craybot imports
import regcmds as regcmd
import settings as settings
import startup.craybot_initdata as data

def auth(bot, user, channel, command):
    """
    Log into the bot's auth system. Logging in (assuming the user has 
    bot operator status in any channel, will grant them the ability to 
    use these commands in said channel.
    """
    if channel.lower() == user.lower():
        if user.lower() in data.authlevels:
            command = command.split()
            if not data.authlevels[user.lower()]['logged in']:
                if len(command) == 2:
                    psswrd = command[1]
                    if hashlib.sha1(psswrd).hexdigest() == data.authlevels[user.lower()]['password']:
                        data.authlevels[user.lower()]['logged in'] = True
                        bot.respond(user, "You have been successfully logged in.")
                        bot.printer("!!! AUTH: %s has successfully been logged in" % (user))
                    else:
                        bot.printer("!!! AUTH: -FAILED- Incorrect password")
                        bot.respond(user, "Incorrect password.")
            else:
                bot.printer("!!! AUTH: -FAILED- Already logged in")
                bot.respond(user, "You are already logged in!")
        else:
            bot.printer("!!! AUTH: -FAILED- Not a registered botop")
            bot.respond(user, "You are not a registered botop!")

def deauth(bot, user):
    """
    Log out of the bot's auth system.
    """
    if user.lower() in data.authlevels:
        if data.authlevels[user.lower()]['logged in']:
            data.authlevels[user.lower()]['logged in'] = False
            bot.respond(user, "You have been successfully logged out.")
            bot.printer("!!! DEAUTH: %s has successfully been logged out" % (user))
        else:
            bot.printer("!!! DEAUTH: -FAILED- Not logged in")
            bot.respond(user, "You were never logged in!")
    else:
        bot.printer("!!! DEAUTH: -FAILED- Not a registered botop")
        bot.respond(user, "You are not a registered botop!")

def opAdd(bot, user, command):
    """
    Grant bot operator status to a user for a specified channel.
    """
    if bot.isop(user, 10, '***'):
        elements = command.split()
        if len(elements) >= 3:
            authlevel = int(elements[2])
            if 0 < authlevel <= 3:
                chanstobe = elements[3].lower().split(',')
                if elements[1].lower() not in data.authlevels:
                    data.authlevels[elements[1].lower()] = {'password':bot.defaultpass,'logged in':False,'channels':{}}
                    bot.respond(elements[1], "Congratulations, you have been granted botop status by %s. You may check your authorization levels with  settings.print  command. The default password is 'pass', however you must change it as soon as possible. To change your password use the 'settings.password' function. Thanks and good luck!" % (user))
                for chan in chanstobe:
                    data.authlevels[elements[1].lower()]['channels'][chan.lower()] = authlevel
                bot.respond(elements[1], "You have just been made a botop of authlevel %d in the following channels: %s" % (authlevel, ','.join(chanstobe)))
                bot.respond(user, "You have successfully given %s bot op status in %s! %s's authorization level is %d." % (elements[1], ','.join(chanstobe), elements[1], authlevel))
                bot.printer("!!! OP ADD: %s granted op status (%d in %s) by %s." % (elements[1],authlevel,','.join(chanstobe),user))
                data.saveFile('authlevels')
            else:
                bot.respond(user, "You may only add botops with an authlevel of either 1, 2, or 3!")
                return False

def opDel(bot, user, command):
    """
    Remove bot operator status for all channels.
    """
    if bot.isop(user, 10, '***'):
        if len(command.split()) == 3:
            tobedel = command.split()[1]
            chanstodel = command.lower().split()[2].split(',')
            if tobedel.lower() in data.authlevels.keys():
                if '*' in chanstodel:
                    del data.authlevels[tobedel.lower()]
                    bot.respond(user, "%s has been stripped of botop status" % (tobedel))
                    bot.respond(tobedel, "%s has removed all of your botop privilages in all channels. If you think this may be a mistake, please talk to %s." % (user, user))
                    bot.printer("!!! OP DEL: %s removed from op status by %s." % (tobedel, user))
                    data.saveFile('authlevels')
                else:
                    for chan in chanstodel:
                        if chan.lower() in data.authlevels[tobedel.lower()]['channels']:
                            del data.authlevels[tobedel.lower()]['channels'][chan.lower()]
                            bot.printer("!!! OP DEL: %s removed from op status in %s by %s." % (tobedel, chan, user))
                        else:
                            bot.respond(user, "%s is not a botop in %s! Passing..." % (tobedel,chan))
                            chanstodel.remove(chan)
                    bot.respond(tobedel, "%s has removed your botop privilages from: %s . If you think this may be a mistake, please talk to %s." % (user, ','.join(chanstodel), user))
                    data.saveFile('authlevels')
            else:
                bot.printer("!!! OP DEL: -FAILED- %s is not a botop" % (tobedel))
                bot.respond(user, "%s is not one of my registered botops!" % (tobedel))
                
def saySomething(bot, user, command):
    """
    Say something to the chat.
    """
    if len(command.split(' ',2)) == 3:
        chan, astring = command.split(' ',2)[1:]
        if bot.isop(user, 3, chan):
            if chan.lower() in data.channelsettings:
                bot.say(chan, astring)
            else:
                bot.respond(user, "I'm not currently in that channel!")
                bot.printer("!!! ERROR: Failed to send message because bot is not in channel %s" % (chan))

def doSomething(bot, user, command):
    """
    Runs a /me command in the chat.
    """
    if len(command.split(' ',2)) == 3:
        chan, astring = command.split(' ',2)[1:]
        if bot.isop(user, 3, chan):
            if chan.lower() in data.channelsettings:
                bot.do(chan, astring)
            else:
                bot.respond(user, "I'm not currently in that channel!")
                bot.printer("!!! ERROR: Failed to send message because bot is not in channel %s" % (chan))
                
def hilightMass(bot, user, channel):
    """
    If mass hilighting is enabled for the channel, this will message the
    channel with a list of all users who haven't personally opted out of 
    the mass hilighting list.
    """
    if data.channelsettings[channel.lower()]['hilightable']:
        if user.lower() in data.authlevels.keys():
            if data.authlevels[user.lower()]['logged in'] and channel.lower() in data.authlevels[user.lower()]['channels']:
                bot.say(channel, massHilighter(bot, user, channel))
                data.channelsettings[channel.lower()]['hilighted'] = True
                reactor.callLater(300, hilightMassTimeReset, bot, channel)
                bot.printer("!!! MASS HILIGHT: called by %s for %s. OPTOUTS = %s" % (user,channel,data.channelsettings[channel.lower()]['optoutable']))
                return
        if not data.channelsettings[channel.lower()]['hilighted']:
            bot.say(channel, massHilighter(bot, user, channel))
            data.channelsettings[channel.lower()]['hilighted'] = True
            reactor.callLater(30, hilightMassTimeReset, bot, channel)
            bot.printer("!!! MASS HILIGHT: called by %s for %s. OPTOUTS = %s" % (user,channel,data.channelsettings[channel.lower()]['optoutable']))
        else:
            bot.printer('!!! MASS HILIGHT: -FAILED- Mass hilight in %s was already called recently' % (channel))
            bot.respond(user, "Sorry, a mass hilight was called recently!")
    else:
        bot.printer('!!! MASS HILIGHT: -FAILED- Mass hilighting is off for %s' % (channel))
            
        

def hilightMassTimeReset(bot, channel):
    """
    Mass hilighting of a channel is on a time limit, so users cannot abuse 
    the power to annoy other users. This command resets the timer.
    """
    bot.printer('!!! MASS HILIGHT RESET: Mass hilighting is now available for %s' % (channel))
    data.channelsettings[channel.lower()]['hilighted'] = False

def massHilighter(bot, user, channel):
    masshilightlist = []
    for usrr in data.channelsettings[channel.lower()]['userlist']:
        if usrr.lower() != user.lower() and not data.usersettings[usrr.lower()]['bot']:
            if data.channelsettings[channel.lower()]['optoutable']:
                if usrr.lower() not in data.channelsettings[channel.lower()]['hilightoptout']:
                    masshilightlist.append(usrr)
            else:
                masshilightlist.append(usrr)
    masshilightstring = "\x02MASS HILIGHT CALLED BY %s:\x02 " % user + ', '.join(masshilightlist)
    return masshilightstring

def botListParse(bot, user, command):
    """
    Add other bots to an internal registry so Craybot will not deal with 
    the bot as if it were a person.
    """
    if bot.isop(user, 2, '***'):
        alterbot = command.split()[1]
        cmd = command.split()[0].split('.')[1]
        bot.setusersettings(alterbot)
        if cmd == 'add':
            if not data.usersettings[alterbot.lower()]['bot']:
                data.usersettings[alterbot.lower()]['bot'] = True
                bot.respond(user, "%s is now registered as a fellow bot." % (alterbot))
                bot.printer("!!! BOT LIST: -REGISTER- %s is registered as a bot by %s" % (alterbot, user))
            else:
                bot.printer("!!! BOT LIST: -FAILED- %s is already registered as a bot" % (alterbot))
                bot.respond(user, "%s is already registered as a bot!" % (alterbot))
        elif cmd == 'del':
            if data.usersettings[alterbot.lower()]['bot']:
                data.usersettings[alterbot.lower()]['bot'] = False
                bot.respond(user, "%s is not no longer considered a bot." % (alterbot))
                bot.printer("!!! BOT LIST: -UNREGISTERED- %s is unregistered as a bot by %s" % (alterbot, user))
            else:
                bot.printer("!!! BOT LIST: -FAILED- %s is not registered as a bot" % (alterbot))
                bot.respond(user, "%s is not registered as a bot!" % (alterbot))

def joinChan(bot, user, msg):
    """
    Force the bot to join a channel.
    """
    if len(msg.split()) == 2:
        chantojoin = msg.split()[1]
        if bot.isop(user, 1, '***'):
            bot.setchansettings(chantojoin)
            if chantojoin.lower() in data.channelsettings:
                if not chantojoin.startswith('#'):
                    chantojoin = "#"+chantojoin
                if msg.startswith("join.silent"):
                    data.channelsettings[chantojoin.lower()]['shutup'] = True
                    bot.respond(user, 'Attempting to join %s. SILENT MODE' % chantojoin)
                    bot.printer("!!! JOIN: Attempting to join %s silently" % chantojoin)
                    bot.join(chantojoin)
                else:
                    bot.printer("!!! JOIN: Attempting to join %s" % chantojoin)
                    bot.respond(user, 'Attempting to join %s.' % chantojoin)
                    bot.join(chantojoin)
            else:
                bot.printer("!!! JOIN: -FAILED- Already in %s" % chantojoin)
                bot.respond(user, "I'm already in %s!" % chantojoin)
    
def partChan(bot, user, msg):
    """
    Force the bot to leave a channel.
    """
    if len(msg.split()) == 2:
        chantopart = msg.split()[1]
        if bot.isop(user, 1, '***'):
            bot.setchansettings(chantopart)
            if chantopart.lower() in data.channelsettings:
                if not chantopart.startswith('#'):
                    chantopart = "#"+chantopart
                bot.respond(user, "Attempting to part %s." % chantopart)
                bot.printer("PART: %s" % chantopart)
                bot.part(chantopart)
            else:
                bot.printer("!!! PART: -FAILED- Not in %s" % chantojoin)
                bot.respond(user, "I'm not currently in %s!" % chantopart)

def banner(bot, user, realuser, hostmask, channel, msg, reason='', isself=False):
    """
    This function gives the bot the ability to ban users.
    """
    for usr in data.channelsettings[channel.lower()]['userlist']:
        if usr.lower() == msg.split()[1].lower():
            tokill = usr
    bot.getUserhost(tokill).addCallback(ban_callback, bot, user, channel, msg, reason, isself)
        
def ban_callback(result, bot, user, channel, msg, reason='', isself=False):
    """
    Temporary timed bans! :D
    """
    bot.debugprint(result)
    tokill, realuser, host = result
    hostmask = host.split('@',1)[0]+"@*."+host.split('.',1)[1]
    if bot.isop(user, 3, channel) or isself:
        if len(msg.split()) >= 3:
            try:
                timeamount = msg.split(' ',2)[2]
                timeban = bot.timeParser(timeamount)
            except:
                timeban = 300
            killmask = '*!*%s' % (hostmask)
            bot.printer("!!! KICKBAN: %s is attempting to have a timed kickban %s from %s for %s seconds" % (user, killmask, channel, timeamount))
            bot.mode(channel, True, 'b', mask='*!*%s' % (hostmask))
            bot.kick(channel, tokill, "Banned for %s seconds. %s" % (str(timeban), reason))
            bot.respond(tokill, "Banned for %s seconds. %s" % (str(timeban), reason))
            reactor.callLater(timeban, unbanner, bot, user, killmask, channel, 'b', timeban, tokill)
        elif len(msg.split()) == 2:
            for usr in data.channelsettings[channel.lower()]['userlist']:
                if usr.lower() == msg.split()[1].lower():
                    tokill = usr
            killmask='*!*%s' % (hostmask)
            bot.printer("!!! KICKBAN: %s is attempting to have a timed kickban %s from %s" % (user, killmask, channel))
            bot.mode(channel, True, 'b', mask='*!*%s' % (hostmask))
            bot.kick(channel, tokill, "Banned by %s." % (user))

def unbanner(bot, user, mask, channel, mode, time, enemy):
    """
    This function will unban a user after their temporary ban is up.
    """
    bot.mode(channel, False, mode, mask=mask)
    bot.printer("!!! UNBAN: Attempting to unban %s" % (mask))
    bot.respond(user, "%s's %d second ban has been lifted." % (enemy, time))

def muter(bot, user, realuser, hostmask, channel, msg, reason='', isself=False):
    """
    This will issue a quiet ban on a user, supported by most IRC servers.
    """
    for usr in data.channelsettings[channel.lower()]['userlist']:
        if usr.lower() == msg.split()[1].lower():
            tokill = usr
    bot.getUserhost(tokill).addCallback(mute_callback, bot, user, channel, msg, reason, isself)
    
def mute_callback(result, bot, user, channel, msg, reason='', isself=False):
    """
    This function handles timed quiet bans.
    """
    bot.debugprint(result)
    tokill, realuser, host = result
    hostmask = host.split('@',1)[0]+"@*."+host.split('.',1)[1]
    if bot.isop(user, 2, channel) or isself:
        if len(msg.split()) >= 3:
            try:
                timeamount = msg.split(' ',2)[2]
                timeban = bot.timeParser(timeamount)
            except:
                timeban = 300
            for usr in data.channelsettings[channel.lower()]['userlist']:
                if usr.lower() == msg.split()[1].lower():
                    tokill = usr
            killmask = '~q:*!*%s' % (hostmask)
            bot.printer("!!! KICKBAN: %s is attempting to have a timed kickban %s from %s for %s seconds" % (user, killmask, channel, timeamount))
            bot.mode(channel, True, 'b', mask='~q:*!*%s' % (hostmask))
            bot.respond(tokill, "Muted for %s seconds. %s" % (str(timeban), reason))
            reactor.callLater(timeban, unbanner, bot, user, killmask, channel, 'b', timeban, tokill)
        elif len(msg.split()) == 2:
            for usr in data.channelsettings[channel.lower()]['userlist']:
                if usr.lower() == msg.split()[1].lower():
                    tokill = usr
            killmask='~q:*!*%s' % (hostmask)
            bot.printer("!!! KICKBAN: %s is attempting to have a timed kickban %s from %s" % (user, killmask, channel))
            bot.mode(channel, True, 'b', mask='~q:*!*%s' % (hostmask))
            bot.respond(tokill, "You have been muted by %s" % (user))
            
def ignore(bot, user, command):
    """
    Ignore a user who is trying to spam bot commands.
    """
    if command.startswith("ignore.add"):
        if bot.isop(user, 2, '***'):
            if len(command.split()) == 2:
                toignore = command.split()[1]
                if toignore.lower() == bot.Owner.lower():
                    bot.printer("!!! IGNORE: -FAILED- %s attempted to put the bot owner on the ignore list" % (user))
                    bot.respond(user, "I will not ignore my Owner!")
                else:
                    bot.setusersettings(toignore)
                    if not data.usersettings[toignore.lower()]['ignore']:
                        data.usersettings[toignore.lower()]['ignore'] = True
                        bot.respond(user, "%s will now be ignored."%toignore)
                        bot.respond(toignore, "You have been placed on my ignore list by %s. If you wish to have this ignore lifted, please talk to one of my botops." % (user))
                        bot.printer("!!! IGNORE: Now ignoring %s" % toignore)
                    else:
                        bot.printer("!!! IGNORE: -FAILED- Already ignoring %s" % toignore)
                        bot.respond(user, "I was already ignoring %s!" % (toignore))
                data.saveFile('usersettings')
    elif command.startswith("ignore.del"):
        if bot.isop(user, 2, '***'):
            if len(command.split()) == 2:
                tounignore = command.split()[1]
                bot.setusersettings(tounignore)
                if data.usersettings[tounignore.lower()]['ignore']:
                    data.usersettings[tounignore.lower()]['ignore'] = False
                    bot.respond(user, "%s will no longer be ignored."%tounignore)
                    bot.respond(tounignore, "You have been removed from my ignore list by %s." % (user))
                    bot.printer("!!! UNIGNORE: No longer ignoring %s" % tounignore)
                else:
                    bot.printer("!!! UNIGNORE: -FAILED- Never ignoring %s" % toignore)
                    bot.respond(user, "I was never ignoring %s!" % (tounignore))
                data.saveFile('usersettings')

def specignore(bot, user, command):
    """
    This special ignore will prevent the bot from even registering the 
    user's chat messages when dealing with channel protection (i.e. spam)
    """
    if command.startswith("specignore.add"):
        if bot.isop(user, 10, '***'):
            if len(command.split()) == 2:
                toignore = command.split()[1]
                bot.setusersettings(toignore)
                if not data.usersettings[toignore.lower()]['specignore']:
                    data.usersettings[toignore.lower()]['specignore'] = True
                    bot.respond(user, "%s will now be excluded from my spam checking."%toignore)
                    bot.respond(toignore, "%s has granted you immunity from my spam checker." % (user))
                    bot.printer("!!! SPECIGNORE ADD: No longer checking %s for spam" % toignore)
                else:
                    bot.printer("!!! SPECIGNORE ADD: -FAILED- Already excluding %s from spam checking" % toignore)
                    bot.respond(user, "I was already not checking %s's spam!" % (toignore))
                data.saveFile('usersettings')
    elif command.startswith("specignore.del"):
        if bot.isop(user, 10, '***'):
            if len(command.split()) == 2:
                tounignore = command.split()[1]
                bot.setusersettings(tounignore)
                if data.usersettings[tounignore.lower()]['specignore']:
                    data.usersettings[tounignore.lower()]['specignore'] = False
                    bot.respond(user, "%s will now stop being specially ignored."%tounignore)
                    bot.respond(tounignore, "Your immunity to my spam checking has been removed by %s." % (user))
                    bot.printer("!!! SPECIGNORE DEL: No longer excluding %s from spam checking" % tounignore)
                else:
                    bot.respond(user, "I was never checking %s's spam!" % (tounignore))
                    bot.printer("!!! SPECIGNORE DEL: -FAILED- Was never excluding %s from spam checking" % toignore)
                data.saveFile('usersettings')

####################
# BOT OWNER POWERS
#
# WARNING: Do not use these commands UNLESS YOU KNOW WHAT YOU ARE DOING!
####################
#def execute(bot, user, command):
#    astring = command.split(' ',1)[1]
#    if user.lower() == bot.Owner:
#        if data.authlevels[user.lower()]['logged in']:
#            try:
#                bot.respond(user, astring)
#                exec(astring)
#                bot.respond(user, 'DONE')
#            except:
#                bot.respond(user, "%s: %s" % (sys.exc_type,sys.exc_value))
#                bot.printer("~~~ EXECUTE: -ERROR- %s: %s" % (sys.exc_type,sys.exc_value))
#        else:
#            bot.printer("~~~ EXECUTE: -FAILURE- Must be logged in to use this feature.")
#            bot.respond(user, "You must be logged in to use this feature.")
#    else:
#        bot.printer("~~~ EXECUTE: -FAILURE- %s is not the bot owner" % (user))
#        bot.respond(user, "Only my bot owner may use this UBER command.")
#
#def evaluate(bot, user, command):
#    astring = command.split(' ',1)[1]
#    if user.lower() == bot.Owner:
#        if data.authlevels[user.lower()]['logged in']:
#            try:
#                bot.respond(user, astring)
#                bot.respond(user, eval(astring))
#                bot.respond(user, 'DONE')
#            except:
#                bot.respond(user, "%s: %s" % (sys.exc_type,sys.exc_value))
#                bot.printer("~~~ EVALUATE: -ERROR- %s: %s" % (sys.exc_type,sys.exc_value))
#        else:
#            bot.printer("~~~ EVALUATE: -FAILURE- Must be logged in to use this feature.")
#            bot.respond(user, "You must be logged in to use this feature.")
#    else:
#        bot.printer("~~~ EVALUATE: -FAILURE- %s is not the bot owner" % (user))
#        bot.respond(user, "Only my bot owner may use this UBER command.")
#    
        
