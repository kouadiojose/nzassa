/** Types partagés de l'API N'Zassa Business. */

export interface ApiResponse<T> {
  success: boolean;
  message: string;
  data: T;
  meta: Record<string, unknown>;
}

export interface ApiError {
  success: false;
  message: string;
  error: { code: string; details: Record<string, unknown> };
}

export interface TokenPair {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
}

export interface User {
  id: string;
  tenant_id: string | null;
  email: string;
  phone: string | null;
  first_name: string;
  last_name: string;
  is_active: boolean;
  is_superadmin: boolean;
}

export interface AuthResult {
  user: User;
  tokens: TokenPair;
  permissions: string[];
}

export interface Branch {
  id: string;
  code: string;
  name: string;
  is_active: boolean;
}

export interface Product {
  id: string;
  name: string;
  sku: string | null;
  barcode: string | null;
  selling_price: string;
  purchase_price: string;
  promo_price: string | null;
  low_stock_threshold: string;
  track_stock: boolean;
  is_active: boolean;
}

export interface Customer {
  id: string;
  first_name: string;
  last_name: string | null;
  phone: string | null;
  email: string | null;
}

export interface SaleItem {
  id: string;
  label: string;
  quantity: string;
  unit_price: string;
  line_total: string;
}

export interface Sale {
  id: string;
  number: string;
  status: string;
  sold_at: string;
  total: string;
  amount_paid: string;
  amount_due: string;
  items: SaleItem[];
}

export interface StockLevel {
  id: string;
  branch_id: string;
  product_id: string;
  quantity: string;
}

export interface DashboardData {
  period: { from: string; to: string };
  revenue: string;
  sales_count: number;
  expenses: string;
  gross_margin: string;
  estimated_profit: string;
  open_debts: string;
  stock_value: string;
  low_stock_count: number;
}

export interface TenantSummary {
  id: string;
  name: string;
  slug: string;
  status: string;
  created_at: string;
}
