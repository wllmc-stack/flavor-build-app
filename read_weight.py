import hid

# The IDs we found in your scan
VENDOR_ID = 0x1446
PRODUCT_ID = 0x6a73

def get_weight():
    try:
        # Open the scale
        device = hid.device()
        device.open(VENDOR_ID, PRODUCT_ID)
        
        print("Scale found! Place an item on it...")
        
        while True:
            # Read 6 bytes of data from the scale
            data = device.read(6)
            
            if data:
                # Data byte 4 and 5 usually contain the weight
                # This logic is common for Stamps.com scales
                raw_weight = data[4] + (data[5] << 8)
                
                # Check for unit (Ounces vs Pounds)
                # Most 5lb scales default to ounces
                weight_oz = raw_weight / 10.0 
                
                print(f"Current Weight: {weight_oz} oz", end="\r")
                
    except Exception as e:
        print(f"\nError: {e}")
    finally:
        device.close()

if __name__ == "__main__":
    get_weight()