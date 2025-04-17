#!/usr/bin/env python3
import time
import serial
from Crypto.Cipher import AES

class TC66Monitor:
    def __init__(self, port='/dev/ttyACM0', baudrate=115200, timeout=5):
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout
        self.serial = None
        # AES encryption key from the original code
        self.key = [
            88, 33, -6, 86, 1, -78, -16, 38,
            -121, -1, 18, 4, 98, 42, 79, -80,
            -122, -12, 2, 96, -127, 111, -102, 11,
            -89, -15, 6, 97, -102, -72, 114, -120
        ]
        
    def connect(self):
        """Connect to the TC66 device"""
        try:
            self.serial = serial.Serial(
                port=self.port, 
                baudrate=self.baudrate, 
                timeout=self.timeout,
                write_timeout=0
            )
            return True
        except Exception as e:
            print(f"Error connecting to {self.port}: {e}")
            return False
            
    def disconnect(self):
        """Disconnect from the device"""
        if self.serial:
            self.serial.close()
            
    def send_command(self, command):
        """Send a command to the device"""
        if not self.serial or not self.serial.isOpen():
            if not self.connect():
                return False
        self.serial.write((command + "\r\n").encode("ascii"))
        return True
        
    def read_data(self):
        """Read and decode data from the device"""
        if not self.send_command("getva"):
            return None
            
        # Read 192 bytes as per the original code
        data = self.serial.read(192)
        if len(data) < 192:
            print(f"Incomplete data received: {len(data)} bytes")
            return None
            
        return self.decode_response(data)
        
    def decode_response(self, data):
        """Decrypt and decode the response"""
        # Convert key for AES decryption
        key = bytes([value & 255 for value in self.key])
            
        # Decrypt the data
        try:
            aes = AES.new(key, AES.MODE_ECB)
            decrypted = aes.decrypt(data)
        except Exception as e:
            print(f"Error decrypting data: {e}")
            return None
            
        # Determine temperature multiplier
        if self.decode_integer(decrypted, 88) == 1:
            temperature_multiplier = -1
        else:
            temperature_multiplier = 1
            
        # Extract and return the values
        return {
            "timestamp": time.time(),
            "voltage": self.decode_integer(decrypted, 48, 10000),
            "current": self.decode_integer(decrypted, 52, 100000),
            "power": self.decode_integer(decrypted, 56, 10000),
            "resistance": self.decode_integer(decrypted, 68, 10),
            "accumulated_current": self.decode_integer(decrypted, 72),
            "accumulated_power": self.decode_integer(decrypted, 76),
            "temperature": self.decode_integer(decrypted, 92) * temperature_multiplier,
            "data_plus": self.decode_integer(decrypted, 96, 100),
            "data_minus": self.decode_integer(decrypted, 100, 100),
        }
        
    def decode_integer(self, data, first_byte, divider=1):
        """Decode an integer from the decrypted data"""
        temp4 = data[first_byte] & 255
        temp3 = data[first_byte + 1] & 255
        temp2 = data[first_byte + 2] & 255
        temp1 = data[first_byte + 3] & 255
        return ((((temp1 << 24) | (temp2 << 16)) | (temp3 << 8)) | temp4) / float(divider)
        
    def format_data(self, data):
        """Format the data as a string"""
        if not data:
            return "No data available"
            
        return (
            f"Voltage: {data['voltage']:.3f} V | "
            f"Current: {data['current']:.3f} A | "
            f"Power: {data['power']:.3f} W | "
            f"Resistance: {data['resistance']:.1f} Ω | "
            f"Temperature: {data['temperature']:.1f} °C"
        )
        
    def monitor(self, interval=1.0, csv=False):
        """Continuously monitor and output data"""
        try:
            if not self.connect():
                return
                
            print(f"Connected to TC66 at {self.port}")
            print("Press Ctrl+C to exit")
            
            if csv:
                print("timestamp,voltage,current,power,resistance,temperature")
                
            while True:
                data = self.read_data()
                if data:
                    if csv:
                        print(f"{data['timestamp']},{data['voltage']},{data['current']},{data['power']},{data['resistance']},{data['temperature']}")
                    else:
                        print(self.format_data(data))
                else:
                    print("Failed to read data")
                    
                time.sleep(interval)
                
        except KeyboardInterrupt:
            print("\nMonitoring stopped")
        finally:
            self.disconnect()
            print("Disconnected from device")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Monitor TC66 USB-C Power Meter')
    parser.add_argument('-p', '--port', default='/dev/ttyACM0', help='Serial port')
    parser.add_argument('-i', '--interval', type=float, default=1.0, help='Sampling interval in seconds')
    parser.add_argument('--csv', action='store_true', help='Output in CSV format')
    
    args = parser.parse_args()
    
    monitor = TC66Monitor(args.port)
    monitor.monitor(args.interval, args.csv)