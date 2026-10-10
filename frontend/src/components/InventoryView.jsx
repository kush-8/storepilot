import React, { useState, useMemo } from 'react';
import {
  Search,
  Filter,
  AlertTriangle,
  PackageCheck,
  PackageX,
  Sparkles,
  RefreshCw,
  Building,
} from 'lucide-react';
import { STORES } from '../data/mockData';

export default function InventoryView({
  inventory,
  setInventory,
  onTriageWithCopilot,
  selectedStore = 'ALL',
}) {
  const [searchQuery, setSearchQuery] = useState('');
  const [storeFilter, setStoreFilter] = useState(selectedStore || 'ALL');
  const [statusFilter, setStatusFilter] = useState('ALL');
  const [reorderNotification, setReorderNotification] = useState(null);

  // Summary Metrics
  const totalItems = inventory.length;
  const outOfStockItems = inventory.filter((i) => i.status === 'Out of Stock').length;
  const lowStockItems = inventory.filter((i) => i.status === 'Low Stock').length;
  const healthyItems = inventory.filter((i) => i.status === 'In Stock').length;

  // Filtered Inventory
  const filteredInventory = useMemo(() => {
    return inventory.filter((item) => {
      const matchesSearch =
        item.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
        item.sku.toLowerCase().includes(searchQuery.toLowerCase()) ||
        item.category.toLowerCase().includes(searchQuery.toLowerCase()) ||
        item.vendor.toLowerCase().includes(searchQuery.toLowerCase());

      const matchesStore = storeFilter === 'ALL' || item.storeId === storeFilter;
      const matchesStatus = statusFilter === 'ALL' || item.status === statusFilter;

      return matchesSearch && matchesStore && matchesStatus;
    });
  }, [inventory, searchQuery, storeFilter, statusFilter]);

  const handleSimulateRestock = (item) => {
    const qtyToAdd = Math.max(item.reorderPoint * 2, 20);
    setInventory((prev) =>
      prev.map((i) => {
        if (i.sku === item.sku && i.storeId === item.storeId) {
          const newOnHand = i.onHand + qtyToAdd;
          return {
            ...i,
            onHand: newOnHand,
            status: newOnHand > i.reorderPoint ? 'In Stock' : 'Low Stock',
            lastRestocked: 'Just now (Simulated)',
          };
        }
        return i;
      })
    );

    setReorderNotification(
      `Replenishment simulated: Ordered +${qtyToAdd} units of "${item.name}" for Store ${item.storeId} from ${item.vendor}.`
    );
    setTimeout(() => setReorderNotification(null), 4000);
  };

  const getStatusBadge = (status) => {
    switch (status) {
      case 'Out of Stock':
        return <span className="status-badge-out">Out of Stock</span>;
      case 'Low Stock':
        return <span className="status-badge-low">Low Stock Alert</span>;
      case 'In Stock':
        return <span className="status-badge-in">In Stock</span>;
      default:
        return <span className="status-badge-neutral">{status}</span>;
    }
  };

  return (
    <div className="inventory-container">
      {/* Reorder Notification Toast */}
      {reorderNotification && (
        <div className="inventory-toast-banner">
          <PackageCheck size={18} className="text-success" />
          <span>{reorderNotification}</span>
          <button className="toast-close" onClick={() => setReorderNotification(null)}>
            ✕
          </button>
        </div>
      )}

      {/* Inventory KPI Summary */}
      <div className="kpi-grid">
        <div className="kpi-card">
          <div className="kpi-header">
            <span className="kpi-label">TOTAL TRACKED SKUS</span>
            <div className="kpi-icon-wrapper bg-blue-subtle">
              <PackageCheck size={20} className="text-blue" />
            </div>
          </div>
          <div className="kpi-body">
            <div className="kpi-value">{totalItems}</div>
            <div className="kpi-meta text-muted">Across all Punjab sports branches</div>
          </div>
        </div>

        <div className="kpi-card kpi-border-p1">
          <div className="kpi-header">
            <span className="kpi-label text-danger font-semibold">OUT OF STOCK (CRITICAL)</span>
            <div className="kpi-icon-wrapper bg-red-subtle">
              <PackageX size={20} className="text-danger" />
            </div>
          </div>
          <div className="kpi-body">
            <div className="kpi-value text-danger">{outOfStockItems}</div>
            <div className="kpi-meta text-danger">Immediate vendor replenishment required</div>
          </div>
        </div>

        <div className="kpi-card">
          <div className="kpi-header">
            <span className="kpi-label text-orange font-semibold">LOW STOCK ALERTS</span>
            <div className="kpi-icon-wrapper bg-orange-subtle">
              <AlertTriangle size={20} className="text-orange" />
            </div>
          </div>
          <div className="kpi-body">
            <div className="kpi-value text-orange">{lowStockItems}</div>
            <div className="kpi-meta text-muted">Below configured safety buffer threshold</div>
          </div>
        </div>

        <div className="kpi-card">
          <div className="kpi-header">
            <span className="kpi-label text-success font-semibold">OPTIMAL STOCK HEALTH</span>
            <div className="kpi-icon-wrapper bg-green-subtle">
              <PackageCheck size={20} className="text-success" />
            </div>
          </div>
          <div className="kpi-body">
            <div className="kpi-value text-success">{healthyItems}</div>
            <div className="kpi-meta text-muted">Adequate floor inventory coverage</div>
          </div>
        </div>
      </div>

      {/* Controls & Search Filter Bar */}
      <div className="table-filter-bar">
        <div className="search-input-wrapper">
          <Search size={18} className="search-icon" />
          <input
            type="text"
            className="search-input"
            placeholder="Search by product name, SKU (e.g. PSM-CRK-101), category, vendor..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
          />
          {searchQuery && (
            <button className="clear-search-btn" onClick={() => setSearchQuery('')}>
              ✕
            </button>
          )}
        </div>

        <div className="filter-dropdowns-group">
          {/* Store Filter */}
          <div className="select-wrapper">
            <Building size={15} className="dropdown-icon" />
            <select
              value={storeFilter}
              onChange={(e) => setStoreFilter(e.target.value)}
              className="filter-select"
            >
              <option value="ALL">All Store Locations</option>
              {STORES.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.id} ({s.city})
                </option>
              ))}
            </select>
          </div>

          {/* Stock Status Filter */}
          <div className="select-wrapper">
            <Filter size={15} className="dropdown-icon" />
            <select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              className="filter-select"
            >
              <option value="ALL">All Stock Statuses</option>
              <option value="Out of Stock">Out of Stock</option>
              <option value="Low Stock">Low Stock Alert</option>
              <option value="In Stock">In Stock</option>
            </select>
          </div>
        </div>
      </div>

      {/* Inventory Table Card */}
      <div className="dashboard-table-card">
        <div className="table-header-row">
          <div>
            <h3 className="table-title">Store Inventory Ledger</h3>
            <p className="table-subtitle">
              Displaying {filteredInventory.length} of {inventory.length} demo sporting goods SKUs
            </p>
          </div>
          <span className="sample-badge">Sample ERP Inventory</span>
        </div>

        <div className="table-responsive">
          <table className="enterprise-table">
            <thead>
              <tr>
                <th>Product Name</th>
                <th>SKU</th>
                <th>Store ID</th>
                <th>Category</th>
                <th className="text-center">On-Hand Stock</th>
                <th className="text-center">Reorder Point</th>
                <th>MSRP Unit Price</th>
                <th>Status</th>
                <th>Primary Vendor</th>
                <th className="text-right">Actions</th>
              </tr>
            </thead>
            <tbody>
              {filteredInventory.length === 0 ? (
                <tr>
                  <td colSpan={10} className="empty-table-cell">
                    No matching inventory items found for &ldquo;{searchQuery}&rdquo;.
                  </td>
                </tr>
              ) : (
                filteredInventory.map((item) => {
                  const isStockCritical = item.status === 'Out of Stock';
                  const isLow = item.status === 'Low Stock';

                  return (
                    <tr
                      key={`${item.sku}-${item.storeId}`}
                      className={isStockCritical ? 'row-critical' : isLow ? 'row-warning' : ''}
                    >
                      <td className="cell-product-name">
                        <div className="product-title font-medium">{item.name}</div>
                        <div className="product-meta text-xs text-muted">
                          Restocked: {item.lastRestocked}
                        </div>
                      </td>
                      <td className="font-mono text-xs text-primary font-semibold">{item.sku}</td>
                      <td>
                        <span className="store-pill font-mono">{item.storeId}</span>
                      </td>
                      <td>
                        <span className="category-pill">{item.category}</span>
                      </td>
                      <td className="text-center font-bold">
                        <span
                          className={
                            isStockCritical
                              ? 'text-danger'
                              : isLow
                              ? 'text-orange'
                              : 'text-dark font-medium'
                          }
                        >
                          {item.onHand} units
                        </span>
                      </td>
                      <td className="text-center text-muted font-mono">{item.reorderPoint} units</td>
                      <td className="font-semibold text-dark">₹{item.unitPrice.toLocaleString('en-IN')}</td>
                      <td>{getStatusBadge(item.status)}</td>
                      <td className="text-muted text-sm">{item.vendor}</td>
                      <td className="text-right">
                        <div className="table-actions">
                          {/* Copilot Triage */}
                          <button
                            className="btn-table-action"
                            onClick={() =>
                              onTriageWithCopilot(
                                `${item.name} out of stock at ${item.storeId}`
                              )
                            }
                            title="Triage stock issue with Copilot"
                          >
                            <Sparkles size={14} />
                            <span>Copilot</span>
                          </button>

                          {/* Quick Restock simulation */}
                          <button
                            className="btn-table-action-secondary"
                            onClick={() => handleSimulateRestock(item)}
                            title="Simulate PO Replenishment"
                          >
                            <RefreshCw size={14} />
                            <span>Reorder</span>
                          </button>
                        </div>
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
