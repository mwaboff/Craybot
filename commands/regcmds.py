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
import time, sys, urllib, pickle, random, re, os, shelve, math, httplib, datetime
from datetime import datetime

# Twisted imports
from twisted.words.protocols import irc
from twisted.internet import reactor, protocol, task, defer

# Craybot imports
import opcmds as opcmd
import settings as settings
import startup.craybot_initdata as data

####################
# SEARCH COMMANDS
####################
def tinyURL(search_url):
    tinyurl = urllib.urlopen("http://tinyurl.com/api-create.php?url=%s" % search_url).readline()
    return tinyurl
    
def searchGoogle(bot, user, msg):
    term = msg.split(' ',1)[1]
    search_term = term.replace(" ", "+")
    search_url = "http://www.google.com/search?q=%s" % (search_term)
    bot.respond(user, "Google search for %s: %s" % (term, tinyURL(search_url)))

def searchWikipedia(bot, user, msg):
    term = msg.split(' ',1)[1]
    search_term = term.replace(" ", "+")
    search_url = "http://en.wikipedia.org/wiki/%s" % (search_term)
    html = urllib.urlopen(search_url).readlines()
    validlink = True
    for line in html:
        if "<div class='searchresults'><p>There were no results matching the query." in line:
            validlink = False
    if validlink:
        bot.respond(user, "Wikipedia search for %s: %s" % (term, tinyURL(search_url)))
    else:
        bot.respond(user, "Was not able to find a Wikipedia result for %s." % (term))

def searchSongza(bot, user, msg):
    term = msg.split(' ',1)[1]
    search_term = msg.replace(" ", "+")
    search_url = "http://songza.com/search/%s" % (search_term)
    bot.respond(user, 'Songza search for %s: %s' % (term, tinyURL(search_url)))

def googleCalc(bot, user, msg): # WARNING NO LONGER WORKS
    q = msg.split(' ',1)[1]
    query = urllib.urlencode({'q':q})

    start='<h2 class=r style="font-size:138%"><b>'
    end='</b>'
    req = '/search?'+query

    google=httplib.HTTPConnection("www.google.com")
    google.request("GET",req)
    search=google.getresponse()
    data=search.read()

    if data.find(start)==-1: 
        bot.respond(user, "Google Calculator results for %s was not found." % (q))
    else:
        begin=data.index(start)
        result=data[begin+len(start):begin+data[begin:].index(end)]
        result = result.replace("<font size=-2> </font>",",").replace(" &#215; 10<sup>","E").replace("</sup>","").replace("\xa0",",")
        bot.respond(user, "%s = %s" % (q, result))

def searchYoutube(bot, user, msg):
    term = msg.split(' ',1)[1]
    search_term = term.replace(" ", "+")
    search_url = "http://www.youtube.com/results?search_type=&search_query=%s" % (search_term)
    bot.respond(user, 'Youtube search for %s: %s' % (term, tinyURL(search_url)))
    
####################
# MISC COMMANDS
####################
def genderPrinter(bot, user, channel, msg):
    """
    Prints user defined gender data on a person. Only the user in question 
    can set their own gender.
    """
    msg = msg.split()
    if len(msg) == 1:
        person = user
    else:
        person = msg[1]
    bot.setusersettings(person)
    if data.usersettings[person.lower()]['gender'] == '':
        bot.say(channel, user+": I do not know what gender %s is." % person)
    else:
        bot.say(channel, user+": My files indicate that %s is %s" % (person, data.usersettings[person.lower()]['gender']))
    
def timer(bot, channel, user, msg):
    """
    Timer that can convert a variety of different syntaxes into seconds.
    
    Example Syntax: timer 1m2s
    
    Example Output: 62 seconds
    """
    timeamount = msg.split(' ')[1]
    timeamount = bot.timeParser(timeamount)
    reason = ''
    if len(msg.split()) >= 3:
        reason = 'Your timer had the associated message: "%s"' % (msg.split(' ',2)[2])
    if msg.startswith('timer.private'):
        public = False
    else:
        public = True
    def timerHilighter(channel, user, msg, reason):
        if public:
            bot.say(channel, user+": Your timer has expired. %d seconds have elapsed. %s" % (timeamount, reason))
        else:
            bot.respond(user, "Your timer has expired. %d seconds have elapsed. %s" % (timeamount, reason))
    try:
        timeamount = abs(int(timeamount))
        reactor.callLater(timeamount, timerHilighter, channel, user, msg, reason)
        if public:
            bot.say(channel, user+": Timer set to %d seconds." % (timeamount))
        else:
            bot.respond(user, "Timer set to %d seconds." % (timeamount))
    except ValueError:
        bot.respond(user, "I don't know how to time words!")

def test(bot, user, channel):
    bot.say(channel, user+": TEST")
    bot.respond(user, "TEST")
    bot.printer("!!! TEST: Command sent by %s" % user)
    
def docPrinter(bot, user):
    bot.respond(user, "For all commands and explanations: <insert helpdocs url> for quick command syntax lookup, use %shelp [command]."%bot.trigger)

def karmaAddMinus(bot, user, channel, msg):
    """
    Automatically track karma addition and subtraction. Syntax:
    
    Karma addition:   "Crayboff++"
    Karma subtraction:   "Crayboff--"
    
    User cannot add or deduct karma from himself.
    """
    msg = list(msg.split())
    for part in msg:
        if part[-2:] == '++':
            if user.lower() != part[:-2].lower():
                bot.setusersettings(part[:-2])
                data.usersettings[part[:-2].lower()]['karma'] += 1
            else:
                bot.say(channel, user+": Don't be greedy!")
        elif part[-2:] == '--':
            if user.lower() != part[:-2].lower():
                bot.setusersettings(part[:-2])
                data.usersettings[part[:-2].lower()]['karma'] -= 1
            else:
                bot.say(channel, user+": You know, there's medicine for this sort of stuff...")
        data.saveFile('usersettings')

def karmaPrinter(bot, user, channel, command):
    """
    Responds with the karma level of a user.
    """
    if '.' in command.split()[0]:
        elements = command.split('.')[1].split()
    else:
        elements = command.split()
    if len(command) == 1:
        person = user
        if elements[0] == 'private':
            bot.respond(user, "Your karma is %d" % (person, data.usersettings[person.lower()]['karma']))
        else:
            bot.say(channel, user+": Your karma is %d" % (data.usersettings[person.lower()]['karma']))
    else:
        person = command.split()[1]
        bot.setusersettings(person)
        if elements[0] == 'private':
            bot.respond(user, "%s's karma is %d" % (person, data.usersettings[person.lower()]['karma']))
        else:
            bot.say(channel, user+": %s's karma is %d" % (person, data.usersettings[person.lower()]['karma']))
            

def opPrinter(bot, user):
    """
    Responds with a list of all bot operators in all channels.
    """
    bot.respond(user, "My current botops are: %s" % data.authlevels.keys())

def botListPrinter(bot, user):
    """
    Responds with a list of all registered bots.
    """
    genericlist = []
    for usr in data.usersettings.keys():
        if data.usersettings[usr]['bot']:
            genericlist.append(usr)
    bot.respond(user, "Registered Bots: %s" % ", ".join(genericlist))

def ignorePrinter(bot, user):
    """
    Responds with a list of all users ignored.
    """
    genericlist = []
    for usr in data.usersettings:
        if data.usersettings[usr]['ignore']:
            genericlist.append(usr)
    bot.respond(user, "Ignore list: %s" % (", ".join(genericlist)))

def specignorePrinter(bot, user):
    """
    Responds with a list of all users special ignored (exempt from spam 
    filtering).
    """
    genericlist = []
    for usr in data.usersettings:
        if data.usersettings[usr]['specignore']:
            genericlist.append(usr)
    bot.respond(user, "Special ignore list: %s" % ", ".join(genericlist))
    
def chooser(bot, user, channel, command):
    """
    Randomly decide between different options deliminated by " or "
    """
    choices = command.split(' ',1)[1].split(' or ')
    choice = random.choice(choices)
    if command.startswith('choose.private'):
        bot.respond(user, "I choose '%s'." % (choice))
    elif command.startswith('choose '):
        bot.respond(channel, user+": I choose '%s'." % (choice))

####################
# HELP
####################
def helpParser(cmd):
    html = urllib.urlopen("http://dl.dropbox.com/u/45046764/emy.html").readlines()
    for line in html:
        if line.lstrip().startswith('<li><b>'):
            command = line.split('<b>')[1].split('</b>')[0]
            if command == cmd.lower():
                syntax = line.split('<i>',1)[1].split('</i>',1)[0]
                explaination = line.split('| ')[1].split('</li>')[0].strip('\n').replace("<i>",'').replace("</i>",'')
                return syntax, explaination

def helpPrinter(bot, user, command):
    bot.printer("!!! HELP: %s asked for help!" % user)
    try:
        cmd = command.split()[1]
        syntax, explaination = helpParser(cmd)
        bot.respond(user, "%s%s == %s"%(bot.trigger,syntax,explaination))
    except:
        bot.respond(user, "I am not sure what you are asking. For a list of my commands, please go to http://www.tinyurl.com/craybot2doc")
            

####################
# MESSAGING  - The following methods deal with PM's via Craybot's PM system.
####################
def messageParser(bot, user, command):
    elements = command.split('.',1)[1].split(' ',2)
    if elements[0] == 'print':
        messagePrinter(bot, user, command)
    elif elements[0] == 'send':
        messageSender(bot, user, elements)

def messagePrinter(bot, user, command):
    """
    Respond to a user any unread messages he may have.
    """
    if len(data.usersettings[user.lower()]['messages']) > 0:
        bot.respond(user, 'You have messages: '+' | '.join(data.usersettings[user.lower()]['messages']))
        data.usersettings[user.lower()]['messages'] = []
        data.saveFile('usersettings')
    else:
        bot.respond(user, "You don't appear to have any messages!")

def messageSender(bot, user, command):
    """
    Send another user a PM (just storing it until the other user gets it 
    with timestamp data).
    """
    to = command[1]
    bot.setusersettings(to)
    if user.lower() not in data.usersettings[to.lower()]['messageblock']:
        message = command[2]
        newmessagetime = datetime.utcnow().timetuple()
        newmonth = str(newmessagetime[1])
        monthabbrev = {'1':'JAN', '2':'FEB', '3':'MAR', '4':'APR', '5':'MAY', '6':'JUN', '7':'JUL', '8':'AUG', '9':'SEP', '10':'OCT', '11':'NOV', '12':'DEC'}
        newday = str(newmessagetime[2])
        newhour = str(newmessagetime[3])
        newminute = str(newmessagetime[4])
        newyear = str(newmessagetime[0])
        msgtime = '[%s %s %s  %s:%s] ' % (monthabbrev[newmonth], newday, newyear, newhour, newminute)
        newmessage = '<%s> %s' % (user, message)
        data.usersettings[to.lower()]['messages'].append('%s%s' % (msgtime,newmessage))
        data.usersettings[to.lower()]['toldofmessages'] = False
        data.saveFile('usersettings')
        bot.respond(user, "Message sent. [To: %s  Time Sent: %s %s %s  %s:%s]" % (to, monthabbrev[newmonth], newday, newyear, newhour, newminute))
    else:
        bot.respond(user, "I'm sorry, but you have been blacklisted from sending messages to %s" % (to))

def messageNotify(bot, user):
    """
    Notify a user that he has unread messages.
    """
    if not data.usersettings[user.lower()]['toldofmessages'] and len(data.usersettings[user.lower()]['messages']) > 0:
        bot.respond(user, "You have %d unread messages! Use the message.print function to read them." % (len(data.usersettings[user.lower()]['messages'])))
        data.usersettings[user.lower()]['toldofmessages'] = True
        data.saveFile('usersettings')
