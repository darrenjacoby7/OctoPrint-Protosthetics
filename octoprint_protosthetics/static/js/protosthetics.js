/*
 * View model for OctoPrint-Protosthetics
 *
 * Author: Aaron Burton
 * License: AGPLv3
 */
$(function() {
    function ProtostheticsViewModel(parameters) {
        var self = this;
		self.settings = parameters[0];
		console.log("this much is working");
		//console.log(self.settings);
		
		self.passSerial = ko.observable("Ready");
		self.printerStatus = ko.observable("Printer ON");
		self.dryerStatus = ko.observable("Dryer OFF");
		self.buttonStatus = ko.observable("Ready");
		self.lightStatus = ko.observable("Lights ON");
		self.brightness = ko.observable(50);
		self.temperature = ko.observable(0);
		self.humidity = ko.observable(0);
		self.humidityLow = ko.observable(); //self.settings.settings.plugins.protosthetics.hum_low);
		self.humidityHigh = ko.observable(); //self.settings.settings.plugins.protosthetics.hum_high);
		self.filamentStatus = ko.observable("");

		self.passSerial.subscribe(function(newValue) {
			console.log(newValue);
			OctoPrint.simpleApiCommand("protosthetics","passSerial",{"payload": newValue});
		});
		
		self.humidityLow.subscribe(function(newValue) {
			OctoPrint.simpleApiCommand("protosthetics","settings",{variable: "hum_low",
                                    			                   data: newValue});
		});
		
		self.humidityHigh.subscribe(function(newValue) {
			OctoPrint.simpleApiCommand("protosthetics","settings",{variable: "hum_high", 
			                                                       data: newValue});
		});
		
		self.brightness.subscribe(function(newValue) {
			console.log(newValue);
			OctoPrint.simpleApiCommand("protosthetics","brightness",{"payload": newValue});
		});
		
		// called just before bindings, almost done.
		self.onBeforeBinding = function() {
			self.humidityLow(self.settings.settings.plugins.protosthetics.hum_low());
			self.humidityHigh(self.settings.settings.plugins.protosthetics.hum_high());
		}
		
		self.onDataUpdaterPluginMessage = function(plugin, data) {
			if (plugin != "protosthetics") {
				return;
			}
			//console.log("a message from protosthetics≈ " + data);
			if (data.type == "ERROR"){
				alert(data.message);
			} else if (data.type == "INFO"){
				console.log(data.message);
			} else if (data.type == "POP"){
				new PNotify({
					title: 'Protosthetics?',
					text: data.message,
					type: 'success',
					hide: true,
					buttons: {
						closer: true,
						sticker: false
					}
				});
			} else if (data.type == "FUNCTION") {
				if (data.message=='resumeQueue') {
					self.resumeQueue();
				} else if (data.message=='startQueue') {
					self.startQueue();
				} else if (data.message=='setActive') {
					self.setActive();
				}
			} else if (data.type == "L"){
				self.lightStatus("Lights "+ data.message +"%");
			} else if (data.type =="DRYER"){
				if (data.message=="1") {
					self.dryerStatus("Dryer ON");
				} else if (data.message=="0") {
					self.dryerStatus("Dryer OFF");
				}
			} else if (data.type=="P"){
				if (data.message==1) {
					self.printerStatus("Printer ON");
				} else if (data.message==0) {
					self.printerStatus("Printer OFF");
				}
			} else if (data.type=="B1") {
				self.buttonStatus(data.message);
			} else if (data.type=="Temp") {
				self.temperature(data.message.toFixed(2));
			} else if (data.type=="Hum") {
				self.humidity(data.message.toFixed(2));
			} else if (data.type=="FIL") {
				self.filamentStatus(data.message);
			} else if (data.type=="PROGRESS") {
				console.log(data.message + "%");
			} else {
				console.log(data);
			}
		}
		
		// k.o. button functions from jinja pages
		self.lightButtonFunction = function() {
		  OctoPrint.simpleApiCommand("protosthetics","lightToggle");
		}
		
		self.dryerButtonFunction = function() {
			OctoPrint.simpleApiCommand("protosthetics","dryerToggle");
		}
		
		self.printerPowerFunction = function() {
			OctoPrint.simpleApiCommand("protosthetics","printerToggle");
		}
		
		self.changeFilamentFunction = function() {
			OctoPrint.simpleApiCommand("protosthetics","changeFilament");
		}
		
		self.resetESPFunction = function() {
			OctoPrint.simpleApiCommand("protosthetics","resetESP");
		}
		
		// js functions from python pages
		self.resumeQueue = function() {
			$.ajax({
				url: "plugin/continuousprint/resumequeue",
				type: "GET",
				dataType: "json",
				headers: {
					"X-Api-Key":UI_API_KEY,
				},
				data: {}
			});
		}
		
		self.startQueue = function() {
			$.ajax({
				url: "plugin/continuousprint/startqueue",
				type: "GET",
				dataType: "json",
				headers: {
					"X-Api-Key":UI_API_KEY,
				},
				data: {}
			});
		}
		
		self.setActive = function() {
			$.ajax({
				url: "plugin/continuousprint/set_active",
				type: "GET",
				dataType: "json",
				headers: {
					"X-Api-Key":UI_API_KEY,
				},
				data: {}
			});
		}
    }
	
	

    /* view model class, parameters for constructor, container to bind to
     * Please see http://docs.octoprint.org/en/master/plugins/viewmodels.html#registering-custom-viewmodels for more details
     * and a full list of the available options.
     */
    OCTOPRINT_VIEWMODELS.push({
        construct: ProtostheticsViewModel,
        dependencies: [  "settingsViewModel"  ],
        // ViewModels your plugin depends on, e.g. loginStateViewModel, settingsViewModel, ...
        // Elements to bind to, e.g. #settings_plugin_helloworld, #tab_plugin_helloworld, ...
        elements: [ "#settings_plugin_protosthetics" , "#sidebar_plugin_protosthetics" ]
    });
});
