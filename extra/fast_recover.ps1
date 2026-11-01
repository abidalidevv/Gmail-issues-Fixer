# Google Account Rapid Recovery Automation Tool (PowerShell + ADB)
# Target: Auto-configure ADB, Reset Android Play Services Rate-Limit, Rotate Mobile 4G IP, and Launch Native No-QR Login

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ScriptDir

Write-Host "=====================================================" -ForegroundColor Cyan
Write-Host "   Google Account Rapid Recovery Tool (No-QR Flow)   " -ForegroundColor Yellow
Write-Host "=====================================================" -ForegroundColor Cyan

# Step 0: Ensure ADB is available (Auto-download portable if missing)
$AdbBin = "adb"
if (-not (Get-Command "adb" -ErrorAction SilentlyContinue)) {
    $PortableAdb = Join-Path $ScriptDir "platform-tools\adb.exe"
    if (-not (Test-Path $PortableAdb)) {
        Write-Host "`n[*] ADB system mein nahi mila. Google Official Platform-Tools download ho raha hai..." -ForegroundColor Yellow
        $ZipPath = Join-Path $ScriptDir "platform-tools.zip"
        $Url = "https://dl.google.com/android/repository/platform-tools-latest-windows.zip"
        
        try {
            [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
            Invoke-WebRequest -Uri $Url -OutFile $ZipPath -UseBasicParsing
            Write-Host "[*] Extracting platform-tools..." -ForegroundColor Yellow
            Expand-Archive -Path $ZipPath -DestinationPath $ScriptDir -Force
            Remove-Item $ZipPath -Force -ErrorAction SilentlyContinue
            Write-Host "[OK] ADB Platform-Tools setup complete!" -ForegroundColor Green
        } catch {
            Write-Host "[!] Download fail ho gaya: $_" -ForegroundColor Red
            pause
            Exit
        }
    }
    $AdbBin = $PortableAdb
}

# Step 1: Check ADB Connection
Write-Host "`n[1/4] Checking Android device connection via ADB..." -ForegroundColor Yellow
$adbCheck = & $AdbBin devices 2>$null | Select-String "device$"
if (-not $adbCheck) {
    Write-Host "[!] Koi Android device detect nahi hua!" -ForegroundColor Red
    Write-Host "    - Phone ko USB cable se PC se connect karein." -ForegroundColor White
    Write-Host "    - Phone Settings > Developer Options mein 'USB Debugging' ON karein." -ForegroundColor White
    Write-Host "    - Phone screen par 'Allow USB Debugging' ka popup accept karein." -ForegroundColor White
    pause
    Exit
}
Write-Host "[OK] Android Phone Connected Successfully!" -ForegroundColor Green

# Step 2: Rotate 4G IP via Airplane Mode
Write-Host "`n[2/4] Rotating 4G Mobile IP via Airplane Mode toggle..." -ForegroundColor Yellow
& $AdbBin shell cmd connectivity airplane-mode enable
Start-Sleep -Seconds 3
& $AdbBin shell cmd connectivity airplane-mode disable
Start-Sleep -Seconds 4
Write-Host "[OK] Clean Dynamic 4G Carrier IP Assigned!" -ForegroundColor Green

# Step 3: Clear Play Services Rate Limit Quota
Write-Host "`n[3/4] Purging GMS & GSF Rate-Limit databases..." -ForegroundColor Yellow
& $AdbBin shell pm clear com.google.android.gms >$null 2>&1
& $AdbBin shell pm clear com.google.android.gsf >$null 2>&1
Write-Host "[OK] Device 'Too Many Times' Counter reset to 0!" -ForegroundColor Green

# Step 4: Launch Native Add-Account Activity
Write-Host "`n[4/4] Launching Native Android Add-Account screen..." -ForegroundColor Yellow
& $AdbBin shell am start -a android.settings.ADD_ACCOUNT_SETTINGS >$null 2>&1

Write-Host "`n=====================================================" -ForegroundColor Green
Write-Host "SUCCESS! Phone screen par 'Google' choose karein." -ForegroundColor Green
Write-Host "Direct Email, Password, aur Authenticator App ka code mangay ga (NO QR CODE)!" -ForegroundColor White
Write-Host "Agar PC par 2FA code chahiye, run: python generate_totp.py <SecretKey>" -ForegroundColor Cyan
Write-Host "Login hotay hi https://myaccount.google.com/security se 10 Backup Codes nikaal lein!" -ForegroundColor Yellow
Write-Host "=====================================================" -ForegroundColor Green
pause
