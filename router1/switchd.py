#!/usr/bin/python3

# Copyright (C) 2022 strangebit

# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.

# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

__author__ = "Dmitriy Kuptsov"
__copyright__ = "Copyright 2022, stangebit"
__license__ = "GPL"
__version__ = "0.0.1b"
__maintainer__ = "Dmitriy Kuptsov"
__email__ = "dmitriy.kuptsov@gmail.com"
__status__ = "development"

# Import the needed libraries
# Stacktrace
import traceback
# Sockets
import socket
# Threading
import threading
# Logging
import logging
# Timing
import time
# Math functions
from math import ceil, floor
# System
import sys
# Exit handler
import atexit
# Timing 
from time import sleep

# Hex
from binascii import hexlify

# Import HIP library
from hiplib import hlib

from hiplib.hlib import HIPLib

# HIP related packets
from hiplib.packets import HIP
# IPSec packets
from hiplib.packets import IPSec
# IPv6 packets
from hiplib.packets import IPv6
# IPv4 packets 
from hiplib.packets import IPv4
# Ethernet frame
from hiplib.packets import Ethernet
# Configuration
from hiplib.config import config as hip_config
# Import switch FIB
from switchfabric import FIB

# Copy routines
import copy

# Configure logging to console and file
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("hipls.log")#,
#        logging.StreamHandler(sys.stdout)
    ]
);

# HIP configuration 
hiplib = HIPLib(hip_config.config);

hip_socket = socket.socket(socket.AF_INET, socket.SOCK_RAW, HIP.HIP_PROTOCOL);
hip_socket.bind(("0.0.0.0", HIP.HIP_PROTOCOL));
# We will need to perform manual fragmentation
hip_socket.setsockopt(socket.IPPROTO_IP, socket.IP_HDRINCL, 1);
logging.info("Initializing IPSec socket");
ip_sec_socket = socket.socket(socket.AF_INET, socket.SOCK_RAW, IPSec.IPSEC_PROTOCOL);
ip_sec_socket.bind(("0.0.0.0", IPSec.IPSEC_PROTOCOL));
#ip_sec_socket.bind((hip_config.config["swtich"]["source_ip"], IPSec.IPSEC_PROTOCOL))

# We will need to perform manual fragmentation
ip_sec_socket.setsockopt(socket.IPPROTO_IP, socket.IP_HDRINCL, 1);
# Open raw ethernet socket and bind it to the interface
ETH_P_ALL = 3
ether_socket = socket.socket(socket.AF_PACKET, socket.SOCK_RAW, socket.htons(ETH_P_ALL));
ether_socket.bind((hip_config.config["swtich"]["l2interface"], 0))

# Initialize FIB
fib = FIB(hip_config.config["swtich"]["mesh"])

def onclose():
    packets = hiplib.exit_handler()
    for (packet, dest) in packets:
        hip_socket.sendto(packet, dest)

def hip_loop():
    while True:
        try:
            logging.debug("Got HIP packet on the interface")
            packet = bytearray(hip_socket.recv(1524))
            packets = hiplib.process_hip_packet(packet);
            for (packet, dest) in packets:
                hip_socket.sendto(packet, dest)
        except Exception as e:
            logging.debug("Exception occured while processing HIP packet")
            logging.debug(e)

def ip_sec_loop():
    while True:
        try:
            packet = bytearray(ip_sec_socket.recv(1524));
            (frame, src, dst) = hiplib.process_ip_sec_packet(packet)
            if not frame:
                continue;
            ether_socket.send(frame);
            frame = Ethernet.EthernetFrame(frame);
            fib.set_next_hop(frame.get_source(), src, dst);
        except Exception as e:
            logging.critical(e)

def ether_loop():
    while True:
        try:
            buf = bytearray(ether_socket.recv(1514));
            logging.debug("Got data on Ethernet link...")
            frame = Ethernet.EthernetFrame(buf);
            dst_mac = frame.get_destination();
            #src_mac = frame.get_source();
            mesh = fib.get_next_hop(dst_mac);
            for (ihit, rhit) in mesh:
                packets = hiplib.process_l2_frame(frame, ihit, rhit, hip_config.config["swtich"]["source_ip"]);
                for (hip, packet, dest) in packets:
                    logging.debug("Sending L2 frame to: %s %s" % (ihit, rhit))
                    if not hip:
                        """
                        #+------------------------------------------------------------------+
                        #|IP Header fields modified on sending when IP_HDRINCL is specified |
                        #+------------------------------------------------------------------+
                        #|  Sending fragments with IP_HDRINCL is not supported currently.   |
                        #+--------------------------+---------------------------------------+
                        #|IP Checksum               |Always filled in.                      |
                        #+--------------------------+---------------------------------------+
                        #|Source Address            |Filled in when zero.                   |
                        #+--------------------------+---------------------------------------+
                        #|Packet Id                 |Filled in when passed as 0.            |
                        #+--------------------------+---------------------------------------+
                        #|Total Length              |Always filled in.                      |
                        #+--------------------------+---------------------------------------+
                        #Fragmentation does not work on RAW sockets

                        packet = IPv4.IPv4Packet(packet)
                        buf = copy.deepcopy(packet.get_payload())
                        total_length = len(buf);
                        fragment_len = 100;
                        num_of_fragments = int(ceil(total_length / fragment_len))
                        offset = 0;
                        for i in range(0, num_of_fragments):
                            # Create IPv4 packet
                            ipv4_packet = IPv4.IPv4Packet();
                            ipv4_packet.set_version(IPv4.IPV4_VERSION);
                            ipv4_packet.set_destination_address(packet.get_destination_address());
                            ipv4_packet.set_source_address(packet.get_source_address());
                            ipv4_packet.set_ttl(IPv4.IPV4_DEFAULT_TTL);
                            ipv4_packet.set_protocol(HIP.HIP_PROTOCOL);
                            ipv4_packet.set_ihl(IPv4.IPV4_IHL_NO_OPTIONS);
                        
                            # Fragment the packet
                            ipv4_packet.set_fragment_offset(offset);
                            if num_of_fragments > 1 and num_of_fragments - 1 != i:
                                # Set flag more fragments to follow
                                ipv4_packet.set_flags(0x4)
                                ipv4_packet.set_payload(buf[offset:offset + fragment_len]);
                                offset += fragment_len;
                            else:
                                if num_of_fragments > 1:
                                    ipv4_packet.set_payload(buf[offset:offset + fragment_len]);
                                else:
                                    ipv4_packet.set_payload(buf);
                            logging.debug("Sending IPv4 fragment of size %s" % (len(ipv4_packet.get_buffer())))
                            logging.debug(ipv4_packet);
                            ip_sec_socket.sendto(bytearray(ipv4_packet.get_buffer()), dest)
                            """
                        ip_sec_socket.sendto(packet, dest)
                    else:
                        hip_socket.sendto(packet, dest)
        except Exception as e:
           logging.debug("Exception occured while processing L2 frame")
           logging.debug(e)


# Register exit handler
atexit.register(onclose);

hip_th_loop = threading.Thread(target = hip_loop, args = (), daemon = True);
ip_sec_th_loop = threading.Thread(target = ip_sec_loop, args = (), daemon = True);
ether_if_th_loop = threading.Thread(target = ether_loop, args = (), daemon = True);

logging.info("Starting the CuteHIP");

hip_th_loop.start();
ip_sec_th_loop.start();
ether_if_th_loop.start();

def run_swtich():
    while True:
        packets = hiplib.maintenance();
        for (packet, dest) in packets:
            hip_socket.sendto(packet, dest)
        logging.debug("...Periodic cleaning task...")
        sleep(1);

run_swtich()
