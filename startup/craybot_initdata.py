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
import os, pickle, hashlib, time, sys
global authlevels, usersettings, channelsettings, karmadb, stopwords, userlists


def printer(message):
    lt = time.localtime()
    date = "%d/%d/%d %d:%d.%d" % (lt[1],lt[2],lt[0],lt[3],lt[4],lt[5])
    log.write("[%s] %s\n" % (date, message))
    log.flush()
    
def saveFile(avar):

    if avar == 'authlevels':
        data = open('%s/data/craybot_auth_dict.txt'%fileup,'w')
    elif avar == 'usersettings':
        data = open('%s/data/craybot_user_settings.txt'%fileup,'w')
    elif avar == 'channelsettings':
        data = open('%s/data/craybot_channel_settings.txt'%fileup,'w')
    elif avar == 'stopwords':
        data = open('%s/data/craybot_stopwords.txt'%fileup, 'w')
    printer('!!! SAVING/CREATING: %s' % avar)
    exec('pickle.dump('+avar+',data)')
    data.close()

def main():
    """
    Initialize data.
    """
    fileup = sys.path[0]
    userlists = {}
    modules = []
    config = open('%s/config.txt'%fileup,'r')
    for line in config:
        if line[0] != '#':
            exec(line)
    config.close()

    lt = time.localtime()
    date = "%d-%d-%d|%d:%d:%d" % (lt[1],lt[2],lt[0],lt[3],lt[4],lt[5])
    dt = "%d/%d/%d %d:%d.%d" % (lt[1],lt[2],lt[0],lt[3],lt[4],lt[5])
    log = open("%s/data/logs/craybot_logs_%s.log"%(fileup,date),'w')
    log.write("####################\n#\n#  Craybot logs\n#\n#  LOG CREATED: %s\n#\n####################\n\n[m/d/year h:m.s] ~TIME AND DATE IS LOCAL! NOT UTC~\n\n"%dt)
    log.flush()

    if os.path.exists('%s/data/craybot_auth_dict.txt'%fileup):
        auth = open('%s/data/craybot_auth_dict.txt'%fileup,'r')
        printer('!!! LOAD: auth_dict')
        authlevels = pickle.load(auth)
        auth.close()
    else:
        authlevels = {owner.lower():{'auth level':10,'password':hashlib.sha1('pass').hexdigest(),'logged in':False, 'channels':{}}}
        saveFile('authlevels')
        
    if os.path.exists('%s/data/craybot_user_settings.txt'%fileup):
        set = open('%s/data/craybot_user_settings.txt'%fileup,'r')
        printer('!!! LOAD: user_settings')
        usersettings = pickle.load(set)
        set.close()
    else:
        usersettings = {}
        saveFile('usersettings')
        
    if os.path.exists('%s/data/craybot_channel_settings.txt'%fileup):
        set = open('%s/data/craybot_channel_settings.txt'%fileup,'r')
        printer('!!! LOAD: channel_settings')
        channelsettings = pickle.load(set)
        set.close()
    else:
        channelsettings = {nickname.lower():{'welcomewagon':True, 'guard':False, 'shutup':False, 'listen':True, 'hilightoptout':[], 'optoutable':False, 'userlist':[], 'hilightable':False, 'hilighted':False, 'floodwatcher':{}, 'stopword':[], 'chanops':[], 'strikes':{}}}
        saveFile('channelsettings')

main()
