#!/usr/bin/env python3

import os
import math
import json
import logging
import subprocess
import sys
import socket
import tibber
import time
import statistics
import datetime
import argparse


def home_to_string(home):
    return f"{home.address1}, {home.postal_code} {home.city}, {home.country}"


def load_or_create_json_config(file_name):
    if os.path.exists(file_name):
        try:
            with open(file_name, "r") as f:
                logging.info(f"Loading credentials from: {file_name}")
                return json.load(f)
        except Exception as e:
            logging.fatal(
                f"Failed to read credentials from {file_name}. Please check permissions or delete the credentials file and re-run the script.")
            sys.exit(1)

    logging.info(f"Loading credentials from: {file_name}")
    destination_not_reachable = True
    while destination_not_reachable:
        destination_ip = input("Please enter your destination IP or hostname of the (Miniserver):\n > ")
        error, output = subprocess.getstatusoutput("ping -c 1 -w 1 " + destination_ip)
        if error:
            logging.error(output)
        else:
            destination_not_reachable = False

    destination_port_invalid = True
    while destination_port_invalid:
        destination_port = input("Please enter your destination port (Miniserver):\n > ")
        max_port = 2**16-1
        try:
            destination_port = int(destination_port)
            if destination_port > max_port:
                raise ValueError(f"The given port {destination_port} is not in the valid range [1-{max_port}].")
            destination_port_invalid = False
        except Exception as e:
            logging.error(e)

    token_invalid = True
    while (token_invalid):
        token = input("Please enter your Tibber API Token:\n > ")
        token = token.strip()
        try:
            account = tibber.Account(token)
            token_invalid = False
        except:
            logging.error(
                "Can't authenticate to tibber by using this token. Please check the validity of the token and ensure a connection to the internet is available.")

    invalid_home_selected = True
    while invalid_home_selected:
        home_id = input("Please select the number of the home you wish to monitor:\n" +
                        "\n".join(f"{i:2d}: " + home_to_string(h) for i, h in enumerate(account.homes)) + "\n > ")
        try:
            home_id = int(home_id)
            max_len = len(account.homes) - 1
            if home_id < 0 or home_id > max_len:
                raise ValueError(f"The given id {home_id} is not in the valid range [0-{max_len}].")
            invalid_home_selected = False
        except Exception as e:
            logging.error(e)

    destination = {}
    destination["ip"] = destination_ip
    destination["port"] = destination_port

    config = {}
    config["destination"] = destination

    config["token"] = token
    config["home_id"] = home_id

    with open(file_name, "w") as f:
        json.dump(config, f, indent=4)
        logging.info(f"Stored credentials in {file_name}")

    # Set the credentials to be write protected and readable for the user only.
    os.chmod(file_name, 0o400)

    return config


def get_time_dictionary():
    time_information = {}
    today = datetime.date.today()
    time_information["date_now"] = str(today)
    time_information["date_now_epoch"] = time.mktime(today.timetuple())
    time_information["date_now_seconds_since_epoch"] = int(time.time())
    time_information["date_now_day"] = today.day
    time_information["date_now_month"] = today.month
    time_information["date_now_year"] = today.year
    return time_information


def get_price_dictionary(tibber_account, home_id):
    subscription = tibber_account.homes[home_id].current_subscription
    price_info_today = subscription.price_info.today
    prices_total = [p.total for p in price_info_today]

    price_information = {}
    price_information["price_low"] = min(prices_total)
    price_information["price_high"] = max(prices_total)
    price_information["price_median"] = statistics.median(prices_total)
    price_information["price_average"] = statistics.mean(prices_total)
    price_information["price_stdev"] = statistics.stdev(prices_total)
    price_information["price_current"] = subscription.price_info.current.total
    price_information["price_unit"] = subscription.price_info.current.currency

    prices_total_sorted = sorted(prices_total)
    for i, p in enumerate(prices_total_sorted):
        price_information[f"price_threshold_{i:02d}"] = p

    for i, p in enumerate(prices_total):
        price_information[f"data_price_hour_abs_{i:02}_amount"] = p

    # Merge two lists into one and preserve order.
    price_information_available = subscription.price_info.today + subscription.price_info.tomorrow
    now = datetime.datetime.now()

    # Setting this variable to False will cause to only valid send valid values and skip the placeholders.
    always_send_invalid_values = True
    if always_send_invalid_values:
        # Assume there is never more than 23 values in the past and never more than
        # 36 values in the future. First store all values in an invalid state.
        invalid_state_value = -1000
        for i in range(-23, 0):
            price_information[f"data_price_hour_rel_-{abs(i):02}_amount"] = invalid_state_value

        for i in range(36):
            price_information[f"data_price_hour_rel_{i:02}_amount"] = invalid_state_value

    for i, price_info in enumerate(price_information_available):
        isoformat = datetime.datetime.fromisoformat(price_info.starts_at).replace(tzinfo=None)
        delta_hour = math.ceil((isoformat - now).total_seconds()/3600)
        sign = '-' if delta_hour < 0 else ''
        price_information[f"data_price_hour_rel_{sign}{abs(delta_hour):02}_amount"] = price_info.total

    return price_information


def get_power_dictionary(tibber_account, config):
    # Not implemented yet
    return {}


def merge_dictionaries(dict_list):
    result = {}
    for d in dict_list:
        result.update(d)
    return result


def prepare_datagram_string(key_value_dictionary, format=False):
    s = json.dumps(key_value_dictionary, indent=2 if format else None)
    s = s.replace('"', '')
    return s

def send_to_destination(config, key_value_dictionary):
    string_to_be_sent = prepare_datagram_string(key_value_dictionary)
    string_to_be_sent_formatted = prepare_datagram_string(key_value_dictionary, format=True)

    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    destination = (config["destination"]["ip"], config["destination"]["port"])
    bytes_sent = s.sendto(string_to_be_sent.encode(), destination)

    if bytes_sent < len(string_to_be_sent):
        logging.error("Failed to send the information to " + destination)
    else:
        logging.info(f"Sent {bytes_sent} bytes to {destination}")
        logging.debug(f"Sent the following string:\n" + string_to_be_sent_formatted)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('-l', '--log', help="Logging level for the application (default=INFO)",
                        choices=["DEBUG", "INFO", "WARNING", "ERROR"], default="INFO")
    args = parser.parse_args()

    choice_map = {"DEBUG": logging.DEBUG, "INFO": logging.INFO, "WARNING": logging.WARNING, "ERROR": logging.ERROR}
    logging.getLogger().setLevel(choice_map[args.log])

    credentials_dir = os.path.dirname(os.path.abspath(__file__))
    config = load_or_create_json_config(os.path.join(credentials_dir, ".tibber_credentials"))

    tibber_account = tibber.Account(config["token"])
    time_dict = get_time_dictionary()
    price_dict = get_price_dictionary(tibber_account, config["home_id"])
    power_dict = get_power_dictionary(tibber_account, config)

    information_to_be_sent = merge_dictionaries([time_dict, price_dict, power_dict])

    send_to_destination(config, information_to_be_sent)
