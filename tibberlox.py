#!/usr/bin/env python3

#
# Simple Python Script to get Values from the Tibber API to Loxone Server
#
# Version 1.0: Initial GITHUB Release
# Version 1.1: Fix empty list, clean udp, main added
# Version 1.2: Relative extended to 24h
#
# Todo: Config Files + Dirs/Php scripts for Loxberry Plugin
#

import os
import sys
import socket
import tibber
import time
import statistics
import datetime
import argparse
import json
from datetime import date

# Konfiguration/Configuration
#
ACCESS_TOKEN = "5K4MVS-OjfWhK_4yrjOlFe1F6kJXPVf7eQYggo8ebAE"   # Tibber ACCESS Token (DEFAULT = DEMO TOKEN!)
msip= "192.168.1.5"             # IP Adress Loxone Mini Server
msport = 5005                   # Port the Mini Server is listening to
homes = 0                       # Tibber Home (mostly 0)
PRICEEMPTY = 100                # Send this, if no price is available

# udp functions
#
def openudp():
    connection = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    return connection

def closeudp(connection):
    connection.close()

def sendudp(connection, data):
    print(data)
    res = connection.sendto(data.encode(), (msip, msport))
    if res != data.encode().__len__():
        print("Sent bytes do not match - expected {0} : got {1}".format(data.__len__(), res))
        print("Packet-Payload {0}".format(data))

#
# SendUDP2MS() - Send the Tibber Data to the Miniserver
#
def sendudp2ms():
    con = openudp()
    sendudp(con, "date_now: {}".format(date.today()))
    sendudp(con, "date_now_epoch: {}".format(time.mktime(date.today().timetuple())))
    sendudp(con, "date_now_day: {}".format(date.today().day))
    sendudp(con, "date_now_month: {}".format(date.today().month))
    sendudp(con, "date_now_year: {}".format(date.today().year))

    price_data = home.current_subscription.price_info.today
    i = 0
    calc = 0
    list1 = []
    for prices in price_data:
        list1.append(prices.total)
        calc = calc + prices.total
        i = i + 1

    if list1:
        sendudp(con, "price_low: {}".format(min(list1)) )
        sendudp(con, "price_high: {}".format(max(list1)) )
        sendudp(con, "price_median: {}".format(statistics.median(list1)) )
        sendudp(con, "price_average: {:.4f}".format(calc/i) )
        sendudp(con, "price_current: {}".format(home.current_subscription.price_info.current.total) )
        sendudp(con, "price_unit: Cent/kWh")

        list1.sort()
        i = 0
        for listelem in list1:
            sendudp(con, "price_threshold_{}: {}" .format(str(i).zfill(2), listelem))
            i = i + 1

    i = 0
    for prices in price_data:
        sendudp(con, "data_price_hour_abs_{}_amount: {}" .format(str(i).zfill(2), prices.total))
        i = i + 1

    now = datetime.datetime.now()
    hour = now.hour
    price_tomorrow = home.current_subscription.price_info.tomorrow
    i = 0

    while i < 24:
        if hour + i > 23 :
            if len(price_tomorrow)> 0:
                sendudp(con, "data_price_hour_rel_{}_amount: {}" .format(str(i).zfill(2), price_tomorrow[hour+i-24].total))
            else:
                sendudp(con, "data_price_hour_rel_{}_amount: {}" .format(str(i).zfill(2), PRICEEMPTY))
        else:
            sendudp(con, "data_price_hour_rel_{}_amount: {}" .format(str(i).zfill(2), price_data[hour+i].total))
        i = i + 1
    closeudp(con)

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    account = tibber.Account(ACCESS_TOKEN)
    home = account.homes[homes]
    sendudp2ms()
