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
import time, sys, urllib, pickle, random, re, os, shelve, math, httplib
from datetime import datetime

# Craybot imports
import commands.regcmds as regcmd
import commands.opcmds as opcmd
import commands.settings as settings
import startup.craybot_initdata as data

# Twisted imports
import twisted
from twisted.words.protocols import irc
from twisted.internet import reactor, protocol, task, defer

def floodProtect(bot, user, channel):
    """
    Auto punish users who are spamming the channel.
    """
    user = user.lower()
    if len(data.channelsettings[channel.lower()]['floodwatcher'][user.lower()]) < bot.floodmax:
        data.channelsettings[channel.lower()]['floodwatcher'][user.lower()].append(time.time())
    else:
        if data.channelsettings[channel.lower()]['floodwatcher'][user.lower()][bot.floodmax-1] - data.channelsettings[channel.lower()]['floodwatcher'][user.lower()][0] <= bot.floodtime:
            data.channelsettings[channel.lower()]['floodwatcher'][user.lower()] = []
            return True
        else:
            data.channelsettings[channel.lower()]['floodwatcher'][user.lower()].pop(0)
            data.channelsettings[channel.lower()]['floodwatcher'][user.lower()].append(time.time())
    return False

def yellProtect(bot, msg):
    """
    Auto punish users who spam capital letters.
    """
    caps_length = len(filter(lambda n:n.isupper(), msg))
    if float(caps_length)/float(len(msg)) > bot.cap_ratio and len(msg) > bot.min_sent_len:
        return True
    else:
        return False

def repeatProtect(bot, msg):
    """
    Auto punish users who spam by holding the same letter down.
    """
    if len(msg) >= 45:    
        prevchar=''
        char = 0
        for char in msg:
            if char == prevchar:
                count += 1
                if count > bot.max_reps:
                    return True
            else:
                count = 0
                prevchar = char
    return False

def specialcharProtect(bot, msg):
    """
    Auto punish users who spam special characters.
    """
    special_characters = "!@#$%^&*()_-+={[}]|\\'\";:?/.><,~`"
    special_length = len(filter(lambda n: n in special_characters, msg))
    if float(special_length)/float(len(msg)) > bot.special_ratio and len(msg) > 15:
        return True
    return False
    
def stopwordProtect(bot, channel, msg):
    """
    Auto punish users who are using a forbidden word.
    """
    specchar = "!@#$%^&*()_-+={[}]|\\'\";:?/.><,~` "
    msg = msg.lower()
    for char in specchar:
        msg.strip(char)
    for stopword in data.channelsettings[channel.lower()]['stopword']:
        if stopword.lower() in msg:
            return True
    return False
    
def checkSpam(bot, user, realuser, hostmask, channel, msg):
    """
    Assign strikes to a user based on their punishment.
    """
    if channel.lower() != bot.nickname.lower() and data.channelsettings[channel.lower()]['guard'] and not data.usersettings[user.lower()]['specignore']:
        if floodProtect(bot, user, channel):
            assignStrikes(user, channel, 10)
            punisher(bot, user, realuser, hostmask, channel, reason="Channel Guard: Flood Protection | Flooding is not cool.")
            return True
        elif repeatProtect(bot, msg):
            assignStrikes(user, channel, 7)
            punisher(bot, user, realuser, hostmask, channel, reason="Channel Guard: Spam Protection | 1) Take finger off key. 2) Stop it!")
            return True
        elif specialcharProtect(bot, msg):
            assignStrikes(user, channel, 7)
            punisher(bot, user, realuser, hostmask, channel, reason="Channel Guard: Spam Protection | Please use actual words!")
            return True
        elif yellProtect(bot, msg):
            assignStrikes(user, channel, 2)
            punisher(bot, user, realuser, hostmask, channel, reason="Channel Guard: Yelling | CAPS LOCK IS CRUISE CONTROL FOR COOL, but you still have to steer!")
            return True
        elif stopwordProtect(bot, channel, msg) and user.lower() not in data.authlevels:
            assignStrikes(user, channel, 1)
            punisher(bot, user, realuser, hostmask, channel, reason="Channel Guard: Blacklisted Word Use | You be triggering mah stopwords!")
            return True
    return False

def punisher(bot, user, realuser, hostmask, channel, reason=''):
    """
    Based on a user's strike level, different punishments will be 
    handed out.
    """
    bot.printer("!!! CHANNEL GUARD: %s -- %s has %d strikes in %s." % (reason, user, data.channelsettings[channel.lower()]['strikes'][user.lower()], channel))
    if 0 < data.channelsettings[channel.lower()]['strikes'][user.lower()] <= 10:
        bot.kick(channel, user, reason)
    elif 9 < data.channelsettings[channel.lower()]['strikes'][user.lower()] <= 25:
        opcmd.muter(bot, bot.nickname, realuser, hostmask, channel, 'mute %s %d' % (user,data.channelsettings[channel.lower()]['strikes'][user.lower()]/2*60) , reason, isself=True)
    elif 25 < data.channelsettings[channel.lower()]['strikes'][user.lower()] <= 35:
        opcmd.banner(bot, bot.nickname, realuser, hostmask, channel, 'ban %s %d' % (user,data.channelsettings[channel.lower()]['strikes'][user.lower()]*60) , reason, isself=True)
    elif 35 < data.channelsettings[channel.lower()]['strikes'][user.lower()] <= 50:
        opcmd.banner(bot, bot.nickname, realuser, hostmask, channel, 'ban %s %d' % (user,data.channelsettings[channel.lower()]['strikes'][user.lower()]*120) , reason, isself=True)
    elif 50 < data.channelsettings[channel.lower()]['strikes'][user.lower()] <= 85:
        opcmd.banner(bot, bot.nickname, realuser, hostmask, channel, 'ban %s %d' % (user,data.channelsettings[channel.lower()]['strikes'][user.lower()]*180) , reason, isself=True)
    elif 85 < data.channelsettings[channel.lower()]['strikes'][user.lower()]:
        reason = " %s | You have been permabanned. Please speak to an op to plead your case." % reason
        opcmd.banner(bot, bot.nickname, realuser, hostmask, channel, 'ban %s' % (user), reason, isself=True)

def assignStrikes(user, channel, punishment):
    data.channelsettings[channel.lower()]['strikes'][user.lower()] += punishment
    reactor.callLater(604800, deductStrikes, user)
    #reactor.callLater(120, deductStrikes, user, channel)
    data.saveFile('channelsettings')
    
def deductStrikes(user, channel):
    if data.channelsettings[channel.lower()]['strikes'][user.lower()] - 25 <= 0:
        data.channelsettings[channel.lower()]['strikes'][user.lower()] = 0
    else:
        data.channelsettings[channel.lower()]['strikes'][user.lower()] -= 25
        bot.printer('!!! CHANNEL GUARDING: Automatically deducted 25 strikes from %s in %s' % (user,channel))
