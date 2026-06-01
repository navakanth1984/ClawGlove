# -*- coding: utf-8 -*-
"""
ClawGlove CPT Time-Travel Explorer UI
Embedded HTML dashboard content (Design Refinement 4).
"""

EXPLORER_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ClawGlove CPT Auditing Explorer</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=Outfit:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500;700&display=swap" rel="stylesheet">
    <style>
        :root {
            --bg-color: #0b0f19;
            --card-bg: rgba(17, 24, 39, 0.7);
            --card-border: rgba(255, 255, 255, 0.08);
            --text-color: #f3f4f6;
            --text-muted: #9ca3af;
            --primary: hsl(263, 90%, 65%);
            --primary-glow: rgba(139, 92, 246, 0.35);
            --success: #10b981;
            --success-glow: rgba(16, 185, 129, 0.25);
            --warning: #f59e0b;
            --danger: #ef4444;
            --danger-glow: rgba(239, 68, 68, 0.25);
            --transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
        }

        * {
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }

        body {
            font-family: 'Inter', sans-serif;
            background-color: var(--bg-color);
            color: var(--text-color);
            min-height: 100vh;
            overflow-x: hidden;
            background-image: 
                radial-gradient(circle at 10% 20%, rgba(139, 92, 246, 0.08) 0%, transparent 40%),
                radial-gradient(circle at 90% 80%, rgba(16, 185, 129, 0.05) 0%, transparent 40%);
            background-attachment: fixed;
        }

        h1, h2, h3, h4 {
            font-family: 'Outfit', sans-serif;
            letter-spacing: -0.02em;
        }

        /* Glassmorphism Header */
        header {
            position: sticky;
            top: 0;
            z-index: 100;
            backdrop-filter: blur(16px);
            -webkit-backdrop-filter: blur(16px);
            background: rgba(11, 15, 25, 0.75);
            border-bottom: 1px solid var(--card-border);
            padding: 1rem 2rem;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }

        .logo-container {
            display: flex;
            align-items: center;
            gap: 0.75rem;
        }

        .shield-icon {
            color: var(--primary);
            filter: drop-shadow(0 0 8px var(--primary-glow));
            animation: pulse 3s infinite ease-in-out;
        }

        .logo-text {
            font-size: 1.5rem;
            font-weight: 700;
            background: linear-gradient(135deg, #f3f4f6 30%, #8b5cf6 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }

        .logo-badge {
            font-size: 0.75rem;
            font-weight: 600;
            background: var(--primary-glow);
            color: #c4b5fd;
            border: 1px solid rgba(139, 92, 246, 0.3);
            padding: 0.2rem 0.5rem;
            border-radius: 9999px;
        }

        /* Container Layout */
        .dashboard {
            max-width: 1440px;
            margin: 2rem auto;
            padding: 0 2rem;
            display: grid;
            grid-template-columns: 360px 1fr;
            gap: 2rem;
        }

        /* Sidebar Glass Panels */
        .sidebar {
            display: flex;
            flex-direction: column;
            gap: 1.5rem;
        }

        .panel {
            background: var(--card-bg);
            border: 1px solid var(--card-border);
            backdrop-filter: blur(12px);
            -webkit-backdrop-filter: blur(12px);
            border-radius: 16px;
            padding: 1.5rem;
            box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.37);
        }

        .panel-title {
            font-size: 1.1rem;
            font-weight: 600;
            margin-bottom: 1.25rem;
            color: #f3f4f6;
            display: flex;
            align-items: center;
            gap: 0.5rem;
            border-bottom: 1px solid rgba(255, 255, 255, 0.05);
            padding-bottom: 0.75rem;
        }

        /* Telemetry Monitors */
        .integrity-item {
            padding: 0.75rem;
            background: rgba(255, 255, 255, 0.02);
            border-radius: 8px;
            border: 1px solid rgba(255, 255, 255, 0.03);
            margin-bottom: 0.75rem;
        }

        .integrity-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 0.5rem;
        }

        .integrity-name {
            font-size: 0.85rem;
            font-weight: 600;
            text-transform: uppercase;
            color: #d1d5db;
        }

        .status-badge {
            font-size: 0.7rem;
            font-weight: 700;
            padding: 0.2rem 0.5rem;
            border-radius: 4px;
            text-transform: uppercase;
            display: inline-flex;
            align-items: center;
            gap: 0.3rem;
        }

        .status-verified {
            background: rgba(16, 185, 129, 0.15);
            color: var(--success);
            border: 1px solid rgba(16, 185, 129, 0.3);
            box-shadow: 0 0 10px rgba(16, 185, 129, 0.1);
        }

        .status-violation {
            background: rgba(239, 68, 68, 0.15);
            color: var(--danger);
            border: 1px solid rgba(239, 68, 68, 0.3);
            box-shadow: 0 0 10px rgba(239, 68, 68, 0.15);
            animation: pulse-red 2s infinite;
        }

        .status-dot {
            width: 6px;
            height: 6px;
            border-radius: 50%;
            background-color: currentColor;
            display: inline-block;
        }

        .status-dot.glowing {
            box-shadow: 0 0 8px currentColor;
        }

        .integrity-details {
            font-size: 0.75rem;
            color: var(--text-muted);
            display: flex;
            flex-direction: column;
            gap: 0.25rem;
        }

        /* Controls */
        .control-group {
            display: flex;
            flex-direction: column;
            gap: 0.75rem;
        }

        select {
            background: rgba(11, 15, 25, 0.8);
            border: 1px solid var(--card-border);
            color: var(--text-color);
            padding: 0.75rem 1rem;
            border-radius: 8px;
            font-family: inherit;
            font-size: 0.9rem;
            outline: none;
            cursor: pointer;
            width: 100%;
            transition: var(--transition);
        }

        select:focus {
            border-color: var(--primary);
            box-shadow: 0 0 0 2px var(--primary-glow);
        }

        .btn {
            background: linear-gradient(135deg, var(--primary) 0%, #6d28d9 100%);
            color: white;
            border: none;
            padding: 0.75rem 1rem;
            border-radius: 8px;
            font-family: inherit;
            font-size: 0.9rem;
            font-weight: 600;
            cursor: pointer;
            transition: var(--transition);
            display: flex;
            justify-content: center;
            align-items: center;
            gap: 0.5rem;
            box-shadow: 0 4px 12px 0 rgba(139, 92, 246, 0.3);
        }

        .btn:hover {
            transform: translateY(-2px);
            box-shadow: 0 6px 20px 0 rgba(139, 92, 246, 0.45);
        }

        .btn:active {
            transform: translateY(0);
        }

        .btn:disabled {
            background: #4b5563;
            box-shadow: none;
            cursor: not-allowed;
            transform: none;
        }

        .btn-warning {
            background: linear-gradient(135deg, #f59e0b 0%, #d97706 100%);
            box-shadow: 0 4px 12px 0 rgba(245, 158, 11, 0.2);
        }

        .btn-warning:hover {
            box-shadow: 0 6px 20px 0 rgba(245, 158, 11, 0.35);
        }

        /* Main Audit Panel */
        main {
            display: flex;
            flex-direction: column;
            gap: 1.5rem;
        }

        /* Modern Table Card */
        .table-card {
            background: var(--card-bg);
            border: 1px solid var(--card-border);
            border-radius: 16px;
            box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.37);
            overflow: hidden;
            display: flex;
            flex-direction: column;
            min-height: 480px;
        }

        .table-header {
            padding: 1.25rem 1.5rem;
            border-bottom: 1px solid rgba(255, 255, 255, 0.05);
            display: flex;
            justify-content: space-between;
            align-items: center;
        }

        .table-title {
            font-size: 1.2rem;
            font-weight: 700;
            color: #fff;
        }

        .table-container {
            overflow-x: auto;
            flex-grow: 1;
        }

        table {
            width: 100%;
            border-collapse: collapse;
            text-align: left;
        }

        th {
            background: rgba(0, 0, 0, 0.2);
            color: #d1d5db;
            font-size: 0.75rem;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            padding: 1rem 1.5rem;
            border-bottom: 1px solid rgba(255, 255, 255, 0.05);
        }

        td {
            padding: 1rem 1.5rem;
            border-bottom: 1px solid rgba(255, 255, 255, 0.03);
            font-size: 0.85rem;
            color: #e5e7eb;
            transition: var(--transition);
        }

        tr {
            cursor: pointer;
        }

        tr:hover td {
            background: rgba(255, 255, 255, 0.02);
            color: #fff;
        }

        .mono {
            font-family: 'JetBrains Mono', monospace;
            font-size: 0.8rem;
        }

        .badge-list {
            display: flex;
            flex-wrap: wrap;
            gap: 0.3rem;
        }

        .risky-badge {
            background: rgba(239, 68, 68, 0.12);
            color: #f87171;
            border: 1px solid rgba(239, 68, 68, 0.2);
            font-size: 0.7rem;
            font-weight: 600;
            padding: 0.1rem 0.4rem;
            border-radius: 4px;
        }

        /* Empty state implementation (Design Refinement 7) */
        .empty-state {
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            text-align: center;
            padding: 4rem 2rem;
            color: var(--text-muted);
            height: 100%;
            flex-grow: 1;
        }

        .empty-icon {
            width: 64px;
            height: 64px;
            color: var(--success);
            opacity: 0.6;
            margin-bottom: 1.5rem;
            filter: drop-shadow(0 0 12px var(--success-glow));
        }

        .empty-title {
            font-size: 1.4rem;
            font-weight: 700;
            color: #fff;
            margin-bottom: 0.5rem;
        }

        .empty-desc {
            font-size: 0.9rem;
            max-width: 420px;
        }

        /* Alert notifications */
        .alert-box {
            background: rgba(16, 185, 129, 0.08);
            border: 1px solid rgba(16, 185, 129, 0.2);
            padding: 1rem 1.25rem;
            border-radius: 12px;
            display: flex;
            flex-direction: column;
            gap: 0.5rem;
            animation: slide-in 0.3s ease;
        }

        .alert-title {
            font-weight: 700;
            font-size: 0.95rem;
            color: var(--success);
            display: flex;
            align-items: center;
            gap: 0.5rem;
        }

        .alert-body {
            font-size: 0.85rem;
            color: #d1d5db;
        }

        /* Modal Dialog */
        .modal-overlay {
            position: fixed;
            top: 0;
            left: 0;
            width: 100vw;
            height: 100vh;
            background: rgba(0, 0, 0, 0.7);
            backdrop-filter: blur(8px);
            z-index: 1000;
            display: flex;
            align-items: center;
            justify-content: center;
            opacity: 0;
            pointer-events: none;
            transition: var(--transition);
        }

        .modal-overlay.active {
            opacity: 1;
            pointer-events: auto;
        }

        .modal {
            background: #111827;
            border: 1px solid var(--card-border);
            border-radius: 16px;
            width: 680px;
            max-height: 90vh;
            overflow-y: auto;
            box-shadow: 0 24px 48px -12px rgba(0, 0, 0, 0.5);
            transform: scale(0.95);
            transition: var(--transition);
        }

        .modal-overlay.active .modal {
            transform: scale(1);
        }

        .modal-header {
            padding: 1.25rem 1.5rem;
            border-bottom: 1px solid rgba(255, 255, 255, 0.05);
            display: flex;
            justify-content: space-between;
            align-items: center;
        }

        .modal-close {
            background: none;
            border: none;
            color: var(--text-muted);
            cursor: pointer;
            font-size: 1.5rem;
            transition: var(--transition);
        }

        .modal-close:hover {
            color: #fff;
        }

        .modal-body {
            padding: 1.5rem;
            display: flex;
            flex-direction: column;
            gap: 1.25rem;
        }

        .info-grid {
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 1rem;
        }

        .info-item {
            display: flex;
            flex-direction: column;
            gap: 0.25rem;
        }

        .info-label {
            font-size: 0.7rem;
            font-weight: 700;
            text-transform: uppercase;
            color: var(--text-muted);
        }

        .info-val {
            font-size: 0.85rem;
            color: #f3f4f6;
            word-break: break-all;
        }

        .code-panel {
            background: rgba(0, 0, 0, 0.4);
            border: 1px solid rgba(255, 255, 255, 0.05);
            border-radius: 8px;
            padding: 1rem;
            font-family: 'JetBrains Mono', monospace;
            font-size: 0.8rem;
            color: #c4b5fd;
            overflow-x: auto;
        }

        /* Animations */
        @keyframes pulse {
            0% { transform: scale(1); opacity: 1; }
            50% { transform: scale(1.05); opacity: 0.8; }
            100% { transform: scale(1); opacity: 1; }
        }

        @keyframes pulse-red {
            0% { box-shadow: 0 0 0 0 rgba(239, 68, 68, 0.5); }
            70% { box-shadow: 0 0 0 8px rgba(239, 68, 68, 0); }
            100% { box-shadow: 0 0 0 0 rgba(239, 68, 68, 0); }
        }

        @keyframes slide-in {
            from { transform: translateY(10px); opacity: 0; }
            to { transform: translateY(0); opacity: 1; }
        }

        /* Loading animation */
        .spinner {
            width: 20px;
            height: 20px;
            border: 2px solid rgba(255,255,255,0.2);
            border-top: 2px solid #fff;
            border-radius: 50%;
            animation: spin 0.8s linear infinite;
            display: inline-block;
        }

        @keyframes spin {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
        }
    </style>
</head>
<body>

    <header>
        <div class="logo-container">
            <svg class="shield-icon" width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
                <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>
            </svg>
            <span class="logo-text">ClawGlove CPT Auditing Suite</span>
            <span class="logo-badge">Explorer UI</span>
        </div>
    </header>

    <div class="dashboard">
        <!-- Sidebar Controls & Health Monitors -->
        <div class="sidebar">
            <!-- 1. Database Integrity Monitor -->
            <div class="panel">
                <div class="panel-title">
                    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <ellipse cx="12" cy="5" rx="9" ry="3"></ellipse>
                        <path d="M3 5V19A9 3 0 0 0 21 19V5"></path>
                        <path d="M3 12A9 3 0 0 0 21 12"></path>
                    </svg>
                    Durable Ledger Integrity
                </div>
                
                <div class="integrity-item">
                    <div class="integrity-header">
                        <span class="integrity-name">Lineage Envelopes</span>
                        <span id="env-badge" class="status-badge status-verified">
                            <span class="status-dot glowing"></span>
                            <span>VERIFYING...</span>
                        </span>
                    </div>
                    <div class="integrity-details">
                        <span>Records: <strong id="env-rows" class="mono">-</strong></span>
                        <span>Chain Hash: <strong id="env-last-id" class="mono">-</strong></span>
                    </div>
                </div>

                <div class="integrity-item">
                    <div class="integrity-header">
                        <span class="integrity-name">Quarantine Store</span>
                        <span id="q-badge" class="status-badge status-verified">
                            <span class="status-dot glowing"></span>
                            <span>VERIFYING...</span>
                        </span>
                    </div>
                    <div class="integrity-details">
                        <span>Records: <strong id="q-rows" class="mono">-</strong></span>
                        <span>Chain Hash: <strong id="q-last-id" class="mono">-</strong></span>
                    </div>
                </div>
            </div>

            <!-- 2. Tenant Selector panel -->
            <div class="panel">
                <div class="panel-title">
                    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"></path>
                        <circle cx="9" cy="7" rx="4" ry="4"></circle>
                        <path d="M23 21v-2a4 4 0 0 0-3-3.87"></path>
                        <path d="M16 3.13a4 4 0 0 1 0 7.75"></path>
                    </svg>
                    Audited Tenancy Scope
                </div>
                <div class="control-group">
                    <label style="font-size: 0.75rem; font-weight: 700; color: var(--text-muted); text-transform: uppercase; margin-bottom: -0.25rem;">Active Tenant</label>
                    <select id="tenant-select">
                        <option value="" disabled selected>Retrieving tenants...</option>
                    </select>
                    
                    <button id="reconcile-btn" class="btn btn-warning" style="margin-top: 0.5rem;" disabled>
                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                            <path d="M21.5 2v6h-6M21.34 15.57a10 10 0 1 1-.57-8.38l5.67-5.67"/>
                        </svg>
                        Execute Tenant Reconcile
                    </button>
                </div>
            </div>

            <!-- 3. Cryptographic Key Management -->
            <div class="panel">
                <div class="panel-title">
                    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <rect x="3" y="11" width="18" height="11" rx="2" ry="2"></rect>
                        <path d="M7 11V7a5 5 0 0 1 10 0v4"></path>
                    </svg>
                    Ledger Key Management
                </div>
                <div class="control-group">
                    <div class="integrity-details" style="margin-bottom: 0.5rem; display: flex; flex-direction: column; gap: 0.35rem;">
                        <span>Node ID: <strong id="node-id-display" class="mono" style="font-size: 0.65rem; color: #d1d5db; word-break: break-all;">-</strong></span>
                        <span>Active Key ID: <strong id="active-key-id-display" class="mono" style="font-size: 0.75rem; color: var(--primary);">v1</strong></span>
                    </div>
                    <button id="rotate-btn" class="btn" style="background: linear-gradient(135deg, var(--primary) 0%, #4f46e5 100%);">
                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                            <path d="M21 2v6h-6M3 22v-6h6M21 13a9 9 0 1 1-3-7.7L21 8"/>
                        </svg>
                        Rotate Key version
                    </button>
                </div>
            </div>

            <!-- 4. Telemetry Alert box -->
            <div id="reconcile-alert" style="display: none;"></div>
        </div>

        <!-- Main Audit logs area -->
        <main>
            <div class="table-card">
                <div class="table-header">
                    <h2 class="table-title" id="table-head-text">Quarantine Event Logs</h2>
                </div>
                
                <div class="table-container" id="logs-container">
                    <table id="audit-table">
                        <thead>
                            <tr>
                                <th>Skill Name</th>
                                <th>Session ID</th>
                                <th>Risky Imports Detected</th>
                                <th>Quarantine Timestamp</th>
                                <th>Ledger Chain Link</th>
                            </tr>
                        </thead>
                        <tbody id="audit-tbody">
                            <!-- Table rows injected by JS -->
                        </tbody>
                    </table>
                </div>

                <!-- Empty state visual placeholder (Refinement 7) -->
                <div id="empty-state" class="empty-state" style="display: none;">
                    <svg class="empty-icon" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" />
                    </svg>
                    <h3 class="empty-title">All Systems Sovereign</h3>
                    <p class="empty-desc">No quarantine events have been logged for this tenant. The runtime execution substrate remains completely clean, integral, and secure.</p>
                </div>
            </div>
        </main>
    </div>

    <!-- deep inspector detail modal -->
    <div id="detail-modal-overlay" class="modal-overlay">
        <div class="modal">
            <div class="modal-header">
                <h3 id="modal-skill-id" style="font-size: 1.25rem;">Provenance Envelope Detail</h3>
                <button class="modal-close" onclick="closeModal()">&times;</button>
            </div>
            <div class="modal-body">
                <div class="info-grid">
                    <div class="info-item">
                        <span class="info-label">Active Active-Store Target</span>
                        <span id="modal-file-path" class="info-val mono"></span>
                    </div>
                    <div class="info-item">
                        <span class="info-label">Lineage Session ID</span>
                        <span id="modal-session-id" class="info-val mono"></span>
                    </div>
                    <div class="info-item">
                        <span class="info-label">Generation Model</span>
                        <span id="modal-model" class="info-val"></span>
                    </div>
                    <div class="info-item">
                        <span class="info-label">Time Generated</span>
                        <span id="modal-timestamp" class="info-val mono"></span>
                    </div>
                </div>

                <div class="info-item">
                    <span class="info-label">Cryptographic Content Hash</span>
                    <span id="modal-content-hash" class="info-val mono" style="font-weight: 600; color: var(--primary);"></span>
                </div>

                <div class="info-item">
                    <span class="info-label">Lineage Parent Request Hash</span>
                    <span id="modal-parent-hash" class="info-val mono"></span>
                </div>

                <div class="info-item">
                    <span class="info-label">Cryptographic Lineage Signature</span>
                    <div id="modal-signature" class="code-panel" style="color: #10b981; border: 1px solid rgba(16, 185, 129, 0.2);"></div>
                </div>

                <div class="info-item">
                    <span class="info-label">Security Evaluation Status</span>
                    <span id="modal-status" class="info-val"></span>
                </div>
            </div>
        </div>
    <!-- cryptographic key rotation instruction modal -->
    <div id="rotation-modal-overlay" class="modal-overlay">
        <div class="modal">
            <div class="modal-header">
                <h3 style="font-size: 1.25rem;">Cryptographic Key Rotation Instructions</h3>
                <button class="modal-close" onclick="closeRotationModal()">&times;</button>
            </div>
            <div class="modal-body" style="gap: 1rem;">
                <p style="font-size: 0.85rem; color: #d1d5db; line-height: 1.4;">
                    To protect sensitive signing materials from HTTP exposure (such as browser logs, server transcripts, or network proxies), ClawGlove requires all key rotations to be performed locally via the terminal console.
                </p>
                <div class="info-item">
                    <span class="info-label">Active Key ID</span>
                    <span id="rotation-active-key-id" class="info-val mono" style="font-weight: 700; color: var(--primary);">-</span>
                </div>
                <div class="info-item" style="margin-top: 0.5rem;">
                    <span class="info-label">Administrative Rotation Command</span>
                    <p style="font-size: 0.75rem; color: var(--text-muted); margin-bottom: 0.35rem;">
                        Run the standalone rotation module from your workspace directory:
                    </p>
                    <div id="rotation-cmd-box" class="code-panel" style="color: #34d399; border: 1px solid rgba(16, 185, 129, 0.2); cursor: text; user-select: all;" title="Double click or select all to copy">
                        uv run python -m clawglove.provenance.rotate --workspace ./
                    </div>
                </div>
                <p style="font-size: 0.75rem; color: var(--warning); font-style: italic; margin-top: 0.25rem;">
                    Executing this command automatically bootstraps a cryptographically secure <code>.clawglove_secrets</code> keyring. Historical database signature entries remain fully immutable, preserving operational lineage.
                </p>
            </div>
        </div>
    </div>

    <script>
        const API_BASE = window.location.origin;

        // Elements
        const tenantSelect = document.getElementById("tenant-select");
        const reconcileBtn = document.getElementById("reconcile-btn");
        const reconcileAlert = document.getElementById("reconcile-alert");
        const auditTable = document.getElementById("audit-table");
        const auditTbody = document.getElementById("audit-tbody");
        const emptyState = document.getElementById("empty-state");
        const tableHeadText = document.getElementById("table-head-text");

        // Database Badges
        const envBadge = document.getElementById("env-badge");
        const envRows = document.getElementById("env-rows");
        const envLastId = document.getElementById("env-last-id");
        
        const qBadge = document.getElementById("q-badge");
        const qRows = document.getElementById("q-rows");
        const qLastId = document.getElementById("q-last-id");

        // Key management elements
        const nodeIdDisplay = document.getElementById("node-id-display");
        const activeKeyIdDisplay = document.getElementById("active-key-id-display");
        const rotateBtn = document.getElementById("rotate-btn");
        const rotationModalOverlay = document.getElementById("rotation-modal-overlay");
        const rotationActiveKeyId = document.getElementById("rotation-active-key-id");

        // Detail Modal Elements
        const modalOverlay = document.getElementById("detail-modal-overlay");
        const modalSkillId = document.getElementById("modal-skill-id");
        const modalFilePath = document.getElementById("modal-file-path");
        const modalSessionId = document.getElementById("modal-session-id");
        const modalModel = document.getElementById("modal-model");
        const modalTimestamp = document.getElementById("modal-timestamp");
        const modalContentHash = document.getElementById("modal-content-hash");
        const modalParentHash = document.getElementById("modal-parent-hash");
        const modalSignature = document.getElementById("modal-signature");
        const modalStatus = document.getElementById("modal-status");

        // 1. Initialise
        document.addEventListener("DOMContentLoaded", () => {
            fetchHealthAndIntegrity();
            fetchTenants();
            
            // Hook up rotate modal trigger
            rotateBtn.onclick = () => {
                rotationModalOverlay.classList.add("active");
            };
        });

        // 2. Poll Database Chain Integrity
        async function fetchHealthAndIntegrity() {
            try {
                const response = await fetch(`${API_BASE}/audit/chain/verify`);
                const data = await response.json();
                
                // Envelopes Chain
                if (data.envelopes && data.envelopes.status === "VERIFIED") {
                    envBadge.className = "status-badge status-verified";
                    envBadge.innerHTML = '<span class="status-dot"></span><span>VERIFIED</span>';
                    envRows.innerText = data.envelopes.verified_rows;
                    envLastId.innerText = data.envelopes.last_row_id !== null ? `Row #${data.envelopes.last_row_id}` : "None";
                } else {
                    envBadge.className = "status-badge status-violation";
                    envBadge.innerHTML = '<span class="status-dot"></span><span>VIOLATION</span>';
                    envRows.innerText = "CRITICAL ERROR";
                    envLastId.innerText = data.envelopes ? data.envelopes.error_detail : "Corrupted";
                }

                // Quarantine log Chain
                if (data.quarantine_log && data.quarantine_log.status === "VERIFIED") {
                    qBadge.className = "status-badge status-verified";
                    qBadge.innerHTML = '<span class="status-dot"></span><span>VERIFIED</span>';
                    qRows.innerText = data.quarantine_log.verified_rows;
                    qLastId.innerText = data.quarantine_log.last_row_id !== null ? `Row #${data.quarantine_log.last_row_id}` : "None";
                } else {
                    qBadge.className = "status-badge status-violation";
                    qBadge.innerHTML = '<span class="status-dot"></span><span>VIOLATION</span>';
                    qRows.innerText = "CRITICAL ERROR";
                    qLastId.innerText = data.quarantine_log ? data.quarantine_log.error_detail : "Corrupted";
                }

                // Populate Node ID and Key ID
                if (nodeIdDisplay) {
                    nodeIdDisplay.innerText = data.node_id || "unknown";
                }
                if (activeKeyIdDisplay) {
                    activeKeyIdDisplay.innerText = data.active_key_id || "v1";
                }
                if (rotationActiveKeyId) {
                    rotationActiveKeyId.innerText = data.active_key_id || "v1";
                }
            } catch (err) {
                console.error("Failed to query DB integrity status", err);
            }
        }

        // 3. Fetch list of distinctive tenants
        async function fetchTenants() {
            try {
                const response = await fetch(`${API_BASE}/audit/tenants`);
                const tenants = await response.json();

                tenantSelect.innerHTML = "";
                
                if (!tenants || tenants.length === 0) {
                    // Refinement 7: Explicit Empty-Tenant State
                    const opt = document.createElement("option");
                    opt.value = "";
                    opt.disabled = true;
                    opt.selected = true;
                    opt.innerText = "No Quarantines Logged";
                    tenantSelect.appendChild(opt);

                    reconcileBtn.disabled = true;
                    renderEmptyState();
                    return;
                }

                // Populate tenants
                tenants.forEach(tenant => {
                    const opt = document.createElement("option");
                    opt.value = tenant;
                    opt.innerText = tenant;
                    tenantSelect.appendChild(opt);
                });

                // Trigger loading of logs for first selected tenant
                loadQuarantineLogs(tenantSelect.value);
                reconcileBtn.disabled = false;

                tenantSelect.onchange = (e) => {
                    loadQuarantineLogs(e.target.value);
                };
            } catch (err) {
                console.error("Failed to fetch tenants", err);
            }
        }

        // 4. Load quarantine logs table
        async function loadQuarantineLogs(tenantId) {
            if (!tenantId) return;
            tableHeadText.innerText = `Quarantine Event Logs — [${tenantId}]`;
            
            try {
                const response = await fetch(`${API_BASE}/audit/quarantine/${tenantId}`);
                const logs = await response.json();

                auditTbody.innerHTML = "";

                if (!logs || logs.length === 0) {
                    renderEmptyState();
                    return;
                }

                auditTable.style.display = "table";
                emptyState.style.display = "none";

                logs.forEach(log => {
                    const tr = document.createElement("tr");
                    tr.onclick = () => showDeepEnvelope(log.skill_id, log.tenant_id);

                    const importBadges = log.risky_imports
                        .map(imp => `<span class="risky-badge">${imp}</span>`)
                        .join(" ");

                    tr.innerHTML = `
                        <td style="font-weight:600; color:#fff;">${log.skill_id}</td>
                        <td class="mono">${log.session_id.substring(0, 8)}...</td>
                        <td><div class="badge-list">${importBadges}</div></td>
                        <td class="mono">${log.timestamp}</td>
                        <td class="mono" style="font-size:0.75rem; color:#8b5cf6;">${log.chain_hash.substring(0, 16)}...</td>
                    `;
                    auditTbody.appendChild(tr);
                });
            } catch (err) {
                console.error("Failed to query quarantine log records", err);
            }
        }

        // 5. Render empty state placeholders (Refinement 7)
        function renderEmptyState() {
            auditTable.style.display = "none";
            emptyState.style.display = "flex";
        }

        // 6. Deep envelope modal popup (inspect verification signature)
        async function showDeepEnvelope(skillId, tenantId) {
            try {
                const response = await fetch(`${API_BASE}/audit/envelope/${tenantId}/${skillId}`);
                if (!response.ok) throw new Error("Envelope details not found");
                
                const env = await response.json();
                
                modalSkillId.innerText = `Envelope Inspector: ${env.skill_id}`;
                modalFilePath.innerText = env.file_path;
                modalSessionId.innerText = env.originating_session_id;
                modalModel.innerText = env.generator_model;
                modalTimestamp.innerText = env.generation_timestamp;
                modalContentHash.innerText = env.content_hash;
                modalParentHash.innerText = env.parent_user_request_hash || "ROOT USER TURN";
                modalSignature.innerText = env.signature;
                
                // Visual verification status
                if (env.signature.startsWith("clawglove-")) {
                    modalStatus.innerHTML = '<span style="color:#10b981; font-weight:700;">VERIFIED ACTIVE SIGNATURE</span>';
                } else {
                    modalStatus.innerHTML = '<span style="color:#ef4444; font-weight:700;">UNSUPPORTED OR INVALID SIGNATURE</span>';
                }

                modalOverlay.classList.add("active");
            } catch (err) {
                alert(`Error reading lineage envelope details: ${err.message}`);
            }
        }

        function closeModal() {
            modalOverlay.classList.remove("active");
        }

        function closeRotationModal() {
            rotationModalOverlay.classList.remove("active");
        }

        // Close modal when overlay clicked
        modalOverlay.onclick = (e) => {
            if (e.target === modalOverlay) closeModal();
        };

        rotationModalOverlay.onclick = (e) => {
            if (e.target === rotationModalOverlay) closeRotationModal();
        };

        // 7. Trigger self-healing reconciliation (State-Mutating POST, Blocker 3)
        reconcileBtn.onclick = async () => {
            const tenantId = tenantSelect.value;
            if (!tenantId) return;

            reconcileBtn.disabled = true;
            reconcileBtn.innerHTML = '<span class="spinner"></span> <span>Running Reconcile...</span>';

            try {
                // Design Blocker 3: Changed from GET to POST for state mutation!
                const response = await fetch(`${API_BASE}/audit/reconcile/${tenantId}`, {
                    method: "POST"
                });
                const res = await response.json();

                reconcileAlert.style.display = "block";
                
                if (response.ok) {
                    const prunedText = res.pruned_files && res.pruned_files.length > 0 
                        ? `<br><span style="color:#f59e0b; font-weight:600;">Pruned untracked files:</span><ul style="padding-left:1.2rem; margin-top:0.25rem;">` + 
                          res.pruned_files.map(f => `<li style="font-size:0.75rem; word-break:break-all;">${f.split(/[\\\\/]/).pop()}</li>`).join("") + "</ul>"
                        : "No residual files were discovered.";

                    reconcileAlert.className = "alert-box";
                    reconcileAlert.innerHTML = `
                        <div class="alert-title">
                            <svg width="16" height="16" fill="none" stroke="currentColor" stroke-width="2.5" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z"/></svg>
                            Reconciliation Success
                        </div>
                        <div class="alert-body">
                            Validated <strong>${res.verified_count}</strong> database quarantine ledger records.<br>
                            ${prunedText}
                        </div>
                    `;
                    // Refresh data
                    fetchHealthAndIntegrity();
                    loadQuarantineLogs(tenantId);
                } else {
                    reconcileAlert.className = "alert-box";
                    reconcileAlert.style.background = "rgba(239, 68, 68, 0.08)";
                    reconcileAlert.style.borderColor = "rgba(239, 68, 68, 0.2)";
                    reconcileAlert.innerHTML = `
                        <div class="alert-title" style="color:var(--danger)">
                            <svg width="16" height="16" fill="none" stroke="currentColor" stroke-width="2.5" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"/></svg>
                            Chain Integrity Compromised
                        </div>
                        <div class="alert-body">
                            ${res.error || "A severe database discrepancy has been caught."}
                        </div>
                    `;
                }
            } catch (err) {
                console.error(err);
                reconcileAlert.style.display = "block";
                reconcileAlert.className = "alert-box";
                reconcileAlert.style.background = "rgba(239, 68, 68, 0.08)";
                reconcileAlert.style.borderColor = "rgba(239, 68, 68, 0.2)";
                reconcileAlert.innerHTML = `
                    <div class="alert-title" style="color:var(--danger)">System Offline</div>
                    <div class="alert-body">${err.message}</div>
                `;
            } finally {
                reconcileBtn.disabled = false;
                reconcileBtn.innerHTML = `
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <path d="M21.5 2v6h-6M21.34 15.57a10 10 0 1 1-.57-8.38l5.67-5.67"/>
                    </svg>
                    Execute Tenant Reconcile
                `;
            }
        };
    </script>
</body>
</html>
"""
