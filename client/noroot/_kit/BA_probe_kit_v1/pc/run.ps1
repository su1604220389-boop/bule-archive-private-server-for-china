# run.ps1 -- one-shot launcher for BA Prober
# ASCII only.
param(
    [ValidateSet("passthrough","logonly","tls")]
    [string]$Mode = "logonly",
    [int]$Port = 7890,
    [string]$Servers = "http://127.0.0.1:5000/api/",
    [int]$State = 0,
    [string]$Catalog = "https://static.bluearchive-cn.com/prodm39"
)

$ErrorActionPreference = "Stop"
$here = Split-Path -Parent $MyInvocation.MyCommand.Path

# --- python ---------------------------------------------------------------
$py = (Get-Command python -ErrorAction SilentlyContinue)
if (-not $py) { $py = (Get-Command py -ErrorAction SilentlyContinue) }
if (-not $py) { throw "python not found on PATH" }
$python = $py.Source
Write-Host "[*] python = $python"

# --- certs ----------------------------------------------------------------
$leaf = Join-Path $here "certs\leaf.crt"
$key  = Join-Path $here "certs\leaf.key"
if ($Mode -eq "tls" -and (-not (Test-Path $leaf) -or -not (Test-Path $key))) {
    Write-Host "[*] certs missing, generating..."
    & (Join-Path $here "make_certs.ps1")
    if (-not (Test-Path $leaf)) { throw "cert generation failed" }
}

# --- adb reverse (so the phone can use 127.0.0.1) -------------------------
$adb = (Get-Command adb -ErrorAction SilentlyContinue).Source
if ($adb) {
    $devs = (& $adb devices) -split "`r?`n" | Where-Object { $_ -match "\tdevice$" }
    if ($devs) {
        Write-Host "[*] adb device present, setting reverse tcp:$Port"
        & $adb reverse "tcp:$Port" "tcp:$Port" | Out-Null
        Write-Host "    phone Wi-Fi proxy -> 127.0.0.1:$Port"
    } else {
        Write-Host "[!] no adb device; use the LAN IP below instead of 127.0.0.1"
    }
} else {
    Write-Host "[!] adb not found"
}

# --- LAN IP + firewall hint ----------------------------------------------
$ip = (Get-NetIPAddress -AddressFamily IPv4 -ErrorAction SilentlyContinue |
       Where-Object { $_.IPAddress -notlike "127.*" -and $_.IPAddress -notlike "169.254.*" -and $_.PrefixOrigin -ne "WellKnown" } |
       Sort-Object -Property InterfaceMetric | Select-Object -First 1).IPAddress
Write-Host ""
Write-Host "================================================================"
Write-Host " mode    : $Mode"
Write-Host " listen  : 0.0.0.0:$Port"
if ($ip) { Write-Host " phone   : Wi-Fi proxy = $ip`:$Port" }
Write-Host "================================================================"
if ($ip) {
    $fw = "New-NetFirewallRule -DisplayName 'BA Prober' -Direction Inbound -Protocol TCP -LocalPort $Port -Action Allow"
    Write-Host " if the phone cannot connect, run this once in an ADMIN shell:"
    Write-Host "   $fw"
    Write-Host ""
}

# --- run ------------------------------------------------------------------
$argsList = @(
    (Join-Path $here "state_gw.py"),
    "--mode", $Mode,
    "--port", "$Port",
    "--cert", $leaf,
    "--key",  $key,
    "--servers", $Servers,
    "--state", "$State",
    "--catalog", $Catalog
)
& $python @argsList
