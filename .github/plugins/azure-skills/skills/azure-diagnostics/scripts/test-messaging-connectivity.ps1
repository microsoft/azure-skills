<#
.SYNOPSIS
    Probes reachability of an Azure Service Bus / Event Hubs namespace and prints
    a normalized per-check report.
.DESCRIPTION
    Runs the mechanical connectivity probe for a messaging namespace: DNS
    resolution, HTTPS reachability, and TCP connectivity to the well-known
    messaging ports (AMQP 5671/5672, HTTPS 443, and — with -Kafka — Event Hubs
    Kafka 9093). Emits one normalized table plus a summary so the result is clear
    without re-inspecting raw Test-NetConnection / Resolve-DnsName output.

    A blocked port is a valid diagnostic result, not a failure. Choosing which
    namespace to test and diagnosing a blocked port (IP firewall vs. corporate
    proxy vs. NSG) require judgment and stay in the skill prose.
.PARAMETER Namespace
    The messaging namespace. May be a full FQDN (e.g.
    "contoso.servicebus.windows.net") or a bare namespace name (e.g. "contoso");
    when no dot is present, ".servicebus.windows.net" is appended automatically.
.PARAMETER Kafka
    Also probe the Event Hubs Kafka endpoint on port 9093.
.EXAMPLE
    .\test-messaging-connectivity.ps1 -Namespace contoso
    # Tests contoso.servicebus.windows.net (DNS, HTTPS, AMQP 5671/5672, 443)
.EXAMPLE
    .\test-messaging-connectivity.ps1 -Namespace contoso.servicebus.windows.net -Kafka
    # Also probes Event Hubs Kafka port 9093
#>
param(
    [string]$Namespace,
    [switch]$Kafka
)

if ([string]::IsNullOrWhiteSpace($Namespace)) {
    Write-Error "Namespace is required. Usage: test-messaging-connectivity.ps1 -Namespace <namespace> [-Kafka]"
    exit 2
}

# Accept a bare namespace name or a full FQDN.
$fqdn = if ($Namespace -like "*.*") { $Namespace } else { "$Namespace.servicebus.windows.net" }

Write-Host "Testing messaging connectivity for: $fqdn"
Write-Host ""

# ── DNS resolution ────────────────────────────────────────────────────────────
$resolvedIp = $null
try {
    $records = Resolve-DnsName -Name $fqdn -ErrorAction Stop
    $resolvedIp = ($records | Where-Object { $_.IPAddress } | Select-Object -First 1).IPAddress
} catch {
    try {
        $resolvedIp = ([System.Net.Dns]::GetHostAddresses($fqdn) | Select-Object -First 1).IPAddressToString
    } catch {
        $resolvedIp = $null
    }
}

$dnsOk = [bool]$resolvedIp
$dnsResult = if ($dnsOk) { "resolved ($resolvedIp)" } else { "NOT RESOLVED" }

# ── TCP port probe ────────────────────────────────────────────────────────────
function Test-TcpPort {
    param([string]$TargetHost, [int]$Port)
    try {
        $client = [System.Net.Sockets.TcpClient]::new()
        $async = $client.BeginConnect($TargetHost, $Port, $null, $null)
        $ok = $async.AsyncWaitHandle.WaitOne(5000, $false)
        if ($ok -and $client.Connected) {
            $client.EndConnect($async)
            $client.Close()
            return $true
        }
        $client.Close()
        return $false
    } catch {
        return $false
    }
}

function Get-PortResult {
    param([int]$Port)
    if (Test-TcpPort -TargetHost $fqdn -Port $Port) { "reachable" } else { "BLOCKED" }
}

# ── HTTPS reachability ────────────────────────────────────────────────────────
# On success the namespace returns an Atom feed or HTTP 401 — either proves the
# endpoint is reachable. A connection failure means blocked. -SkipHttpErrorCheck
# is intentionally not used: it is unavailable in Windows PowerShell 5.1, so we
# instead treat an HTTP-error response (caught below) as proof of reachability.
function Get-HttpsResult {
    try {
        $resp = Invoke-WebRequest -Uri "https://$fqdn/" -Method Get -TimeoutSec 15 `
            -UseBasicParsing -ErrorAction Stop
        return "reachable (HTTP $($resp.StatusCode))"
    } catch {
        # An HTTP error response (e.g. 401) still proves reachability. The
        # exception type differs between PowerShell editions (WebException in
        # 5.1, HttpResponseException in 7+) but both expose Response.StatusCode.
        $status = $_.Exception.Response.StatusCode
        if ($null -ne $status) {
            return "reachable (HTTP $([int]$status))"
        }
        # Fall back to a plain TCP probe of 443.
        if (Test-TcpPort -TargetHost $fqdn -Port 443) {
            return "reachable (TCP 443 open)"
        }
        return "BLOCKED"
    }
}

$rows = [System.Collections.Generic.List[object]]::new()
$rows.Add([PSCustomObject]@{ Check = "DNS resolution"; Port = "-"; Result = $dnsResult })

if ($dnsOk) {
    $rows.Add([PSCustomObject]@{ Check = "HTTPS reachability"; Port = "443";  Result = (Get-HttpsResult) })
    $rows.Add([PSCustomObject]@{ Check = "AMQP over TLS";      Port = "5671"; Result = (Get-PortResult 5671) })
    $rows.Add([PSCustomObject]@{ Check = "AMQP";               Port = "5672"; Result = (Get-PortResult 5672) })
    $rows.Add([PSCustomObject]@{ Check = "HTTPS / WebSockets"; Port = "443";  Result = (Get-PortResult 443) })
    if ($Kafka) {
        $rows.Add([PSCustomObject]@{ Check = "Event Hubs Kafka"; Port = "9093"; Result = (Get-PortResult 9093) })
    }
} else {
    $rows.Add([PSCustomObject]@{ Check = "HTTPS reachability"; Port = "443";  Result = "skipped (DNS failed)" })
    $rows.Add([PSCustomObject]@{ Check = "AMQP over TLS";      Port = "5671"; Result = "skipped (DNS failed)" })
    $rows.Add([PSCustomObject]@{ Check = "AMQP";               Port = "5672"; Result = "skipped (DNS failed)" })
    $rows.Add([PSCustomObject]@{ Check = "HTTPS / WebSockets"; Port = "443";  Result = "skipped (DNS failed)" })
    if ($Kafka) {
        $rows.Add([PSCustomObject]@{ Check = "Event Hubs Kafka"; Port = "9093"; Result = "skipped (DNS failed)" })
    }
}

$rows | Format-Table -AutoSize

if (-not $dnsOk) {
    Write-Host "Summary: could not resolve $fqdn. Check the namespace name and DNS/private-endpoint configuration before testing ports."
} else {
    Write-Host "Summary: DNS resolved to $resolvedIp. 'reachable' ports accept TCP connections; any 'BLOCKED' port points to an IP firewall, NSG, corporate proxy, or private-endpoint restriction to investigate. Port 443 (WebSockets) can be used as a fallback when AMQP ports 5671/5672 are blocked."
}
