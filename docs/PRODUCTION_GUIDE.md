# NetCap Dashboard - Production Deployment Guide

## 🚀 Production-Ready Features

### Performance Optimizations
- **Throttled Rendering**: Prevents UI lag during high packet rates
- **Efficient DOM Updates**: Uses DocumentFragment for batch updates
- **Memory Management**: Automatic cleanup of old packet data
- **Chart Optimization**: RequestAnimationFrame for smooth animations
- **CSS Containment**: Optimized rendering performance

### Production Features
- **Auto-Reconnection**: WebSocket automatically reconnects on failure
- **Error Handling**: Graceful degradation on component failures
- **Performance Monitoring**: Real-time performance status in footer
- **Responsive Design**: Optimized for all screen sizes
- **Professional UI**: Clean, modern interface suitable for enterprise use

## 📋 System Requirements

### Software Dependencies
- **Python 3.8+** with required packages
- **TShark/Wireshark** for packet capture
- **Modern Web Browser** (Chrome, Firefox, Safari, Edge)
- **Network Interface** with appropriate permissions

### Hardware Recommendations
- **CPU**: Multi-core processor (2+ cores recommended)
- **RAM**: 4GB minimum, 8GB+ for high-traffic networks
- **Storage**: 1GB+ free space for packet logs
- **Network**: Gigabit Ethernet for high-speed capture

## 🔧 Quick Deployment

### Windows
```batch
# Run the deployment script
deploy_production.bat
```

### Linux/macOS
```bash
# Make script executable and run
chmod +x deploy_production.sh
./deploy_production.sh
```

### Manual Deployment
```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Start the dashboard server
python Server1.py

# 3. In another terminal, start packet capture
python netcap_manager.py interfaces
python netcap_manager.py capture --interface "Your-Interface"

# 4. Access dashboard at http://localhost:8000
```

## 🌐 Network Access

### Local Access
- **Dashboard**: `http://localhost:8000`
- **WebSocket**: `ws://localhost:8765`

### Network Access
- **Dashboard**: `http://[YOUR-IP]:8000`
- **WebSocket**: `ws://[YOUR-IP]:8765`

### Firewall Configuration
Ensure these ports are open:
- **Port 8000**: HTTP dashboard access
- **Port 8765**: WebSocket real-time data
- **Port 8081**: TCP data relay (internal)

## 🔒 Security Considerations

### Network Security
- **Packet Capture**: Requires elevated privileges
- **Network Exposure**: Consider firewall rules for network access
- **Data Sensitivity**: Captured packets may contain sensitive information

### Access Control
- **Local Only**: Default configuration for localhost access
- **Network Access**: Modify Server1.py to bind to specific interfaces
- **Authentication**: Consider adding authentication for production use

### Data Protection
- **Automatic Cleanup**: JSON files are cleaned after capture stops
- **Log Rotation**: PCAP files are stored separately in logs/ directory
- **Memory Limits**: Configurable packet buffer limits

## 📊 Performance Tuning

### High-Traffic Networks
```python
# Adjust these values in the dashboard JavaScript:
MAX_PACKETS = 2000        # Increase packet history
MAX_DISPLAY_PACKETS = 200 # Increase visible packets
renderThrottle = 50       # Decrease for more responsive UI
```

### Low-Resource Systems
```python
# Reduce resource usage:
MAX_PACKETS = 500         # Decrease packet history
MAX_DISPLAY_PACKETS = 50  # Decrease visible packets
renderThrottle = 200      # Increase for less CPU usage
```

### Chart Performance
- Charts update every 2 seconds by default
- Disable charts on low-end systems by setting `chartsEnabled = false`
- Reduce chart data points for better performance

## 🔧 Configuration Options

### Server Configuration (Server1.py)
```python
PORT = 8081              # TCP data port
WEBSOCKET_PORT = 8765    # WebSocket port
HTTP_PORT = 8000         # Dashboard port
SERVER = '0.0.0.0'       # Listen on all interfaces
```

### Capture Configuration
```bash
# Batch interval (seconds between packet batches)
python netcap_manager.py capture --interface "eth0" --duration 3600

# Different interfaces
python netcap_manager.py interfaces  # List available interfaces
```

### Dashboard Configuration
- **Auto-scroll**: Toggle automatic packet table scrolling
- **Protocol Filters**: Filter by specific protocols
- **Search**: Real-time search across all packet fields
- **Export**: Download packet data in JSON format

## 📈 Monitoring & Maintenance

### Performance Monitoring
- **Footer Status**: Shows current system load (Normal/Active/High Load)
- **Packet Rate**: Real-time packets per second display
- **Memory Usage**: Automatic cleanup prevents memory leaks
- **Connection Status**: Visual WebSocket connection indicator

### Log Management
```bash
# Clean up old JSON files
python netcap_manager.py cleanup --json

# Clean up old PCAP logs (older than 7 days)
python netcap_manager.py cleanup --logs 7

# Check system status
python netcap_manager.py status
```

### Troubleshooting
1. **No Packets Visible**: Check if capture is running and interface is correct
2. **WebSocket Errors**: Verify port 8765 is not blocked
3. **High CPU Usage**: Reduce packet display limits or disable charts
4. **Memory Issues**: Decrease MAX_PACKETS value

## 🚀 Advanced Features

### Multi-Interface Monitoring
Run multiple capture instances:
```bash
# Terminal 1
python netcap_manager.py capture --interface "eth0"

# Terminal 2  
python netcap_manager.py capture --interface "wlan0"
```

### Custom Security Rules
Modify the `checkSecurity()` function in index.html to add custom alerts:
```javascript
// Example: Alert on specific IP ranges
if (packet.src_ip.startsWith('10.0.0.')) {
    alerts.push({
        type: 'warning',
        message: 'Internal network traffic detected',
        packet: packet
    });
}
```

### API Integration
The WebSocket can be consumed by other applications:
```javascript
const socket = new WebSocket('ws://localhost:8765');
socket.onmessage = function(event) {
    const packet = JSON.parse(event.data);
    // Process packet data
};
```

## 📝 Production Checklist

- [ ] All dependencies installed
- [ ] TShark/Wireshark installed and accessible
- [ ] Network interface identified and accessible
- [ ] Firewall ports configured
- [ ] Performance settings tuned for your environment
- [ ] Log rotation configured
- [ ] Monitoring and alerting set up
- [ ] Backup and recovery procedures in place
- [ ] Security considerations reviewed
- [ ] User training completed

## 🆘 Support & Troubleshooting

### Common Issues
1. **Permission Denied**: Run with administrator/root privileges
2. **Interface Not Found**: Use exact interface name from `interfaces` command
3. **Port Already in Use**: Check if another instance is running
4. **Charts Not Loading**: Check browser console for JavaScript errors

### Performance Issues
- High packet rates may require tuning
- Consider dedicated hardware for production use
- Monitor system resources during peak usage

### Getting Help
- Check the console output for error messages
- Review the browser developer tools for JavaScript errors
- Ensure all system requirements are met

---

**NetCap Dashboard v2.0 Production** - Enterprise-Ready Network Analysis