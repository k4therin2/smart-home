# Access from Phone

## Quick Start

On your phone's browser, go to:

```
http://192.168.254.12:5001/
```

## How to Use

**Type:** Enter your command and tap "Send"
**Voice:** Tap the microphone button on your phone's keyboard to dictate

Try commands like:
- 🔥 "turn living room to fire"
- 🌊 "make me feel like I'm under the sea"
- 📚 "cozy reading light in the bedroom"
- ⚡ "energizing office lighting"
- 🌙 "romantic lighting for dinner"

## How It Works

- **Server:** Running on your Mac at http://localhost:5001
- **Local Network Access:** http://192.168.254.12:5001
- **Your Mac must be running** with `./start.sh` active
- Works on same WiFi network only

## Troubleshooting

**Can't connect from phone?**
1. Check Mac is on and server is running: `./start.sh status`
2. Both devices on same WiFi network?
3. Try restarting server: `./start.sh stop && ./start.sh`

**Server IP changed?**
Your Mac's IP might change. To find current IP:
```bash
ifconfig | grep "inet " | grep -v 127.0.0.1
```

Look for something like `inet 192.168.x.x`

## Bookmark It!

Add http://192.168.254.12:5001/ to your phone's home screen for quick access!

---

**Note:** Alexa integration is on hold until HA voice puck arrives (Dec).
Using web UI for now - it's actually faster and more reliable!
