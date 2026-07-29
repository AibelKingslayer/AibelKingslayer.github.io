---
title: "Building a Lightweight Python SIEM with Discord Notifications"
author: "Aibel Jaic Aju"
date: 2025-10-18
draft: false
tags: ["SIEM", "blue-team", "python", "windows", "detection", "discord", "monitoring"]
description: "How to build a lightweight, cost-effective SIEM for Windows environments using Python and Discord webhooks — making real-time security monitoring accessible without enterprise-grade budgets."
---

## Introduction

In the modern cybersecurity landscape, continuous monitoring and rapid incident response are critical components of an organization's defense strategy. Security Information and Event Management (SIEM) systems serve as the central nervous system of security operations, providing the visibility and intelligence needed to detect, investigate, and respond to threats.

This article explores the development of a lightweight, Python-based SIEM solution that leverages Discord webhooks for real-time alerting — making enterprise-grade security monitoring accessible to smaller organizations and individual security practitioners.

## Understanding SIEM: The Foundation of Security Monitoring

### What is SIEM?

Security Information and Event Management (SIEM) aggregates, normalizes, and analyzes security event data from diverse sources across an organization's IT infrastructure. By correlating events from multiple sources, SIEM systems enable security teams to identify patterns that might indicate malicious activity, policy violations, or system anomalies.

### Core SIEM Functions

- **Log Collection and Aggregation**: Centralized collection from servers, workstations, network devices, and security tools
- **Normalization and Parsing**: Converts varied log formats into a consistent structure for cross-source correlation
- **Real-Time Monitoring and Alerting**: Continuously analyzes incoming events against predefined rules
- **Correlation and Analysis**: Identifies patterns across multiple events — e.g., a failed login followed by a successful one from an unusual location
- **Compliance and Reporting**: Maintains audit trails and generates reports for regulatory requirements

### Why Organizations Need SIEM

Without centralized monitoring, security teams face:

- **Visibility gaps** — events scattered across numerous systems create blind spots
- **Alert fatigue** — individual tools generate thousands of daily alerts without centralized analysis
- **Slow incident response** — manual investigation across multiple systems delays containment
- **Resource constraints** — enterprise SIEMs like Splunk, IBM QRadar, or Microsoft Sentinel can cost tens of thousands to millions annually

## Architecture

### Design Philosophy

This implementation focuses on high-value Windows security events rather than trying to cover every possible use case. It prioritizes simplicity, ease of deployment, and practical utility — leveraging Discord as the notification layer to eliminate complex alert management infrastructure.

### Three Core Components

**1. Event Log Monitor**
Uses the `pywin32` library to interface directly with the Windows Event Log API, continuously polling for new events matching specified Event IDs.

**2. Event Parser and Analyzer**
Processes raw Windows Event Log XML entries, extracting key details (account names, timestamps, source systems, event-specific metadata) and applying context-appropriate formatting.

**3. Discord Notification Engine**
Constructs JSON payloads conforming to Discord's webhook API spec and transmits them via HTTPS POST. Near-instantaneous delivery to the security team's channel.

### Monitored Security Events

| Event ID | Description | Why It Matters |
|---|---|---|
| **4624** | Successful Logon | Baselines user behavior; detects off-hours or lateral movement |
| **4625** | Failed Logon | High volume → brute force; success after failures → compromise |
| **4720** | User Account Created | Common post-compromise persistence technique |
| **4723** | Password Change Attempt | Detects unauthorized account access |
| **4724** | Password Reset | Admin-initiated resets can indicate account takeover |
| **11707** | Application Installed | Unauthorized software = malware risk or policy violation |
| **6416** | USB Device Inserted | Data exfiltration, malware introduction, policy violations |

## Implementation

### Prerequisites

- **Administrative privileges** — required to access the Security Event Log
- **Windows Audit Policy configured** — some events are disabled by default
- **Discord webhook URL** — destination for all security alerts

### Configuring Windows Audit Policy

Run `gpedit.msc` and navigate to:
`Computer Configuration → Windows Settings → Security Settings → Advanced Audit Policy Configuration`

Enable the following:

| Category | Subcategory | Events |
|---|---|---|
| Account Logon | Audit Credential Validation | Success, Failure |
| Account Management | Audit User Account Management | Success |
| Logon/Logoff | Audit Logon | Success, Failure |
| Object Access | Audit Removable Storage | Success |
| Policy Change | Audit Audit Policy Change | Success |

Apply with:
```cmd
gpupdate /force
```

### Discord Notification Format

Each alert includes:
- **Event Classification** — descriptive event type label
- **Event ID Reference** — for Microsoft documentation lookup
- **Timestamp** — precise date/time in local timezone
- **Source System** — hostname of the generating system
- **Event Details** — parsed, formatted event-specific information

## Deployment

### Installation

```bash
pip install pywin32 requests
```

Clone the repository and configure the Discord webhook URL in the config file.

### Running the SIEM

**Interactive Mode** (testing and troubleshooting):
```powershell
python .\SIEM.py
```

After launching, you should see the monitor initializing:

![SIEM running and monitoring Windows Event Log](/images/posts/siem/siem-running.png)

**Service Mode** (production): Use NSSM (Non-Sucking Service Manager) to run as a Windows service that survives reboots and user logoffs.

### Validation

Generate a test event:
```cmd
net user john P@ssw0rd /add
```

This triggers Event ID 4720, which should produce a Discord notification within seconds:

![Discord alert for new user account creation](/images/posts/siem/siem-discord-alert.png)

Test other event types by attempting failed logons, changing passwords, or inserting a USB device.

## Security Considerations

### Protecting the Webhook URL

The Discord webhook URL functions as an authentication token. If compromised, an attacker can spam false alerts to hide genuine security events. Protect it by:

- Storing it in an encrypted config file or using Windows DPAPI
- Restricting file permissions on the config file
- Rotating the webhook URL periodically and immediately after suspected compromise

### Rate Limiting and Alert Management

High-volume environments may generate hundreds of events per hour. Implement:

- **Event batching** — aggregate similar events within a short window
- **Severity classification** — prioritize critical events over informational ones
- **Deduplication logic** — suppress repeated identical alerts

### Monitoring the Monitor

SIEM systems become critical infrastructure and must be monitored themselves:

- Verify the application process stays running
- Test Discord webhook connectivity periodically
- Generate heartbeat messages at regular intervals
- Alert if the monitoring application stops generating expected events

## Extending the Solution

### Adding New Event Types

1. Identify the Event ID using Event Viewer or Microsoft's documentation
2. Add it to the monitoring config (source, log name)
3. Implement a parsing function for the event's XML structure
4. Design a notification format conveying the essential information

### Integration Paths

- **Enterprise SIEM forwarding** — forward parsed events to Splunk or Elastic while maintaining the Discord layer as a lightweight parallel channel
- **Ticketing integration** — auto-create ServiceNow or Jira tickets for high-severity events
- **Threat intelligence enrichment** — check IPs against known malicious indicators, correlate users with identity threat intel

## Conclusion

This lightweight Python SIEM demonstrates that effective security monitoring doesn't require enterprise-scale budgets or infrastructure. By focusing on high-value security events and leveraging Discord for notifications, organizations can implement meaningful monitoring with minimal investment.

While this implementation isn't a replacement for enterprise SIEM in large, complex environments, it proves that the fundamental principles — continuous visibility, real-time alerting, and centralized analysis — are achievable with accessible tools.

The complete source code, documentation, and deployment guides are available at: [https://github.com/AibelKingslayer/SIEM-Python](https://github.com/AibelKingslayer/SIEM-Python)
