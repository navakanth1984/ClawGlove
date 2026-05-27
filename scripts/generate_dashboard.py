import os
import csv
import json
import sys

def generate_dashboard():
    """Compiles telemetry spreadsheets and partitioned warehouse logs into a 4-tab console."""
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    analytics_dir = os.path.join(base_dir, "analytics")
    warehouse_dir = os.path.join(analytics_dir, "warehouse")
    
    perf_csv = os.path.join(analytics_dir, "agent-performance.csv")
    token_csv = os.path.join(analytics_dir, "token-usage.csv")
    registry_yaml = os.path.join(base_dir, "registry", "manifest.yaml")
    dest_html = os.path.join(analytics_dir, "dashboard.html")
    
    print(f"[*] Reading telemetry from: {analytics_dir}")
    
    # 1. Parse Agent Performance CSV
    perf_data = []
    total_tokens_in = 0
    total_tokens_out = 0
    total_cost = 0.0
    total_retries = 0
    success_count = 0
    
    if os.path.exists(perf_csv):
        try:
            with open(perf_csv, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    perf_data.append(row)
                    total_tokens_in += int(row.get("tokens_in", 0))
                    total_tokens_out += int(row.get("tokens_out", 0))
                    total_cost += float(row.get("cost_usd", 0.0))
                    total_retries += int(row.get("retries", 0))
                    if row.get("status", "").upper() == "SUCCESS":
                        success_count += 1
        except Exception as e:
            print(f"[WARN] Performance CSV empty or missing: {e}")
                    
    # 2. Parse Token Usage CSV
    token_data = []
    total_tokens_consumed = 0
    if os.path.exists(token_csv):
        try:
            with open(token_csv, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    token_data.append(row)
                    total_tokens_consumed += int(row.get("tokens_consumed", 0))
        except Exception as e:
            print(f"[WARN] Token usage CSV empty or missing: {e}")
                
    # 3. Parse Registry Active Skills Capabilities
    skills_data = []
    if os.path.exists(registry_yaml):
        try:
            import yaml
            with open(registry_yaml, "r", encoding="utf-8") as f:
                reg = yaml.safe_load(f)
                skills_data = reg.get("active_skills", [])
        except Exception as e:
            print(f"[WARN] Failed parsing registry YAML for dashboard: {e}")

    # 4. Parse Warehouse Partitions
    warehouse_logs = []
    policy_violations = []
    
    partitions = {
        "executions": os.path.join(warehouse_dir, "executions"),
        "policies": os.path.join(warehouse_dir, "policies"),
        "escalations": os.path.join(warehouse_dir, "escalations"),
        "simulations": os.path.join(warehouse_dir, "simulations")
    }
    
    for key, path in partitions.items():
        if os.path.exists(path):
            for file in os.listdir(path):
                if file.endswith(".json"):
                    file_path = os.path.join(path, file)
                    try:
                        with open(file_path, "r", encoding="utf-8") as f:
                            event = json.load(f)
                            
                        warehouse_logs.append(event)
                        
                        # Filter out violations
                        if event.get("event_type") in ["POLICY_VIOLATION", "DELEGATION_VIOLATION"]:
                            policy_violations.append(event)
                    except Exception as e:
                        pass
                        
    # Sort warehouse logs by timestamp descending
    warehouse_logs.sort(key=lambda x: x.get("timestamp", ""), reverse=True)

    success_rate = (success_count / len(perf_data) * 100) if perf_data else 100.0

    # Build gorgeous 4-tab HTML Dashboard
    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ACDLC v1.6 Distributed Observability Console</title>
    <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;800&family=Space+Grotesk:wght@400;700&display=swap" rel="stylesheet">
    <style>
        :root {{
            --bg-base: #0b0f19;
            --bg-surface: rgba(22, 28, 45, 0.45);
            --bg-card: rgba(30, 41, 59, 0.7);
            --border-glow: rgba(99, 102, 241, 0.2);
            --color-primary: #818cf8;
            --color-secondary: #c084fc;
            --color-success: #34d399;
            --color-warning: #fbbf24;
            --color-error: #f87171;
            --text-main: #f1f5f9;
            --text-muted: #94a3b8;
            --glass-blur: blur(12px);
        }}

        * {{
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }}

        body {{
            background-color: var(--bg-base);
            color: var(--text-main);
            font-family: 'Outfit', sans-serif;
            background-image: radial-gradient(circle at 10% 20%, rgba(129, 140, 248, 0.05) 0%, transparent 40%),
                              radial-gradient(circle at 90% 80%, rgba(192, 132, 252, 0.05) 0%, transparent 40%);
            min-height: 100vh;
            padding: 2.5rem;
        }}

        .dashboard-container {{
            max-width: 1400px;
            margin: 0 auto;
        }}

        header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 2rem;
            border-bottom: 1px solid rgba(255, 255, 255, 0.05);
            padding-bottom: 1.5rem;
        }}

        .logo-title h1 {{
            font-family: 'Space Grotesk', sans-serif;
            font-weight: 800;
            font-size: 2.5rem;
            background: linear-gradient(to right, var(--color-primary), var(--color-secondary));
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            margin-bottom: 0.25rem;
        }}

        .logo-title p {{
            color: var(--text-muted);
            font-size: 1rem;
        }}

        .badge-v16 {{
            background: rgba(192, 132, 252, 0.15);
            border: 1px solid var(--color-secondary);
            color: var(--color-secondary);
            padding: 0.35rem 0.75rem;
            border-radius: 9999px;
            font-weight: 600;
            font-size: 0.85rem;
            letter-spacing: 0.05em;
        }}

        /* Navigation Tabs */
        .tabs-nav {{
            display: flex;
            gap: 1rem;
            margin-bottom: 2rem;
            border-bottom: 1px solid rgba(255, 255, 255, 0.05);
            padding-bottom: 0.5rem;
        }}

        .tab-btn {{
            background: transparent;
            border: none;
            color: var(--text-muted);
            font-size: 1rem;
            font-weight: 600;
            padding: 0.75rem 1.5rem;
            cursor: pointer;
            border-radius: 8px;
            transition: all 0.3s ease;
        }}

        .tab-btn:hover {{
            color: var(--text-main);
            background: rgba(255, 255, 255, 0.02);
        }}

        .tab-btn.active {{
            color: var(--color-primary);
            background: rgba(129, 140, 248, 0.1);
            border-bottom: 2px solid var(--color-primary);
        }}

        .tab-content {{
            display: none;
            animation: fadeIn 0.4s ease forwards;
        }}

        .tab-content.active {{
            display: block;
        }}

        /* Metrics grid */
        .metrics-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
            gap: 1.5rem;
            margin-bottom: 3rem;
        }}

        .card-metric {{
            background: var(--bg-surface);
            border: 1px solid rgba(255, 255, 255, 0.05);
            border-radius: 16px;
            padding: 1.5rem;
            backdrop-filter: var(--glass-blur);
            transition: all 0.3s ease;
            position: relative;
            overflow: hidden;
        }}

        .card-metric:hover {{
            transform: translateY(-3px);
            border-color: var(--border-glow);
            box-shadow: 0 10px 25px -5px rgba(99, 102, 241, 0.1);
        }}

        .card-metric h3 {{
            color: var(--text-muted);
            font-size: 0.9rem;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            margin-bottom: 0.75rem;
        }}

        .card-metric .metric-value {{
            font-family: 'Space Grotesk', sans-serif;
            font-size: 2.2rem;
            font-weight: 700;
            color: #ffffff;
        }}

        .card-metric .metric-subtext {{
            font-size: 0.85rem;
            color: var(--text-muted);
            margin-top: 0.5rem;
        }}

        .layout-main {{
            display: grid;
            grid-template-columns: 2fr 1fr;
            gap: 2rem;
            margin-bottom: 3rem;
        }}

        @media (max-width: 1024px) {{
            .layout-main {{
                grid-template-columns: 1fr;
            }}
        }}

        .section-box {{
            background: var(--bg-surface);
            border: 1px solid rgba(255, 255, 255, 0.05);
            border-radius: 20px;
            padding: 2rem;
            backdrop-filter: var(--glass-blur);
            margin-bottom: 2rem;
        }}

        .section-box h2 {{
            font-family: 'Space Grotesk', sans-serif;
            font-size: 1.4rem;
            margin-bottom: 1.5rem;
            display: flex;
            align-items: center;
            gap: 0.5rem;
        }}

        /* Table design */
        table {{
            width: 100%;
            border-collapse: collapse;
            text-align: left;
        }}

        th {{
            color: var(--text-muted);
            font-weight: 600;
            font-size: 0.85rem;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            padding: 1rem;
            border-bottom: 1px solid rgba(255, 255, 255, 0.05);
        }}

        td {{
            padding: 1rem;
            border-bottom: 1px solid rgba(255, 255, 255, 0.02);
            font-size: 0.95rem;
        }}

        tr:hover td {{
            background: rgba(255, 255, 255, 0.02);
        }}

        .status-badge {{
            display: inline-block;
            padding: 0.25rem 0.5rem;
            border-radius: 6px;
            font-size: 0.8rem;
            font-weight: 600;
            text-transform: uppercase;
        }}

        .status-success {{ background: rgba(52, 211, 153, 0.1); color: var(--color-success); }}
        .status-error {{ background: rgba(248, 113, 113, 0.1); color: var(--color-error); }}
        .status-warn {{ background: rgba(251, 191, 36, 0.1); color: var(--color-warning); }}

        /* Token chart lists */
        .token-chart-list {{
            display: flex;
            flex-direction: column;
            gap: 1.25rem;
        }}

        .token-bar-item {{
            display: flex;
            flex-direction: column;
            gap: 0.5rem;
        }}

        .token-bar-header {{
            display: flex;
            justify-content: space-between;
            font-size: 0.9rem;
        }}

        .token-bar-bg {{
            height: 10px;
            background: rgba(255, 255, 255, 0.05);
            border-radius: 9999px;
            overflow: hidden;
            position: relative;
        }}

        .token-bar-fill {{
            height: 100%;
            background: linear-gradient(90deg, var(--color-primary), var(--color-secondary));
            border-radius: 9999px;
        }}

        /* Capability pill */
        .cap-pill {{
            display: inline-block;
            background: rgba(129, 140, 248, 0.15);
            border: 1px solid rgba(129, 140, 248, 0.3);
            color: var(--color-primary);
            padding: 0.2rem 0.5rem;
            border-radius: 6px;
            font-size: 0.8rem;
            margin-right: 0.4rem;
            margin-bottom: 0.4rem;
            font-weight: 600;
        }}

        @keyframes fadeIn {{
            from {{ opacity: 0; transform: translateY(8px); }}
            to {{ opacity: 1; transform: translateY(0); }}
        }}
    </style>
</head>
<body>
    <div class="dashboard-container">
        <header>
            <div class="logo-title">
                <h1>ACDLC Distributed Observability Console</h1>
                <p>Telemetry Analytics and Active Governance Metrics Overview</p>
            </div>
            <span class="badge-v16" id="platform-version-badge">v1.6 DISTRIBUTED RUNTIME</span>
        </header>

        <div class="tabs-nav">
            <button class="tab-btn active" onclick="switchTab('metrics')" id="btn-tab-metrics">Metrics Console</button>
            <button class="tab-btn" onclick="switchTab('registry')" id="btn-tab-registry">Capability Registry</button>
            <button class="tab-btn" onclick="switchTab('warehouse')" id="btn-tab-warehouse">Execution Warehouse</button>
            <button class="tab-btn" onclick="switchTab('violations')" id="btn-tab-violations">Policy Violations</button>
        </div>

        <!-- TAB 1: METRICS CONSOLE -->
        <div id="tab-metrics" class="tab-content active">
            <div class="metrics-grid">
                <div class="card-metric" id="metric-success-rate">
                    <h3>System Success Rate</h3>
                    <div class="metric-value">{success_rate:.1f}%</div>
                    <div class="metric-subtext">Aggregated successful task transitions</div>
                </div>
                <div class="card-metric" id="metric-token-usage">
                    <h3>Total Tokens Burned</h3>
                    <div class="metric-value">{total_tokens_consumed:,}</div>
                    <div class="metric-subtext">Cumulative input & output tokens</div>
                </div>
                <div class="card-metric" id="metric-financial-burn">
                    <h3>Total Cost (USD)</h3>
                    <div class="metric-value">${total_cost:.4f}</div>
                    <div class="metric-subtext">Active API financial expenditure</div>
                </div>
                <div class="card-metric" id="metric-retries-count">
                    <h3>Recovery Retries</h3>
                    <div class="metric-value">{total_retries}</div>
                    <div class="metric-subtext">Automated self-healing iterations</div>
                </div>
            </div>

            <div class="layout-main">
                <div class="section-box" id="sec-agent-performance">
                    <h2>📊 Agent Workforce Performance</h2>
                    <table>
                        <thead>
                            <tr>
                                <th>Task ID</th>
                                <th>Agent Role</th>
                                <th>Active Stage</th>
                                <th>Status</th>
                                <th>Retries</th>
                                <th>Token Cost</th>
                                <th>Financial Burn</th>
                            </tr>
                        </thead>
                        <tbody>
        """
        
    for row in perf_data:
        task_id = row.get("task_id", "").upper()
        role = row.get("agent_role", "")
        stage = row.get("stage", "")
        status = row.get("status", "")
        retries = row.get("retries", "0")
        tok_in = int(row.get("tokens_in", 0))
        tok_out = int(row.get("tokens_out", 0))
        tok_cost = tok_in + tok_out
        cost_usd = float(row.get("cost_usd", 0.0))
        
        status_cls = "status-success" if status.upper() == "SUCCESS" else "status-error"
        
        html_content += f"""
                            <tr>
                                <td><strong>{task_id}</strong></td>
                                <td>{role}</td>
                                <td>{stage}</td>
                                <td><span class="status-badge {status_cls}">{status}</span></td>
                                <td>{retries}</td>
                                <td>{tok_cost:,}</td>
                                <td>${cost_usd:.4f}</td>
                            </tr>
        """
        
    html_content += """
                        </tbody>
                    </table>
                </div>

                <div class="section-box" id="sec-stage-burn">
                    <h2>⚡ Token Burn by Stage</h2>
                    <div class="token-chart-list">
    """
    
    for row in token_data:
        stage = row.get("stage", "")
        consumed = int(row.get("tokens_consumed", 0))
        limit = int(row.get("max_token_limit", 250000))
        percentage = (consumed / limit * 100) if limit else 0
        
        html_content += f"""
                        <div class="token-bar-item">
                            <div class="token-bar-header">
                                <span>{stage}</span>
                                <strong>{consumed:,} / {limit:,} ({percentage:.1f}%)</strong>
                            </div>
                            <div class="token-bar-bg">
                                <div class="token-bar-fill" style="width: {percentage}%"></div>
                            </div>
                        </div>
        """
        
    html_content += """
                    </div>
                </div>
            </div>
        </div>

        <!-- TAB 2: CAPABILITY REGISTRY -->
        <div id="tab-registry" class="tab-content">
            <div class="section-box" id="sec-capability-registry">
                <h2>📋 Capability-Aware Service Catalog</h2>
                <table>
                    <thead>
                        <tr>
                            <th>Skill ID</th>
                            <th>Name</th>
                            <th>Version</th>
                            <th>Location Type</th>
                            <th>Registry Status</th>
                            <th>Capabilities Competencies (Level)</th>
                        </tr>
                    </thead>
                    <tbody>
    """
    
    for skill in skills_data:
        caps_dict = skill.get("capabilities", {})
        caps_list = []
        if isinstance(caps_dict, dict):
            for cap, level in caps_dict.items():
                caps_list.append(f"{cap} ({level})")
        else:
            caps_list = list(caps_dict)
            
        caps = "".join(f'<span class="cap-pill">{c}</span>' for c in caps_list)
        html_content += f"""
                        <tr>
                            <td><strong>{skill.get("id")}</strong></td>
                            <td>{skill.get("name")}</td>
                            <td>v{skill.get("version")}</td>
                            <td><span class="cap-pill" style="background: rgba(192, 132, 252, 0.15); border-color: rgba(192, 132, 252, 0.3); color: var(--color-secondary);">{skill.get("type")}</span></td>
                            <td><span class="status-badge status-success">{skill.get("status")}</span></td>
                            <td>{caps}</td>
                        </tr>
        """
        
    html_content += """
                    </tbody>
                </table>
            </div>
        </div>

        <!-- TAB 3: EXECUTION WAREHOUSE -->
        <div id="tab-warehouse" class="tab-content">
            <div class="section-box" id="sec-execution-warehouse">
                <h2>🗄️ Partitioned Execution Event Warehouse</h2>
                <table>
                    <thead>
                        <tr>
                            <th>Event ID</th>
                            <th>Correlation ID</th>
                            <th>Timestamp</th>
                            <th>Event Type</th>
                            <th>Event Source</th>
                            <th>Severity</th>
                            <th>Payload Summary</th>
                        </tr>
                    </thead>
                    <tbody>
    """
    
    for event in warehouse_logs:
        payload_str = json.dumps(event.get("payload", {}))
        if len(payload_str) > 60:
            payload_str = payload_str[:60] + "..."
            
        severity = event.get("severity", "info").upper()
        severity_cls = "status-success" if severity == "INFO" else ("status-warn" if severity == "WARNING" else "status-error")
        
        html_content += f"""
                        <tr>
                            <td><strong>{event.get("event_id")}</strong></td>
                            <td>{event.get("correlation_id")}</td>
                            <td><code>{event.get("timestamp")}</code></td>
                            <td><span class="status-badge status-success" style="background: rgba(129, 140, 248, 0.15); border-color: rgba(129, 140, 248, 0.3); color: var(--color-primary);">{event.get("event_type")}</span></td>
                            <td><span class="cap-pill" style="margin: 0; font-size: 0.75rem;">{event.get("source", "kernel")}</span></td>
                            <td><span class="status-badge {severity_cls}">{severity}</span></td>
                            <td><code style="font-size: 0.85rem; color: var(--text-muted);">{payload_str}</code></td>
                        </tr>
        """
        
    if not warehouse_logs:
        html_content += '<tr><td colspan="7" style="text-align: center; color: var(--text-muted);">Warehouse partitioned data directory empty. Run simulations to generate event tracks.</td></tr>'
        
    html_content += """
                    </tbody>
                </table>
            </div>
        </div>

        <!-- TAB 4: POLICY VIOLATIONS -->
        <div id="tab-violations" class="tab-content">
            <div class="section-box" id="sec-policy-violations">
                <h2>⚠️ Governance Policy Violations Log</h2>
                <table>
                    <thead>
                        <tr>
                            <th>Violation Event</th>
                            <th>Task ID</th>
                            <th>Timestamp</th>
                            <th>Event Source</th>
                            <th>Severity</th>
                            <th>Breached Constraint Details</th>
                        </tr>
                    </thead>
                    <tbody>
    """
    
    for event in policy_violations:
        payload = event.get("payload", {})
        err = payload.get("error", "Breach detected")
        severity = event.get("severity", "error").upper()
        severity_cls = "status-warn" if severity == "WARNING" else "status-error"
        
        html_content += f"""
                        <tr>
                            <td><strong>{event.get("event_id")}</strong></td>
                            <td>{event.get("correlation_id")}</td>
                            <td><code>{event.get("timestamp")}</code></td>
                            <td><span class="cap-pill" style="margin: 0; font-size: 0.75rem;">{event.get("source", "policy_engine")}</span></td>
                            <td><span class="status-badge {severity_cls}">{severity}</span></td>
                            <td><code style="color: var(--color-error); font-size: 0.9rem;">{err}</code></td>
                        </tr>
        """
        
    if not policy_violations:
        html_content += '<tr><td colspan="6" style="text-align: center; color: var(--color-success); font-weight: 600; padding: 2rem;">Zero policy exceptions or token bounds violations detected. System fully compliant.</td></tr>'
        
    html_content += """
                    </tbody>
                </table>
            </div>
        </div>
    </div>

    <script>
        function switchTab(tabId) {
            document.querySelectorAll('.tab-content').forEach(el => el.classList.remove('active'));
            document.querySelectorAll('.tab-btn').forEach(el => el.classList.remove('active'));
            
            document.getElementById('tab-' + tabId).classList.add('active');
            document.getElementById('btn-tab-' + tabId).classList.add('active');
        }
    </script>
</body>
</html>
"""
    
    try:
        with open(dest_html, "w", encoding="utf-8") as f:
            f.write(html_content)
        print(f"[SUCCESS] Telemetry 4-tab dashboard generated successfully at: {dest_html}")
    except Exception as e:
        print(f"[ERROR] Failed writing HTML dashboard: {e}")
        sys.exit(1)
        
    sys.exit(0)

if __name__ == "__main__":
    generate_dashboard()
