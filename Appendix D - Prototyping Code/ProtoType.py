import sys
# multiprocessing support
from multiprocessing import Process
# Scapy packet manipulation and construction library
from scapy.all import *
# OS level access methods, simpler version than subprocess
import os
#multiple threading support
from threading import Thread
import threading
#excrete terminal commands in linux
from subprocess import Popen
import time
from netaddr import *
# manuf library to lookup wireshark OUI MAC codes
import manuf
import math
# wifi module to access linux terminal based wireless tools from python seamlessly 
from wifi import Cell, Scheme
# Micro Database System
from tinydb import TinyDB, where
import logging
# Daemon IDS logging 
logging.basicConfig(filename='daedmonIDS.log',level=logging.DEBUG)

from subprocess import check_output
# Decimal to handle larger floating point numbers used by clock skew calculations
from decimal import *
from multiprocessing import Process, Value, Array, Manager
#add colour to standard output
from termcolor import colored
# accessing and converting hex and acsii values
from binascii import *
import binascii
# for capturing keyboard interrupt signals
import signal
#https://github.com/ivanlei/airodump-iv/blob/master/airoiv/scapy_ex.py
#import scapy_ex

# GUI library - Yet to be Implemented
#import wx
#from wx.lib.pubsub import pub


# Custom Module Imports
from iw_karma_detect import *
from clock_skew_main1 import *
from honey_pot import *
from custom_log_rouge import *
from accumulator import *
from test_channel_change import *
#manager = Manager()

import sys
# Add the Arudio Display folder path to the sys.path list
sys.path.append('/home/odroid/RougeDetection/Ardunio')
from show import *
# Code to Initiate the Arduino Display
'''
#if __name__ == '__main__':
#    t = Thread_Manager()
#    t.start()
#    #t.update_screen()
#    t.update_message("f","y")
#t.update_screen()
'''


# create an accumulator (points adder for Rouge AP)
accum = accumulator()
# Start a memory manager - in this case for shared memory between classes , objects and threads
manager = Manager()



'''
Class: Scanning

Methods:
channel_change: IEEE Channel Change
set_ch: mutator method to set channel
check_rm: flag accessors method (not used)
ch_hop: sets iface monitor mode and changes the channel on a call
checkTheSeq: verifies a sequence
oui: Verify manufactures Original Unique Code of MAC
stop_sniffing: was intended to help stop sniffing function manually (not working)
keep_sniffing: was intended to help stop sniffing function manually (not working)
sniffAP: Main IDS Code
sniffAP_daemon : Daemonizes Version of Main IDS Code ( will cause interface Conflicts in current state)


Constructor takes:
interface
count - no packets to sniff on this call
Channel
BSSID - mac of target access point
SSID - Network name of the target access point
Database - Copy of the white-list database
access point - list of detiaLs of the current access point under inspection, taken from white list DB
'''

class scanning:
    """Class for a user of the chat client."""
    def __init__(self, intf, count, channel,BSSID, SSID, accesspoint, database, Shared_Mem_Dictionary):
        self.intf = intf
        self.BSSID = BSSID
        self.SSID = SSID
        self.accesspoint = accesspoint
        self.seq1 = 0
        self.flag1 = 0
        self.counter = 0
        self.counter2 = 0
        # original channel of access point under inspection being set
        self.channel = accesspoint["channel"]
        self.count = count
        # not used
        self.accessPointsSQ = []
        # sequence numbers list for this access point
        self.seq_list = []
        # stores the timestamps sequences for this access point on this pass
        self.time_seq = []
        #speed up the check if a whitelisted access point being checked is off line
        self.appearanceCounter = 0
        self.database = database
        # defunct flag to remove an entry from database under certain circumstances
        self.flag_remove = 0
        #flag for stopping sniffing (not working)
        self.stop_sniff = False
        #custom log
        self.log = rougelog()
        self.Shared_Mem_Dictionary = Shared_Mem_Dictionary
        
        
        
    
    '''
    channel_change:
    Changes the IEEE channel frequency that the monitor mode interface is listening on
    uses the linux terminal commands  Ifconfig to turn the interface off and iw dev to put the
    interface into monitor mode. then bring the interface back up with ifconfig again... then
    a channel change can also be achieved by using the iw dev command.
    '''
    def channel_change(self, ssid, daemon = False):
        os.system("sudo ifconfig %s down" %  self.intf )
        os.system("sudo iw dev "+  self.intf + " set type monitor")
        os.system("sudo ifconfig %s up" %  self.intf )
        try:
            os.system("sudo iw dev %s set channel %d" % (self.intf, self.channel))
            if not daemon == True:
                print colored("+++++++++++++++++++++++++++++++++++++channel Change-----------------------------","yellow"), self.channel
                print colored("+++++++++++++++++++++++++++++++++++++","yellow"), ssid
        except Exception, err :
               print err 
    
    
    '''
    set_ch:
    mutator method to set the channel
    '''
    def set_ch(self, channel):
        self.channel = channel
    
    '''
    check_rm:
    check if remove flag is set
    (not used)
    '''
    def check_rm(self):
        return self.flag_remove
    
    
    '''
    ch_hop:
    doesn't hop channels itself
    but is called by code that requests different channels
    uses linux terminal commands through the python OS system call
    to change the channel of the monitor interface
    '''
    def ch_hop(self, channel, ssid, daemon = False):
           try:
               os.system("sudo ifconfig %s down" %  self.intf )
               os.system("sudo iw dev "+  self.intf + " set type monitor")
               os.system("sudo ifconfig %s up" %  self.intf ) 
               os.system("sudo iw dev %s set channel %d" % (self.intf, channel))
               if not daemon == True:
                print colored("-----------------------------channel Change-----------------------------","yellow"), channel
                print colored("-----------------------------SSID-----------------------------","yellow"), ssid
           except Exception, err :
               print err  

    '''
    checkTheSeq:
    checks a sample of sequence numbers extracted for an SSID
    if the numbers remain sequential then it returns True
    otherwise False
    '''
    def checkTheSeq(self, li):
        # splice the first index to get the initial value
        start=int(li[0])
        # then for the rest of the indexes
        for e in li[1:]:
            a=int(e)
            # if next value is greater, then copy that to start variable
            if a > start:
                start = a
            #attempt to catch if sequence resets
            #stop a false positive
            elif a == 0:
                start = a
            else:
                return False
        return True
    
    '''
    OUI:
    uses the manuf modules to check the 
    code of the
    BSSID against verified wireshark manufactures database
    '''
    def oui(self, frame):
        result = False
        p = manuf.MacParser()
        test = p.get_all(frame.lower())
        if test.manuf is not None:
            #print colored("Real Manufacture OUI Code", "yellow")
            result = True
        return result
    
    '''
    stop_sniffing:
    was to be used to stop sniffing on a pass earlier through
    keyboard interrupt (not working)
    '''
    def stop_sniffing(self, signal, frame):
        self.stop_sniff = True
        self.__del__()
        
    #def __del__(self):
    #    print 'died'
    
    '''
    keep_sniffing:
    same as above usage (not working)
    ''' 
    def keep_sniffing(self, pckt):
        return self.stop_sniff
       
       
    '''
    sniffAP:
    main sniffing code - main IDS code
    Scapy sniff function called first at bottom of function
    with interface, amount, timeout values cetera
    '''   
    def sniffAP(self):
        print "------------------Started-----------------------------------------------"
        def PacketHandler(frame):
          # caputre exceptions - especially accessing frame that do not have (.info) element
          try:    
            
            #essid = frame[Dot11Elt].info if '\x00' not in frame[Dot11Elt].info and frame[Dot11Elt].info != '' else 'Hidden SSID'
            #print colored("Hidden Test~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~","red"), essid
            
            
            #Test if the frame is IEEE 802.11 and a beacon management frame, and not the correct SSID for this pass check
            if frame.haslayer(Dot11) and frame.type == 0 and frame.subtype == 8 and not frame.info == self.accesspoint["ssid"]:
                self.appearanceCounter +=1
                if self.appearanceCounter > 15:
                    print "Appears to be offline on this Channel"
                    self.appearanceCounter = 0
                    #choice = str(raw_input("Remove Acccess Point y/n \n"))
                    #if choice == "y" or choice == "Y":                   
                    #    self.flag_remove = 1
                #stops the method
                    return
                return
            
            #Test if the frame is IEEE 802.11 and a beacon management frame and the correct SSID value
            elif frame.haslayer(Dot11) and frame.type == 0 and frame.subtype == 8 and frame.info == self.accesspoint["ssid"]:           
              self.appearanceCounter = 0
              
              '''
              formatting areas that scapy has not decoded.
              not using the scapy_ex class
              '''
              #try:
              #   extra = frame.notdecoded
              #except:
              #   extra = None
              #if extra!=None:
              #   #signal_strength = -(256-ord(extra[-4:-3]))
              #   #signal_strength = -(256-ord(extra[14:15]))
              #   signal_strength = frame.dBm_AntSignal
              #else:
              #   signal_strength = -100
              #   print "No signal strength found"              
              #### not much use as scanning the one channel
              #try:
              #    val = self.datab.search((where('ssid') == str(frame.info)))
              #    #print "$$$$$$$$$$$$$$$$$$$    VAL    $$$$$$$$$$$$$$$$$$$$$$$$$$$$$"
              #    #print val, frame.info
              #    ch = int(ord(frame[Dot11Elt:3].info))
              #    if not ch == val["channel"]:
              #        print "Channel Has changed"
              #except:
              #    pass
              #sig_str = -(256-ord(frame.notdecoded[-4:-3]))
              #print sig_str
              # overlapping channel causes bug where frame
              # is received by scapy on mon interface on overlapping channel and
              # then perceived to be a channel change
              
              
              #print frame.addr2
              
              
              # counter to limit printing to the standard output
              self.counter2 += 1 
              #channel = int( ord(frame[Dot11Elt:3].info))
              channel = 1
              try:
                channel = int( ord(frame[Dot11Elt:3].info))
              #print "channel", channel
                #print channel
              
                '''
                Checks if the channels has changed from the original white listed access point
                logs the change if noticed
                '''
                if not channel == self.accesspoint["channel"] :
                    #if self.counter2 == 25:
                    print colored("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!", "red")
                    print "Channel Has been Changed to another Frequency", "from", str(self.accesspoint["channel"]), "to " + str(channel)
                    #def channelChange(self, SSID, BSSID, Channel, level=2):
                    print colored("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!", "red") 
                    self.log.channelChange(self.accesspoint["ssid"],self.accesspoint["address"],str(self.accesspoint["channel"]) + " " +str(channel))
              except Exception:
                print "channel detection Exception"
                pass                 
              #get received signal strength
              #import scapy_ex
              import scapy_ex
              signal_strength = frame.dBm_AntSignal
              # unload module scapy_Ex otherwise mess with channel decoding on next loop
              del(scapy_ex)
            
               
              '''
              OUI:
              checks the OUI code of the MAC (BSSID) address to make
              sure that it is a valid manufacturers address
              log if this is not the case
              '''
              enc = None
              if self.flag1 == 0 and (channel == self.channel):
                  result = self.oui(frame.addr2)
                  if self.counter2 == 25:
                    print colored("*******************    OUI ", "blue"),result
                  self.flag1 = 1
                  if result == False:
                    if self.counter2 == 25:
                        print colored("Not a Manufactures OUI Code ", "red"),result
                    self.log.Invalid_OUI(frame.info,frame.addr2,frame.Channel)
                    
                  '''
                  Checks if encryption has been disabled on the whitelisted access point,
                  logs this if it is the case
                  '''
                  
                  ## directly from Airoscapy
                  capability = frame.sprintf("{Dot11Beacon:%Dot11Beacon.cap%}\
                  {Dot11ProbeResp:%Dot11ProbeResp.cap%}")
                  # Check for encrypted networks
                  if re.search("privacy", capability):
                      enc = True
                  else:
                      enc = False
                  if not self.accesspoint["encrypted"] == enc:
                      #if self.counter2 == 25:
                      print colored("the encryption has changed", "red")
                      #logger.error("the encryption has changed for " + frame.info)
                      self.log.general(str("Security Details changes to " + enc),frame.info,frame.addr2,frame.Channel, level=8)
                     
              '''
              Check and log if the BSSID address has changed
              '''
              
              # attempting to use self.channel which is current channel being scanned to stop
              # false positives generated by frames observed in overlapping
              # channels 
              if not self.accesspoint["address"].lower() == frame.addr2 and (frame.info == self.accesspoint["ssid"])  and (channel == self.channel):
                  if self.counter2 == 25:
                    print colored("BSSID Address has been changed", "red"), frame.info
                  self.log.general(str("BSSID Address has been changed from " + self.accesspoint["address"].lower()),frame.info,frame.addr2,frame.Channel, level=10)
                  if self.counter2 == 25:
                    print frame.info
                    print frame.addr2
                    print self.accesspoint["address"]
                    print self.accesspoint["address"].lower()
              
                                   
              '''
              Simple check for an Android software access point (they randomize MAC) and use AndroidAP as default SSID
              ''' 
              #Android randomizes mac
              if not self.accesspoint["address"].lower() == frame.addr2 and (frame.info =="AndroidAP")  and (channel == self.channel):
                  if self.counter2 == 25:
                    print colored("Android Software access Point Operating", "red")
                  self.log.general(str("Android Random Mac Change" + self.accesspoint["address"].lower()),frame.info,frame.addr2,frame.Channel, level=10)
                  if self.counter2 == 25:
                    print colored("OR crosstalk, or System that uses random MACS like Android","yellow"), frame.info
                  print frame.info
                  print frame.addr2
                  print self.accesspoint["address"]
                  print self.accesspoint["address"].lower()             
              
              self.counter2 = 0
              
              
              
              '''
              Grab sequence numbers and timestamps if SSID or BSSID are the same
              then check that group to verify if they are indeed sequential.
              if they are not then log this as a potential evil twin
              '''
              try:
                  if (frame.info == self.SSID or self.BSSID.lower() == frame.addr2) and (channel == self.channel):
                      try:
                          #print frame.SC
                          self.seq1 = frame.SC
                          self.seq_list.append(frame.SC)
                          self.time_seq.append(frame.timestamp)
                          self.counter += 1
                          if self.counter == 25:
                              print "RSSI for ", frame.info, signal_strength
                              
                              
                              print colored("++++++++++++++++++++++ 25 Sequence Numbers Collected", "yellow")
                              print colored("++++++++++++++++++++++ Analyzing +++++++++++++++++++++", "yellow")
                              val = self.checkTheSeq(self.seq_list)
                              print colored("++++++++++++++++++++++ Sequence","magenta"), val
                              if val == False:
                                  print colored("<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<< Sequence Numbers Irregular >>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>> ", "red")
                                  self.log.general(str("Sequence Numbers Irregular "),frame.info,frame.addr2,frame.Channel, level=10)
                              self.seq_list = []
                              
                              
                              if not self.BSSID.lower() == frame.addr2:
                                  print colored("<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<< Possible Evil Twin Address Change >>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>> ", "red")
                                  self.log.general(str(" Possible Evil Twin Address Change from " + self.BSSID.lower()),frame.info,frame.addr2,frame.Channel, level=9)
                              
                              
                              result_timestamp = self.checkTheSeq(self.time_seq)
                              if result_timestamp == False:
                                  print colored("$$$$$$$$$$$$$$$     Time stamp Sequence Change", "red")
                                  self.log.general(str(" Possible Evil Twin Time stamp Sequence Change " + self.BSSID.lower()),frame.info,frame.addr2,frame.Channel, level=9)
                                  
                                  
                              self.counter = 0
                              result = self.oui(frame.addr2)
                              print colored("******************** OUI ", "red"), result
                              if result == False:
                                  print colored("<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<< Possible Mac Spoof >>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>> ","red")
                                  
                          self.accessPointsSQ.append(frame.SC)
                      except  Exception,e:
                          print "error", e
              except:
                  pass
          except Exception, e:
                print e
                pass
        #signal.signal(signal.SIGINT, self.stop_sniffing)
        sniff(iface=self.intf, count = self.count, prn=PacketHandler, store=0,timeout = 10,lfilter = lambda x:(x.haslayer(Dot11Beacon)))# and x.info == self.accesspoint["ssid"])#, stop_filter=self.keep_sniffing )









    '''
    sniffAP_daemon:
    same as previous function but this time there are not printout to the standard out in the terminal.
    all is logged and run in non blocking daemon mode.
    at the moment this will cause issues as this daemon code would use the same interface as the
    the other features - causing conflicts.
    '''
    
    def sniffAP_daemon(self):
        def PacketHandler_d(frame):
          try:
            if frame.haslayer(Dot11) and frame.type == 0 and frame.subtype == 8 and not frame.info == self.accesspoint["ssid"]:
                self.appearanceCounter +=1
                if self.appearanceCounter > 15:
                    logging.info("Appears to be off line on this Channel")
                    self.appearanceCounter = 0
                    return
                return  
            if frame.haslayer(Dot11) and frame.type == 0 and frame.subtype == 8 and frame.info == self.accesspoint["ssid"]:           
              self.appearanceCounter = 0
  
              # overlapping channel causes bug where frame
              # is received by scapy on mon interface on overlapping channel and
              # then perceived to be a channel change
              channel    = int( ord(frame[Dot11Elt:3].info))
  
  
  
              if not channel == self.accesspoint["channel"] and frame.info == self.accesspoint["ssid"]:
                  logging.info("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
                  logging.info("Channel Has been Changed to another Frequency")
                  #def channelChange(self, SSID, BSSID, Channel, level=2):
                  self.log.channelChange(self.accesspoint["ssid"],self.accesspoint["address"],str(self.accesspoint["channel"] + " " + channel))
                  logging.info("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")                
              #signal_strength = frame.dBm_AntSignal
  
              enc = None
              if self.flag1 == 0:
                  result = self.oui(frame.addr2)
                  logging.info("*******************    OUI ")
                  self.flag1 = 1
                  if result == False:
                    logging.info("Not a Manufactures OUI Code ")
                    self.log.Invalid_OUI(frame.info,frame.addr2,frame.Channel) 
                  ## directly from Airoscapy
                  capability = frame.sprintf("{Dot11Beacon:%Dot11Beacon.cap%}\
                  {Dot11ProbeResp:%Dot11ProbeResp.cap%}")
                  # Check for encrypted networks
                  if re.search("privacy", capability):
                      enc = True
                  else:
                      enc = False
                  if not self.accesspoint["encrypted"] == enc:
                      logging.info("the encryption has changed")
                      #logger.error("the encrpytion has changed for " + frame.info)
                      self.log.general(str("Security Details changes to " + enc),frame.info,frame.addr2,channel, level=8)
                     
                      
              if not self.accesspoint["address"].lower() == frame.addr2 and( frame.info == self.accesspoint["ssid"]):
                  logging.info("BSSID Address has been changed")
                  self.log.general(str("BSSID Address has been changed from " + self.accesspoint["address"].lower()),frame.info,frame.addr2,frame.Channel, level=10)
                  logging.info(frame.info)
                  logging.info(frame.addr2)
                  logging.info(str(self.accesspoint["address"]))
                  logging.info(str(self.accesspoint["address"].lower()))
                  
              #Android randomizes mac
              if not self.accesspoint["address"].lower() == frame.addr2 and frame.info =="AndroidAP":
                  logging.info("Android Software access Point Operating")
                  self.log.general(str("Android Random Mac Change" + self.accesspoint["address"].lower()),frame.info,frame.addr2,frame.Channel, level=10)
                  logging.info("OR crosstalk, or System that uses random MACS like Android" + frame.info)
                  logging.info(frame.info)
                  logging.info(frame.addr2)
                  logging.info(self.accesspoint["address"])
                  logging.info(self.accesspoint["address"].lower())             
             
              try:
                  if frame.info == self.SSID or self.BSSID.lower() == frame.addr2 and (channel == self.accesspoint["channel"]):
                      try:
                          logging.info(frame.SC)
                          self.seq1 = frame.SC
                          self.seq_list.append(frame.SC)
                          self.time_seq.append(frame.timestamp)
                          self.counter += 1
                          if self.counter == 25:
                             # logging.info ("RSSI for " + str(frame.info) + " " + str(signal_strength))
                              logging.info("++++++++++++++++++++++ 25 Sequence Numbers Collected")
                              logging.info("++++++++++++++++++++++ Analyzing +++++++++++++++++++++")
                              val = self.checkTheSeq(self.seq_list)
                              logging.info("++++++++++++++++++++++ Sequence " + str(val))
                              if val == False:
                                  logging.info("<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<< Sequence Numbers Irregular >>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>> ")
                                  self.log.general(str("Sequence Numbers Irregular "),frame.info,frame.addr2,frame.Channel, level=10)
                              self.seq_list = []
                              
                              if not self.BSSID.lower() == frame.addr2:
                                  logging.info("<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<< Possible Evil Twin Address Change >>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>> ")
                                  self.log.general(str(" Possible Evil Twin Address Change from " + self.BSSID.lower()),frame.info,frame.addr2,frame.Channel, level=9)

                              result_timestamp = self.checkTheSeq(self.time_seq)
                              if result_timestamp == False:
                                  logging.info("$$$$$$$$$$$$$$$     Time stamp Sequence Change")
                                  self.log.general(str(" Possible Evil Twin Time-stamp Sequence Change " + self.BSSID.lower()),frame.info,frame.addr2,frame.Channel, level=9)
                                                                  
                              self.counter = 0
                              result = self.oui(frame.addr2)
                              logging.info("******************** OUI ")
                              if result == False:
                                  logging.info("<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<< Possible Mac Spoof >>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>")
                                  
                          self.accessPointsSQ.append(frame.SC)
                      except  Exception,e:
                          print "error", e
              except:
                  pass
          except Exception, e:
                print e
                pass
        #signal interrupt with keyboard (not working)
        #signal.signal(signal.SIGINT, self.stop_sniffing)
        '''
        main Scapy sniff function, interface, numbers pkts with count, the function handler to call, dont store in mem, timeout 10 seconds
        filter for int beacon frames
        '''
        sniff(iface=self.intf, count = self.count, prn=PacketHandler_d, store=0,timeout = 10,lfilter = lambda x:(x.haslayer(Dot11Beacon)))# and x.info == self.accesspoint["ssid"])#, stop_filter=self.keep_sniffing )
    

'''
Class Modes:

__init__: Constructor creating instances of dictionary for storage, a Tiny Database and a Log

get_db: accessors method to get database
KARMA_PROBE: Locate KARMA access points
airbaseNG_manual: Manually enter SSID and Channel of Access point to measure clock skew of
airbaseNG_secondAttempt: Attempt around the Airbase-NG bug where it broadcasts an empty SSID along with normal
airbaseNG: first attempt does tries to circumvent Airbase-NG bug, not reliably
white_listing: allows for scanning, entry, deletion of authored Access Points
chann_change: Allows the channel to be changes
managed: turn an interface to managed mode
purge_db: purge the database of all entries    
honey_pot: create a WIFI Honey-Pot
'''
class modes:
    """Class for a user of the chat client."""
    def __init__(self, Shared_Mem_Dictionary):
        self.karmaDetecetection = {}
        self.airbaseNG_Detection = {}
        self.db = TinyDB('db.json')
        self.log = rougelog()
        self.Shared_Mem_Dictionary = Shared_Mem_Dictionary
        #global manager
    #def start_ap(self, mon_iface, channel, essid, args):
    #    print " Starting the fake access point..."
    #    config = (
    #    'interface=%s\n'
    #    'driver=nl80211\n'
    #    'ssid=%s\n'
    #    'hw_mode=g\n'
    #    'channel=%s\n'
    #    'macaddr_acl=0\n'
    #    'ignore_broadcast_ssid=0\n'
    #     )
    #    with open('/tmp/hostapd.conf', 'w') as dhcpconf:
    #        dhcpconf.write(config % (mon_iface, essid, channel))
    #    from subprocess import Popen, PIPE, check_output
    #    DN = open(os.devnull, 'w')
    #    Popen(['hostapd', '/tmp/hostapd.conf'], stdout=DN, stderr=DN)
    #    try:
    #        time.sleep(6)  # Copied from Pwnstar which said it was necessary?
    #    except KeyboardInterrupt:
    #        cleanup(None, None)
    #        
    #        
    #def dhcp_conf(self, interface):
    # config = (
    #     # disables dnsmasq reading any other files like
    #     # /etc/resolv.conf for nameservers
    #     'no-resolv\n'
    #     # Interface to bind to
    #     'interface=%s\n'
    #     # Specify starting_range,end_range,lease_time
    #     'dhcp-range=%s\n'
    #     'address=/#/10.0.0.1'
    #    )    
    # with open('/tmp/dhcpd.conf', 'w') as dhcpconf:
    #         # subnet, range, router, dns
    #    dhcpconf.write(config % (interface, '10.0.0.2,10.0.0.100,12h'))
    # return '/tmp/dhcpd.conf'


    '''
    accessors for database
    '''
    def get_db(self):
        return self.db
    
    '''
    KARMA_PROBE:
    create instance of iw_karma_detect karmaid
    which creates random ESSID values assigning then to a local interface
    which when brought up, sends probe requests for these ESSID,
    A check is performed to see if an association is established with a KARMA enabled access point
    
    results are logged
    '''
    def KARMA_PROBE(self):
        k = karmaid()
        val = k.fakeSSID()
        
        if not val == False:
            #return {"count":self.count,"result":result,"BSSID":self.KARMAAP}
            self.log.detectedkarma(val["BSSID"],val["count"],val["result"],10)
            print "^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^"
            print "karma", val["count"], "detected"
            print "BSSID ", val["result"], "same"
            print "BSSID", val["BSSID"]
            print "^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^"
            AP =  AccessPoint(str("KARMA" + val["BSSID"][0]))
            AP.setBSSID = val["BSSID"][0]
            AP.setKARMA(val["count"], val["BSSID"][0])
            AP.setSSID("NA")
            self.Shared_Mem_Dictionary[AP.getID()]=AP
            
        else:
            print "^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^"
            print "karma not detected"           
            print "^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^"
    
    '''
    airbaseNG_manual:
    manual entry for target access point for clock skew calculation
    '''        
    def airbaseNG_manual(self):
        m_channnel = int(input("Enter Channel: "))
        print "-----------------------------------------"
        m_ssid = str(raw_input("Enter SSID: "))
        print "-----------------------------------------"
    
        chann_change(m_channnel)

        clock = ClockSkew(str(m_ssid))
        clock.overlordfuntion()
        value = clock.rmse_function()
        time.sleep(1)
        f = open('rmse.txt','r')
        val3 = f.read()
        f.close()
        
        #'print "value", value
        if Decimal(val3) > Decimal(299):     
           print colored("^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^", "red")
           print colored("Possible AIRBASE-NG Software Based Access Point","red")
           print colored("^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^", "red")
           self.log.detectedAIRBASE(m_ssid,m_channnel)
           import random
           AP =  AccessPoint(str("AIRBASE-NG" + str(m_ssid) + str(m_channnel)) + str(random.uniform(1, 10000)))
           AP.setBSSID = ""
           AP.setAirbaseNG()
           AP.setSSID(m_ssid)
           self.Shared_Mem_Dictionary[AP.getID()]=AP
           
        else:
          print "<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<"
          print colored("<<<<<<<<<<<<    Not AirBase-NG   <<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<", "yellow")
          print ""    
    
    '''
    airbaseNG_secondAttempt:
    Second attempt at circumventing the Airbase-NG error of sending both an SSID and Empty string SSID.
    target access point for clock skew calculation
    '''    
    
    def airbaseNG_secondAttempt(self):
       import subprocess 
       import re
       #switch to managed mode
       self.managed()
       #scan with iswlist linux OS command
       
       try:
            proc = subprocess.Popen('iwlist wlan4 scan', shell=True, stdout=subprocess.PIPE, ) 
            stdout_str = proc.communicate()[0] 
            stdout_list=stdout_str.split('\n') 
            essid=[] 
            address=[]
            channel=[]
            ## use regular expressions to attempt the get the SSID and other values
            for line in stdout_list: 
                 line=line.strip() 
                 match=re.search('ESSID:"(\S+)"',line) 
                 if match: 
                     essid.append(match.group(1)) 
                 match=re.search('Address: (\S+)',line) 
                 if match: 
                     address.append(match.group(1))
                     
                 match = re.search('Channel:([0-9]+)',line)
                 if match:
                     channel.append(match.group(1))
                     
            print essid 
            print address
            print channel
            
            '''
            print them out and offer a choice
            '''
            count = 0
            for s in essid:
                 print s , count 
                 count +=1
            
            c = int(input("Enter Choice: "))
            print "-----------------------------------------"
        
            '''
            Switch to the channel, and scan the specified SSID 
            '''
         
            chann_change(int(channel[c]))
            # create instance of the clock skew Class from clock_skew_main1.py
            clock = ClockSkew(str(essid[c]))
            clock.overlordfuntion()
            value = clock.rmse_function()
            time.sleep(1)
            ## could not return the RMSE Value from function call so just write to local file
            # and read back in from file here
            f = open('rmse.txt','r')
            val3 = f.read()
            f.close()
             
             # if the RMSE Value is over 299 then this is an indication that it is Airbase-NG access pointy
             # threshold taken from results of testing
            if Decimal(val3) > Decimal(299):     
                print colored("^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^", "red")
                print colored("Possible AIRBASE-NG Software Based Access Point","red")
                print colored("^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^", "red")
                self.log.detectedAIRBASE(str(essid[c]),channel[c])
                import random
                AP =  AccessPoint(str("AIRBASE-NG") + str(essid[c]) + str(channel[c]) +  str(address[c]) + str(random.uniform(1, 10000)))
                AP.setBSSID = address[c]
                AP.setAirbaseNG()
                AP.setSSID(essid[c])
                self.Shared_Mem_Dictionary[AP.getID()]=AP
                
            else:
               print "<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<"
               print colored("<<<<<<<<<<<<    Not AirBase-NG   <<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<", "yellow")
               print "" 
       except Exception, e:
            pass
       
    '''
    airbaseNG   --- first attempt:
    '''         
    def airbaseNG(self):
        self.managed()
        ce = Cell.all("wlan4")
        s = []
        count = 0
        
        
        try:
            proc = subprocess.Popen('iwlist wlan4 scan', shell=True, stdout=subprocess.PIPE, ) 
            stdout_str = proc.communicate()[0] 
            stdout_list=stdout_str.split('\n') 
            essid=[] 
            address=[]
            for line in stdout_list: 
                line=line.strip() 
                match=re.search('ESSID:"(\S+)"',line) 
                if match: 
                    essid.append(match.group(1)) 
                match=re.search('Address: (\S+)',line) 
                if match: 
                    address.append(match.group(1))                
            # temp fix
            pos = 0
            missing = ""
            place = 0
            for c in ce:
                if c.ssid == "":
                    if essid[pos] not in ce:
                        print colored("!!!!!!!!!Airbase-NG error Sending empty SSID simultaneously!!!!!!!!! SSID\n", "red")
                        print colored("!!!!!!!!!missing!!!!!!!!! SSID\n", "red"), essid[pos], "count ", pos , "\n"
                        print colored("!!!!!!!!!Substition for Null ssid may work\n", "yellow")
                        
                        ### attempts to account for the empty string SSID bug in Airbase-NG
                        ### does not always work very well 
                        missing = essid[pos]
                        place = pos
                        break
                pos += 1
            
            print essid
        except Exception:
            print "exception"
            pass
        #
        #for c in ce:
        #    count += 1    
        #    if flag_missing == True:
        #        if place +1 == count:
        #            print ":"+ str(count), " ssid:", essid[place+1]
        #        else:
        #            print ":"+ str(count), " ssid:", c.ssid
        #            #create dictionary with informnation on the accesss point
        #        SSIDS = {"no" : count ,"ssid": c.ssid, "channel":c.channel,"encrypted":c.encrypted, \
        #                    "frequency":c.frequency,"address":c.address, "signal":c.signal, "mode":c.mode}
        #            #append this dictionary to a list
        #        s.append(SSIDS)        
        #    else:
        #        print ":"+ str(count), " ssid:", c.ssid
        #            #create dictionary with informnation on the accesss point
        #        SSIDS = {"no" : count ,"ssid": c.ssid, "channel":c.channel,"encrypted":c.encrypted, \
        #                    "frequency":c.frequency,"address":c.address, "signal":c.signal, "mode":c.mode}
        #            #append this dictionary to a list
        #        s.append(SSIDS)
                
        for c in ce:
            count += 1    
            print ":"+ str(count), " ssid:", c.ssid
                #create dictionary with information on the access point
            SSIDS = {"no" : count ,"ssid": c.ssid, "channel":c.channel,"encrypted":c.encrypted, \
                        "frequency":c.frequency,"address":c.address, "signal":c.signal, "mode":c.mode}
                #append this dictionary to a list
            s.append(SSIDS)
                        
                
        input_var = int(input("Choose: "))
        print "-----------------------------------------"
        target = s[input_var - 1]
        
        
        
        chann_change(target["channel"])
        #targetSSID , ifaceno, switch, amount
        
        if target["ssid"] == "":
            clock = ClockSkew(missing)
        else:
            clock = ClockSkew(target["ssid"])
            
        clock.overlordfuntion()
        value = clock.rmse_function()
        time.sleep(1)
        f = open('rmse.txt','r')
        val3 = f.read()
        f.close()
        
        #'print "value", value
        if Decimal(val3) > Decimal(299):     
           print colored("^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^", "red")
           print colored("Possible AIRBASE-NG Software Based Access Point","red")
           print colored("^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^", "red")
           if target["ssid"] == "":
                self.log.detectedAIRBASE(missing,target["channel"])
           else:
                self.log.detectedAIRBASE(target["ssid"],target["channel"])
           import random
           AP =  AccessPoint(str("AIRBASE-NG") + str(target["ssid"]) + str(target["channel"]) + str(target["address"]))
           AP.setBSSID = target["address"]
           AP.setAirbaseNG()
           AP.setSSID(target["ssid"])
           self.Shared_Mem_Dictionary[AP.getID()]=AP
        else:
          print "<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<"
          print colored("<<<<<<<<<<<<    Not AirBase-NG   <<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<", "yellow")
          print ""    
    
    
    
    '''
    white_listing:
    
    Allows for the scanning, entry and deletion of Authorized access points
    from the database.
    '''
    

    def white_listing(self):
        # put interface into managed mode for scanning
        interface = "wlan4"
        os.system("sudo ifconfig %s down" %  interface)
        os.system("sudo iwconfig "+  interface + " mode managed")
        os.system("sudo ifconfig %s up" %  interface )
        cell = Cell.all(interface)
        #b = TinyDB('db.json')
        #db.purge()
        
        
        # give options
        print "1: Purge Database"
        print "2: Enter new"
        print "3: Delete"
        choice = int(raw_input("Please Choose :"))
        if choice == 1:
            self.db.purge()
        
        elif choice == 2:
            Auth_AP = {}
            S = []
            #have a counter for user choice input
            count = 0
            # for each scanned access point display its denials and store
            for c in cell:
                count += 1
                print ":"+ str(count), " ssid:", c.ssid, " BSSID:", c.address, " Channel:", c.channel
                    #create dictionary with information on the access point
                SSIDS = {"no" : count ,"ssid": c.ssid, "channel":c.channel,"encrypted":c.encrypted, \
                            "frequency":c.frequency,"address":c.address, "signal":c.signal, "mode":c.mode}
                    #append this dictionary to a list
                S.append(SSIDS)
            ## get choice from the user
            input_var = int(input("Choose: "))
            print "---------------------------------------------"
            ap = S[input_var - 1]
            print ap["ssid"] 
            print ap["address"]
            print ap["encrypted"]
            print ap["channel"]
            print "---------------------------------------------"
            
            loop = True
            while loop:
                try:
                    # choice to store or disregard
                    input_var = int(input("1: Store Valid AP \n2: Disregard and Continue\n:"))     
                    if input_var > 0 and input_var <= 2:
                        loop = False
                except ValueError:
                    pass
            
            if input_var == 1:
                #db.purge()
                ## check if the entry already exists in the database
                if self.db.search((where('ssid') == ap["ssid"]) & (where('address') == str(ap["address"]))) == []:
                    self.db.insert(ap)
                else:
                    print colored("!!!!!!!!!! already Stored in the database", "red")
                #print all database
                print self.db.all()
        
        # display all entries and give choice for deletion
        elif choice == 3:
                c = {}
                count = 1
                for ap in self.db.all():
                    try:
                        print count, ap["ssid"] , " ", ap["address"], " ", ap["channel"]
                        c[count] = ap["ssid"]
                        count +=1
                    except KeyboardInterrupt, err:
                        print(traceback.format_exc())
                        print "interrupted"
                        
                choice = int(raw_input("Delete Number? or 0 to exit :"))
                if choice == 0:
                    pass
                else:
                    try:
                        #self.db.update(remove('ssid'), where('ssid') == str(c[choice]))
                        
                        # delete the choice
                         self.db.remove(where('ssid') == str(c[choice]))
                         print "Deletion of " +  str(c[choice]) + " Successful"
                    except Exception, e:
                        print e
                        print "Deletion Error!!!!!!!!!!!"
                        pass
            
    
    
    '''
    allows changing of the monitor channel
    '''
    def chann_change(self, channel, daemon = False):
        os.system("sudo ifconfig %s down" % "wlan4" )
        os.system("sudo iw dev "+ "wlan4" + " set type monitor")
        os.system("sudo ifconfig %s up" %  "wlan4")
        try:
            os.system("sudo iw dev %s set channel %d" % ("wlan4", channel))
            if not daemon == True:
                print "channel Change", channel
                print ""
        except Exception, err :
               print err
             
    '''
    allows to put interface into managed mode for scanning
    '''
    def managed(self):
        os.system("sudo ifconfig %s down" % "wlan4" )
        os.system("sudo iw dev "+ "wlan4" + " set type managed")
        os.system("sudo ifconfig %s up" %  "wlan4")
        
    
    '''
    Purge the database
    '''
    def purge_db(self):
        self.db.purge()
        return True
    
    '''
    Start a WIFI Honey-pot
    '''
    def honey_pot(self, h):
        honey = h
        print "::options:"
        print "1:Start HoneyPot"
        print "2:Stop HoneyPot"
        print "3:Nmap Scan" #Not even close to being useful yet
        
        
        choice = int(raw_input(":>"))
        
        if choice > 1 and choice < 4:
            if choice == 1:
                h.start_honey()
            if choice == 2:
                h.stop_honey()
            if choice == 3:
                h.leases()
        else:
            print "Invalid Selection!!!!!"
        

 
 
from subprocess import *

'''
Main:

Gives options to start or stop different services and modes

'''
def main(acc):
    # Create a Shared Memory manager to share object between threads
    # access them as global variables with global scope
    global accum
    global manager
    # create the Dictionary from the manager
    Shared_Mem_Dictionary = manager.dict()
    # pass both to the modes instance
    m = modes(Shared_Mem_Dictionary)
    # Then pass both to the accumulator (Alert System)
    accum.setSMem(Shared_Mem_Dictionary, manager)
    
    # Start the accumulator Daemon if enabled via the command line
    # causes issues randomly 
    if acc == True:
        accum.start()
    
    loop = True
    while loop:
        try:
            
            
            input_var = int(input(colored("1: Scan for Karma Access Points \n2:> Scan a target to determine Airbase-NG \n3:> Manually Scan a target to determine Airbase-NG  \n4:> Try other attempt Airbase-NG  \n5: Enter Whitelist AP \n6: Start Wireless IDS \n7: HoneyPot \n8: System Exit \n:>", "yellow")))
            if input_var < 0 and input_var >8:
                pass
            elif input_var == 1:
                result = m.KARMA_PROBE()
            elif input_var == 2:
                val = m.airbaseNG()
            elif input_var == 3:
                val = m.airbaseNG_manual()
            elif input_var == 4:
                val = m.airbaseNG_secondAttempt()             
            elif input_var == 5:
                m.white_listing()
                
                
            elif input_var == 6:
                i = int(input(colored("1: Blocking IDS Mode \n2: Daemon Mode \n3: Disable CH Hopping")))
                db = m.get_db()
                if i == 1:
                    Rouge_IDS = Rouge_IDS_Background(db, False, Shared_Mem_Dictionary,False)  
                elif i == 2:
                    Rouge_IDS = Rouge_IDS_Background(db, True, Shared_Mem_Dictionary,False)
                elif i == 3:
                    Rouge_IDS = Rouge_IDS_Background(db, False, Shared_Mem_Dictionary, True)   
                Rouge_IDS.start()    
                #subprocess.Popen([sys.executable, Rouge_IDS.start], shell = True)
                
            elif input_var == 7:
                h = honey()
                m.honey_pot(h)
            elif input_var == 8:
                sys.exit(0)
                
                
        except SyntaxError, s:
            print s
    

'''
Rouge_IDS_Background:

Main IDS mode which allows for a Daemon Mode and standard output mode
Daemon mode will currently interfere with other mode as they use the same interface.

loop through all entries in the database, and start a sniffing scan for that SSID on its original channel
and on 3 other channels per loop

Currently cannot be stopped appropriately and safely 
'''
class Rouge_IDS_Background(threading.Thread):
    def __init__(self, db , daemon, Shared_Mem_Dictionary, CHop):
        threading.Thread.__init__(self)
        self.daemon = daemon
        self.db = db
        self.Shared_Mem_Dictionary = Shared_Mem_Dictionary
        self.CHop = CHop
        
    def run(self):
        loop = True
        while loop:
            flag = 1
            for ap in self.db.all():
                    try:
                        if not self.daemon == True:
                            print colored("^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^", 'red')
                            print "$$$$$$$$$$$$$$$$$$$$$$$   Now Scanning -----> " , ap["ssid"]
                            print colored("^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^", 'red')
                        s = scanning(intf="wlan4", count = 100, channel=ap["channel"], BSSID=ap["address"],SSID=ap["ssid"], accesspoint=ap, database=self.db, Shared_Mem_Dictionary=self.Shared_Mem_Dictionary)
                       
                       
                        if flag == 1 and not self.CHop == True:
                            for i in xrange(1, 3):
                                ch = random.randrange(1,11)
                                s.set_ch(ch)
                                if self.daemon == True:
                                    s.ch_hop(ch, ap["ssid"], daemon = True)
                                else:
                                    s.ch_hop(ch, ap["ssid"])
                                if self.daemon == True:
                                    s.sniffAP_daemon()
                                else:
                                    s.sniffAP()
                                if i == 2:
                                    flag = 0
                        
                        if  self.CHop == True:
                            flag = 0
                         
                        if flag == 0:
                            s.set_ch(ap["channel"])
                            if self.daemon == True:
                                s.channel_change(ap["ssid"], daemon = True)
                            else:
                                s.channel_change(ap["ssid"])
                                   
                        
                        
                        flag = 1
                        if self.daemon == True:
                            s.sniffAP_daemon()
                        else:
                            s.sniffAP()
                        
                        
                        #if s.check_rm() == 1:
                        #    self.db.remove(where("ssid") == ap["ssid"])
                          
                    except KeyboardInterrupt, err:
                        print(traceback.format_exc())
                        print "interrupted"                                         
            #loop = False         




# If called as script then it calls the Main() function
if __name__ == '__main__':
    from tinydb import TinyDB, where
    
    
    ## take a command from the CLI to enable or Disable the (accumulator)(Alert System)
    if len(sys.argv) != 2:
        print "%s - [1 for accumulator] [0 for disable] " % sys.argv[0]
        sys.exit(1)
    
    
    #pass it to main
    acc = False  
    if int(sys.argv[1]) == 1:
        acc = True
    main(acc)




