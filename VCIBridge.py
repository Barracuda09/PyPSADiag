"""
   VCIBridge.py

   32-bit Python subprocess bridge for Evolution XS VCI DLL access
   This module runs in a separate 32-bit Python process to access the VCIAccess.dll

   Copyright (C) 2025 Marc Postema (mpostema09 -at- gmail.com)

   This program is free software; you can redistribute it and/or
   modify it under the terms of the GNU General Public License
   as published by the Free Software Foundation; either version 2
   of the License, or (at your option) any later version.
"""

import sys
import json
import ctypes
import time
import re
from datetime import datetime

class VCIBridge:
    """
    32-bit bridge to access Evolution XS VCI DLL
    Communicates via stdin/stdout JSON messages
    """
    
    def __init__(self):
        self.vci = None
        self.connected = False
        self.currEcuDesc = None
        self.active_protocol = None
        self.MSG_BUFFER = 2048
        self.writeReadTimeout = 1000
        
        # Protocol constants
        self.KWP2000_PSA = 1
        self.PSA2 = 2
        self.DIAG_ON_CAN = 3
        self.KWP2000_FIAT = 6
        self.KWP_ON_CAN_FIAT = 7
        self.UDS_PSA = 11
        
        # COM line constants
        self.LINE_CAN_DIAG = 17
        self.LINE_CAN_IS = 18
        self.LINE_CAN_PSA2000 = 0
        self.LINE_CAN_FIAT_LS6 = 47
        self.LINE_CAN_FIAT_LS3 = 48
        
        # Protocol descriptors
        self.pd_DIAG_ON_CAN = "03 10 E8"
        self.pd_KWP_ON_CAN_FIAT = "07"
        self.pd_KWP2000PSA = "01 00"
        self.pd_UDS_PSA = "0B"
        
        try:
            self.vci = ctypes.CDLL("C:\\AWRoot\\drv\\VCIAccess.dll")
            self.log("VCI DLL loaded successfully")
        except Exception as e:
            self.log(f"Failed to load VCI DLL: {e}")
            self.vci = None
    
    def log(self, message):
        """Send log message to parent process"""
        self.send_response("log", {"message": f"[VCI-32] {message}"})
    
    def send_response(self, command, data):
        """Send JSON response to parent process"""
        response = {
            "command": command,
            "timestamp": datetime.now().isoformat(),
            "data": data
        }
        print(json.dumps(response), flush=True)
    
    def statusToStr(self, code):
        """Convert VCI status code to string"""
        status_codes = {
            0: "OPERATION SUCCEEDED",
            1: "OPERATION SUCCEEDED (ALT)",
            -1: "HARDWARE ERROR",
            -2: "SOFTWARE ERROR", 
            -3: "MISSING DRIVER RESOURCE",
            -4: "CABLE IS UNPLUGGED",
            -5: "NO RESPONSE FROM ECU",
            -6: "INVALID COMMUNICATION LINE",
            -7: "INVALID PROTOCOL DESCRIPTOR",
            -8: "INVALID ECU DESCRIPTOR",
            -9: "INVALID FUNCTION ORDER",
            -10: "RESPONSE BUFFER OVERFLOW",
            -11: "COMMUNICATION TIMEOUT",
            -12: "VCI BUSY",
            -13: "INVALID PARAMETER",
            -14: "INITIALIZATION FAILED",
            -15: "PROTOCOL NOT SUPPORTED"
        }
        return status_codes.get(code, f"UNKNOWN ERROR {code}")
    
    def bytesEncode(self, pd, divisor=" "):
        """Convert string format to descriptor"""
        if divisor is None:
            byt = re.findall('.{1,2}', pd)
        else:
            byt = pd.split(" ")
        out = []
        for by in byt:
            out.append(int(by, 16))
        return ctypes.create_string_buffer(bytes(out), len(out)), len(out)
    
    def connect(self):
        """Connect to VCI"""
        if self.vci is None:
            return False
            
        try:
            vciOpenSession = self.vci["_openSession"]
            vciOpenSession.restype = ctypes.c_int
            result = vciOpenSession()
            
            if result == 0 or result == 1:
                self.log("Connected to Evolution XS VCI successfully")
                self.connected = True
                
                # Get version info - this returns the actual version number, not a status code
                vciGetVersion = self.vci["_getVersion"]
                vciGetVersion.restype = ctypes.c_int
                version = vciGetVersion()
                if version > 0:
                    # Convert version number to readable format (e.g. 322 might be v3.22)
                    major = version // 100
                    minor = version % 100
                    self.log(f"VCI API Version: {major}.{minor:02d}")
                else:
                    self.log(f"VCI API Version: Unknown ({version})")
                
                # Get firmware version
                vciGetFirmwareVersion = self.vci["_getFirmwareVersion"]
                vciGetFirmwareVersion.restype = ctypes.c_int
                vciGetFirmwareVersion.argtypes = [ctypes.c_char_p, ctypes.c_int]
                outputBuffer = ctypes.create_string_buffer(40)
                fw_result = vciGetFirmwareVersion(outputBuffer, ctypes.c_int(len(outputBuffer)))
                
                if fw_result > 0:
                    fw_version = ""
                    for i in range(0, fw_result):
                        fw_version += chr(outputBuffer.raw[i])
                    self.log(f"VCI Firmware Version: {fw_version}")
                else:
                    self.log("VCI Firmware Version not available")
                
                return True
            else:
                self.log(f"VCI connection failed: {self.statusToStr(result)}")
                return False
                
        except Exception as e:
            self.log(f"VCI connection error: {e}")
            return False
    
    def disconnect(self):
        """Disconnect from VCI"""
        if self.connected and self.vci:
            try:
                vciCloseSession = self.vci["_closeSession"]
                vciCloseSession.restype = ctypes.c_int
                result = vciCloseSession()
                self.connected = False
                
                if result >= 0:
                    self.log("VCI disconnected")
                    return True
                else:
                    self.log(f"VCI disconnect error: {self.statusToStr(result)}")
                    return False
            except Exception as e:
                self.log(f"VCI disconnect exception: {e}")
                return False
        return True
    
    def configure(self, tx_h="752", rx_h="652", bus="DIAG", protocol="DIAGONCAN", target=None, dialog_type="0"):
        """Configure VCI for specific ECU communication"""
        if not self.connected:
            if not self.connect():
                return False
        
        try:
            # Handle numeric bus codes
            if bus == "0":
                bus = "IS"
                protocol = "DIAGONCAN"
            elif bus == "1":
                bus = "DIAG" 
                protocol = "DIAGONCAN"
            elif bus == "2":
                bus = "DIAG"
                protocol = "KWPONCAN_FIAT"
            elif bus == "3":
                bus = "IS"
                protocol = "KWPONCAN_FIAT"
            elif bus == "4":
                bus = "IS"
                protocol = "PSA2000"
            
            self.log(f"Configuring VCI: {tx_h}:{rx_h} {bus}, {protocol}, target={target}, dialog={dialog_type}")
            
            if protocol == "DIAGONCAN":
                if bus == "DIAG":
                    self.log("Using CAN DIAG connection (pins 3/8)")
                    self.currEcuDesc = self.ecuToEcuDescriptor(tx_h, rx_h, protocol=self.DIAG_ON_CAN)
                    if not (self._changeComLine(self.LINE_CAN_DIAG) and self._bindProtocol(self.DIAG_ON_CAN)):
                        return False
                elif bus == "IS":
                    self.log("Using CAN I/S connection (pins 6/14)")
                    self.currEcuDesc = self.ecuToEcuDescriptor(tx_h, rx_h, protocol=self.DIAG_ON_CAN)
                    if not (self._changeComLine(self.LINE_CAN_IS) and self._bindProtocol(self.DIAG_ON_CAN)):
                        return False
                else:
                    self.log(f"Unknown bus for DIAGONCAN: {bus}")
                    return False
                    
            elif protocol == "KWPONCAN_FIAT":
                if bus == "DIAG":
                    self.log("Using FIAT BCAN connection on LS6/14")
                    self.currEcuDesc = self.ecuToEcuDescriptor(tx_h, rx_h, protocol=self.KWP_ON_CAN_FIAT, kwp_id=target, dialog_type=dialog_type)
                    if not (self._changeComLine(self.LINE_CAN_FIAT_LS6) and self._bindProtocol(self.KWP_ON_CAN_FIAT)):
                        return False
                elif bus == "IS":
                    self.log("Using FIAT BCAN connection on LS3/8") 
                    self.currEcuDesc = self.ecuToEcuDescriptor(tx_h, rx_h, protocol=self.KWP_ON_CAN_FIAT, kwp_id=target, dialog_type=dialog_type)
                    if not (self._changeComLine(self.LINE_CAN_FIAT_LS3) and self._bindProtocol(self.KWP_ON_CAN_FIAT)):
                        return False
                else:
                    self.log(f"Unknown bus for KWPONCAN_FIAT: {bus}")
                    return False
                    
            elif protocol == "PSA2000":
                self.log("Using PSA2000 K-Line protocol")
                if target is None:
                    target = 0x0D
                try:
                    target_int = int(target, 16) if isinstance(target, str) else int(target)
                    dialog_int = int(dialog_type)
                except ValueError:
                    self.log(f"Invalid target code or dialog_type: {target} / {dialog_type}")
                    return False
                    
                self.currEcuDesc = self.ecuToEcuDescriptor(protocol=self.KWP2000_PSA, kwp_id=hex(target_int)[2:].upper().zfill(2))
                if not (self._changeComLine(dialog_int) and self._bindProtocol(self.KWP2000_PSA)):
                    return False
                    
                # PSA2000 requires initialization
                if not self.perform_init():
                    self.log("PSA2000 initialization failed")
                    return False
                    
            else:
                self.log(f"Unsupported protocol: {protocol}")
                return False
            
            self.active_protocol = protocol
            self.log(f"VCI configured successfully for {protocol} on {bus}")
            return True
            
        except Exception as e:
            self.log(f"VCI configure error: {e}")
            return False
    
    def _changeComLine(self, num_line):
        """Change VCI communication line"""
        try:
            vciChangeComLine = self.vci["_changeComLine"]
            vciChangeComLine.restype = ctypes.c_int
            vciChangeComLine.argtypes = [ctypes.c_int]
            result = vciChangeComLine(num_line)
            
            self.log(f"ChangeComLine({num_line}): {self.statusToStr(result)}")
            return result >= 0
        except Exception as e:
            self.log(f"ChangeComLine error: {e}")
            return False
    
    def _bindProtocol(self, protocol):
        """Bind VCI to specific protocol"""
        try:
            protocolDescriptor, pDlen = self.protocolToProtocolDescriptor(protocol)
            vciBindProtocol = self.vci["_bindProtocol"]
            vciBindProtocol.restype = ctypes.c_int
            vciBindProtocol.argtypes = [ctypes.c_char_p, ctypes.c_int]
            result = vciBindProtocol(protocolDescriptor, pDlen)
            
            self.log(f"BindProtocol: {self.statusToStr(result)}")
            return result >= 0
        except Exception as e:
            self.log(f"BindProtocol error: {e}")
            return False
    
    def protocolToProtocolDescriptor(self, protocol=None):
        """Get protocol descriptor for protocol"""
        if protocol == self.DIAG_ON_CAN or protocol is None:
            return self.bytesEncode(self.pd_DIAG_ON_CAN)
        elif protocol == self.KWP_ON_CAN_FIAT:
            return self.bytesEncode(self.pd_KWP_ON_CAN_FIAT)
        elif protocol == self.KWP2000_PSA:
            return self.bytesEncode(self.pd_KWP2000PSA)
        else:
            self.log(f"Protocol {protocol} not implemented")
            return None, 0
    
    def ecuToEcuDescriptor(self, tx_h=None, rx_h=None, protocol=3, kwp_id=None, dialog_type="0"):
        """Create ECU descriptor from headers and protocol"""
        try:
            if protocol == self.DIAG_ON_CAN:
                if tx_h and rx_h:
                    # Ensure 4-digit format
                    if len(tx_h) == 3:
                        tx_h = "0" + tx_h
                    if len(rx_h) == 3:
                        rx_h = "0" + rx_h
                    # Format: RX_H + TX_H (reversed for VCI)
                    return self.strby_to_char(rx_h + tx_h)
                else:
                    self.log("Invalid ECU headers for DIAG_ON_CAN")
                    return None
                    
            elif protocol == self.KWP_ON_CAN_FIAT:
                if tx_h and rx_h and kwp_id:
                    # Ensure 4-digit format
                    if len(tx_h) == 3:
                        tx_h = "0" + tx_h
                    if len(rx_h) == 3:
                        rx_h = "0" + rx_h
                    # Ensure 2-digit KWP ID
                    if len(str(kwp_id)) == 1:
                        kwp_id = "0" + str(kwp_id)
                    # Format: RX_H + TX_H + KWP_ID + 00
                    descriptor = rx_h + tx_h + str(kwp_id) + "00"
                    self.log(f"FIAT ECU descriptor: {descriptor}")
                    return self.strby_to_char(descriptor)
                else:
                    self.log("Invalid parameters for KWP_ON_CAN_FIAT")
                    return None
                    
            elif protocol == self.PSA2:
                if kwp_id:
                    return self.strby_to_char(str(kwp_id))
                else:
                    self.log("KWP ID required for PSA2")
                    return None
                    
            elif protocol == self.KWP2000_PSA:
                if kwp_id:
                    return self.strby_to_char(str(kwp_id))
                else:
                    self.log("KWP ID required for KWP2000_PSA")
                    return None
                    
            else:
                self.log(f"Unsupported protocol for ECU descriptor: {protocol}")
                return None
                
        except Exception as e:
            self.log(f"Error creating ECU descriptor: {e}")
            return None
    
    def strby_to_char(self, inp):
        """Convert string bytes to char buffer"""
        bys = re.findall('.{1,2}', inp)
        return self.bytesEncode(" ".join(bys))
    
    def send_receive(self, data, timeout=1500):
        """Send data to ECU and receive response"""
        if self.currEcuDesc is None:
            self.log("VCI not configured")
            return ""
        
        try:
            inBuffer, inLen = self.bytesEncode(data, None)
            ecuDesc, ecuDescLen = self.currEcuDesc
            
            vciWriteAndRead = self.vci["_writeAndRead"]
            vciWriteAndRead.restype = ctypes.c_int
            vciWriteAndRead.argtypes = [ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_int]
            outputBuffer = ctypes.create_string_buffer(self.MSG_BUFFER)
            
            result = vciWriteAndRead(ecuDesc, ecuDescLen, inBuffer, inLen, outputBuffer, self.MSG_BUFFER, timeout)
            
            if result > 0:
                out = ""
                for i in range(0, result):
                    hex_val = hex(outputBuffer.raw[i]).replace("0x", "").upper().zfill(2)
                    out += hex_val
                return out
            else:
                self.log(f"WriteAndRead error: {self.statusToStr(result)}")
                return ""
                
        except Exception as e:
            self.log(f"Send/Receive error: {e}")
            return ""
    
    def send_receive_multiple(self, data, responses=1, timeout=1500):
        """Send data and receive multiple responses (for KWP2000)"""
        if self.currEcuDesc is None:
            self.log("VCI not configured")
            return ""
        
        try:
            inBuffer, inLen = self.bytesEncode(data, None)
            ecuDesc, ecuDescLen = self.currEcuDesc
            
            vciWriteAndReadMF = self.vci["_writeAndReadMultipleFrames"]
            vciWriteAndReadMF.restype = ctypes.c_int
            vciWriteAndReadMF.argtypes = [ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_int]
            outputBuffer = ctypes.create_string_buffer(self.MSG_BUFFER)
            
            result = vciWriteAndReadMF(ecuDesc, ecuDescLen, inBuffer, inLen, responses, outputBuffer, self.MSG_BUFFER, timeout)
            
            if result > 0:
                out = ""
                for i in range(0, result):
                    hex_val = hex(outputBuffer.raw[i]).replace("0x", "").upper().zfill(2)
                    out += hex_val
                return out
            else:
                self.log(f"WriteAndReadMultipleFrames error: {self.statusToStr(result)}")
                return ""
                
        except Exception as e:
            self.log(f"Send/Receive Multiple error: {e}")
            return ""
    
    def perform_init(self, ecu_descriptor=None):
        """Perform ECU initialization (for KWP2000/PSA2 protocols)"""
        if ecu_descriptor is None:
            ecu_descriptor = self.currEcuDesc
            
        if ecu_descriptor is None:
            self.log("No ECU descriptor available for initialization")
            return False
            
        try:
            ecuDesc, ecuDescLen = ecu_descriptor
            
            vciPerformInit = self.vci["_performInit"]
            vciPerformInit.restype = ctypes.c_int
            vciPerformInit.argtypes = [ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_int]
            outputBuffer = ctypes.create_string_buffer(self.MSG_BUFFER)
            
            result = vciPerformInit(ecuDesc, ecuDescLen, outputBuffer, self.MSG_BUFFER)
            
            if result > 0:
                out = ""
                for i in range(0, result):
                    hex_val = hex(outputBuffer.raw[i]).replace("0x", "").upper().zfill(2)
                    out += hex_val
                self.log(f"ECU Init Response: {out}")
                return True
            elif result == 0:
                self.log("ECU initialization completed (no response)")
                return True
            else:
                self.log(f"ECU initialization failed: {self.statusToStr(result)}")
                return False
                
        except Exception as e:
            self.log(f"ECU initialization error: {e}")
            return False
    
    def get_analog_data(self, channel_index):
        """Get analog voltage reading from VCI"""
        try:
            c_float_p = ctypes.POINTER(ctypes.c_float)
            vciGetAnalogicData = self.vci["_getAnalogicData"]
            vciGetAnalogicData.restype = ctypes.c_int
            vciGetAnalogicData.argtypes = [ctypes.c_int, c_float_p]
            
            data_value = ctypes.c_float()
            result = vciGetAnalogicData(channel_index, ctypes.byref(data_value))
            
            if result >= 0:
                voltage = data_value.value
                self.log(f"Analog channel {channel_index}: {voltage:.2f}V")
                return voltage
            else:
                self.log(f"Analog data read failed: {self.statusToStr(result)}")
                return None
                
        except Exception as e:
            self.log(f"Analog data error: {e}")
            return None
    
    def handle_command(self, cmd_data):
        """Handle command from parent process"""
        command = cmd_data.get("command")
        params = cmd_data.get("params", {})
        
        if command == "connect":
            success = self.connect()
            self.send_response("connect_response", {"success": success})
            
        elif command == "disconnect":
            success = self.disconnect()
            self.send_response("disconnect_response", {"success": success})
            
        elif command == "configure":
            success = self.configure(**params)
            self.send_response("configure_response", {"success": success})
            
        elif command == "send_receive":
            response = self.send_receive(params.get("data", ""), params.get("timeout", 1500))
            self.send_response("send_receive_response", {"response": response})
            
        elif command == "send_receive_multiple":
            response = self.send_receive_multiple(
                params.get("data", ""), 
                params.get("responses", 1), 
                params.get("timeout", 1500)
            )
            self.send_response("send_receive_multiple_response", {"response": response})
            
        elif command == "perform_init":
            success = self.perform_init()
            self.send_response("perform_init_response", {"success": success})
            
        elif command == "get_analog_data":
            voltage = self.get_analog_data(params.get("channel", 0))
            self.send_response("get_analog_data_response", {"voltage": voltage})
            
        elif command == "quit":
            self.disconnect()
            self.send_response("quit_response", {"success": True})
            return False
            
        else:
            self.log(f"Unknown command: {command}")
            
        return True
    
    def run(self):
        """Main bridge loop"""
        self.log("VCI Bridge started")
        
        try:
            while True:
                line = sys.stdin.readline()
                if not line:
                    break
                    
                try:
                    cmd_data = json.loads(line.strip())
                    if not self.handle_command(cmd_data):
                        break
                        
                except json.JSONDecodeError as e:
                    self.log(f"JSON decode error: {e}")
                except Exception as e:
                    self.log(f"Command handling error: {e}")
                    
        except KeyboardInterrupt:
            self.log("Bridge interrupted")
        except Exception as e:
            self.log(f"Bridge error: {e}")
        finally:
            self.disconnect()
            self.log("VCI Bridge stopped")

if __name__ == "__main__":
    bridge = VCIBridge()
    bridge.run()