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
import startup.craybot_initdata as data

####################
# USER SETTINGS
####################

def settingsParser(bot, user, channel, command):
    command = command.split('.',1)[1].split()
    bot.setusersettings(user)
    if command[0] == 'print':
        settingsPrint(bot, user)
    elif len(command) == 2:
        if command[0] == 'reply':
            settingsRespond(bot, user, command)
        elif command[0] == 'welcomewagon':
            settingsWelcomewagon(bot, user, command)
        elif command[0] == 'ignore':
            settingsIgnore(bot, user, command)
        elif command[0] == 'unignore':
            settingsUnignore(bot, user, command)
        elif command[0] == 'gender':
            settingsGender(bot, user, command)
        elif command[0] == 'password':
            settingsPassword(bot, user, command)
        elif command[0].startswith('hilight.opt'):
            settingsHilightOpt(bot, user, command)

##########
# NORMAL USER COMMANDS
##########
def settingsPrint(bot, user):
    """
    Respond to a user with all of their personal settings.
    """
    optouts = []
    for channel in data.channelsettings:
        if user.lower() in data.channelsettings[channel]['hilightoptout']:
            optouts.append(channel)
    if data.usersettings[user.lower()]['ignore']:
        uhoh = '!ACHTUNG! You are currently on my ignore list. If you have any questions, you may talk to my botops. | '
    else:
        uhoh = ''
    if user.lower() in data.authlevels:
        chanopswlevel = []
        for chan in data.authlevels[user.lower()]['channels']:
            chanopswlevel.append('%s(%d)'%(chan, data.authlevels[user.lower()]['channels'][chan]))
        opness = '  |  Botops: %s | Logged in: %s' % (', '.join(chanopswlevel), data.authlevels[user.lower()]['logged in'])
    else:
        opness = ''
    strikerlist = []
    for chan in data.channelsettings:
        if user.lower() in data.channelsettings[chan]['strikes']:
            strikerlist.append("%s:%d" % (chan,data.channelsettings[chan]['strikes'][user.lower()]))
    strikerstring = ', '.join(list(set(strikerlist)))
    temp = "~ %s's SETTINGS ~ %sBot Reply: %s  |  Welcomewagon %%: %d  |  Strikes against you: %s | Users you are ignoring: %s  |  Channel mass hilight optouts: %s%s" % (user, uhoh, data.usersettings[user.lower()]['reply'], data.usersettings[user.lower()]['welcomewagonpercentage'], strikerstring, ', '.join(data.usersettings[user.lower()]['messageblock']), ', '.join(optouts),opness)
    bot.respond(user, temp)
    
def settingsRespond(bot, user, command):
    """
    Sets the preference of how the user would like for Craybot to respond.
    
    Options include via NOTICE (in compliance with RFC 1459) or PRIVMSG 
    (something many users prefer).
    """
    if command[1].lower() in ['notice','notify']:
        data.usersettings[user.lower()]['reply'] = 'NOTICE'
        bot.respond(user, "I will respond to your commands with notices from now on.")
    elif command[1].lower() in ['pm','privmsg','msg']:
        data.usersettings[user.lower()]['reply'] = 'PRIVMSG'
        bot.respond(user, "I will respond to your commands with PMs from now on.")
    data.saveFile('usersettings')

def settingsWelcomewagon(bot, user, command):
    """
    Users can define how frequently they would like to be welcomed into 
    a channel containing Craybot.
    """
    try:
        percent = int(command[1])
        if percent < 101 and percent >= 0:
            data.usersettings[user.lower()]['welcomewagonpercentage'] = percent
            bot.respond(user, "You will now be welcomed when you join one of my channels %d%% of the time" % (percent))
            data.saveFile('usersettings')
        else:
            bot.respond(user, "Please only choose an integer between 0 and 100!")
    except:
        pass

def settingsIgnore(bot, user, command):
    """
    Users may block other users from sending them PMs via Craybot's 
    messaging system.
    """
    data.usersettings[user.lower()]['messageblock'].append(command[1].lower())
    bot.respond(user, "I will not allow for %s to send you any more messages." % (command[1]))
    data.saveFile('usersettings')

def settingsUnignore(bot, user, command):
    """
    Users may use this command to unblock other users from sending them 
    PMs via Craybot's messaging system.
    """
    if command[1].lower() in data.usersettings[user.lower()]['messageblock']:
        data.usersettings[user.lower()]['messageblock'].remove(command[1].lower())
        bot.respond(user, "I will allow for %s to send you messages again." % (command[1]))
        data.saveFile('usersettings')
    else:
        bot.respond(user, "You don't seem to be ignoring %s's messages!" % command[1])

def settingsGender(bot, user, command):
    """
    Users may set their own gender record. Other users may ask Craybot 
    what gender the original user is, and if it is defined, Craybot will 
    respond.
    """
    if data.usersettings[user.lower()]['gender'] == '':
        if command[1].lower() in ['male','boy','guy','man','masc','masculine']:
            data.usersettings[user.lower()]['gender'] = 'male'
            bot.respond(user, "I will now know you as a male")
        elif command[1].lower() in ['female','girl','gal','woman','fem','feminine']:
            data.usersettings[user.lower()]['gender'] = 'female'
            bot.respond(user, "I will now know you as a female")
        data.saveFile('usersettings')
    else:
        bot.respond(user, "Your gender is already set! If you must change this, please contact one of my botops.")
        
def settingsHilightOpt(bot, user, command):
    """
    Users may opt-in or opt-out of mass hilighting on a channel-to-channel 
    basis.
    """
    if len(command) == 2:
        channel = command[1]
        bot.setchansettings(channel)
        if command[0] == 'hilight.optout':
            if user.lower() not in data.channelsettings[channel.lower()]['hilightoptout']:
                data.channelsettings[channel.lower()]['hilightoptout'].append(user.lower())
                bot.respond(user, "You will not be hilighted in my mass hilighting for %s" % channel)
            else:
                bot.respond(user, "You are already opted out of %s channel hilights!" % channel)
        elif command[0] == 'hilight.optin':
            if user.lower() in data.channelsettings[channel.lower()]['hilightoptout']:
                data.channelsettings[channel.lower()]['hilightoptout'].remove(user.lower())
                bot.respond(user, "You will now be included in my mass hilighting for %s." % channel)
            else:
                bot.respond(user, "You do not seem to be opted out of %s channel hilights!" % channel)
        data.saveFile('channelsettings')
            
##########
# OP SETTINGS
##########
def settingsPassword(bot, user, command):
    """
    Bot operators may change their password.
    """
    if bot.isop(user, 0, '***'):
        data.authlevels[user.lower()]['password'] = hashlib.sha1(command[1]).hexdigest()
        bot.respond(user, "You have changed your password to %s. Please remember this password as I will not be able to tell you what it is later." % (command[1]))
        data.saveFile('authlevels')

####################
# CHANNEL SETTINGS
####################

def chansettingsParser(bot, user, msg):
    if len(msg.split()) > 1:
        command = msg.lower().split('.',1)[1].split()[0]
        channel = msg.split()[1]
        if len(msg.split()) > 2:
            elements = msg.lower().split()[2:]
        else:
            elements = []
        bot.setchansettings(channel)
        if command.startswith('welcomewagon'):
            chansettingsWelcomewagon(bot, user, command, channel)
        elif command.startswith('guard'):
            chansettingsGuard(bot, user, command, channel)
        elif command.startswith('shutup'):
            chansettingsShutup(bot, user, command, channel)
        elif command.startswith('hilight'):
            chansettingsHilightable(bot, user, command, channel)
        elif command.startswith('stopword'):
            chansettingsStopword(bot, user, command, channel, elements)
        elif command.startswith('print'):
            chansettingsPrint(bot, user, command, channel)
        elif command.startswith('optouts'):
            chansettingsOptoutable(bot, user, command, channel)
        

def chansettingsPrint(bot, user, command, channel):
    """
    Prints out settings unique to a particular channel.
    """
    chanops = []
    for botops in data.authlevels:
        if channel.lower() in data.authlevels[botops.lower()]['channels']:
            chanops.append(botops)
    bot.respond(user, "~ %s CHANNEL SETTINGS ~ Welcomewagon: %s | Guard: %s | Silent Mode: %s | Mass Hilightable: %s | Optouts allowed: %s | Forbidden Words: %s | Channel botops: %s" % (channel, data.channelsettings[channel.lower()]['welcomewagon'], data.channelsettings[channel.lower()]['guard'], data.channelsettings[channel.lower()]['shutup'], data.channelsettings[channel.lower()]['hilightable'], data.channelsettings[channel.lower()]['optoutable'], ', '.join(data.channelsettings[channel.lower()]['stopword']), ', '.join(chanops)))

def chansettingsStopword(bot, user, command, channel, elements):
    """
    Ban the usage of a certain word in a channel. If Craybot has moderation 
    privilages, he can levy punishments against abusers.
    """
    if bot.isop(user, 1, channel):
        if command.startswith('stopword.add'):
            for element in elements:
                if element.lower() not in data.channelsettings[channel.lower()]['stopword']:
                    data.channelsettings[channel.lower()]['stopword'].append(element.lower())
                    bot.respond(user, "Added %s to my forbidden word list for channel %s." % (element, channel))
                else:
                    bot.respond(user, "%s is already a forbidden word in channel %s!" % (element, channel))
        elif command.startswith('stopword.del'):
            for element in elements:
                if element.lower() in data.channelsettings[channel.lower()]['stopword']:
                    data.channelsettings[channel.lower()]['stopword'].remove(element.lower())
                    bot.respond(user, "Removed %s from my forbidden word list for channel %s." % (element, channel))
                else:
                    bot.respond(user, "%s is not a forbidden word in channel %s!" % (element, channel))
        data.saveFile('channelsettings')

def chansettingsWelcomewagon(bot, user, command, channel):
    """
    Toggle whether or not Craybot will randomly welcome users to the channel.
    
    This overrides a user's personal settings.
    """
    onoff = command.split('.')[1].split()[0].lower()
    if bot.isop(user, 1, channel):
        if onoff == 'on':
            data.channelsettings[channel.lower()]['welcomewagon'] = True
            data.saveFile('channelsettings')
        elif onoff == 'off':
            data.channelsettings[channel.lower()]['welcomewagon'] = False
            data.saveFile('channelsettings')
        bot.respond(user, '%s welcomewagon status: %s' % (channel, data.channelsettings[channel.lower()]['welcomewagon']))

def chansettingsGuard(bot, user, command, channel):
    """
    Toggle whether or not Craybot shall attempt to protect the channel 
    from spammers/other threats. Only useful if Craybot has moderation 
    privilages.
    """
    onoff = command.split('.')[1].split()[0].lower()
    if bot.isop(user, 1, channel):
        if onoff == 'on':
            data.channelsettings[channel.lower()]['guard'] = True
            data.saveFile('channelsettings')
        elif onoff == 'off':
            data.channelsettings[channel.lower()]['guard'] = False
            data.saveFile('channelsettings')
        bot.respond(user, '%s guard status: %s' % (channel, data.channelsettings[channel.lower()]['guard']))
        
def chansettingsOptoutable(bot, user, command, channel):
    onoff = command.split('.')[1].split()[0].lower()
    if bot.isop(user, 1, channel):
        if onoff == 'on':
            data.channelsettings[channel.lower()]['optoutable'] = True
            data.saveFile('channelsettings')
        elif onoff == 'off':
            data.channelsettings[channel.lower()]['optoutable'] = False
            data.saveFile('channelsettings')
        bot.respond(user, '%s optoutable status: %s' % (channel, data.channelsettings[channel.lower()]['optoutable']))

def chansettingsShutup(bot, user, command, channel):
    """
    Prevent the bot from speaking at all in a channel.
    """    
    onoff = command.split('.')[1].split()[0].lower()
    if bot.isop(user, 1, channel):
        if onoff == 'on':
            data.channelsettings[channel.lower()]['shutup'] = True
            data.saveFile('channelsettings')
        elif onoff == 'off':
            data.channelsettings[channel.lower()]['shutup'] = False
            data.saveFile('channelsettings')
        bot.respond(user, '%s shutup status: %s' % (channel, data.channelsettings[channel.lower()]['shutup']))

def chansettingsHilightable(bot, user, command, channel):
    """
    Toggle whether or not a mass highlight can be called in the channel.
    """
    onoff = command.split('.')[1].split()[0].lower()
    if bot.isop(user, 1, channel):
        if onoff == 'on':
            data.channelsettings[channel.lower()]['hilightable'] = True
            data.saveFile('channelsettings')
        elif onoff == 'off':
            data.channelsettings[channel.lower()]['hilightable'] = False
            data.saveFile('channelsettings')
        bot.respond(user, '%s hilightable status: %s' % (channel, data.channelsettings[channel.lower()]['hilightable']))

