#!/usr/bin/env python3
"""
Generate SonarQube Generic Issue Import JSON from C static analyzers:
- Cppcheck (XML -> Sonar JSON)
- Flawfinder (CSV -> Sonar JSON)
Produces the modern SonarQube schema including 'rules' and 'issues'.
"""

import os
import sys
import json
import csv
import xml.etree.ElementTree as ET
import subprocess
from pathlib import Path

def run_cppcheck() -> tuple:
    rules = []
    issues = []
    rule_ids = set()

    cmd = [
        "cppcheck",
        "--enable=all",
        "--inconclusive",
        "--xml",
        "--xml-version=2",
        "src/"
    ]

    res = subprocess.run(cmd, capture_output=True, text=True)
    xml_data = res.stderr if res.stderr else res.stdout

    if not xml_data.strip():
        return rules, issues

    try:
        root = ET.fromstring(xml_data)
        errors = root.findall(".//error")
        for err in errors:
            rule_id = err.get("id", "cppcheck-generic")
            msg = err.get("msg", "Issue found by cppcheck")
            severity_str = err.get("severity", "style")

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

            if rule_id not in rule_ids:
                rules.append({
                    "id": rule_id,
                    "name": f"Cppcheck: {rule_id}",
                    "description": msg,
                    "engineId": "cppcheck",
                    "cleanCodeAttribute": "CONVENTIONAL",
                    "impacts": [
                        {
                            "softwareQuality": "MAINTAINABILITY" if sonar_type == "CODE_SMELL" else "RELIABILITY",
                            "severity": "MEDIUM"
                        }
                    ]
                })
                rule_ids.add(rule_id)

            loc = err.find("location")
            if loc is not None:
                file_path = loc.get("file", "")
                line_str = loc.get("line", "1")
                try:
                    line_num = max(1, int(line_str))
                except ValueError:
                    line_num = 1

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

    return rules, issues

def run_flawfinder() -> tuple:
    rules = []
    issues = []
    rule_ids = set()

    cmd = ["flawfinder", "--csv", "src/"]
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode not in [0, 1] or not res.stdout.strip():
        return rules, issues

    lines = res.stdout.strip().splitlines()
    if len(lines) <= 1:
        return rules, issues

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

            if rule_id not in rule_ids:
                rules.append({
                    "id": rule_id,
                    "name": f"Flawfinder: {rule_id}",
                    "description": msg,
                    "engineId": "flawfinder",
                    "cleanCodeAttribute": "TRUSTWORTHY",
                    "impacts": [
                        {
                            "softwareQuality": "SECURITY",
                            "severity": "HIGH" if level >= 3 else "MEDIUM"
                        }
                    ]
                })
                rule_ids.add(rule_id)

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

    return rules, issues

def main():
    all_rules = []
    all_issues = []

    if subprocess.run(["which", "cppcheck"], capture_output=True).returncode == 0:
        print("[*] Running cppcheck...")
        r, i = run_cppcheck()
        all_rules.extend(r)
        all_issues.extend(i)
    else:
        print("[!] cppcheck not installed, skipping.")

    if subprocess.run(["which", "flawfinder"], capture_output=True).returncode == 0:
        print("[*] Running flawfinder...")
        r, i = run_flawfinder()
        all_rules.extend(r)
        all_issues.extend(i)
    else:
        print("[!] flawfinder not installed, skipping.")

    report = {
        "rules": all_rules,
        "issues": all_issues
    }
    output_path = Path("sonar-issues.json")
    output_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"[+] Generated {output_path} with {len(all_rules)} rules and {len(all_issues)} issues for SonarQube.")

if __name__ == "__main__":
    main()
