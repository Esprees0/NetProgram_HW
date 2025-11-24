from flask import Flask, render_template, request, redirect, url_for, flash
import time
import random

app = Flask(__name__)
app.secret_key = 'your-secret-key-here-change-this'

# กำหนด IP ของอุปกรณ์ (เพิ่มหรือลบได้เลย)
SNMP_HOSTS = {
    'R1': '192.168.84.10',
    'R2': '192.168.84.11',
    'SW1': '192.168.84.12',
    'SW2': '192.168.84.13'
}

# จำนวน Port ต่ออุปกรณ์ (ค่าเริ่มต้น)
DEFAULT_PORTS = 4

# สร้าง PORT_STATUS อัตโนมัติจาก SNMP_HOSTS
def init_port_status():
    """สร้างสถานะ Port เริ่มต้นสำหรับทุกอุปกรณ์"""
    status = {}
    for device in SNMP_HOSTS.keys():
        status[device] = {port_id: ('up' if port_id == 1 else 'down') 
                         for port_id in range(1, DEFAULT_PORTS + 1)}
    return status

# จำลองสถานะ Port (สร้างอัตโนมัติ)
PORT_STATUS = init_port_status()

# ตัวเลือก: ใช้ SNMP จริงหรือจำลอง
USE_REAL_SNMP = False  # เปลี่ยนเป็น True เมื่อต้องการใช้ SNMP จริง

SNMP_COMMUNITY = 'public'
SNMP_PORT = 161

if USE_REAL_SNMP:
    from pysnmp.hlapi import *
    OID_IF_OPER_STATUS = '1.3.6.1.2.1.2.2.1.8'
    OID_IF_ADMIN_STATUS = '1.3.6.1.2.1.2.2.1.7'

def get_port_status_real(host, port_index):
    """อ่านสถานะ Port จาก SNMP จริง"""
    try:
        oid = f'{OID_IF_OPER_STATUS}.{port_index}'
        
        iterator = getCmd(
            SnmpEngine(),
            CommunityData(SNMP_COMMUNITY),
            UdpTransportTarget((host, SNMP_PORT), timeout=2, retries=1),
            ContextData(),
            ObjectType(ObjectIdentity(oid))
        )
        
        errorIndication, errorStatus, errorIndex, varBinds = next(iterator)
        
        if errorIndication or errorStatus:
            return 'unknown'
        
        for varBind in varBinds:
            status = int(varBind[1])
            return 'up' if status == 1 else 'down'
            
    except Exception as e:
        print(f"Exception: {str(e)}")
        return 'unknown'

def set_port_status_real(host, port_index, status):
    """เปลี่ยนสถานะ Port ผ่าน SNMP จริง"""
    try:
        oid = f'{OID_IF_ADMIN_STATUS}.{port_index}'
        admin_status = 1 if status == 'up' else 2
        
        print(f"🔧 Trying to set {host} Port {port_index} to {status}")
        
        iterator = setCmd(
            SnmpEngine(),
            CommunityData(SNMP_COMMUNITY),
            UdpTransportTarget((host, SNMP_PORT), timeout=2, retries=1),
            ContextData(),
            ObjectType(ObjectIdentity(oid), Integer(admin_status))
        )
        
        errorIndication, errorStatus, errorIndex, varBinds = next(iterator)
        
        if errorIndication:
            print(f"❌ Error: {errorIndication}")
            return False
        
        if errorStatus:
            print(f"❌ Error: {errorStatus.prettyPrint()}")
            return False
        
        print(f"✅ Success!")
        time.sleep(0.5)
        return True
        
    except Exception as e:
        print(f"❌ Exception: {str(e)}")
        return False

def get_port_status_demo(device, port_index):
    """จำลองการอ่านสถานะ Port"""
    return PORT_STATUS.get(device, {}).get(port_index, 'unknown')

def set_port_status_demo(device, port_index, status):
    """จำลองการเปลี่ยนสถานะ Port"""
    print(f"🎭 Device Setting {device} Port {port_index} to {status}")
    time.sleep(0.3)  # จำลองความหน่วง
    
    if device in PORT_STATUS and port_index in PORT_STATUS[device]:
        PORT_STATUS[device][port_index] = status
        print(f"✅ Device Success!")
        return True
    
    print(f"❌ Device Failed!")
    return False

def get_port_status(device, port_index):
    """อ่านสถานะ Port"""
    if USE_REAL_SNMP:
        return get_port_status_real(SNMP_HOSTS[device], port_index)
    else:
        return get_port_status_demo(device, port_index)

def set_port_status(device, port_index, status):
    """เปลี่ยนสถานะ Port"""
    if USE_REAL_SNMP:
        return set_port_status_real(SNMP_HOSTS[device], port_index, status)
    else:
        return set_port_status_demo(device, port_index, status)

def get_all_ports():
    """ดึงสถานะ Port ทั้งหมด"""
    result = {
        'routers': {},
        'switches': {}
    }
    
    # อ่านสถานะทุกอุปกรณ์ใน SNMP_HOSTS
    for device_name, device_ip in SNMP_HOSTS.items():
        ports = []
        for port_id in range(1, DEFAULT_PORTS + 1):
            status = get_port_status(device_name, port_id)
            connected = 'Net' if port_id == 1 else None
            ports.append({
                'id': port_id,
                'status': status,
                'connected': connected
            })
        
        device_data = {
            'ip': device_ip,
            'ports': ports
        }
        
        # แยกประเภทตามชื่อ
        if device_name.startswith('R'):  # Router
            result['routers'][device_name] = device_data
        elif device_name.startswith('SW'):  # Switch
            result['switches'][device_name] = device_data
        else:
            # ถ้าไม่ขึ้นต้นด้วย R หรือ SW ให้ใส่ใน switches
            result['switches'][device_name] = device_data
    
    return result

@app.route('/')
def index():
    """หน้าแรก"""
    ports_data = get_all_ports()
    return render_template('index.html', data=ports_data, demo_mode=not USE_REAL_SNMP)

@app.route('/toggle', methods=['POST'])
def toggle_port():
    """สลับสถานะ Port"""
    device = request.form.get('device')
    port_id = int(request.form.get('port_id'))
    
    if device not in SNMP_HOSTS:
        flash('ไม่พบอุปกรณ์', 'error')
        return redirect(url_for('index'))
    
    # อ่านสถานะปัจจุบัน
    current_status = get_port_status(device, port_id)
    
    if current_status == 'unknown':
        flash(f'ไม่สามารถอ่านสถานะ {device} Port {port_id}', 'error')
        return redirect(url_for('index'))
    
    # สลับสถานะ
    new_status = 'down' if current_status == 'up' else 'up'
    
    # เปลี่ยนสถานะ
    success = set_port_status(device, port_id, new_status)
    
    if success:
        mode = "[DEMO]" if not USE_REAL_SNMP else ""
        flash(f'{mode} {device} Port {port_id} เปลี่ยนเป็น {new_status.upper()} แล้ว', 'success')
    else:
        flash(f'ไม่สามารถเปลี่ยนสถานะ {device} Port {port_id}', 'error')
    
    return redirect(url_for('index'))

if __name__ == '__main__':
    print("=" * 60)
    print("🚀 Starting SNMP Port Management Server...")
    print("=" * 60)
    print("Available devices:")
    for device, ip in SNMP_HOSTS.items():
        print(f"  {device}: {ip}")
    print()
    
    if USE_REAL_SNMP:
        print("🔴 MODE: REAL SNMP")
        print(f"   Community: {SNMP_COMMUNITY}")
        print("   ⚠️  ต้องมีสิทธิ์ Write ในอุปกรณ์จริง")
    else:
        print("🎭 MODE: DEMO (จำลองการทำงาน)")
        print("   ✅ คลิกเปลี่ยนสถานะ Port ได้เลย")
        print("   💡 เปลี่ยนเป็น USE_REAL_SNMP = True เมื่อพร้อม")
    
    print()
    print("=" * 60)
    print("🌐 Server running on http://0.0.0.0:5000")
    print("=" * 60)
    app.run(host='0.0.0.0', port=5000, debug=True)