# make_certs.ps1 -- generate a throwaway CA + leaf cert for BA Prober
# ASCII only on purpose (avoid PowerShell encoding issues on zh-CN systems).
# Notes:
#   * we deliberately keep $ErrorActionPreference = "Continue" here, because
#     redirecting a native command's stderr (2>&1) with "Stop" makes PowerShell
#     throw on perfectly normal openssl chatter ("Certificate request self-signature ok").
#   * shell-out goes through cmd.exe so quoting/exit code behave predictably.

$ErrorActionPreference = "Continue"
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$dir  = Join-Path $here "certs"
New-Item -ItemType Directory -Force -Path $dir | Out-Null

# --- locate openssl -------------------------------------------------------
$cands = @(
    "C:\msys64\ucrt64\bin\openssl.exe",
    "C:\msys64\mingw64\bin\openssl.exe",
    "C:\Program Files\Git\usr\bin\openssl.exe",
    "C:\Program Files\OpenSSL-Win64\bin\openssl.exe",
    "openssl"
)
$openssl = $null
foreach ($c in $cands) {
    if ($c -eq "openssl") {
        $g = Get-Command openssl -ErrorAction SilentlyContinue
        if ($g) { $openssl = $g.Source; break }
    } elseif (Test-Path $c) {
        $openssl = $c; break
    }
}
if (-not $openssl) { throw "openssl not found. install Git-for-Windows or msys2, or put openssl.exe on PATH." }
Write-Host "[*] openssl = $openssl"

$caKey  = Join-Path $dir "ca.key"
$caCrt  = Join-Path $dir "ca.crt"
$leafKey= Join-Path $dir "leaf.key"
$leafCsr= Join-Path $dir "leaf.csr"
$leafCrt= Join-Path $dir "leaf.crt"
$cnf    = Join-Path $dir "leaf.cnf"

# --- leaf SAN config ------------------------------------------------------
$san = @(
    "DNS:*.bluearchive-cn.com",
    "DNS:bluearchive-cn.com",
    "DNS:*.yostar.cn",
    "DNS:yostar.cn",
    "DNS:*.yostar.net",
    "DNS:*.yostar.com",
    "DNS:*.aliyuncs.com",
    "DNS:*.adjust.cn",
    "IP:127.0.0.1"
) -join ","

@"
[req]
prompt             = no
distinguished_name = dn
x509_extensions    = v3leaf
[dn]
CN = *.bluearchive-cn.com
O  = BA Prober
[v3leaf]
basicConstraints       = CA:FALSE
keyUsage               = digitalSignature, keyEncipherment, keyAgreement
extendedKeyUsage       = serverAuth
subjectAltName         = $san
"@ | Set-Content -Path $cnf -Encoding ascii

function Run-Openssl([string[]]$a) {
    $quoted = ($a | ForEach-Object { if ($_ -match '[\s"]') { '"' + ($_ -replace '"','\"') + '"' } else { $_ } }) -join ' '
    $out = & cmd /c "`"$openssl`" $quoted 2>&1"
    $code = $LASTEXITCODE
    if ($out) { $out | ForEach-Object { Write-Host "    $_" } }
    if ($code -ne 0) { throw "openssl failed ($code): $quoted" }
}

Write-Host "[1/4] CA key + cert (10 years)"
if (-not (Test-Path $caKey)) { Run-Openssl @("genrsa","-out",$caKey,"2048") }
Run-Openssl @("req","-x509","-new","-nodes","-key",$caKey,"-sha256","-days","3650",
              "-out",$caCrt,"-subj","/CN=BA Prober Root CA/O=BA Prober")

Write-Host "[2/4] leaf key"
if (-not (Test-Path $leafKey)) { Run-Openssl @("genrsa","-out",$leafKey,"2048") }

Write-Host "[3/4] leaf CSR"
Run-Openssl @("req","-new","-key",$leafKey,"-out",$leafCsr,"-config",$cnf)

Write-Host "[4/4] sign leaf with our CA (825 days)"
Run-Openssl @("x509","-req","-in",$leafCsr,"-CA",$caCrt,"-CAkey",$caKey,
              "-CAcreateserial","-out",$leafCrt,"-days","825","-sha256",
              "-extfile",$cnf,"-extensions","v3leaf")

Write-Host ""
Write-Host "== done =="
Write-Host "  CA   : $caCrt"
Write-Host "  leaf : $leafCrt"
Write-Host "  key  : $leafKey"
Write-Host ""
$sanOut = & cmd /c "`"$openssl`" x509 -in `"$leafCrt`" -noout -text 2>&1" | Select-String -Pattern "DNS:" -SimpleMatch
if ($sanOut) { Write-Host "  SAN  : $($sanOut -join ' ')" }
Write-Host ""
Write-Host "next:  .\run.ps1 -Mode passthrough"
