# Home Assistant to Emotiva XMC-1 service


[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg?style=for-the-badge)](https://github.com/hacs/integration)


This custom component provides 3 services to Home Assistant to allow for integration with Emotiva XMC-1.  The discover service discovers XMCs on the local subnet and populates a number of state variables.  The updates_states service polls the XMC-1 for current status volume, power, formats etc..  The send_command allows you to send commands to the XMC to update volume, mute, power, input etc..

## Installation

The preferred installation approach is via Home Assistant Community Store - aka [HACS](https://hacs.xyz/).  The repo is installable as a [Custom Repo](https://hacs.xyz/docs/faq/custom_repositories) via HACS.

If you want to download the integration manually, create a new folder called xmc under your custom_components folder in your config folder.  If the custom_components folder doesn't exist, create it first.  Once created, download the 3 files from the [github repo](https://github.com/peteS-UK/xmc/tree/main/custom_components/xmc) into this xmc folder.

Once downloaded either via HACS or manually, restart your Home Assistant server.

## Configuration

To enable the integration, add the following line to your configuration.yaml file, typically in your /config folder.

```yaml
xmc:
```

Once updated, restart your Home Assistant server again to enable the integration.







