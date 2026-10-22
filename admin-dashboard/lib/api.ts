export class APIError extends Error { constructor(message: string, public code: string, public status: number) {super(message);} }
export async function api<T>(path: string, method = 'GET', body?: unknown): Promise<T> {
  const csrf = typeof document === 'undefined' ? '' : document.cookie.split('; ').find(v => v.startsWith('chesslab_csrf='))?.split('=')[1] || '';
  const response = await fetch('/api/v1' + path, {method, credentials:'same-origin', cache:'no-store', headers:{'Content-Type':'application/json', 'X-CSRF-Token':decodeURIComponent(csrf)}, body: body === undefined ? undefined : JSON.stringify(body)});
  const result = await response.json();
  if (!response.ok) throw new APIError(result.error?.message || 'Permintaan gagal.', result.error?.code || 'UNKNOWN', response.status);
  return result as T;
}
export interface User {email: string; role: 'admin'|'operator'|'viewer'}
export interface Customer {id: string; name: string; email: string; status: string; created_at: string}
export interface Product {id: string; code: string; name: string; status: string}
export interface Plan {id: string; product_id: string; name: string; duration_seconds: number; price_idr: number; max_devices: number; is_active: boolean}
export interface License {id: string; customer_id: string; product_id: string; plan_id: string; key_prefix: string; status: string; activated_at: string|null; expires_at: string|null; created_at: string; max_devices: number}
export interface Activation {id: string; device_hash: string; license_id: string; activated_at: string; last_seen_at: string; deactivated_at: string|null}
export interface Renewal {id: string; license_id: string; created_at: string; previous_expiry: string; new_expiry: string; duration_seconds: number}
export interface Audit {id: string; action: string; actor_id: string; actor_type: string; resource_id: string; created_at: string; details: Record<string, unknown>}
export interface Page<T> {items: T[]; total: number; page: number; size: number}
export interface Summary {total: number; counts: Record<string, number>; expiring_soon: number; recent_activations: Activation[]; recent_renewals: Renewal[]}
export interface Detail {license: License; customer: Customer; plan: Plan; activations: Activation[]; renewals: Renewal[]}
