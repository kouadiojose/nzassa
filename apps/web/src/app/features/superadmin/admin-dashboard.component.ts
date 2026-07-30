import { Component, OnInit, inject, signal } from '@angular/core';

import { ApiService } from '../../core/api.service';

interface GlobalDashboard {
  tenants_total: number;
  tenants_active: number;
  users_total: number;
  sales_total: number;
  subscriptions_by_status: Record<string, number>;
  pending_subscription_invoices: number;
  failed_sync_operations: number;
}

@Component({
  selector: 'nz-admin-dashboard',
  standalone: true,
  template: `
    <h2 class="text-xl font-bold mb-4">Super Administration — Vue globale</h2>
    @if (data(); as d) {
      <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div class="nz-card">
          <p class="text-sm text-gray-500">Entreprises</p>
          <p class="text-2xl font-bold">{{ d.tenants_total }}</p>
          <p class="text-xs text-gray-400">{{ d.tenants_active }} actives</p>
        </div>
        <div class="nz-card">
          <p class="text-sm text-gray-500">Utilisateurs</p>
          <p class="text-2xl font-bold">{{ d.users_total }}</p>
        </div>
        <div class="nz-card">
          <p class="text-sm text-gray-500">Ventes (toutes entreprises)</p>
          <p class="text-2xl font-bold">{{ d.sales_total }}</p>
        </div>
        <div class="nz-card">
          <p class="text-sm text-gray-500">Factures d'abonnement en attente</p>
          <p class="text-2xl font-bold text-amber-600">{{ d.pending_subscription_invoices }}</p>
        </div>
        <div class="nz-card">
          <p class="text-sm text-gray-500">Synchronisations en échec</p>
          <p class="text-2xl font-bold" [class.text-red-600]="d.failed_sync_operations > 0">
            {{ d.failed_sync_operations }}
          </p>
        </div>
      </div>
    } @else {
      <p class="text-gray-500">Chargement…</p>
    }
  `
})
export class AdminDashboardComponent implements OnInit {
  private readonly api = inject(ApiService);
  readonly data = signal<GlobalDashboard | null>(null);

  ngOnInit(): void {
    this.api.get<GlobalDashboard>('/superadmin/dashboard').subscribe((d) => this.data.set(d));
  }
}
