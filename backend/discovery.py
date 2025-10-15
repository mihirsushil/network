
from operator import ipow
from tabnanny import verbose
import scapy.all as scapy 
import re 
from scapy.layers.l2 import getmacbyip
from mac_vendor_lookup import MacLookup

# makes sure the user writes the ip address correctly
pattern = r'^((25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)(/(3[0-2]|[12]?[0-9]))?$'



def get_devices(ip_address): # function when its called in app.py 
    if not re.match(pattern, ip_address): 
        print(f'{ip_address} is not valid, type another one ')
        return []

    else:
        print(f'{ip_address} is valid')
    
    devices = [] # list of devices that will appear when scapy scans the network 

    ans, dead = scapy.arping(ip_address,verbose = False) # scapy sends the ARP request to devices in the ip address and ans just collects the ones that respond. verbose= False just declutters the terminal 
    for sent, received in ans: # since ans is a tuple it just loops through the two info 
        ip = received.psrc # extracts the ip address from the ARP reply 
        mac = getmacbyip(ip) # changes it from ip address to mac address 
        # if mac address wasn't found it marks it as "Unavailable" and then look at vendor based on mac if that fails set that as "Unknown"
        if mac is None:
            mac = 'Unavailable'
            try:
                vendor = MacLookup().lookup(mac)
            except:
                vendor = "Unknown"
            devices.append({
                'ip':ip,
                'mac':mac,
                'vendor':vendor
                })
    if not devices:
        print("No devices found: fake devices: ")
        devices = [
        {'ip': '192.168.40.10', 'mac': 'AA:BB:CC:DD:EE:FF', 'vendor': 'MockPhone'},
        {'ip': '192.168.40.15', 'mac': '11:22:33:44:55:66', 'vendor': 'MockLaptop'}
    ]

        
    return devices 

