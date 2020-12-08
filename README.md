# Domoticz-VirtualThermostat-PID

## Overview
Smart Virtual Thermostat with PID python plugin for Domoticz home automation system

Inspired by SmartVirtualThermostat https://www.domoticz.com/wiki/Plugins/Smart_Virtual_Thermostat.html

An internal temperature sensor is used to control a smart thermostatic radiator valve.  using a PID regulator.

Possible control modes:
- changing a TRV set point temperature
- changing an internal TRV temperature sensor value adjustment (not tested)
- replacing an internal TRV temperature sensor values by an additional sensor value (not implemented)

Current code was tested with Danfoss Living Connect Z-Wave (014G0013) and Xiaomi Mi ZigBee Temperature and Humidity Sensor WSDCG6Q01LM

Plugin creates a new device

![Device](https://user-images.githubusercontent.com/74839419/101463532-d1c3f200-393d-11eb-8ec5-b9ee874c3af2.png)

Example of timers. Pause is applied once a week for 10 minutes to close a valve regularly.

![Timers](https://user-images.githubusercontent.com/74839419/101463492-c670c680-393d-11eb-911e-8d8c8d6e7bbd.png)

Example of plugin settings

![Settings](https://user-images.githubusercontent.com/74839419/101463418-ad681580-393d-11eb-961a-0f9b63df3d25.png)

## Parameters

### Inside Temperature Sensors (csv list of idx)
List of all temperature sensors installed in the controlled room. An average is caluclated.

Example: 4,5

### Open Window Sensors (csv list of idx)
List of all open window sensors installed in the controlled room. 

Example: 6

### Thermostat Radiator Valves (csv list of idx)
List of all TRV installed in the controlled room. 

Example: 9,11

### High/Low/Pause/Precision/Max shift Temperatures (csv list of values)
* High - temperature (in C) during a day
* Low - temperature (in C) during a night
* Pause - temperature (in C) used when windows are open or during Pause mode (antifreeze)
* Precision - precision of sensor or valve set point (in C) - this parameter prevent too frequent changes  and adds kind of histeresis
* Max shift - highest accepted difference between set point and target temperatur (High/Low)

Example: 21.0,20.0,5.0,0.5,2.0

### Calc. interval, Pause On delay, Pause Off delay, Sensor Timeout (all in minutes):
* Calc. interval - time between calculation of PID shift
* Pause On delay - time between opening a window and virtual thermostat switching to Pause mode
* Pause Off delay - time between closing a window and virtual thermostat switching  to previous mode (Normal/Economic)
* Sensor Timeout - when temperature sensors are not responding - virtual thermostat will use only an internal TRV temperature sensor (not implemented)

Example: 10,1,10,90

### PID Params P/I/D/Debug/E/C:
* Kp - proportional factor
* Ki - integral factor
* Kd - differential factor
* Debug - 1/0 debug logging on/off
* E - shift calculation mode: 1 - PID, 2 - simple delta
* C - TRV Control mode - 1 - set point, 2 - internal TRV sensor temperature value adjustment, 3 - internal TRV sensor temperature value replacement

Example: 0.9,0.1,0.2,0,1,1

## Thermostat modes
* Off - virtual thermostat is not controlling TRV devices
* Normal - control TRV to achive defined higher temperture
* Economy - control TRV to achive defined lower temperture
* Pause - sets on all TRVs antifreeze temperture
* 3x Off - reload internal values from user variable - after first "Off" update user variable (i.e. "Integral")
* 3x Pause - restore default internal values

## TODO:
- open window pause
- TRV control modes 2 and 3
- Sensor Timeout
- Multiple temperature sensors - min/max/avg mode - currently only avg
