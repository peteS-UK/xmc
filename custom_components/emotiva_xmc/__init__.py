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
        
        _state = hass.states.get("%s.processor" % DOMAIN)
        #if hass.states.get("%s.control_port" % DOMAIN) is not None :
        try:
          if int(_state.attributes['control_port']) != 0 :
            # Call with the ports
            _LOGGER.debug("Create with ports")
            xmc = Emotiva(ip = _state.attributes['address'],
                          transp_xml = None, 
                          _ctrl_port = int(_state.attributes['control_port']), 
                          _notify_port = int(_state.attributes['notify_port']),
                          _name = _state.attributes['name'],
                          _model = _state.attributes['model'],
                          _proto_ver = float(_state.attributes['protocol_version']),
                          _info_port = int(_state.attributes['info_port']),
                          _setup_port = int(_state.attributes['setup_port']),
                          )
            _method = "ports"
          else :
            _LOGGER.debug("Create with xml1")
            _ip, _xml = _discover()
            # call with xml
            xmc = Emotiva(ip = _ip,transp_xml = _xml)
            _method = "discover"
        
        except :
          _LOGGER.debug("Create with xml2")
          _ip, _xml = _discover()
          # call with xml
          xmc = Emotiva(ip = _ip,transp_xml = _xml)
          _method = "discover"
        
        return xmc, _method

    def send_command(call: ServiceCall) -> None:

        xmc, _method = create_xmc()

        xmc.connect()

        try:
          xmc.send_command(call.data.get("xmcCommand"),call.data.get("xmcValue"))
          xmc._update_status(xmc._events, float(xmc._proto_ver))
          _update_all_hass_states(xmc)
        except:
          pass
        
        xmc.disconnect()

        del xmc
            
    def update_state(call: ServiceCall) -> None:

        xmc,_method = create_xmc()

        xmc.connect()

        # xmc._subscribe_events(xmc._events, xmc._proto_ver)
        # update status is create wasn't via discover, which will already have done update
        if _method != "discover":
          if call.data.get("xmcNotify") is not None:
             xmc._events = xmc._events.union(set(call.data.get("xmcNotify")))
             xmc._current_state.update(dict((m, None) for m in call.data.get("xmcNotify")))
          xmc._update_status(xmc._events, xmc._proto_ver)
          _update_all_hass_states(xmc)

        xmc.disconnect()

        del xmc  

    def _update_all_hass_states(xmc):
        
        try:
          _attributes = hass.states.get("%s.processor" % DOMAIN).attributes.copy()
        except:
           _attributes = {}
        
        for ev in xmc._events:
          _attributes[ev] = xmc._current_state[ev]

        hass.states.set("%s.processor" % DOMAIN, xmc._current_state['power'],_attributes)

    def discover(call: ServiceCall) -> None:

        _ip, _xml = _discover()
    
    def _discover() :
        
        _ip, _xml = Emotiva.discover(version=3)[0]

        xmc = Emotiva(_ip,_xml)

        _LOGGER.debug("_discover.  Transponder version %s", xmc._proto_ver )

        xmc.connect()

        xmc._update_status(xmc._events, float(xmc._proto_ver))

        hass.states.set("%s.processor" % (DOMAIN),"",
                        {"control_port":xmc._ctrl_port,
                         "protocol_version":xmc._proto_ver,
                         "name":xmc._name,
                         "model":xmc._model,
                         "address":xmc._ip,
                         "info_port":xmc._info_port,
                         "notify_port":xmc._notify_port,
                         "setup_port":xmc._setup_port_tcp
                         })
                                
        _update_all_hass_states(xmc)
        
        xmc.disconnect()

        del xmc

        return _ip, _xml 

    # Register our service with Home Assistant.
    hass.services.register(DOMAIN, 'send_command', send_command)
    hass.services.register(DOMAIN, 'discover', discover)
    hass.services.register(DOMAIN, 'update_state', update_state)


    # Return boolean to indicate that initialization was successfully.
    return True
