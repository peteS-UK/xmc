"""Example of a custom component exposing a service."""
from __future__ import annotations

import logging
import socket


from lxml import etree


from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers.typing import ConfigType

class Error(Exception):
  pass

# The domain of your component. Should be equal to the name of your component.
DOMAIN = "emotiva_xmc"
_LOGGER = logging.getLogger(__name__)


class InvalidTransponderResponseError(Error):
  pass


class InvalidSourceError(Error):
  pass

class InvalidModeError(Error):
  pass


class Emotiva(object):
  XML_HEADER = '<?xml version="1.0" encoding="utf-8"?>'.encode('utf-8')
  DISCOVER_REQ_PORT = 7000
  DISCOVER_RESP_PORT = 7001

  NOTIFY_EVENTS = set([
      'power', 'zone2_power', 'source', 'mode', 'volume', 'audio_input',
      'audio_bitstream', 'video_input', 'video_format',
  ]).union(set(['input_%d' % d for d in range(1, 9)]))


  def __init__(self, ip, transp_xml, _ctrl_port = None, _notify_port = None, 
               _name = 'Unknown', _model = 'Unknown', _proto_ver = None, _info_port = None, _setup_port = None,
                events = NOTIFY_EVENTS ):

    self._ip = ip
    self._name = _name
    self._model = _model
    self._proto_ver = _proto_ver
    self._ctrl_port = _ctrl_port
    self._notify_port = _notify_port
    self._info_port = _info_port
    self._setup_port_tcp = _setup_port
    self._ctrl_sock = None
    self._update_cb = None
    self._modes = {"Stereo" :           ['stereo', 'mode_stereo', True],
              "Direct":             ['direct', 'mode_direct', True],
              "Dolby Surround":     ['dolby', 'mode_dolby', True],
              "DTS":                ['dts', 'mode_dts', True], 
              "All Stereo" :        ['all_stereo', 'mode_all_stereo', True],
              "Auto":               ['auto', 'mode_auto', True],
              "Reference Stereo" :  ['reference_stereo', 'mode_ref_stereo',True],
              "Surround":           ['surround_mode', 'mode_surround', True]}
    self._events = events

    # current state
    self._current_state = dict(((ev, None) for ev in self._events))
    self._current_state.update(dict(((m[1], None) for m in self._modes.values())))
    self._sources = {}

    self._muted = False

    if not self._ctrl_port or not self._notify_port:
      self.__parse_transponder(transp_xml)
 
    if not self._ctrl_port or not self._notify_port:
      raise InvalidTransponderResponseError("Coulnd't find ctrl/notify ports")

  def connect(self):
    self._ctrl_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    self._ctrl_sock.bind(('', self._ctrl_port))
    self._ctrl_sock.settimeout(0.5)

#  def _notify_handler(self, data):
#    resp = self._parse_response(data)
#    self._handle_status(resp)

  def _subscribe_events(self, events, _proto_ver = 2.0):
    _LOGGER.debug("proto_ver %d", _proto_ver)
    msg = self.format_request('emotivaSubscription',
                              [(ev, {}) for ev in events],
                              #{'protocol':"3.0"} if _proto_ver == 3 else {})
                              {})
    self._send_request(msg, ack=True)


  def _update_status(self, events, _proto_ver = 2.0):
    _LOGGER.debug("proto_ver %d", _proto_ver)
    msg = self.format_request('emotivaUpdate',
                              [(ev, {}) for ev in events],
                              #{'protocol':"3.0"} if _proto_ver == 3 else {})
                              {})
    self._send_request(msg, ack=True)

  def _send_request(self, req, ack=False, process_response=True):
    self._ctrl_sock.sendto(req, (self._ip, self._ctrl_port))

    while ack:
      try:
        _resp_data, (ip, port) = self._ctrl_sock.recvfrom(4096)
        _LOGGER.debug("Response on ack: %s",_resp_data)
        if process_response == True:
          resp = self._parse_response(_resp_data)
          self._handle_status(resp)
      except socket.timeout:
        _LOGGER.debug("socket.timeout on ack")
        break

  def __parse_transponder(self, transp_xml):
    elem = transp_xml.find('name')
    if elem is not None: self._name = elem.text.strip()
    elem = transp_xml.find('model')
    if elem is not None: self._model = elem.text.strip()

    ctrl = transp_xml.find('control')
    elem = ctrl.find('version')
    if elem is not None: self._proto_ver = elem.text
    elem = ctrl.find('controlPort')
    if elem is not None: self._ctrl_port = int(elem.text)
    elem = ctrl.find('notifyPort')
    if elem is not None: self._notify_port = int(elem.text)
    elem = ctrl.find('infoPort')
    if elem is not None: self._info_port = int(elem.text)
    elem = ctrl.find('setupPortTCP')
    if elem is not None: self._setup_port_tcp = int(elem.text)

  def _handle_status(self, resp):
    for elem in resp:
      if elem.tag not in self._current_state:
        _LOGGER.debug('Unknown element: %s' % elem.tag)
        continue
      val = (elem.get('value') or '').strip()
      visible = (elem.get('visible') or '').strip()
      #update mode status
      if (elem.tag.startswith('mode_') and visible != "true"):
        _LOGGER.debug(' %s is no longer visible' % elem.tag)
        for v in self._modes.items():
          if(v[1][1] == elem.tag):
            v[1][2] = False
            self._modes.update({v[0]: v[1]})
      #do not 
      if (elem.tag.startswith('input_') and visible != "true"):
        continue
      if elem.tag == 'volume':
        if val == 'Mute':
          self._muted = True
          continue
        self._muted = False
        # fall through
      if val:
        self._current_state[elem.tag] = val
        _LOGGER.debug("Updated '%s' <- '%s'" % (elem.tag, val))
      if elem.tag.startswith('input_'):
        num = elem.tag[6:]
        self._sources[val] = int(num)
    if self._update_cb:
      self._update_cb()

  def set_update_cb(self, cb):
    self._update_cb = cb

  @classmethod
  def discover(cls, version = 2):
    resp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    resp_sock.bind(('', cls.DISCOVER_RESP_PORT))
    resp_sock.settimeout(0.5)

    req_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    req_sock.bind(('', 0))
    req_sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    if version == 3:
      req = cls.format_request('emotivaPing', {}, {'protocol': "3.0"})
    else:
      req = cls.format_request('emotivaPing')
    req_sock.sendto(req, ('<broadcast>', cls.DISCOVER_REQ_PORT))

    devices = []
    while True:
      try:
        _resp_data, (ip, port) = resp_sock.recvfrom(4096)
        resp = cls._parse_response(_resp_data)
        devices.append((ip, resp))
      except socket.timeout:
        break
    return devices

  @classmethod
  def _parse_response(cls, data):
    _LOGGER.debug("parse_response: %s", data)
    try: 
      parser = etree.XMLParser(ns_clean=True, recover = True)
      root = etree.XML(data, parser)
    except etree.ParseError:
      _LOGGER.error("Malformed XML")
      _LOGGER.error(data)
      root = ""
    return root

  @classmethod
  def format_request(cls, pkt_type, req = {}, pkt_attrs = {}):
    """
    req is a list of 2-element tuples with first element being the command,
    and second being a dict of parameters. E.g.
    ('power_on', {'value': "0"})

    pkt_attrs is a dictionary containing element attributes. E.g.
    {'protocol': "3.0"}
    """
    output = cls.XML_HEADER
    builder = etree.TreeBuilder()
    builder.start(pkt_type,pkt_attrs)
    for cmd, params in req:
      builder.start(cmd, params)
      builder.end(cmd)
    builder.end(pkt_type)
    pkt = builder.close()
    return output + etree.tostring(pkt)

  @property
  def name(self):
    return self._name

  @property
  def model(self):
    return self._model

  @property
  def address(self):
    return self._ip

  @property
  def power(self):
    if self._current_state['power'] == 'On':
      return True
    return False

  @power.setter
  def power(self, onoff):
    cmd = {True: 'power_on', False: 'power_off'}[onoff]
    msg = self.format_request('emotivaControl', [(cmd, {'value': '0',
                                                              'ack':'True'})])
    self._send_request(msg, ack=True, process_response=False)


  @property
  def volume(self):
    if self._current_state['volume'] != None:
      return float(self._current_state['volume'].replace(" ", ""))
    return None

  @volume.setter
  def volume(self, value):
    msg = self.format_request('emotivaControl', [('set_volume', {'value': str(value),
                                                              'ack':'True'})])
    self._send_request(msg, ack=True, process_response=False)

  def _volume_step(self, incr):
    # The XMC-1 with firmware version <= 3.1a will not change the volume unless
    # the volume overlay is up. So, we first send a noop command for volume step
    # with value 0, and then send the real step.
    noop = self.format_request('emotivaControl', [('volume', {'value': '0'})])
    msg = self.format_request('emotivaControl', [('volume', {'value': str(incr),
                                                              'ack':'True'})])
    self._send_request(noop)
    self._send_request(msg, ack=True, process_response=False)
    
  def volume_up(self):
    self._volume_step(1)

  def volume_down(self):
    self._volume_step(-1)

  def mute_toggle(self):
    msg = self.format_request('emotivaControl', [('mute', {'value': '0',
                                                              'ack':'True'})])
    self._send_request(msg, ack=True, process_response=False)

  def set_input(self, source):
    msg = self.format_request('emotivaControl', [(source, {'value': '0',
                                                              'ack':'True'})])
    self._send_request(msg, ack=True, process_response=False)

  @property
  def mute(self):
    return self._muted

  @mute.setter
  def mute(self, enable):
    mute_cmd = {True: 'mute_on', False: 'mute_off'}[enable]
    msg = self.format_request('emotivaControl', [(mute_cmd, {'value': '0'})])
    self._send_request(msg)

  @property
  def sources(self):
    return tuple(self._sources.keys())

  @property
  def source(self):
    return self._current_state['source']

  @source.setter
  def source(self, val):
    if val not in self._sources:
      raise InvalidSourceError('Source "%s" is not a valid input' % val)
    elif self._sources[val] is None:
      raise InvalidSourceError('Source "%s" has bad value (%s)' % (
          val, self._sources[val]))
    msg = self.format_request('emotivaControl',
        [('source_%d' % self._sources[val], {'value': '0'})])
    self._send_request(msg)

  
  @property
  def modes(self):
    #we return only the modes that are active
    return tuple(dict(filter(lambda elem: elem[1][2] == True, self._modes.items())).keys())
  
  @property
  def mode(self):
    return self._current_state['mode']

  @mode.setter
  def mode(self, val):
    if val not in self._modes:
      raise InvalidModeError('Mode "%s" does not exist' % val)
    elif self._modes[val][0] is None:
      raise InvalidModeError('Mode "%s" has bad value (%s)' % (
          val, self._modes[val][0]))
    msg = self.format_request('emotivaControl',[(self._modes[val][0],  {'value': '0'})])
    self._send_request(msg)




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
          else :
            _LOGGER.debug("Create with xml1")
            _ip, _xml = _discover()
            # call with xml
            xmc = Emotiva(ip = _ip,transp_xml = _xml)
        
        else :
          _LOGGER.debug("Create with xml2")
          _ip, _xml = _discover()
          # call with xml
          xmc = Emotiva(ip = _ip,transp_xml = _xml)
        
        return xmc

    def send_command(call: ServiceCall) -> None:

        # Test to see if discover has already been run and the ports stored

        xmc = create_xmc()

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

        xmc._update_status(xmc._events, xmc._proto_ver)

        _update_all_hass_states(xmc)
            
    def update_state(call: ServiceCall) -> None:
        xmc = create_xmc()

        xmc.connect()

        # xmc._subscribe_events(xmc._events, xmc._proto_ver)
        xmc._update_status(xmc._events, xmc._proto_ver)

        _update_all_hass_states(xmc)

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

        xmc.connect()

        # xmc._subscribe_events(xmc._events, xmc._proto_ver)
        xmc._update_status(xmc._events, xmc._proto_ver)

        _update_all_hass_states(xmc)

        hass.states.set("emotiva_xmc.control_port", xmc._ctrl_port)
        hass.states.set("emotiva_xmc.protocol_version", xmc._proto_ver)
        hass.states.set("emotiva_xmc.name", xmc._name)
        hass.states.set("emotiva_xmc.model", xmc._model)
        hass.states.set("emotiva_xmc.address", xmc._ip)
        hass.states.set("emotiva_xmc.info_port", xmc._info_port)
        hass.states.set("emotiva_xmc.notify_port", xmc._notify_port)
        hass.states.set("emotiva_xmc.setup_port", xmc._setup_port_tcp) 

        return _ip, _xml 

    # Register our service with Home Assistant.
    hass.services.register(DOMAIN, 'send_command', send_command)
    hass.services.register(DOMAIN, 'discover', discover)
    hass.services.register(DOMAIN, 'update_state', update_state)


    # Return boolean to indicate that initialization was successfully.
    return True
