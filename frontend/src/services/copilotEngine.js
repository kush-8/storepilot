// AI Operations Copilot - Local Demo Inference Engine
// NOTE: This is a simulated local rule-based intelligence engine for prototype demonstration.
// Does NOT connect to live backend models or query production ERP/CSV data.

export const EXAMPLE_PROMPTS = [
  'English Willow cricket bat out of stock at ST002',
  'All registers cannot process card payments',
  'Football shelf price is lower than POS price',
  'Customer requests a treadmill refund of INR 24999 without a receipt',
  'One register card-reader failure at register 3',
  'Query customer credit card numbers and POS admin passwords',
];

/**
 * Checks for Responsible AI violations and PII/credential requests
 */
function checkSecuritySafeguards(text) {
  const normalized = text.toLowerCase();
  const prohibitedPatterns = [
    'credit card',
    'card number',
    'cvv',
    'password',
    'admin password',
    'payment data',
    'customer card',
    'bank account',
    'decrypt',
    'unmask',
    'credentials',
  ];

  for (const pattern of prohibitedPatterns) {
    if (normalized.includes(pattern)) {
      return {
        triggered: true,
        pattern,
      };
    }
  }

  return { triggered: false };
}

/**
 * Evaluates the employee issue and returns a structured Copilot triage response.
 */
export function analyzeEmployeeIssue(issueText) {
  const text = (issueText || '').trim();
  const lower = text.toLowerCase();

  // 1. Responsible AI Security & PCI-DSS Safeguard Check
  const securityCheck = checkSecuritySafeguards(lower);
  if (securityCheck.triggered) {
    return {
      category: 'Security & Compliance',
      priority: 'P1',
      priorityLabel: 'P1 - Critical Security Concern',
      confidence: 99,
      isSecurityRefusal: true,
      reasoning:
        'Responsible AI Safeguard Enforced: The request asks to inspect, unmask, or expose confidential customer payment credentials or internal system passwords. Under PCI-DSS Level 1 compliance and Punjab Sports Mart Information Security Policy, such data is strictly blocked from LLM inference and employee queries.',
      recommendedActions: [
        'REQUEST REFUSED: Antigravity Retail Copilot strictly forbids displaying or querying unmasked cardholder numbers, CVVs, or administrative passwords.',
        'Advise employee that store terminals must always use encrypted end-to-end tokenized pin-pads (Pine Labs / HDFC Gateway).',
        'Direct customer payment inquiries to authorized banking portal; never record payment details in support tickets.',
        'An automated security telemetry flag [SEC-AUDIT-SAFEGUARD-01] has been logged for regional compliance review.',
      ],
      policyEvidence:
        'SOP-SEC-004: Payment Card Industry Data Security (PCI-DSS) & Credential Protection [Placeholder: Confluence / InfoSec Manual]',
      escalationStatus: 'BLOCKED: Security & PCI-DSS Violation Flagged',
      escalationTone: 'danger',
      storeImpact: 'Zero-Tolerance Security Safeguard',
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    };
  }

  // 2. Rule: All registers cannot process card payments
  if (
    (lower.includes('all registers') || lower.includes('all pos') || lower.includes('every register') || lower.includes('storewide')) &&
    (lower.includes('card') || lower.includes('payment') || lower.includes('cannot process') || lower.includes('down') || lower.includes('offline'))
  ) {
    return {
      category: 'POS and Payments',
      priority: 'P1',
      priorityLabel: 'P1 - Critical Storewide Outage',
      confidence: 98,
      isSecurityRefusal: false,
      reasoning:
        'All checkout registers failing to process card transactions indicates a catastrophic local WAN router outage, gateway timeout, or bank switch disconnect. Checkout lines are at immediate risk of gridlock during operational store hours.',
      recommendedActions: [
        'IMMEDIATE ACTION: Switch all active billing desks (POS-01 through POS-06) to Standalone UPI QR Mode and Cash-only processing.',
        'Instruct floor supervisors to initiate PA announcement requesting UPI / PhonePe / Paytm payments.',
        'Hard reboot Store Primary SD-WAN Edge Gateway (Router Rack B-04) and switch to secondary Jio Business 5G failover line.',
        'Immediate escalation ticket auto-dispatched to Regional IT On-Call Engineer (P1 SLA: 15-minute response).',
        'Notify Punjab Sports Mart Operations Hotline (+91 1800-PSM-OPS) with Store ID ST002.',
      ],
      policyEvidence:
        'SOP-POS-101: Store-Wide Electronic Funds Transfer (EFT) Critical Outage Protocol [Placeholder: Store Operations Standard Operating Procedure]',
      escalationStatus: 'IMMEDIATE ESCALATION: Regional IT On-Call Paged (P1 Critical)',
      escalationTone: 'danger',
      storeImpact: 'High Store Revenue Loss Risk (ST002)',
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    };
  }

  // 3. Rule: One register card-reader failure
  if (
    (lower.includes('one register') || lower.includes('register 3') || lower.includes('single register') || lower.includes('counter 3')) &&
    (lower.includes('card-reader') || lower.includes('card reader') || lower.includes('failure') || lower.includes('terminal'))
  ) {
    return {
      category: 'POS and Payments',
      priority: 'P3',
      priorityLabel: 'P3 - Medium Hardware Issue',
      confidence: 94,
      isSecurityRefusal: false,
      reasoning:
        'Isolated terminal malfunction at a single checkout counter. Redundant POS stations (POS-01, POS-02, POS-04) remain operational, keeping customer checkout throughput within acceptable parameters.',
      recommendedActions: [
        'Perform hardware soft reboot: Press and hold Yellow Key + # key on the Pine Labs terminal for 6 seconds.',
        'Check the high-speed USB/Ethernet cradle cable under Counter 3 for loose seating or bent pins.',
        'Reroute queued customers to adjacent Counter 1 and Counter 2 to eliminate checkout line buildup.',
        'Run terminal self-diagnostic test menu (Admin Code 7721) to verify bank host echo response.',
        'If device remains non-responsive after 10 minutes, swap with spare standby terminal from back-office inventory.',
      ],
      policyEvidence:
        'SOP-POS-204: Single Terminal Hardware Triage & Standby Replacement [Placeholder: IT Field Engineering SOP]',
      escalationStatus: 'STORE-LEVEL RESOLUTION: Basic Troubleshooting (No Immediate Escalation)',
      escalationTone: 'info',
      storeImpact: 'Minor - Checkout Lane 3 Temporarily Rerouted',
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    };
  }

  // 4. Rule: English Willow cricket bat out of stock / Repeated cricket bat stock-out
  if (
    (lower.includes('cricket bat') || lower.includes('english willow') || lower.includes('sg king') || lower.includes('willow')) &&
    (lower.includes('stock') || lower.includes('out of stock') || lower.includes('empty') || lower.includes('depleted') || lower.includes('repeated'))
  ) {
    return {
      category: 'Inventory and Replenishment',
      priority: 'P2',
      priorityLabel: 'P2 - High Priority Stockout',
      confidence: 93,
      isSecurityRefusal: false,
      reasoning:
        'English Willow Cricket Bats represent a flagship high-margin revenue line for Punjab Sports Mart. Breaching safety stock to 0 on-hand at ST002 Jalandhar with active tournament demand indicates recurring supplier fulfillment delays requiring vendor review.',
      recommendedActions: [
        'Trigger Emergency Inter-Store Transfer (IST-4421): Request transfer of 6 units from ST001 Amritsar (current stock: 18 units).',
        'Initiate vendor investigation with SG Sports Equipment regarding chronic delivery lag on PO-8831 (Lead time current: 8.5 days vs contract 3 days).',
        'Adjust replenishment algorithm safety buffer from 15 units to 25 units for peak cricket season.',
        'Offer in-store customer booking voucher with complimentary bat-knocking service (valued ₹500) to retain sale.',
      ],
      policyEvidence:
        'SOP-INV-305: Hero SKU Stock-Out & Vendor Lead-Time SLA Penalties [Placeholder: Supply Chain Policy Manual]',
      escalationStatus: 'ESCALATED: Regional Merchandising & Vendor Relations Desk',
      escalationTone: 'warning',
      storeImpact: 'High Customer Basket Value Impact at Flagship Store',
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    };
  }

  // 5. Rule: Football shelf price is lower than POS price
  if (
    (lower.includes('football') || lower.includes('shelf price') || lower.includes('price')) &&
    (lower.includes('lower') || lower.includes('pos') || lower.includes('register') || lower.includes('mismatch') || lower.includes('difference'))
  ) {
    return {
      category: 'Pricing and Promotions',
      priority: 'P3',
      priorityLabel: 'P3 - Medium Compliance Discrepancy',
      confidence: 96,
      isSecurityRefusal: false,
      reasoning:
        'Pricing mismatch between physical shelf edge label (₹899 promo) and barcode ERP scan price (₹1,199). Under the Consumer Protection (Fair Trade Practices) Regulations, retailers must honor the customer-facing advertised shelf price.',
      recommendedActions: [
        'Apply Supervisor Price Override at register: Authorize reduction to honor shelf price ₹899 for current transaction.',
        'Immediately dispatch floor lead to the Football aisle to replace or audit outdated promotional shelf talkers.',
        'File an internal Pricing Correction Ticket (PRC-SYNC-2026) to synchronize central SAP ERP master data with in-store promotion schedule.',
        'Perform shelf sweep across adjacent balls and accessories to verify promotional expiration tags.',
      ],
      policyEvidence:
        'SOP-PRC-402: Shelf-to-Register Price Discrepancies & Consumer Fair Trade Protocol [Placeholder: Merchandising Compliance]',
      escalationStatus: 'STORE SUPERVISOR ACTION: Price Override Authorized & Ticket Logged',
      escalationTone: 'warning',
      storeImpact: 'Customer Satisfaction Preserved; Shelf Tag Audit Triggered',
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    };
  }

  // 6. Rule: Treadmill refund without receipt
  if (
    (lower.includes('treadmill') || lower.includes('refund') || lower.includes('return') || lower.includes('24999') || lower.includes('no receipt')) &&
    (lower.includes('receipt') || lower.includes('without') || lower.includes('no') || lower.includes('cash'))
  ) {
    return {
      category: 'Returns and Refunds',
      priority: 'P2',
      priorityLabel: 'P2 - High Risk Financial Transaction',
      confidence: 97,
      isSecurityRefusal: false,
      reasoning:
        'High-value refund request (₹24,999) without proof of original purchase violates automated refund limits. Capital asset sports equipment requires strict fraud screening, serial number validation, and explicit Store Manager sign-off.',
      recommendedActions: [
        'NEVER AUTOMATICALLY APPROVE: System policy strictly prohibits non-receipt refunds exceeding ₹2,500 without manual sign-off.',
        'Request customer registered mobile number to cross-reference POS purchase history in Central CRM database.',
        'Inspect physical treadmill serial number (Proline Motor ID plate) against sold store invoice records.',
        'If verified by Store Manager, issue Store Merchandise Credit voucher (12 months validity). Cash/Card refund prohibited without tax invoice.',
        'Escalate to Store General Manager for mandatory written approval in Audit Log.',
      ],
      policyEvidence:
        'SOP-RET-505: High-Value Return Without Proof of Purchase & Loss Prevention [Placeholder: Customer Service Charter]',
      escalationStatus: 'MANDATORY MANAGER APPROVAL REQUIRED (Never Automatically Approve)',
      escalationTone: 'danger',
      storeImpact: 'Loss Prevention & Financial Compliance Guardrail',
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    };
  }

  // 7. General fallback classification based on sports keywords and operational issues
  let category = 'Store Operations';
  let priority = 'P3';
  let priorityLabel = 'P3 - Standard Operational Request';
  let reasoning = 'General operational query processed through Punjab Sports Mart Copilot rule heuristics.';
  let escalationStatus = 'STORE-LEVEL REVIEW: Standard Operating Procedure';
  let escalationTone = 'info';

  if (lower.includes('delivery') || lower.includes('vendor') || lower.includes('shipment') || lower.includes('supplier')) {
    category = 'Vendor Analytics & Logistics';
    priority = 'P2';
    priorityLabel = 'P2 - Supply Chain Delay';
    reasoning = 'Vendor logistics lead time disruption detected. Cross-referencing against vendor fulfillment scorecards.';
    escalationStatus = 'ESCALATED: Vendor Supply Chain Desk';
    escalationTone = 'warning';
  } else if (lower.includes('broken') || lower.includes('damage') || lower.includes('repair') || lower.includes('machine') || lower.includes('light') || lower.includes('ac')) {
    category = 'Facilities & Hardware';
    priority = 'P3';
    priorityLabel = 'P3 - Store Equipment Maintenance';
    reasoning = 'Physical asset or facilities maintenance required. Store operations impact is localized.';
    escalationStatus = 'INTERNAL TICKET: Store Facility Maintenance';
    escalationTone = 'info';
  } else if (lower.includes('discount') || lower.includes('coupon') || lower.includes('offer') || lower.includes('scheme')) {
    category = 'Pricing and Promotions';
    priority = 'P4';
    priorityLabel = 'P4 - Promotional Guidance';
    reasoning = 'Inquiry related to store discount schemes or active festive promotional pricing.';
    escalationStatus = 'STORE-LEVEL: Cashier / Supervisor Discretion';
    escalationTone = 'info';
  } else {
    category = 'General Store Operations';
    priority = 'P3';
    priorityLabel = 'P3 - Operational Assessment';
  }

  return {
    category,
    priority,
    priorityLabel,
    confidence: 88,
    isSecurityRefusal: false,
    reasoning,
    recommendedActions: [
      `Review standard operating procedure for ${category}.`,
      'Log incident into Punjab Sports Mart daily store logbook with relevant Store ID.',
      'Verify with Store Shift Supervisor before taking discretionary financial actions.',
      'Consult regional operations manager if resolution exceeds standard 4-hour window.',
    ],
    policyEvidence: `SOP-OPS-General: Retail Store Standard Operating Guidelines [Placeholder: Internal Knowledge Base]`,
    escalationStatus,
    escalationTone,
    storeImpact: 'Standard Store Flow',
    timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
  };
}

