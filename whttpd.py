#!/usr/bin/python

#  .______       _______  _______      __           ___      .______
#  |   _  \     |   ____||       \    |  |         /   \     |   _  \
#  |  |_)  |    |  |__   |  .--.  |   |  |        /  ^  \    |  |_)  |
#  |      /     |   __|  |  |  |  |   |  |       /  /_\  \   |   _  <
#  |  |\  \----.|  |____ |  '--'  |   |  `----. /  _____  \  |  |_)  |
#  | _| `._____||_______||_______/    |_______|/__/     \__\ |______/

''' Communication Gateway for IoT Application

Description:
============

Implementation of an http server that communicates with IoT devices through http.
An SSH tunnel is used to read and write data to and from a central database.

Modifications:
==============

Credits
=======

Author: Holm Smidt
Credits: Mitch McLean, Volker Schwarzer, Matsu Thornton
Date: 12/22/2016
'''

import time, re, os, sys
import ConfigParser
import BaseHTTPServer
import paramiko
import thread #, threading
#from threading import Thread, enumerate
import socket

""" Config Parameters """
global mac_addr, tempSet, valveLim, DR, pGain, iGain
mac_addr = []
tempSet = {}
valveLim = {}
DR = {}
pGain = {}
iGain = {}

HOST_NAME   = '192.168.8.1' # !!!REMEMBER TO CHANGE THIS!!!
PORT_NUMBER = 9000

def init_config():
    """Loads configuration data from config.ini
    """

    global ip,  pinode_id, usr, key_path
    global db_usr, db_pass, db_name

    config = ConfigParser.ConfigParser()
    config.read('config.ini')

    ip = config.get('ssh_login', 'ip')
    usr = config.get('ssh_login', 'username')
    key_path = config.get('ssh_login', 'key_path')
    db_usr = config.get('db_login', 'db_username')
    db_pass = config.get('db_login', 'db_pass')
    db_name = config.get('db_login', 'db_name')
    #pinode_id = config.get('device_info', 'node')


def init_ssh():
    """SSH to the server using paramiko.
    """

    global ssh
    init_config()
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(ip, username=usr, key_filename=key_path)
    print 'SSH Connection established'

def ssh_to_db(node_mac, temp, valvePos):
    """ SSH and insert data to database using
        bash command for postgres.
    """
    COMMAND  = 'PGPASSWORD=' + str(db_pass)
    COMMAND += ' psql -U ' + str(db_usr)
    COMMAND += ' -d ' + str(db_name)
    COMMAND += ' -h 127.0.0.1 -c '
    COMMAND += '"INSERT INTO nodes_data (node_mac, valvePos, temp) VALUES ('
    COMMAND += "'"+str(node_mac)+"'" + ', ' + str(valvePos) + ', ' + str(temp) + ')" '
    print 'SSH_TO_DB: ' + COMMAND 

    try:
        ssh.exec_command(COMMAND)
    except socket.error as e:
        init_ssh()

def ssh_new_node(node):
    """ SSH and add new mac address to the database.
        It is up to the user change default configuration in the DB.
    """
    mac_addr.append(node)

    tempSet[node] = 75.0
    valveLim[node] = 1023
    DR[node] = 1
    pGain[node] = 0.04
    iGain[node] = 0.02

    """
    COMMAND  = 'PGPASSWORD=' + str(db_pass)
    COMMAND += ' psql -U ' + str(db_usr)
    COMMAND += ' -d ' + str(db_name)
    COMMAND += ' -h 127.0.0.1 -c '
    COMMAND += '"INSERT INTO nodes_config (node_mac) VALUES (' + str(node) +')"'

    try:
        ssh.exec_command(COMMAND)
	print 'executed command'
    except socket.error as e:
        init_ssh()
    """

def ssh_from_db(node):
    """ SSH and get configuration (DR parameters) from
        the DB.
        This function updates global control dict's.
    """
    COMMAND  = 'PGPASSWORD=' + str(db_pass)
    COMMAND += ' psql -U ' + str(db_usr)
    COMMAND += ' -d ' + str(db_name)
    COMMAND += ' -h 127.0.0.1 -c '
    COMMAND += '"SELECT (tempSet, valveLim, pGain, iGain, dr) from nodes_config where node_mac='
    COMMAND += "'"+str(node) + "'"+ ' "'
    print 'SSH_FROM_DB: ' + COMMAND
    try:
        stdin, stdout, stderr = ssh.exec_command(COMMAND)
        q_data = stdout.readlines()[2] #empty after reading
        p = re.compile('\d*\.?\d+') # temp, valveLim, pG, iG, DR
        m = p.findall(q_data)
        if len(m) == 5: 
	    tempSet[node] = float(m[0])
            valveLim[node] = int(m[1])
            pGain[node] = float(m[2])
            iGain[node] = float(m[3])
            DR[node] = int(m[4])
	    print 'Node: ' + node + 'T: ' + str(tempSet[node]) + 'V: ' + str(valveLim[node]), 
	    print 'pG: ' + str(pGain[node]) + 'iG: ' + str(iGain[node]) + 'DR: ' + str(DR[node])
        #time.sleep(1)
    except socket.error as e:
        init_ssh()

def update_DR_thread(empty):
    """ Thread to update config parameters by querying
        the database every 5 seconds or so.
    """
    while True:
        print mac_addr

        for node in mac_addr:
            ssh_from_db(node)

        time.sleep(5)


class MyHandler(BaseHTTPServer.BaseHTTPRequestHandler):
    """ HTTP server implementation.
    """
    def do_HEAD(s):
        s.send_response(200)
        s.send_header("Content-type", "text/plain")
        s.end_headers()
    def do_GET(s):
        s.send_response(200)
        s.send_header("Content-type", "text/plain")
        s.end_headers()
        p = re.compile('\?(.+?)!')
        m = p.findall(s.path)
	print s.path
	print m
	node = m[0]
        if node in mac_addr:
            s.wfile.write("?" + str(DR[node]) + "!?" + str(tempSet[node]) + "!?" + str(valveLim[node]) + "!?" + str(pGain[node]) + "!?" + str(iGain[node]) + "!")
            ssh_to_db(node, float(m[1]), int(m[2]))

        else:
            s.wfile.write("?!Adding mac address to DB\n") #not sure if needed
            ssh_new_node(node)



if __name__ == "__main__":
    init_ssh()

    thread.start_new_thread(update_DR_thread, (1,))

    server_class = BaseHTTPServer.HTTPServer
    httpd = server_class((HOST_NAME, PORT_NUMBER), MyHandler)
    print time.asctime(), "Server Starts - %s:%s" % (HOST_NAME, PORT_NUMBER)

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
        isRunning = 0
        httpd.server_close()
        print time.asctime(), "Server Stops - %s:%s" % (HOST_NAME, PORT_NUMBER)
