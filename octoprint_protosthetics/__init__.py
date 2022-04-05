from __future__ import absolute_import, unicode_literals
from gpiozero import Button, PWMLED, DigitalOutputDevice
import time, os, serial
from .DHT20 import DFRobot_DHT20 as DHT

import octoprint.plugin
from octoprint.util import RepeatedTimer

class ProtostheticsPlugin(octoprint.plugin.TemplatePlugin,      # to show up on the dashboard
                       octoprint.plugin.AssetPlugin,            # to use javaScript
                       octoprint.plugin.ProgressPlugin,         # to display print progress
                       octoprint.plugin.EventHandlerPlugin,     # to respond to file uploads and show LED status for other events
                       octoprint.plugin.StartupPlugin,          # to get buttons and functions set up at the beginning
                       octoprint.plugin.ShutdownPlugin,         # to close out all the hardware connections
                       octoprint.plugin.SettingsPlugin,         # to change and test some variables
                       octoprint.plugin.SimpleApiPlugin):       # to let the JavaScript call python functions
					   
  def __init__(self):
    self.button1 = Button(4, hold_time=3, pull_up=None, active_state=True)
    self.button2 = Button(5, hold_time=3, pull_up=None, active_state=True)  # depreciated on HAT 01.2022
    self.button3 = Button(6, hold_time=3, pull_up=None, active_state=True)  # depreciated on HAT 01.2022
    self.printer = DigitalOutputDevice(22, active_high=False, initial_value=True)
    self.dryer   = DigitalOutputDevice(23, active_high=True, initial_value=False)
    self.led = PWMLED(12, initial_value=0, frequency=8000)
    self.flash = DigitalOutputDevice(17, active_high=False, initial_value=False)    # for flashing the ESP8266 firmware
    self.ESPreset = DigitalOutputDevice(16, active_high=False, initial_value=False) # for flashing the ESP8266 firmware
    
    self.button1.when_pressed = self.buttonPress
    self.button1.when_released = self.buttonRelease
    self.button1.when_held = self.longPress
    self.button1holding = False     # to skip the release function when the holding function was executed
    self.custom_mode = 0            # for custom pausing reasons 
    
    self.button2.when_pressed = self.reportDHT
    
    
  def on_after_startup(self):
    # Try to connect to the DHT20 sensor and establish a recurring reading
    try:
      self.dht = DHT(0x01,0x38)  #use i2c port 1 and address 0x38
      self.dht.begin()
      self.updateTimer = RepeatedTimer(10.0, self.reportDHT)
      self.updateTimer.start()
      self.sendMessage('INFO',"DHT Connected")
      self._logger.warning("DHT connection success!")
    except OSError:
      self.sendMessage("INFO","DHT error")
      self._logger.warning("DHT connection error")
      
    # Try to connect to the ESP8266 over serial
    try:
      self.com = serial.Serial('/dev/ttyS0', 9600)
      self.hasSerial = True
    except: #what exception goes here?
      self._logger.warning("No connection to LED controller.  Check raspi-config settings.")
      self.hasSerial = False
    self.send('P3') #plasma
    self.send('C0') #Ocean colors
    
    self._logger.info("Protosthetics ≈ %i %i" %(self._settings.get(["hum_low"]), self._settings.get(["hum_high"])))
  
  # close all gpio zero connections and shut down the timer
  # This is likely not needed, as the plugin only shuts down then the system is restarting
  # But better safe than... not safe.
  def on_shutdown(self):
    self.button1.close()
    self.button2.close()
    self.button3.close()
    self.led.close()
    self.printer.close()
    self.dryer.close()
    self.flash.close()
    self.ESPreset.close()
    self.updateTimer.cancel()
  
  # for settings plugin
  def get_template_vars(self):
    return dict(words=self._settings.get(["words"]),
                version=self._plugin_version,
	            hum_low=self._settings.get(["hum_low"]),
                hum_high=self._settings.get(["hum_high"]),
                filament_load_length=self._settings.get(["filament_load_length"]),
                filament_unload_length=self._settings.get(["filament_unload_length"])
                )

  # for settings plugin
  def get_settings_defaults(self):
    return dict(hum_low=30,
                hum_high=40,
                filament_load_length = 120,
                filament_unload_length = 100
                )
  # what templates will be used
  def get_template_configs(self):
    return [
      #dict(type="navbar"),
      dict(type="settings", custom_bindings=True),
      dict(type="sidebar")
    ]
  
  # what assets are we providing
  def get_assets(self):
    return {
      "js": ["js/protosthetics.js"],
      "css": ["css/protosthetics.css"]
    }
    
  # for reporting the current print progress for LED display
  def on_print_progress(self,storage,path,progress):
    self.sendMessage('PROGRESS',progress)  # This displays it in the console (for debugging)
    if progress == 100:
      # don't send (use print_done event instead)
      return
    
    self.send('C1')  #party colors
    self.send('P8') #progress bar with plasma
    self.send('D%i' %progress)

  # bound to button 1 release
  def buttonRelease(self):
    # Only run this code if the button was not held
    if self.button1holding:
      return
    # report to front end
    self.sendMessage('B1','release')
    # start the next print, or resume the print
    if self._printer.is_ready():
      # self.sendMessage('FUNCTION','startQueue')
      # does it hurt to start and resume here?
      # For the continuousPrint update, this changes to SetActive
      self.sendMessage('FUNCTION','setActive')
      # self.sendMessage('FUNCTION','resumeQueue')
    if self._printer.is_paused():
      self._printer.resume_print()
    elif self._printer.is_printing():
      self._printer.pause_print()
	
  # bound to button 1 press
  def buttonPress(self):
    # self.sendMessage('POP','Button was pressed')
    # report to front end
    self.sendMessage('B1','press')
    # reset held variable
    self.button1holding = False
    
  # bound to button 1 long-press (hold)
  def longPress(self):
    # report to front end
    self.sendMessage('B1','held')
    self.button1holding = True
    self.send('P5')  #juggle pattern
    self.led.blink(0.1,0.1,n=2,background=False)  #Blink front LEDs twice for 0.1 seconds
    self.mode = self._printer.get_state_id()
    self._logger.info(self.mode)
    
    # if the printer is in some paused state...
    # run M108, which will finish the filament change and resume the print
    # or just resume the print if a regular pause
    if self.mode == "PAUSED" or self.mode == "PAUSING" or self.custom_mode == "PAUSED":
      # break and continue (after filament change)
      self._printer.commands("M108")
      #self._printer.resume_print()
      self._logger.info('Theoretically resuming')
      self._logger.info(self.custom_mode)
      if self.custom_mode:
        self.custom_mode = 0
        self._printer.set_temperature('tool0',self.whatItWas)
      self.sendMessage('FIL','')
    # if printing, initiate a filament change
    elif self._printer.is_printing():
      self._printer.commands("M117 Changing filament")
      # change filament command
      self._printer.commands("M603 U%i L%i" %(self._settings.get(["filament_unload_length"]), self._settings.get(["filament_load_length"])))
      # TODO: make these configurable variables
      self._printer.commands("M600")
      self.sendMessage('FIL','Press when new filament is ready')
    # if sitting idle, initiate a filament change
    elif self._printer.is_ready():
      # if the printer is not at an extruding temperature
      # save the current temperature, set a new one, and wait for it to be hot enough
      temps = self._printer.get_current_temperatures()
      self.whatItWas = temps.get('tool0').get('target')
      self._logger.info(temps)
      self._logger.info(self.whatItWas)
      if temps.get('tool0').get('actual') < 200:
        if self.whatItWas < 200:
          #self._printer.set_temperature('tool0',220)
          self._printer.commands("M109 S220")
        else:
          self._printer.commands("M109 S%i" %self._printer.get_current_temperatures().get('tool0').get('target'))
      self._printer.commands("M117 Unloading filament, stand by")
      #self._printer.commands("M603 U120 L125")
      self._printer.commands("M600")
      self.custom_mode = "PAUSED"
      self.sendMessage('FIL','Press when new filament is ready')
    self.led.on()  # turn the lights on for filament change
    self.sendMessage('L',self.led.value*100)
    
  # read the DHT20 sensor and report to front end
  def reportDHT(self):
    temp = self.dht.get_temperature()
    hum  = self.dht.get_humidity()
    self.sendMessage('Temp',temp)
    self.sendMessage('Hum',hum)
    # TODO:  move the humidifier to its own function
    if hum > self._settings.get(['hum_high']):
      self.dryer.on()
      self.sendMessage('DRYER',1)
    elif hum < sefl_settings.get(['hum_low']):
      self.dryer.off()
      self.sendMessage('DRYER',0)
        
  # send data to the ESP8266
  def send(self, data):
    if self.hasSerial:
      self.com.write((data + '\n').encode())
      
  # send data to the front end
  def sendMessage(self, type, message):
    payload = {"type": type, "message": message}
    self._plugin_manager.send_plugin_message(self._identifier, payload)
        
  # things the front end can tell python
  def get_api_commands(self):
    return dict(
                  lightToggle=[],
                  dryerToggle=[],
                  printerToggle=[],
                  changeFilament=[],
                  resetESP=[],
                  passSerial=['payload'],
                  brightness=['payload'],
                  settings=['variable','data']
               )

  # handling what the front end tells python
  def on_api_command(self,command,data):
    self._logger.info(command+str(data))
    if command == 'lightToggle':
      if self.led.value: 
        self.led.off()
      else: 
        self.led.on()
      self._logger.info('Light button pressed')
      self.sendMessage('L',self.led.value*100)
      #self._plugin_manager.send_plugin_message(self._identifier, 'L%i' %self.led.value)
    elif command == 'dryerToggle':
      self.dryer.toggle()
      self._logger.info('Dryer button pressed')
      self.sendMessage('DRYER',self.dryer.value)
    elif command == 'printerToggle':
      self.printer.toggle()
      self._logger.info('Printer power button pressed')
      self.sendMessage('P',self.printer.value)
    elif command == 'changeFilament':
      self.longPress()
    elif command == 'resetESP':
      self.flash.off()
      self.ESPreset.on()
      time.sleep(0.1)
      self.ESPreset.off()
    elif command == 'settings':
      self._settings.set([data.get('variable')], data.get('data'))
      self._settings.save()
    elif command == 'passSerial':
      self.send(data.get('payload'))
      self._logger.info('Serial command sent')
    elif command == 'brightness':
      self.led.value = 10**(int(data.get('payload'))/50)/100
      self.sendMessage('L',self.led.value*100)
               
  # responding to printer events
  # some for code, some for LED patterns
  def on_event(self,event,payload):
    if event == octoprint.events.Events.ERROR:
      self.sendMessage('INFO','Error event reported:\n' + payload.get('error'))
      if payload.get('error').count('kill()'):
        #Printer halted. kill() called!
        #restart printer and the print
        #printer off
        self.printer.off()
        #wait
        time.sleep(3)
        #printer on
        self.printer.on()
        #wait
        time.sleep(3)
        #connect
        self._printer.connect()
        #restart print
        #note how many times it failed
    if event == octoprint.events.Events.PRINT_STARTED:
      self.send('C1')  #party colors
    if event == octoprint.events.Events.PRINT_DONE:
      self.send('P1')  #theater chase
    if event == octoprint.events.Events.PRINT_CANCELLED:
      self.send('P7')  #Fire
      self.send('C2')  #Lava colors
    if event == octoprint.events.Events.PRINT_FAILED:
      self.sendMessage('INFO','Error: Print Failed - ' + payload.get('reason'))
      self._printer.commands("G91") #set relative mode
      self._printer.commands("G0 Z20") #lift z 20mm
      #self._printer.commands("G28 Z")
      # TODO make this configurable
    if event == octoprint.events.Events.DISCONNECTED:
      self.sendMessage('FUNCTION','setNotActive')
    # if a firmware file was uploaded, pass it to the ESP8266
    if event == octoprint.events.Events.FILE_ADDED:
      self._logger.warning('FILE ADDED!!!' + payload.get('name'))
      if payload.get('name').endswith('.sh.gcode'):
        self.sendMessage('POP','Script loaded')
        uploads = '/home/pi/.octoprint/uploads'
        scripts = '/home/pi/.octoprint/scripts'
        files = os.listdir(uploads)
        for file in files:
          if file.endswith('.sh.gcode'):
            os.system('mv '+uploads+'/'+file+' '+scripts+'/'+file[:-6])
      if payload.get('name').endswith('.bin.gcode'):
        self._logger.info('Might be firmware')
        if self._printer.is_printing():
          self._logger.warning("Do not try to upload new firmware while printing‼")
          return
        if not self.hasSerial:
          self._logger.warning("Serial not initialized, use raspi-config")
          return
        # everything checks out, begin upload process
        self._plugin_manager.send_plugin_message(self._identifier, 'new firmware found')
        uploads = '/home/pi/.octoprint/uploads'
        files = os.listdir(uploads)
        for file in files:
          if file.endswith('.bin.gcode'):
            os.system('mv '+uploads+'/'+file+' '+uploads+'/LEDfirmware.bin')
            
            self.sendMessage("POP","Uploading new firmware")
            self._plugin_manager.send_plugin_message(self._identifier, 'uploading new firmware!')
            self.flash.on()
            self.ESPreset.on()
            time.sleep(0.1)
            self.ESPreset.off()
            time.sleep(0.2)
            self._plugin_manager.send_plugin_message(self._identifier, 'Firmware started')
            os.system('esptool.py -p /dev/ttyS0 write_flash 0x00 '+uploads+'/LEDfirmware.bin')
            self._plugin_manager.send_plugin_message(self._identifier, 'Firmware uploaded')
            self.flash.off()
            self.ESPreset.on()
            time.sleep(0.1)
            self.ESPreset.off()
            self.sendMessage("POP","Firmware upload complete")
            break
	
  def get_update_information(self):
    return {
        "protosthetics": {
          'displayName': "Protosthetics Plugin",
          'displayVersion': self._plugin_version,
          'type': "github_release",
          'user': "aburtonProto",
          'repo': "OctoPrint-Protosthetics",
          'current': self._plugin_version,
          "stable_branch": {
                    "name": "Stable",
                    "branch": "master",
                    "comittish": ["master"],
                },
          'pip': "https://github.com/aburtonProto/OctoPrint-Protosthetics/archive/{target_version}.zip"
        }
    }
    
    
__plugin_name__ = "Protosthetics Plugin"
__plugin_pythoncompat__ = ">=3,<4"

__plugin_implementation__ = ProtostheticsPlugin()
__plugin_hooks__ = {
    "octoprint.plugin.softwareupdate.check_config": __plugin_implementation__.get_update_information
}