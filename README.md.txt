# RFEH End-to-End Simulator

This project implements an end-to-end simulator for RF energy harvesting side-channel research.

The simulator maps:

app_id + action_id
-> traffic burst templates
-> RF transmission events
-> received RF power
-> harvested power
-> storage capacitor voltage V_CAP

Version 0 focuses on a minimal working simulator:
- simplified app/action traffic templates
- simplified transmitter model
- log-distance path loss channel
- simplified RF-to-DC efficiency
- capacitor energy update
- output V_CAP time series

Version 0 intentionally excludes:
- Fresnel human movement model
- detailed Wi-Fi MAC/PHY
- packet-level TCP/QUIC model
- AP/router detailed downlink model
- boost converter V_OUT model