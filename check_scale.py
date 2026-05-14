import hid

print(f"{'Product':<30} | {'VID':<10} | {'PID':<10}")
print("-" * 55)

for device in hid.enumerate():
    product = device.get('product_string')
    # If the device has no name, we'll call it Unknown
    name = str(product) if product else "Unknown USB Device"
    
    vid = hex(device.get('vendor_id'))
    pid = hex(device.get('product_id'))
    
    print(f"{name:<30} | {vid:<10} | {pid:<10}")