"""
Smart Virtual Thermostat with PID python plugin for Domoticz
Author: Logread, Worops
        adapted from the Vera plugin by Antor, see:
            http://www.antor.fr/apps/smart-virtual-thermostat-eng-2/?lang=en
            https://github.com/AntorFr/SmartVT
Version: 0.0.1 (November 24, 2020) - see history.txt for versions history
"""
"""
<plugin key="SVTP" name="Domoticz Virtual Thermostat with PID" author="worops" version="0.0.1" wikilink="" externallink="">
    <description>
        <h2>Smart Virtual Thermostat with PID</h2><br/>
    </description>
    <params>
        <param field="Mode1" label="Inside Temperature Sensors (csv list of idx)" width="100px" required="true" default=""/>
        <param field="Mode2" label="Open Window Sensors (csv list of idx)" width="100px" required="false" default=""/>
        <param field="Mode3" label="Thermostat Radiator Valves (csv list of idx)" width="100px" required="true" default=""/>
        <param field="Mode4" label="High/Low/Pause/Precision/Max shift Temperatures" width="200px" required="true" default="21,20,5,0.5,2"/>
        <param field="Mode5" label="Calc. interval, Pause On delay, Pause Off delay, Sensor Timeout (all in minutes)" width="200px" required="true" default="10,1,10,90"/>
        <param field="Mode6" label="PID Params P/I/D/Debug/E/C" width="200px" required="true" default="0.9,0.10,0.2,1,1,1"/>
    </params>
</plugin>
"""

import Domoticz as domoticz
import json
import urllib, requests
from datetime import datetime, timedelta
import time
import base64
import itertools


class deviceparam:

    def __init__(self, unit, nvalue, svalue):
        self.unit = unit
        self.nvalue = nvalue
        self.svalue = svalue


class BasePlugin:

    def __init__(self):

        self.calculate_period = 10  # Time in minutes between two calculations (cycle)
        self.pause_on_delay = 1  # time between pause sensor actuation and actual pause
        self.pauseoffdelay = 10  # time between end of pause sensor actuation and end of actual pause
        
        self.in_temp_sensors = []
        self.radiators = []
        self.open_window_sensors = []
        
        self.InternalsDefaults = {
            'previous_error': float(0.0),  
            'integral': float(-10.0),  
            'current_delta': float(0.0),
            'target_temp': float(-100.0),
            'opened_window': int(0),
            'nValue': int(0)
            }
        
        self.Internals = self.InternalsDefaults.copy()
        
        
        self.high_temp = 21.0
        self.low_temp = 20.0 
        self.prec_temp = 0.5 
        self.max_shift = 2.0 


        
        self.Kp = 0.9
        self.Ki = 0.1
        self.Kd = 0.2
        
        self.shift_calc_mode = 1 # PID
        self.trv_control = 1 # setpoint
        self.temp_sensors_timeout = 90

        self.next_calc = datetime.now()
        self.last_calc = None
        self.last_command = None
        self.enabled = True
        self.reset_cnt = 0 # Pause -> Off -> True
        self.reload_cnt = 0 # Off -> Pause & step1 -> True
 
        


    def onStart(self):

        domoticz.Debugging(1)
        DumpConfigToLog()
        
        # Load config params
        self.in_temp_sensors = parseCSV(Parameters["Mode1"], 'in_temp_sensors', 'int')
        self.check_params(self.in_temp_sensors, 1, "in_temp_sensors")            

        self.open_window_sensors = parseCSV(Parameters["Mode2"], 'open_window_sensors', 'int')
        self.check_params(self.open_window_sensors, 0, "open_window_sensors")
        
        self.radiators = parseCSV(Parameters["Mode3"], 'radiators', 'int')
        self.check_params(self.radiators, 1, "radiators")
        
        temp_params = parseCSV(Parameters["Mode4"], 'temp_params', 'float')
        self.check_params(temp_params, 5, "temp_params")
        
        time_params = parseCSV(Parameters["Mode5"], 'time_params', 'int')
        self.check_params(time_params, 4, "time_params")
        
        pid_params = parseCSV(Parameters["Mode6"], 'pid_params', 'float')
        self.check_params(pid_params, 6, "pid_params")
        
        if len(temp_params) == 5:
            self.high_temp = temp_params[0]
            self.low_temp = temp_params[1]
            self.pause_temp = temp_params[2]
            self.prec_temp = temp_params[3]
            self.max_shift = temp_params[4]
        else:
            domoticz.Error("Error reading Mode4 parameters")
            
 
        
        if len(time_params) == 4:
            self.calculate_period = time_params[0]
            
            if self.calculate_period < 5:
                domoticz.Error("Invalid calculation period parameter. Using minimum of 5 minutes !")
                self.calculate_period = 5
           
            self.pause_on_delay = time_params[1]
            self.pauseoffdelay = time_params[2]
            self.temp_sensors_timeout = time_params[3]
           
        else:
            domoticz.Error("Error reading Mode5 parameters")
            
        
        if len(pid_params) == 6:
            self.Kp = pid_params[0]
            self.Ki = pid_params[1]
            self.Kd = pid_params[2]
            self.debug = int(pid_params[3])
            self.shift_calc_mode = int(pid_params[4])
            self.trv_control = int(pid_params[5])
            domoticz.Debugging(self.debug)
        else:
            domoticz.Error("Error reading Mode6 parameters")
            
            
        # control of devices
        
        # TODO check devices onHeartbeat
        for i_dev in itertools.chain(self.in_temp_sensors, self.radiators):
            if self.get_device_status(i_dev) is None:
                domoticz.Debug("Device {} is not present - turning off SVTP".format(i_dev))
                self.enabled = False
                
        
        # create the child devices if these do not exist yet
        if 1 not in Devices:
            Options = {"LevelActions": "||",
                       "LevelNames": "Off|Normal|Economy|Pause",
                       "LevelOffHidden": "false",
                       "SelectorStyle": "0"}
            domoticz.Device(Name="Thermostat Mode", Unit=1, TypeName="Selector Switch", Switchtype=18, Image=15,
                            Options=Options, Used=1).Create()
            
        
        self.load_internals()
        
        # if any device has been created in onStart(), now is time to update its defaults
        if self.Internals["nValue"] == 0:
            nvalue = 0
            svalue = "0"
            
        elif self.Internals["nValue"] == 1:
            nvalue = 1
            svalue = "10"
            self.Internals["target_temp"] = self.high_temp
            
        elif self.Internals["nValue"] == 2:
            nvalue = 2
            svalue = "20"
            self.Internals["target_temp"] = self.low_temp
        
        elif self.Internals["nValue"] == 3:
            nvalue = 3
            svalue = "30"
            self.Internals["target_temp"] = self.pause_temp
            
        else:
            domoticz.Error("onStart: Unknown Internals nValue: {}".format(self.Internals["nValue"]))
            
        Devices[1].Update(nValue=nvalue, sValue=svalue)
        
        domoticz.Log(str(self.Internals))
        
        
        
    
  

    def onStop(self):

        domoticz.Debugging(0)


    def onCommand(self, Unit, Command, Level, Color):

        domoticz.Log("onCommand called for Unit {}: Command '{}', Level: {}".format(Unit, Command, Level))
        
        if Command == "Off":
        
            nvalue = 0
            self.reset_cnt = 0
            self.reload_cnt += 1
            
            if self.reload_cnt == 1:
            
                self.Internals["target_temp"] = -100.0
                self.save_internals()
            
            elif self.reload_cnt == 3:
                
                self.load_internals()
                domoticz.Log("load_internals")
                self.reload_cnt = 0
                    
            
            
        elif Command == "Set Level":
            
            self.last_command = datetime.now()
            
            
            if Level == 10:
                self.Internals["target_temp"] = self.high_temp
                nvalue = 1
                self.save_internals()
                self.set_target_temp(self.high_temp, self.Internals["current_delta"], force=True)
                self.reset_cnt = 0
                self.reload_cnt = 0

            elif Level == 20:
                self.Internals["target_temp"] = self.low_temp
                nvalue = 2
                self.save_internals()
                self.set_target_temp(self.low_temp, self.Internals["current_delta"], force=True)
                self.reset_cnt = 0
                self.reload_cnt = 0
                
                
            elif Level == 30:
            
                nvalue = 3 
                self.reload_cnt = 0
                self.reset_cnt += 1
                
                if self.reset_cnt == 1:
                    self.Internals["target_temp"] = self.pause_temp
                    self.set_target_temp(self.pause_temp, 0, force=True)
                    self.save_internals()
                    domoticz.Debug("Pause is On")
                    
                elif self.reset_cnt == 3:
                    self.Internals = self.InternalsDefaults.copy()
                    self.save_internals()
                    domoticz.Log("InternalsReset")
                    self.reset_cnt = 0
                
                
                
            else:
                domoticz.Error("Unknown Level {} onCommand {}".format(Level, Command))
                
        Devices[Unit].Update(nValue=nvalue, sValue=str(Level))


    def onHeartbeat(self):
    
        # TODO: once a week valve full closure

        if self.enabled is False:
            return
            
        if Devices[1].nValue in (0, 3):
            return
        
        now = datetime.now()
        
        # fool proof checking.... based on users feedback
        # if not all(device in Devices for device in (1,)):
        #    domoticz.Error("One or more devices required by the plugin is/are missing, please check domoticz device creation settings and restart !")
        #    self.enabled = False
        #    return
            
        opened_window, opened_window_time = self.get_window_data()
           
        if self.Internals["opened_window"] == 0 and opened_window == 1 and opened_window_time + timedelta(minutes=self.pause_on_delay) <= now:  
           
            domoticz.Log("Opened window - set pause temp {}".format(self.pause_temp))
            
            self.Internals["opened_window"] = 1
            self.set_target_temp(self.pause_temp, 0.0, force=True)
            
            
            
            self.last_calc = now
            self.next_calc = now + timedelta(minutes=self.calculate_period /2)
           
        elif self.Internals["opened_window"] == 1 and opened_window == 0 and opened_window_time + timedelta(minutes=self.pause_off_delay) <= now:
           
            
            self.Internals["opened_window"] = 0

            domoticz.Log("Closed window - set {} {}/{}".format(self.Internals["target_temp"], applied_temp))
            
            self.set_target_temp(self.Internals["target_temp"], self.Internals["current_delta"], force=True)
            
            
            self.last_calc = now
            self.next_calc = now + timedelta(minutes=self.calculate_period)
            
        elif self.next_calc <= now:  # we start a new calculation

            # TODO: implement sensors timeout -> switch to TRV only sensor
            current_temp = self.get_current_temp()

            if abs(current_temp - self.Internals["target_temp"]) <= self.prec_temp/2.0:
                if current_temp - self.Internals["target_temp"] <= 0.0:
                    domoticz.Debug("Skipping calc - current_temp {}, target_temp {}, prec ".format(current_temp, self.Internals["target_temp"], self.prec_temp))
                    
                    self.last_calc = now
                    self.next_calc = now + timedelta(minutes=self.calculate_period)
                    return
                else:
                    current_temp = round(self.Internals["target_temp"] + self.prec_temp, 1)
            
            # PID    
            elif self.shift_calc_mode == 1: # PID
                error = round(self.Internals["target_temp"] - current_temp, 2)
                self.Internals["integral"] = round(self.Internals["integral"] + error, 2)
                derivative = round(error - self.Internals["previous_error"], 2)
                
                pid_p = round(self.Kp * error, 2)
                pid_i = round(self.Ki * self.Internals["integral"], 2)
                pid_d = round(self.Kd * derivative, 2)
                
                self.Internals["current_delta"] = round(pid_p + pid_i + pid_d, 1)
                self.Internals["previous_error"] = error

                domoticz.Debug("PID current_temp {}, target_temp {}, temp_shift {}, p {}, i {}, d {}".format(current_temp, self.Internals["target_temp"], self.Internals["current_delta"], error, self.Internals["integral"], derivative))
            
            elif self.shift_calc_mode == 2: # simple delta
            
                temp_shift = round(self.Internals["target_temp"] - current_temp, 1)
                self.Internals["current_delta"] = temp_shift
                
                domoticz.Debug("SD current_temp {}, temp_shift {}".format(current_temp, temp_shift))

            
            # set valves setpoint 
            # TODO: PID/Delta setpoint/adjustval
            
                
            self.set_target_temp(self.Internals["target_temp"], self.Internals["current_delta"], None)
           
            # TODO: next calc after TRV wake up
            self.last_calc = now
            self.next_calc = now + timedelta(minutes=self.calculate_period)
            self.save_internals()
            
            
            domoticz.Log("Next calculation time will be : " + str(self.next_calc))
        

    def get_window_data(self):
    
        if self.open_window_sensors is None or len(self.open_window_sensors) == 0:
            return 0, '2000-01-01 12:00:00'
            
        for i_window_dev in self.open_window_sensors:
            pass
            
        return 0, '2000-01-01 12:00:00'
        
    def get_temp_data(self, idx):
        
        v_json = self.get_device_status(idx)
        device = v_json['result'][0]
        
        domoticz.Debug(str(device))
        
        if device['Type'] != 'Temp' or device['SubType'] != 'LaCrosse TX3':
            domoticz.Error("Device {} is not a thermometer".format(idx))
            return None
            
        else:
            return float(device['Temp']), device['LastUpdate']

            
    def get_current_temp(self):
        
        l_temp = []
        for i_temp_dev in self.in_temp_sensors:
            i_temp = self.get_temp_data(i_temp_dev)
            l_temp.append(i_temp[0])
          
        mean_temp = round(1.0 * sum(l_temp) / len(l_temp), 1)
        return mean_temp
        
    

            
    def get_valve_data(self, idx):
    
        v_json = self.get_device_status(idx)
        device = v_json['result'][0]
        
        domoticz.Debug(str(device))
        
        if device['Type'] != 'Thermostat' or device['SubType'] != 'SetPoint':
            domoticz.Error("Device {} is not a thermostat".format(idx))
            return None
            
        else:
            return float(device['SetPoint']), float(device['AddjValue']), device['LastUpdate']

            
    def set_valve_temp(self, idx, target_temp, shift_temp):
    
        domoticz.Debug("set_valve_temp idx {} temp {} shift {} trv control {}".format(idx, target_temp, shift_temp, self.trv_control))
        
        url = 'http://localhost:8080/json.htm?type=command&param=setsetpoint&idx={}'.format(idx)
        
        if self.max_shift is not None or self.max_shift > 0:
            if abs(shift_temp) > self.max_shift:
                shift_temp = self.max_shift if shift_temp > 0 else -1.0 * self.max_shift
                
        
        if target_temp is None and shift_temp is None:
            domoticz.Error("set_valve_temp for {} - temp and shift is None".format(idx))
            url += '&setpoint={}'.format(self.Internals["target_temp"])
            
        elif self.trv_control == 1: # setpoint

            url += '&setpoint={}'.format(target_temp + shift_temp)
            
        elif self.trv_control == 2: # shift

            url += '&setpoint={}'.format(target_temp)
            url += '&addjvalue={}'.format(round(-1.0*shift_temp,1))
            
        elif self.trv_control == 3: # external sensor
            domoticz.Error("external_sensor is not implemented")
            url += '&setpoint={}'.format(self.Internals["target_temp"])
            
        else:
            domoticz.Error("Unknown control method")
            url += '&setpoint={}'.format(self.Internals["target_temp"])

   
        domoticz.Debug(url)
        
        response = requests.post(url)
        if response.status_code != 200:
            domoticz.Error("set_valve_temp temp {} for {} reponded {}".format(temp, idx, response.status_code))
            
       
        
    def set_target_temp(self, temp, shift, force=False):
        
        max_next_update_time = None
        
        for i_trv_dev in self.radiators:
            v_data = self.get_valve_data(i_trv_dev)
            
            if force is True or abs(temp - v_data[0]) >= self.prec_temp: # or abs(shift - v_data[1]) > self.prec_temp:
                domoticz.Log("set_target_temp - idx {} c_temp {} n_temp {} c_shift {} n_shift {} prec {}".format(i_trv_dev, v_data[0], temp, v_data[1], shift, self.prec_temp))
                self.set_valve_temp(i_trv_dev, target_temp=temp, shift_temp=shift)
                max_next_update_time = v_data[2]
            
            else:
                domoticz.Debug("Skipping set_target_temp - idx {} c_temp {} n_temp {} c_shift {} n_shift {} prec {}".format(i_trv_dev, v_data[0], temp, v_data[1], shift, self.prec_temp))
          
        
        return max_next_update_time 
        # TODO: return last next TRV wake up

        # pause
        
        # check set temp
        # for i_trv_dev in self.radiators:
        #    v_data = self.get_valve_data(i_trv_dev)
        #    if abs(temp - v_data[0]) > self.prec_temp:
        #        domoticz.Error("TRV temp setting error: idx {}, setpoint {}, target {}, prec {}".format(i_trv_dev, v_data[0], temp, self.prec_temp))


    def get_device_status(self, idx):
        # /json.htm?type=devices&rid=IDX
        
        url = 'http://localhost:8080/json.htm?type=devices&rid={}'.format(idx)
        response = requests.get(url)
        
        if response.status_code == 200:
            return response.json()
        else:

            return None
       
        #postdata = {'type':'command', 'param':'udevice', 'idx':'358', 'svalue':'66'}
        # resp = requests.get(url=url, params=postdata)

        
    def save_internals(self, add=False):

        varname = Parameters["Name"] + "-InternalVariables"
        
        if add:
            cparam = 'adduservariable'
        else:
            cparam = 'updateuservariable'
            
        url = 'http://localhost:8080/json.htm?type=command&param={}&vname={}&vtype=2&vvalue={}'.format(cparam, varname, str(self.Internals))
         
        response = requests.post(url)
        
        if response.status_code != 200:
            domoticz.Error("Cannot save_internals")
        
            
    def load_internals(self):

        url = 'http://localhost:8080/json.htm?type=command&param=getuservariables'
        response = requests.get(url)
        
        if response.status_code == 200:
            variables = response.json()
        else:
            domoticz.Error("Cannot get_user_vars")
            variables = None
            
        # variables = self.get_user_vars()
        if variables:
            
            # there is a valid response from the API but we do not know if our variable exists yet
            novar = True
            varname = Parameters["Name"] + "-InternalVariables"
            valuestring = ""
            
            if "result" in variables:
                for variable in variables["result"]:
                    if variable["Name"] == varname:
                        valuestring = variable["Value"]
                        novar = False
                        break
            
            
            if novar:

                # actually calling Domoticz API
                self.Internals = self.InternalsDefaults.copy()  # we re-initialize the internal variables
                self.save_internals(add=True)                
                
                
            else:
                try:
                    self.Internals.update(eval(valuestring))
                except:
                    self.Internals = self.InternalsDefaults.copy()
                return
        else:
            domoticz.Error("Cannot read the uservariable holding the persistent variables")
            self.Internals = self.InternalsDefaults.copy()
       
    def check_params(self, param_list, min_length, param_name):
    
        if min_length > 0 and (param_list is None or len(param_list) < min_length):
            self.enabled = False

            domoticz.Debug("Parameters {} are not valid - turning off SVTP".format(param_name))
            domoticz.Debug(str(param_list))
    





global _plugin
_plugin = BasePlugin()


def onStart():
    global _plugin
    _plugin.onStart()


def onStop():
    global _plugin
    _plugin.onStop()


def onCommand(Unit, Command, Level, Color):
    global _plugin
    _plugin.onCommand(Unit, Command, Level, Color)


def onHeartbeat():
    global _plugin
    _plugin.onHeartbeat()


# Plugin utility functions ---------------------------------------------------

def parseCSV(strCSV, param_name, type):

    listvals = []
    
    if strCSV == '':
        return []
        
    for value in strCSV.split(","):
    
        try:
            if type == 'int':
                val = int(value)
                
            elif type == 'float':
                val = float(value)
                
            listvals.append(val)
                
        except:
            domoticz.Error("Parameter {} has inssuficient values".format(param_name))
            return None
         
    return listvals

def ParseDateTime(datestring):
    dateformat = "%Y-%m-%d %H:%M:%S"
    
    # the below try/except is meant to address an intermittent python bug in some embedded systems
    try:
        result = datetime.strptime(datestring, dateformat)
    except TypeError:
        result = datetime(*(time.strptime(datestring, dateformat)[0:6]))
        
    return result


# Generic helper functions
def DumpConfigToLog():
    for x in Parameters:
        if Parameters[x] != "":
            domoticz.Debug("'" + x + "':'" + str(Parameters[x]) + "'")
    domoticz.Debug("Device count: " + str(len(Devices)))
    for x in Devices:
        domoticz.Debug("Device:           " + str(x) + " - " + str(Devices[x]))
        domoticz.Debug("Device ID:       '" + str(Devices[x].ID) + "'")
        domoticz.Debug("Device Name:     '" + Devices[x].Name + "'")
        domoticz.Debug("Device nValue:    " + str(Devices[x].nValue))
        domoticz.Debug("Device sValue:   '" + Devices[x].sValue + "'")
        domoticz.Debug("Device LastLevel: " + str(Devices[x].LastLevel))
    
