# Home Assistant to Emotiva XMC-1 service

This custom component provides 3 services to Home Assistant to allow for integration with Emotiva XMC-1.  The discover service discovers XMCs on the local subnet and populates a number of state variables.  The updates_states service polls the XMC-1 for current status volume, power, formats etc..  The send_command allows you to send commands to the XMC to update volume, mute, power, input etc..

