from scapy.all import sniff 

def get_activity(): # when called in app ; function runs 
   
    packets = sniff(count=100) # caputures 100 packets that are being sent or recieved per scan 
    total = len(packets) # checks how many packets were actually captured 
    tcp = len([p for p in packets if p.haslayer("TCP")]) # number of packets that were TCP
    udp = len([p for p in packets if p.haslayer("UDP")]) # number of packets that were UDP
    icmp = len([p for p in packets if p.haslayer("ICMP")]) # number of packets that were icmp
    return{
        "total_packets": total,
        "TCP": tcp,
        "UDP": udp,
        "ICMP": icmp
    }