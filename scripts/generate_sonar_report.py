#!/usr/bin/env python3
"""
Generate SonarQube Generic Issue Import JSON from C static analyzers:
- Cppcheck (XML -> Sonar JSON)
- Flawfinder / Clang-Tidy / Checkpatch
"""

import os
import sys
import json
import xml.etree.ElementTree as ET
import subprocess
from pathlib import Path

def run_cppcheck() -> list:
    issues = []
    xml_output = "cppcheck-results.xml"
    
    cmd = [
        "cppcheck",
        "--enable=all",
        "--inconclusive",
        "--xml",
        "--xml-version=2",
        "src/"
    ]
    
    res = subprocess.run(cmd, capture_output=True, text=True)
    # Cppcheck writes XML to stderr
    xml_data = res.stderr if res.stderr else res.stdout
    
    if not xml_data.strip():
        return issues

    try:
        root = ET.fromstring(xml_data)
        errors = root.findall(".//error")
        for err in errors:
            rule_id = err.get("id", "cppcheck-generic")
            msg = err.get("msg", "Issue found by cppcheck")
            severity_str = err.get("severity", "style")
            
            # Map cppcheck severity to SonarQube
            # Sonar severities: INFO, MINOR, MAJOR, CRITICAL, BLOCKER
            # Sonar types: BUG, VULNERABILITY, CODE_SMELL
            sonar_severity = "MAJOR"
            sonar_type = "CODE_SMELL"
            
            if severity_str in ["error"]:
                sonar_severity = "CRITICAL"
                sonar_type = "BUG"
            elif severity_str in ["warning"]:
                sonar_severity = "MAJOR"
                sonar_type = "BUG"
            elif severity_str in ["portability", "performance"]:
                sonar_severity = "MAJOR"
                sonar_type = "CODE_SMELL"
            elif severity_str in ["style"]:
                sonar_severity = "MINOR"
                sonar_type = "CODE_SMELL"
            elif severity_str in ["information"]:
                sonar_severity = "INFO"
                sonar_type = "CODE_SMELL"

            loc = err.find("location")
            if loc is not None:
                file_path = loc.get("file", "")
                line_str = loc.get("line", "1")
                try:
                    line_num = max(1, int(line_str))
                except ValueError:
                    line_num = 1

                # Ensure relative path matches sonar sources
                if file_path.startswith("./"):
                    file_path = file_path[2:]

                issues.append({
                    "engineId": "cppcheck",
                    "ruleId": rule_id,
                    "severity": sonar_severity,
                    "type": sonar_type,
                    "primaryLocation": {
                        "message": msg,
                        "filePath": file_path,
                        "textRange": {
                            "startLine": line_num,
                            "endLine": line_num
                        }
                    }
                })
    except Exception as e:
        print(f"Error parsing cppcheck XML: {e}", file=sys.stderr)

    return issues

def run_flawfinder() -> list:
    issues = []
    cmd = ["flawfinder", "--csv", "src/"]
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode not in [0, 1] or not res.stdout.strip():
        return issues

    lines = res.stdout.strip().splitlines()
    if len(lines) <= 1:
        return issues

    # CSV Header: File,Line,Column,DefaultLevel,Level,Warning,Suggestion,Category,RuleID,Context,...
    import csv
    reader = csv.DictReader(lines)
    for row in reader:
        try:
            fpath = row.get("File", "")
            if fpath.startswith("./"):
                fpath = fpath[2:]
            line = max(1, int(row.get("Line", 1)))
            rule_id = row.get("RuleID", "flawfinder-vuln")
            msg = f"{row.get('Warning', 'Security finding')}: {row.get('Suggestion', '')}".strip()
            level = int(row.get("Level", 1))

            severity = "MINOR"
            if level >= 4:
                severity = "BLOCKER"
            elif level == 3:
                severity = "CRITICAL"
            elif level == 2:
                severity = "MAJOR"

            issues.append({
                "engineId": "flawfinder",
                "ruleId": rule_id,
                "severity": severity,
                "type": "VULNERABILITY",
                "primaryLocation": {
                    "message": msg,
                    "filePath": fpath,
                    "textRange": {
                        "startLine": line,
                        "endLine": line
                    }
                }
            })
        except Exception:
            continue

    return issues

def main():
    all_issues = []
    
    # Run cppcheck
    if subprocess.run(["which", "cppcheck"], capture_output=True).returncode == 0:
        print("[*] Running cppcheck...")
        all_issues.extend(run_cppcheck())
    else:
        print("[!] cppcheck not installed, skipping.")

    # Run flawfinder if available
    if subprocess.run(["which", "flawfinder"], capture_output=True).returncode == 0:
        print("[*] Running flawfinder...")
        all_issues.extend(run_flawfinder())
    else:
        print("[!] flawfinder not installed, skipping.")

    report = {"issues": all_issues}
    output_path = Path("sonar-issues.json")
    output_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"[+] Generated {output_path} with {len(all_issues)} issues for SonarQube.")

if __name__ == "__main__":
    main()
