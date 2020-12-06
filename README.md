# Domoticz-VirtualThermostat-PID

## Overview
Smart Virtual Thermostat with PID python plugin for Domoticz home automation system

Inspired by SmartVirtualThermostat https://www.domoticz.com/wiki/Plugins/Smart_Virtual_Thermostat.html

An internal temeperature sensor is used to control a smart thermostatic radiator valve.  using PID regulator.
Possible control modes:
- changing a TRV set point temperature
- changing an interlnal TRV temperature sensor value adjustment (not tested)
- replacing an internal TRV temperature sensor values by an additional sensor value (not implmented)

Current code was tested with Danfoss Living Connect Z-Wave (014G0013) and Xiaomi Mi ZigBee Temperature and Humidity Sensor WSDCG6Q01LM

## Parameters

### Inside Temperature Sensors (csv list of idx)
List of all temperature sensors installed in the controlled room. Example: 4,5

### Open Window Sensors (csv list of idx)
List of all open window sensors installed in the controlled room. Example: 6

### Thermostat Radiator Valves (csv list of idx)
List of all TRV installed in the controlled room. Example: 9,11

### High/Low/Pause/Precision/Max shift Temperatures (csv list of values)
High - temperature (in C) during a day
Low - temperature (in C) during a night
Pause - temperature (in C) used when windows are open or during Pause mode (antifreeze)
Precision - precission of sensor or valve set point (in C)
Max shift - highest acceppted difference between set point and target temperatur (High/Low)

Example: 21.0,20.0,5.0,0.5,2.0

### Calc. interval, Pause On delay, Pause Off delay, Sensor Timeout (all in minutes):
Calc. interval - time between calculation of PID shift
Pause On delay - time between opening a window and virtual thermostat switching to Pause mode
Pause Off delay - time between closing a window and virtual thermostat switching  to previous mode (Normal/Economic)
Sensor Timeout - when temperature sensors are not responding - virtual thermostat will use only an internal TRV temperature sensor (not implemented)
Example: 10,1,10,90

### PID Params P/I/D/Debug/E/C:
Kp - proportional factor
Ki - integral factor
Kd - differential factor
Debug - 1/0 debug logging on/off
E - shift calculation mode: 1 - PID, 2 - simple delta
C - TRV Control mode - 1 - set point, 2 - internal TRV sensor temperatur value adjustment, 3 - internal TRV sensor temperatur value replacement
Example: 0.9,0.1,0.2,0,1,1
