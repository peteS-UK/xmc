"""Example of a custom component exposing a service."""
from __future__ import annotations

import logging

from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers.typing import ConfigType


# The domain of your component. Should be equal to the name of your component.
DOMAIN = "emotiva_xmc"
_LOGGER = logging.getLogger(__name__)


#import emotiva

from .emotiva import Emotiva

def setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the sync service example component."""


    def create_xmc():
        
        if hass.states.get("emotiva_xmc.control_port") is not None :
          # We already have ports
          if int(hass.states.get("emotiva_xmc.control_port").state) != 0 :
            # Call with the ports
            _LOGGER.debug("Create with ports")
            xmc = Emotiva(ip = hass.states.get("emotiva_xmc.address").state,
                          transp_xml = None, 
                          _ctrl_port = int(hass.states.get("emotiva_xmc.control_port").state), 
                          _notify_port = int(hass.states.get("emotiva_xmc.notify_port").state),
                          _name = hass.states.get("emotiva_xmc.name").state,
                          _model = hass.states.get("emotiva_xmc.model").state,
                          _proto_ver = float(hass.states.get("emotiva_xmc.protocol_version").state),
                          _info_port = int(hass.states.get("emotiva_xmc.info_port").state),
                          _setup_port = int(hass.states.get("emotiva_xmc.setup_port").state),
                          )
            _method = "ports"
          else :
            _LOGGER.debug("Create with xml1")
            _ip, _xml = _discover()
            # call with xml
            xmc = Emotiva(ip = _ip,transp_xml = _xml)
            _method = "discover"
        
        else :
          _LOGGER.debug("Create with xml2")
          _ip, _xml = _discover()
          # call with xml
          xmc = Emotiva(ip = _ip,transp_xml = _xml)
          _method = "discover"
        
        return xmc, _method

    def send_command(call: ServiceCall) -> None:

        # Test to see if discover has already been run and the ports stored

        xmc, _method = create_xmc()

        xmc.connect()

        match call.data.get("xmcCommand"):
          case "volup":
            xmc.volume_up()
          case "voldown":
            xmc.volume_down()
          case "mute":
            xmc.mute_toggle()
          case "poweron":
            xmc.power = True
          case "poweroff":
            xmc.power = False
          case "input":
            _input = call.data.get("xmcValue")
            if (int(_input) < 1 or int(_input) > 8 or _input is None):
              _input = "1"
            xmc.set_input("source_"+_input)

        xmc._update_status(xmc._events, float(xmc._proto_ver))

        _update_all_hass_states(xmc)

        xmc.disconnect()

        del xmc
            
    def update_state(call: ServiceCall) -> None:
        xmc,_method = create_xmc()

        xmc.connect()

        # xmc._subscribe_events(xmc._events, xmc._proto_ver)
        # update status is create wasn't via Fy, which will already have done update
        if _method != "discover":
          xmc._update_status(xmc._events, xmc._proto_ver)
          _update_all_hass_states(xmc)

        xmc.disconnect()

        del xmc  

    def _update_all_hass_states(xmc):
        
        hass.states.set("emotiva_xmc.power", xmc._current_state['power'])
        hass.states.set("emotiva_xmc.source", xmc._current_state['source'])
        hass.states.set("emotiva_xmc.mode", xmc._current_state['mode'])
        hass.states.set("emotiva_xmc.volume", xmc._current_state['volume'])
        hass.states.set("emotiva_xmc.audio_input", xmc._current_state['audio_input'])
        hass.states.set("emotiva_xmc.audio_bitstream", xmc._current_state['audio_bitstream'])
        hass.states.set("emotiva_xmc.video_input", xmc._current_state['video_input'])
        hass.states.set("emotiva_xmc.video_format", xmc._current_state['video_format'])

    def discover(call: ServiceCall) -> None:

        _ip, _xml = _discover()
    
    def _discover() :
        
        _ip, _xml = Emotiva.discover(version=3)[0]

        xmc = Emotiva(_ip,_xml)

        _LOGGER.debug("_discover.  Transponder version %s", xmc._proto_ver )

        xmc.connect()

        # xmc._subscribe_events(xmc._events, xmc._proto_ver)
        xmc._update_status(xmc._events, float(xmc._proto_ver))

        _update_all_hass_states(xmc)

        hass.states.set("emotiva_xmc.control_port", xmc._ctrl_port)
        hass.states.set("emotiva_xmc.protocol_version", xmc._proto_ver)
        hass.states.set("emotiva_xmc.name", xmc._name)
        hass.states.set("emotiva_xmc.model", xmc._model)
        hass.states.set("emotiva_xmc.address", xmc._ip)
        hass.states.set("emotiva_xmc.info_port", xmc._info_port)
        hass.states.set("emotiva_xmc.notify_port", xmc._notify_port)
        hass.states.set("emotiva_xmc.setup_port", xmc._setup_port_tcp) 

        xmc.disconnect()

        del xmc

        return _ip, _xml 

    # Register our service with Home Assistant.
    hass.services.register(DOMAIN, 'send_command', send_command)
    hass.services.register(DOMAIN, 'discover', discover)
    hass.services.register(DOMAIN, 'update_state', update_state)


    # Return boolean to indicate that initialization was successfully.
    return True
