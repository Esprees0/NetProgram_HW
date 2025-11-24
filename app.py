from flask import Flask, render_template, request, redirect, url_for, flash
import time
import os

app = Flask(__name__)
app.secret_key = 'your-secret-key-here-change-this'

# กำหนด IP ของอุปกรณ์
SNMP_HOSTS = {
    'R1': '192.168.84.10',
    'R2': '192.168.84.11',
    'SW1': '192.168.84.12',
    'SW2': '192.168.84.13'
}

# กำหนด Interface Name ตามจริง
INTERFACE_NAMES = {
    'R1': {
        1: 'GigabitEthernet0/0',
        2: 'GigabitEthernet0/1',
        3: 'GigabitEthernet0/2',
        4: 'Serial0/0/0'
    },
    'R2': {
        1: 'GigabitEthernet0/0',
        2: 'GigabitEthernet0/1',
        3: 'GigabitEthernet0/2',
        4: 'Serial0/0/0'
    },
    'SW1': {
        1: 'GigabitEthernet1/0/1',
        2: 'GigabitEthernet1/0/2',
        3: 'GigabitEthernet1/0/3',
        4: 'GigabitEthernet1/0/4'
    },
    'SW2': {
        1: 'GigabitEthernet1/0/1',
        2: 'GigabitEthernet1/0/2',
        3: 'GigabitEthernet1/0/3',
        4: 'GigabitEthernet1/0/4'
    }
}

# จำนวน Port ต่ออุปกรณ์
DEFAULT_PORTS = 4

# สร้าง PORT_STATUS อัตโนมัติ
def init_port_status():
    status = {}
    for device in SNMP_HOSTS.keys():
        status[device] = {port_id: ('up' if port_id == 1 else 'down') 
                         for port_id in range(1, DEFAULT_PORTS + 1)}
    return status

PORT_STATUS = init_port_status()

# ตัวเลือก: ใช้ SNMP จริงหรือจำลอง
USE_REAL_SNMP = True  # เปลี่ยนเป็น True เมื่อต้องการใช้ SNMP จริง

SNMP_COMMUNITY = 'private'
SNMP_PORT = 161

if USE_REAL_SNMP:
    from pysnmp.hlapi import *
    OID_IF_OPER_STATUS = '1.3.6.1.2.1.2.2.1.8'
    OID_IF_ADMIN_STATUS = '1.3.6.1.2.1.2.2.1.7'
    OID_IF_DESCR = '1.3.6.1.2.1.2.2.1.2'

def get_interface_name_real(host, port_index):
    """อ่านชื่อ Interface จาก SNMP จริง"""
    try:
        oid = f'{OID_IF_DESCR}.{port_index}'
        
        iterator = getCmd(
            SnmpEngine(),
            CommunityData(SNMP_COMMUNITY),
            UdpTransportTarget((host, SNMP_PORT), timeout=2, retries=1),
            ContextData(),
            ObjectType(ObjectIdentity(oid))
        )
        
        errorIndication, errorStatus, errorIndex, varBinds = next(iterator)
        
        if errorIndication or errorStatus:
            return f'Port {port_index}'
        
        for varBind in varBinds:
            return str(varBind[1])
            
    except Exception:
        return f'Port {port_index}'

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
    print(f"🎭 [DEMO MODE] Setting {device} Port {port_index} to {status}")
    time.sleep(0.3)
    
    if device in PORT_STATUS and port_index in PORT_STATUS[device]:
        PORT_STATUS[device][port_index] = status
        print(f"✅ [DEMO MODE] Success!")
        return True
    
    print(f"❌ [DEMO MODE] Failed!")
    return False

def get_interface_name(device, port_index):
    """ดึงชื่อ Interface"""
    if USE_REAL_SNMP:
        return get_interface_name_real(SNMP_HOSTS[device], port_index)
    else:
        return INTERFACE_NAMES.get(device, {}).get(port_index, f'Port {port_index}')

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
    
    for device_name, device_ip in SNMP_HOSTS.items():
        ports = []
        for port_id in range(1, DEFAULT_PORTS + 1):
            status = get_port_status(device_name, port_id)
            interface_name = get_interface_name(device_name, port_id)
            connected = 'Net' if port_id == 1 else None
            ports.append({
                'id': port_id,
                'status': status,
                'interface': interface_name,
                'connected': connected
            })
        
        device_data = {
            'ip': device_ip,
            'ports': ports
        }
        
        if device_name.startswith('R'):
            result['routers'][device_name] = device_data
        elif device_name.startswith('SW'):
            result['switches'][device_name] = device_data
        else:
            result['switches'][device_name] = device_data
    
    return result

@app.route('/')
def index():
    """หน้าแรก"""
    ports_data = get_all_ports()
    expanded_device = request.args.get('expanded')
    return render_template('index.html', 
                         data=ports_data, 
                         demo_mode=not USE_REAL_SNMP,
                         expanded_device=expanded_device)

@app.route('/toggle', methods=['POST'])
def toggle_port():
    """สลับสถานะ Port"""
    device = request.form.get('device')
    port_id = int(request.form.get('port_id'))
    
    if device not in SNMP_HOSTS:
        flash('ไม่พบอุปกรณ์', 'error')
        return redirect(url_for('index'))
    
    current_status = get_port_status(device, port_id)
    
    if current_status == 'unknown':
        flash(f'ไม่สามารถอ่านสถานะ {device} Port {port_id}', 'error')
        return redirect(url_for('index', expanded=device))
    
    new_status = 'down' if current_status == 'up' else 'up'
    
    success = set_port_status(device, port_id, new_status)
    
    if success:
        mode = "[DEMO]" if not USE_REAL_SNMP else ""
        interface_name = get_interface_name(device, port_id)
        flash(f'{mode} {device} {interface_name} เปลี่ยนเป็น {new_status.upper()} แล้ว', 'success')
    else:
        flash(f'ไม่สามารถเปลี่ยนสถานะ {device} Port {port_id}', 'error')
    
    # เก็บ device ที่กำลังเปิดอยู่
    return redirect(url_for('index', expanded=device))

if __name__ == '__main__':
    if os.environ.get("WERKZEUG_RUN_MAIN") == "true":
        print("=" * 60)
        print("🚀 Starting SNMP Port Management Server...")
        print("=" * 60)
        print("Available devices:")
        for device, ip in SNMP_HOSTS.items():
            print(f"  {device}: {ip}")
    print()
    app.run(host='0.0.0.0', port=5000, debug=True)