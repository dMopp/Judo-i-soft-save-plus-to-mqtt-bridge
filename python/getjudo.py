#!/urs/bin/python3
# -*- coding: utf-8 -*-
import urllib3
import json
import time
import gc
import config_getjudo
import messages_getjudo
import hashlib
import sys
from paho.mqtt import client as mqtt
from datetime import date
import pickle


class entity():
    def __init__(self, name, icon, entity_type, unit = "", minimum = 1, maximum = 100, step = 1, value = 0):
        self.name = name
        self.unit = unit
        self.icon = icon
        self.entity_type = entity_type #total_inc, sensor, number, switch, 
        self.value = value
        self.minimum = minimum
        self.maximum = maximum
        self.step = step

    def send_entity_autoconfig(self):
        device_config = {
            "identifiers": f"[{client_id}]",
            "manufacturer": config_getjudo.MANUFACTURER,
            "model": config_getjudo.NAME,
            "name": client_id,
            "sw_version": config_getjudo.SW_VERSION
        }

        entity_config = {
            "device": device_config,
            "availability_topic": availability_topic,
            "payload_available": config_getjudo.AVAILABILITY_ONLINE,
            "payload_not_available": config_getjudo.AVAILABILITY_OFFLINE,
            "state_topic": state_topic,
            "name": client_id + " " + self.name,
            "unique_id": client_id + "_" + self.name,
            "icon": self.icon,
            "value_template": "{{value_json." + self.name + "}}"
        }

        if self.entity_type == "total_increasing":
            entity_config["device_class"] = "water"
            entity_config["state_class"] = self.entity_type
            entity_config["unit_of_measurement"] = self.unit
            self.entity_type = "sensor"

        elif self.entity_type == "number":
            entity_config["command_topic"] = command_topic
            entity_config["unit_of_measurement"] = self.unit
            entity_config["min"] = self.minimum
            entity_config["max"] = self.maximum
            entity_config["step"] = self.step
            entity_config["command_template"] = "{\"" + self.name + "\": {{ value }}}"

        elif self.entity_type == "switch":
            entity_config["command_topic"] = command_topic
            entity_config["payload_on"] = "{\"" + self.name + "\": 1}"
            entity_config["payload_off"] = "{\"" + self.name + "\": 0}"
            entity_config["state_on"] = 1
            entity_config["state_off"] = 0

        elif self.entity_type == "sensor":
            entity_config["unit_of_measurement"] = self.unit

        else:
            print(messages_getjudo.debug[26])

        autoconf_topic = f"homeassistant/{self.entity_type}/{config_getjudo.LOCATION}/{config_getjudo.NAME}_{self.name}/config"
        publish_json(client, autoconf_topic, entity_config)

    def parse(self, response, index, a,b):
        val = response["data"][0]["data"][0]["data"][str(index)]["data"]
        if val != "":
            self.value = int.from_bytes(bytes.fromhex(val[a:b]), byteorder='little')


class notification_entity():
    def __init__(self, name, icon, counter=0, value = ""):
        self.name = name
        self.icon = icon
        self.value = value
        self.counter = counter

    def send_autoconfig(self):
        device_config = {
            "identifiers": f"[{client_id}]",
            "manufacturer": config_getjudo.MANUFACTURER,
            "model": config_getjudo.NAME,
            "name": client_id,
            "sw_version": config_getjudo.SW_VERSION
        }
        entity_config = {
            "device": device_config,
            "availability_topic": availability_topic,
            "payload_available": config_getjudo.AVAILABILITY_ONLINE,
            "payload_not_available": config_getjudo.AVAILABILITY_OFFLINE,
            "state_topic": notification_topic,
            "name": client_id + " " + self.name,
            "unique_id": client_id + "_" + self.name,
            "icon": self.icon
        }
        autoconf_topic = f"homeassistant/sensor/{config_getjudo.LOCATION}/{config_getjudo.NAME}_{self.name}/config"
        publish_json(client, autoconf_topic, entity_config)

    def publish(self, message, debuglevel):
        self.value = message
        msg = str(self.value)
        print(msg)
        if config_getjudo.MQTT_DEBUG_LEVEL  >= debuglevel:
            client.publish(notification_topic, msg, qos=0, retain=True)


def on_connect(client, userdata, flags, rc):
    if rc == 0:
        print(messages_getjudo.debug[1])
        client.subscribe(command_topic)
        print(messages_getjudo.debug[2])
        
        client.publish(availability_topic, config_getjudo.AVAILABILITY_ONLINE, qos=0, retain=True)

        for obj in gc.get_objects():
            if isinstance(obj, entity):
                obj.send_entity_autoconfig()
        notify.send_autoconfig()
        print(messages_getjudo.debug[3])
    else:
        print(messages_getjudo.debug[4].format(rc))


#Callback
def on_message(client, userdata, message):
    print(messages_getjudo.debug[5].format(message.topic, message.payload))
    command_json = json.loads(message.payload)
    
    if output_hardness.name in command_json:
        set_value(output_hardness, 60, command_json[output_hardness.name], 8)

    elif salt_stock.name in command_json:
        set_value(salt_stock, 94,command_json[salt_stock.name]*1000, 16)
    
    elif water_lock.name in command_json:
        set_water_lock(command_json[water_lock.name])

    elif regeneration_start.name in command_json:
        start_regeneration()

    elif sleepmode.name in command_json:
        set_sleepmode(command_json[sleepmode.name])

    elif max_waterflow.name in command_json:
        set_value(max_waterflow, 75, command_json[max_waterflow.name], 16)

    elif extraction_time.name in command_json:
        set_value(extraction_time, 74, command_json[extraction_time.name], 16)

    elif extraction_quantity.name in command_json:
        set_value(extraction_quantity, 76, command_json[extraction_quantity.name], 16)

    else:
        print(messages_getjudo.debug[6])


def publish_json(client, topic, message):
    json_message = json.dumps(message)
    result = client.publish(topic, json_message, qos=0, retain=True)


def set_water_lock(pos):
    if pos < 2:
        pos_index = str(73 - pos)
        if send_command(pos_index, ""):
            notify.publish(messages_getjudo.debug[7].format(pos), 2)
    else:
        print(messages_getjudo.debug[9])


def set_sleepmode(hours):
    if hours == 0:
        if send_command("73", ""):
            notify.publish(messages_getjudo.debug[10], 2)
    else:
        if send_command("171", str(hours)):
            notify.publish(messages_getjudo.debug[12].format(hours), 2)
        time.sleep(2)
        if send_command("171", ""):
            notify.publish(messages_getjudo.debug[14], 2)


def start_regeneration():
    if send_command("65", ""):
        notify.publish(messages_getjudo.debug[16], 2)


def set_value(obj, index, value, length):
    if send_command(str(index), int_to_le_hex(value, length)):
        notify.publish(messages_getjudo.debug[18].format(obj.name, value), 2)


def send_command(index, data):
    try:
        cmd_response = http.request('GET', f"https://www.myjudo.eu/interface/?token={my_token}&group=register&command=write%20data&serial_number={my_serial}&dt={my_dt}&index={index}&data={data}&da={my_da}&role=customer")
        cmd_response_json = json.loads(cmd_response.data)
        if "status" in cmd_response_json:
            if cmd_response_json["status"] == "ok":
                return True
    except Exception as e:
        notify.publish([messages_getjudo.debug[27].format(sys.exc_info()[-1].tb_lineno),e], 3)
        return False
    return False


def int_to_le_hex(integer,length):
    if length == 16:
        tmp = "%0.4X" % integer
        return (tmp[2:4] + tmp[0:2])
    elif length == 8:
        return ("%0.2X" % integer)
    else:
        notify.publish(messages_getjudo.debug[20], 3)


def judo_login(username, password):
    pwmd5 = hashlib.md5(password.encode("utf-8")).hexdigest()
    try:
        login_response = http.request('GET', f"https://www.myjudo.eu/interface/?group=register&command=login&name=login&user={username}&password={pwmd5}&nohash=Service&role=customer")
        login_response_json = json.loads(login_response.data)
        if "token" in login_response_json:
            print(messages_getjudo.debug[22].format(login_response_json['token']))
            return login_response_json['token']
        else:
            notify.publish(messages_getjudo.debug[21], 2)
            return False 
    except Exception as e:
        notify.publish([messages_getjudo.debug[28].format(sys.exc_info()[-1].tb_lineno),e], 3)
        return False


#----- MAIN PROGRAM ----
command_topic =f"{config_getjudo.LOCATION}/{config_getjudo.NAME}/command"
state_topic = f"{config_getjudo.LOCATION}/{config_getjudo.NAME}/state"
availability_topic = f"{config_getjudo.LOCATION}/{config_getjudo.NAME}/status"
notification_topic = f"{config_getjudo.LOCATION}/{config_getjudo.NAME}/notify"
client_id = f"{config_getjudo.NAME}-{config_getjudo.LOCATION}"

http = urllib3.PoolManager()

next_revision = entity(messages_getjudo.entities[0], "mdi:account-wrench", "sensor", "Tagen")
total_water = entity(messages_getjudo.entities[1], "mdi:water-circle", "total_increasing", "m³")
total_softwater_proportion = entity(messages_getjudo.entities[2], "mdi:water-outline", "total_increasing", "m³")
total_hardwater_proportion = entity(messages_getjudo.entities[3], "mdi:water", "total_increasing", "m³")
salt_stock = entity(messages_getjudo.entities[4], "mdi:gradient-vertical", "number", "kg", 1, 50)
salt_range = entity(messages_getjudo.entities[5], "mdi:chevron-triple-right", "sensor", "Tage")
output_hardness = entity(messages_getjudo.entities[6], "mdi:water-minus", "number", "°dH", 1, 15)
input_hardness = entity(messages_getjudo.entities[7], "mdi:water-plus", "sensor", "°dH")
water_flow = entity(messages_getjudo.entities[8], "mdi:waves-arrow-right", "sensor", "L/h")
batt_capacity = entity(messages_getjudo.entities[9], "mdi:battery-50", "sensor", "%")
regenerations = entity(messages_getjudo.entities[10], "mdi:recycle-variant", "sensor")
water_lock = entity(messages_getjudo.entities[11], "mdi:pipe-valve", "switch")
regeneration_start = entity(messages_getjudo.entities[12], "mdi:recycle-variant", "switch")
sleepmode = entity(messages_getjudo.entities[13], "mdi:pause-octagon", "number", "h", 0, 10)
water_today = entity(messages_getjudo.entities[14], "mdi:chart-box", "sensor", "L")
water_yesterday = entity(messages_getjudo.entities[15], "mdi:chart-box-outline", "sensor", "L")
notify = notification_entity(messages_getjudo.entities[16], "mdi:alert-outline")

#The maximum possible values for these settings have not been configured here. 
#For a better handling of the sliders I have limited the values. 
#If I need higher values I use the sleepmode to deactivate the leakage protection.
extraction_time = entity(messages_getjudo.entities[17], "mdi:clock-alert-outline", "number", "min", 10, 60, 10) #can setup to max 600min 
max_waterflow = entity(messages_getjudo.entities[18], "mdi:waves-arrow-up", "number", "L/h", 500, 3000, 500) #can setup to max 5000L/h 
extraction_quantity = entity(messages_getjudo.entities[19], "mdi:cup-water", "number", "L", 100, 500, 100)      #can setup to max 3000L

try: 
    client = mqtt.Client()
    client.on_connect = on_connect
    client.on_message = on_message
    if config_getjudo.USE_MQTT_AUTH:
        client.username_pw_set(config_getjudo.MQTTUSER, config_getjudo.MQTTPASSWD)
    client.will_set(availability_topic, config_getjudo.AVAILABILITY_OFFLINE, qos=0, retain=True)
    client.connect(config_getjudo.BROKER, config_getjudo.PORT, 60)
    client.loop_start()
except Exception as e:
    sys.exit(messages_getjudo.debug[33])

my_token = judo_login(config_getjudo.JUDO_USER, config_getjudo.JUDO_PASSWORD)

day_today = 0
offset_total_water = 0
last_err_id = 0

#Load stored variables:
print (messages_getjudo.debug[34])
print ("----------------------")
try:
    with open("temp_getjudo.pkl","rb") as temp_file:
        last_err_id, offset_total_water, water_yesterday.value, day_today = pickle.load(temp_file)
    print (messages_getjudo.debug[35].format(last_err_id))
    print (messages_getjudo.debug[36].format(water_yesterday.value))
    print (messages_getjudo.debug[37].format(offset_total_water))
    print (messages_getjudo.debug[38].format(day_today))
except Exception as e:
    notify.publish([messages_getjudo.debug[29].format(sys.exc_info()[-1].tb_lineno),e], 3)

notify.publish(messages_getjudo.debug[39], 2)

while True:
    if my_token == False:
        break
    try:
        #print("GET error messages from Cloud-Service...")
        error_response = http.request('GET',f"https://myjudo.eu/interface/?token={my_token}&group=register&command=get%20error%20messages")
        error_response_json = json.loads(error_response.data)
        
        if last_err_id != error_response_json["data"][0]["id"]:
            last_err_id = error_response_json["data"][0]["id"]

            if error_response_json["data"][0]["type"] == "w":
                error_message = messages_getjudo.warnings[error_response_json["data"][0]["error"]]
                notify.publish(error_message, 1)
            elif error_response_json["data"][0]["type"] == "e":
                error_message = messages_getjudo.errors[error_response_json["data"][0]["error"]]
                notify.publish(error_message, 1)
    except Exception as e:
        notify.publish([messages_getjudo.debug[30].format(sys.exc_info()[-1].tb_lineno),e], 3)
        notify.counter += 1 

    try:
        #print("GET device data from Cloud-Service...")
        response = http.request('GET',f"https://www.myjudo.eu/interface/?token={my_token}&group=register&command=get%20device%20data")
        response_json = json.loads(response.data)
        if response_json["status"] ==  "ok":
            #print("Parsing values from response...")
            my_serial = response_json["data"][0]["serialnumber"]
            my_da = response_json["data"][0]["data"][0]["da"]
            my_dt = response_json["data"][0]["data"][0]["dt"]

            next_revision.parse(response_json, 7, 0, 4)
            total_water.parse(response_json, 8, 0, 8)
            total_softwater_proportion.parse(response_json, 9, 0, 8)
            salt_stock.parse(response_json,94, 0, 4)
            salt_range.parse(response_json,94, 4, 8)
            output_hardness.parse(response_json, 790, 18, 20)
            input_hardness.parse(response_json, 790, 54, 56)
            water_flow.parse(response_json, 790, 34, 38)
            regenerations.parse(response_json, 791, 62, 66)
            regeneration_start.parse(response_json, 791, 2, 4)
            batt_capacity.parse(response_json, 93, 6, 8)
            water_lock.parse(response_json, 792, 2, 4)
            sleepmode.parse(response_json,792, 20, 22)
            max_waterflow.parse(response_json, 792, 26, 30)
            extraction_quantity.parse(response_json, 792, 30, 34)
            extraction_time.parse(response_json, 792, 34, 38)

            next_revision.value = int(next_revision.value/24)   #Calculation hours to days
            total_water.value =float(total_water.value/1000) # Calculating from L to m³
            total_softwater_proportion.value = float(total_softwater_proportion.value/1000)# Calculating from L to m³
            total_hardwater_proportion.value = round((total_water.value - total_softwater_proportion.value),3)
            salt_stock.value /= 1000
            #input_hardness.value =float(input_hardness.value/2) + 2 	               #This is the formula for the maximum adjustable desired output hardness. See Chapter 9 - Technical data
            regeneration_start.value &= 0x0F
            if regeneration_start.value > 0:
                regeneration_start.value = 1
            if water_lock.value > 1:
                water_lock.value = 1

            today = date.today()
            #It's 12pm...a new day. Store today's value to yesterday's value and setting a new offset for a new count
            if today.day != day_today:
                day_today = today.day
                offset_total_water = int(1000*total_water.value)
                water_yesterday.value = water_today.value
            water_today.value = int(1000*total_water.value) - offset_total_water

            #print("Publishing parsed values over MQTT....")
            outp_val_dict = {}
            for obj in gc.get_objects():
                if isinstance(obj, entity):
                    outp_val_dict[obj.name] = str(obj.value)
            publish_json(client, state_topic, outp_val_dict)

        elif response_json["status"] == "error":
            notify.coutner += 1
            if response_json["data"] == "login failed":
                notify.publish(messages_getjudo.debug[23],3)
                my_token = judo_login(config_getjudo.JUDO_USER, config_getjudo.JUDO_PASSWORD)
            else:
                val = response_json["data"]
                notify.publish(messages_getjudo.debug[24].format(val),3)
        else:
            print(messages_getjudo.debug[25])
    
    except Exception as e:
        notify.publish([messages_getjudo.debug[31].format(sys.exc_info()[-1].tb_lineno),e],3)
        notify.counter += 1 

    if notify.counter >= config_getjudo.MAX_RETRIES:
        notify.publish(messages_getjudo.debug[32].format(config_getjudo.MAX_RETRIES),3)
        break;

    notify.counter = 0

    with open("temp_getjudo.pkl","wb") as temp_file:
        pickle.dump([last_err_id, offset_total_water, water_yesterday.value, day_today], temp_file)

    time.sleep(config_getjudo.STATE_UPDATE_INTERVAL)
#----- MAIN PROGRAM END ----

