#!/usr/bin/env python3
import re
import logging

# Configure logging
logger = logging.getLogger(__name__)

def generate_mac_address(ip_address):
    """
    Generate a MAC address based on an IP address.
    
    Args:
        ip_address (str): The IP address in the format 172.16.x.y
        
    Returns:
        str: A MAC address in the format 06:00:AC:10:xx:yy
    """
    try:
        # Extract the octets from the IP address
        match = re.match(r'172\.16\.(\d+)\.(\d+)', ip_address)
        
        if not match:
            logger.warning(f"IP address {ip_address} doesn't match expected format 172.16.x.y")
            # Fallback to default values if the IP doesn't match
            octet3, octet4 = 0, 0
        else:
            octet3 = int(match.group(1))
            octet4 = int(match.group(2))
        
        # Generate a unique MAC address using the IP octets
        mac_address = f"06:00:AC:10:{octet3:02x}:{octet4:02x}"
        
        return mac_address
    except Exception as e:
        logger.error(f"Error generating MAC address from IP {ip_address}: {str(e)}")
        # Return a fallback MAC address
        return "06:00:AC:10:00:00"

def generate_ip_from_sequence(sequence):
    """
    Generate an IP address for a VM based on a sequence number.
    For a /30 subnet, we use 4 addresses per subnet with the VM getting the .2 address.
    
    Args:
        sequence (int): The sequence number
        
    Returns:
        str: An IP address in the format 172.16.x.y
    """
    try:
        # For a /30 subnet, A = 4
        A = 4
        
        # Calculate octets from the sequence
        octet3 = int((A * sequence + 2) / 256)
        octet4 = int((A * sequence + 2) % 256)
        
        return f"172.16.{octet3}.{octet4}"
    except Exception as e:
        logger.error(f"Error generating IP from sequence {sequence}: {str(e)}")
        return "172.16.0.2"

def generate_tap_ip_from_sequence(sequence):
    """
    Generate a TAP interface IP address based on a sequence number.
    For a /30 subnet, we use 4 addresses per subnet with the TAP getting the .1 address.
    
    Args:
        sequence (int): The sequence number
        
    Returns:
        str: An IP address in the format 172.16.x.y
    """
    try:
        # For a /30 subnet, A = 4
        A = 4
        
        # Calculate octets from the sequence
        octet3 = int((A * sequence + 1) / 256)
        octet4 = int((A * sequence + 1) % 256)
        
        return f"172.16.{octet3}.{octet4}"
    except Exception as e:
        logger.error(f"Error generating TAP IP from sequence {sequence}: {str(e)}")
        return "172.16.0.1"
