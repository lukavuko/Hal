# Windows Webcam Setup for Hal

## Prerequisites
- Windows 10/11 with WSL2 enabled
- Docker Desktop running in WSL2 mode

## Step 1: Install usbipd-win on Windows

Open **PowerShell as Administrator** and run:

```powershell
winget install --interactive --exact dorssel.usbipd-win
```

Or download from: https://github.com/dorssel/usbipd-win/releases

## Step 2: Install USB/IP tools in WSL2

In your WSL2 terminal:

```bash
sudo apt update
sudo apt install linux-tools-virtual hwdata
sudo update-alternatives --install /usr/local/bin/usbip usbip `ls /usr/lib/linux-tools/*/usbip | tail -n1` 20
```

## Step 3: Share Webcam to WSL2

**In PowerShell (Administrator):**

List USB devices:
```powershell
usbipd list
```

Find your webcam (look for "Camera" or "Webcam"). Note the BUSID (e.g., 1-4).

Bind the webcam:
```powershell
usbipd bind --busid 1-4
```

Attach to WSL2:
```powershell
usbipd attach --wsl --busid 1-4
```

## Step 4: Verify in WSL2

In WSL2 terminal:
```bash
ls -la /dev/video*
```

You should see `/dev/video0` (or `/dev/video1`, etc.)

## Step 5: Launch Hal

```bash
cd services
docker-compose up -d
```

## Troubleshooting

**Webcam not appearing:**
```bash
# Check if USB device is attached
lsusb

# Check video devices
v4l2-ctl --list-devices
```

**Permission denied:**
```bash
sudo chmod 666 /dev/video0
```

**Reattach after reboot:**
After Windows reboot, re-run in PowerShell:
```powershell
usbipd attach --wsl --busid 1-4
```

## Auto-attach on boot (Optional)

Create a scheduled task in Windows to auto-attach the webcam on boot:

1. Open Task Scheduler
2. Create Basic Task
3. Trigger: At startup
4. Action: Start a program
5. Program: `usbipd`
6. Arguments: `attach --wsl --busid 1-4`
7. Check "Run with highest privileges"
