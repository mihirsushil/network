
import scapy.all as scapy 
import re 
from scapy.layers.l2 import getmacbyip
from mac_vendor_lookup import MacLookup

# makes sure the user writes the ip address correctly
pattern = r'^((25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)(/(3[0-2]|[12]?[0-9]))?$'

ip_address = input('Give an ip address: ')

def get_devices(): # function when its called in app 
    if re.match(pattern, ip_address): 
        print(f'{ip_address} is valid ')
      
    else:
        print(f'{ip_address} is not valid, type another one ')
    ans, dead = scapy.arping(ip_address) 
    for sent, received in ans: 
        ip = received.psrc
        mac = getmacbyip(ip)
        if mac is None:
            mac = 'Unavailable'
            try:
                vendor = MacLookup().lookup(mac)
            except:
                vendor = "Unknown"
            print(f'{ip:<18}{mac:<20}{vendor}')
get_devices()

