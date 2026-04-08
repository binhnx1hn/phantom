#!/bin/bash
# ══════════════════════════════════════════════════════════════
# Pi Zero 2W — Setup Script
# Cài đặt File Server + WiFi AP "PiZero-Node"
# Chạy bằng: sudo bash setup.sh
# ══════════════════════════════════════════════════════════════

set -e
PI_HOME="/home/pi"
SERVER_DIR="$PI_HOME/pi_zero"
FILES_DIR="$PI_HOME/files"

echo "══════════════════════════════════════════"
echo " Pi Zero 2W — Setup File Server"
echo "══════════════════════════════════════════"

# 1. Cài đặt packages
echo "[1/6] Cài đặt packages..."
apt-get update -qq
apt-get install -y python3-flask hostapd dnsmasq 2>/dev/null || \
  pip3 install flask

# 2. Tạo thư mục files
echo "[2/6] Tạo thư mục $FILES_DIR..."
mkdir -p "$FILES_DIR"
chown pi:pi "$FILES_DIR"

# 3. Copy server.py
echo "[3/6] Copy server.py..."
mkdir -p "$SERVER_DIR"
cp "$(dirname "$0")/server.py" "$SERVER_DIR/server.py"
chown -R pi:pi "$SERVER_DIR"

# 4. Cài systemd service
echo "[4/6] Cài systemd service..."
cp "$(dirname "$0")/pizero-server.service" /etc/systemd/system/
systemctl daemon-reload
systemctl enable pizero-server
systemctl restart pizero-server

# 5. Cấu hình WiFi AP
echo "[5/6] Cấu hình WiFi AP 'PiZero-Node'..."

# /etc/hostapd/hostapd.conf
cat > /etc/hostapd/hostapd.conf << 'EOF'
interface=wlan0
driver=nl80211
ssid=PiZero-Node
hw_mode=g
channel=1
wmm_enabled=0
macaddr_acl=0
auth_algs=1
ignore_broadcast_ssid=0
wpa=2
wpa_passphrase=12345678
wpa_key_mgmt=WPA-PSK
wpa_pairwise=TKIP
rsn_pairwise=CCMP
EOF

# Kích hoạt hostapd
sed -i 's/#DAEMON_CONF=""/DAEMON_CONF="\/etc\/hostapd\/hostapd.conf"/' \
    /etc/default/hostapd 2>/dev/null || true
echo 'DAEMON_CONF="/etc/hostapd/hostapd.conf"' >> /etc/default/hostapd

# /etc/dnsmasq.conf — DHCP cho WiFi AP
cat > /etc/dnsmasq.conf << 'EOF'
interface=wlan0
dhcp-range=192.168.4.2,192.168.4.20,255.255.255.0,24h
dhcp-option=3,192.168.4.1
dhcp-option=6,192.168.4.1
server=8.8.8.8
log-queries
log-dhcp
EOF

# Static IP cho wlan0
cat >> /etc/dhcpcd.conf << 'EOF'

# Pi Zero AP
interface wlan0
    static ip_address=192.168.4.1/24
    nohook wpa_supplicant
EOF

systemctl unmask hostapd
systemctl enable hostapd
systemctl enable dnsmasq
systemctl restart hostapd || true
systemctl restart dnsmasq || true

# 6. Xong
echo "[6/6] Hoàn tất!"
echo ""
echo "══════════════════════════════════════════"
echo " WiFi AP : PiZero-Node / 12345678"
echo " IP      : 192.168.4.1"
echo " Files   : $FILES_DIR"
echo " API     : http://192.168.4.1/file/list"
echo " Service : systemctl status pizero-server"
echo "══════════════════════════════════════════"
echo ""
echo "ESP32 Node-2 cần đặt:"
echo "  #define NODE1_SSID     \"PiZero-Node\""
echo "  #define NODE1_PASSWORD \"12345678\""
echo "  #define NODE1_IP       \"192.168.4.1\""
echo ""
echo "Khởi động lại Pi Zero: sudo reboot"
