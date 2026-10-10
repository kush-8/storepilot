// Punjab Sports Mart - Mock Employee Directory & Backend Credential Mapping
// Compatible with FastAPI backend employee_master (E0001..E0100) and ST001..ST049

export const MOCK_EMPLOYEES = [
  {
    id: 'E0035',
    legacyId: 'EMP-1042',
    name: 'Harpreet Singh',
    email: 'harpreet.singh@punjabsportsmart.com',
    password: 'password123',
    role: 'Store Manager',
    department: 'Store Operations & Incident Escalation',
    storeId: 'ST001',
    storeName: 'Jalandhar Sports Hub',
    city: 'Jalandhar',
    region: 'Punjab',
    shift: 'General Duty Shift (09:00 - 18:00 IST)',
    initials: 'HS',
    avatarBg: 'linear-gradient(135deg, #2563eb, #1d4ed8)',
    badgeText: 'Store Mgr',
    escalationLevel: 4,
    securityClearance: 'Level 4 - Full System & Override Clearance',
    phone: '+91 98140-12345',
  },
  {
    id: 'E0007',
    legacyId: 'EMP-1018',
    name: 'Simran Kaur',
    email: 'simran.kaur@punjabsportsmart.com',
    password: 'password123',
    role: 'POS Support Lead',
    department: 'Front Checkout & Payment Systems',
    storeId: 'ST001',
    storeName: 'Jalandhar Sports Hub',
    city: 'Jalandhar',
    region: 'Punjab',
    shift: 'Morning Shift (08:30 - 17:30 IST)',
    initials: 'SK',
    avatarBg: 'linear-gradient(135deg, #7c3aed, #6d28d9)',
    badgeText: 'POS Lead',
    escalationLevel: 4,
    securityClearance: 'Level 4 - POS & Payment Incident Lead',
    phone: '+91 98722-67890',
  },
  {
    id: 'E0014',
    legacyId: 'EMP-1055',
    name: 'Rajesh Kumar',
    email: 'rajesh.kumar@punjabsportsmart.com',
    password: 'password123',
    role: 'Inventory Associate',
    department: 'Stockroom & Replenishment Control',
    storeId: 'ST001',
    storeName: 'Jalandhar Sports Hub',
    city: 'Jalandhar',
    region: 'Punjab',
    shift: 'Logistics Shift (07:00 - 16:00 IST)',
    initials: 'RK',
    avatarBg: 'linear-gradient(135deg, #059669, #047857)',
    badgeText: 'Inventory Lead',
    escalationLevel: 3,
    securityClearance: 'Level 3 - Inventory & SKU Controller',
    phone: '+91 94170-54321',
  },
  {
    id: 'E0001',
    legacyId: 'EMP-1001',
    name: 'Gurpreet Sandhu',
    email: 'gurpreet.sandhu@punjabsportsmart.com',
    password: 'password123',
    role: 'Regional Manager',
    department: 'Regional Operations & Multi-Store Audit',
    storeId: 'ST008',
    storeName: 'Express Sports Mohali',
    city: 'Mohali',
    region: 'North',
    shift: 'Regional Executive Duty',
    initials: 'GS',
    avatarBg: 'linear-gradient(135deg, #0284c7, #0369a1)',
    badgeText: 'Regional Mgr',
    escalationLevel: 2,
    securityClearance: 'Level 2 - Regional Supervisor',
    phone: '+91 99144-88776',
  },
  {
    id: 'E0015',
    legacyId: 'EMP-1089',
    name: 'Amanpreet Gill',
    email: 'amanpreet.gill@punjabsportsmart.com',
    password: 'password123',
    role: 'POS Support Associate',
    department: 'Customer Desk / Checkout Hub',
    storeId: 'ST008',
    storeName: 'Express Sports Mohali',
    city: 'Mohali',
    region: 'North',
    shift: 'Evening Shift (13:00 - 21:30 IST)',
    initials: 'AG',
    avatarBg: 'linear-gradient(135deg, #ea580c, #c2410c)',
    badgeText: 'POS Associate',
    escalationLevel: 4,
    securityClearance: 'Level 4 - Checkout & Operations Staff',
    phone: '+91 99155-98765',
  },
];

export const DEFAULT_EMPLOYEE = MOCK_EMPLOYEES[0];

/**
 * Normalizes input identifier to backend-compatible employee ID (e.g. E0007).
 */
export function resolveEmployeeCredentials(identifier) {
  if (!identifier) return null;
  const clean = identifier.trim().toLowerCase();

  // Exact ID match (case-insensitive)
  const match = MOCK_EMPLOYEES.find(
    (e) =>
      e.id.toLowerCase() === clean ||
      e.legacyId.toLowerCase() === clean ||
      e.email.toLowerCase() === clean ||
      e.name.toLowerCase() === clean
  );

  if (match) return match;

  // Direct backend pattern: E0001..E0100
  if (/^e\d{4}$/i.test(clean)) {
    const formattedId = clean.toUpperCase();
    return {
      id: formattedId,
      name: `Employee ${formattedId.slice(1)}`,
      email: `${clean}@punjabsportsmart.com`,
      password: 'password123',
      role: 'Store Staff',
      department: 'Store Floor Operations',
      storeId: 'ST001',
      storeName: 'Jalandhar Sports Hub',
      city: 'Jalandhar',
      shift: 'Standard Duty Shift',
      initials: formattedId.slice(0, 2),
      avatarBg: 'linear-gradient(135deg, #2563eb, #1d4ed8)',
      badgeText: 'Staff',
      escalationLevel: 3,
      securityClearance: 'Level 3 - Associate',
    };
  }

  return null;
}
