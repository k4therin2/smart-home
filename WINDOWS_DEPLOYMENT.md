# Windows Deployment Guide

This guide will help you deploy the Home Automation Agent on Windows using Docker Desktop.

## Prerequisites

1. **Install Docker Desktop for Windows**
   - Download from: https://www.docker.com/products/docker-desktop/
   - Requires Windows 10/11 Pro, Enterprise, or Education (64-bit)
   - Or Windows 10/11 Home with WSL 2 backend enabled
   - After installation, ensure Docker Desktop is running (check system tray)

2. **Install Git for Windows** (optional, for cloning)
   - Download from: https://git-scm.com/download/win
   - Or download the ZIP from GitHub directly

## Step-by-Step Deployment

### 1. Get the Code

**Option A: Using Git Bash**
```bash
git clone https://github.com/k4therin2/smart-home.git
cd smart-home
```

**Option B: Download ZIP**
- Go to https://github.com/k4therin2/smart-home
- Click "Code" → "Download ZIP"
- Extract to a folder like `C:\Users\YourName\smart-home`
- Open PowerShell or Command Prompt in that folder

### 2. Configure Environment Variables

**Using PowerShell:**
```powershell
Copy-Item .env.example .env
notepad .env
```

**Using Command Prompt:**
```cmd
copy .env.example .env
notepad .env
```

Edit the `.env` file and add:
- `ANTHROPIC_API_KEY` - Get from https://console.anthropic.com/
- `HA_TOKEN` - Generate in Home Assistant after first setup

### 3. Start the Services

**Using PowerShell or Command Prompt:**
```powershell
docker-compose up -d
```

This will:
- Download Home Assistant image (~500MB)
- Build the Agent image (~200MB)
- Start both containers
- First run takes 5-10 minutes

### 4. Access the Services

**Home Assistant:**
- Open browser: http://localhost:8123
- First time: Create admin account
- Generate Long-Lived Access Token:
  1. Click your profile (bottom left)
  2. Scroll to "Long-Lived Access Tokens"
  3. Click "Create Token"
  4. Copy the token
  5. Add to `.env` file as `HA_TOKEN`
  6. Restart agent: `docker-compose restart agent`

**Agent Web UI:**
- Open browser: http://localhost:5000
- Should work immediately after HA_TOKEN is configured

### 5. Common Windows-Specific Commands

**View running containers:**
```powershell
docker-compose ps
```

**View logs:**
```powershell
docker-compose logs -f agent          # Follow agent logs
docker-compose logs -f homeassistant  # Follow Home Assistant logs
```

**Restart services:**
```powershell
docker-compose restart agent
docker-compose restart homeassistant
```

**Stop everything:**
```powershell
docker-compose down
```

**Rebuild and restart:**
```powershell
docker-compose up -d --build
```

## Accessing from Other Devices

Find your Windows laptop's IP address:

**Using PowerShell:**
```powershell
ipconfig | findstr IPv4
```

**Using Command Prompt:**
```cmd
ipconfig | findstr IPv4
```

Look for your WiFi/Ethernet IPv4 address (e.g., `192.168.1.100`)

Then access from phone/tablet:
- Agent: `http://192.168.1.100:5000`
- Home Assistant: `http://192.168.1.100:8123`

## File Locations on Windows

Docker Desktop stores volumes in WSL 2. Your project files are in your clone directory:

- `C:\Users\YourName\smart-home\home-assistant-config\` - Home Assistant config
- `C:\Users\YourName\smart-home\logs\` - Agent logs
- `C:\Users\YourName\smart-home\data\` - API usage data
- `C:\Users\YourName\smart-home\prompts\` - Agent prompts

## Troubleshooting

### Docker Desktop not starting
- Ensure virtualization is enabled in BIOS
- Enable WSL 2: `wsl --install` in PowerShell (admin)
- Restart Windows

### "Port already in use" errors
```powershell
# Find what's using port 8123 or 5000
netstat -ano | findstr :8123
netstat -ano | findstr :5000

# Stop the process (use PID from above)
taskkill /PID <process_id> /F
```

### Firewall blocking access from other devices
- Open Windows Firewall settings
- Allow port 5000 and 8123 for private networks
- Or temporarily disable firewall for testing

### "drive is not shared" error
- Open Docker Desktop settings
- Go to Resources → File Sharing
- Add the drive where your project is located (e.g., `C:`)

## Automatic Startup (Optional)

To run on Windows startup:

1. Open Docker Desktop settings
2. General → Enable "Start Docker Desktop when you log in"
3. The containers will auto-start with Docker (due to `restart: unless-stopped`)

## Performance Tips

- **Allocate more resources**: Docker Desktop Settings → Resources
  - Memory: At least 4GB (6GB recommended)
  - CPUs: At least 2 cores

- **Use WSL 2 backend**: Settings → General → "Use the WSL 2 based engine"

## Windows Terminal (Recommended)

For a better command-line experience:
- Install Windows Terminal from Microsoft Store
- Better tab support, color coding, and copying/pasting
- Works great with PowerShell and Command Prompt

## Next Steps

Once everything is running:
1. Configure your Philips Hue in Home Assistant (http://localhost:8123)
2. Test the agent: http://localhost:5000
3. Try commands like "turn living room to fire"
4. Access from your phone on the same WiFi network

## Need Help?

- Docker Desktop docs: https://docs.docker.com/desktop/windows/
- Home Assistant docs: https://www.home-assistant.io/installation/windows
- Project issues: https://github.com/k4therin2/smart-home/issues
