# Theory Spec for v0 Simulator

## Goal

Given app_id and action_id, simulate the storage capacitor voltage V_CAP over time.

## End-to-end pipeline

1. App/action template generator
2. RF TxEvent generator
3. Wireless channel model
4. RF-to-DC harvesting model
5. Capacitor voltage model
6. Result export and plotting

## Core equations

Received power:

P_r[k] = sum_j P_eirp_j * G_path(d) * I(t_k in [start_j, end_j]) + P_amb

Path gain:

PL(d) = PL0(d0, f) + 10*n*log10(d/d0) + shadowing_db
G_path = 10^(-PL/10)

Harvested DC power:

P_h[k] = eta_rf(P_r[k]) * P_r[k]

Capacitor energy:

E_c[k+1] = E_c[k] + dt * (P_h[k] - P_leak[k])
V_cap[k+1] = sqrt(2 * E_c[k+1] / C)

## Units

- Power in Watts internally
- dBm only in config/input, converted immediately to Watts
- Time in seconds
- Frequency in Hz
- Capacitance in Farads
- Voltage in Volts

## v0 simplifications

- No Fresnel model
- No detailed Wi-Fi MAC
- No packet-level model
- No AP unless the interface is easy to reserve
- No boost converter; output is V_CAP only