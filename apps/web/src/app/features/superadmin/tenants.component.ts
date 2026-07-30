import { Component, OnInit, inject, signal } from '@angular/core';
import { DatePipe } from '@angular/common';
import { TableModule } from 'primeng/table';

import { ApiService } from '../../core/api.service';
import { TenantSummary } from '../../core/api.types';

@Component({
  selector: 'nz-admin-tenants',
  standalone: true,
  imports: [DatePipe, TableModule],
  template: `
    <h2 class="text-xl font-bold mb-4">Entreprises</h2>
    <div class="nz-card">
      <p-table [value]="tenants()" styleClass="p-datatable-sm">
        <ng-template pTemplate="header">
          <tr>
            <th>Nom</th>
            <th>Statut</th>
            <th>Créée le</th>
            <th></th>
          </tr>
        </ng-template>
        <ng-template pTemplate="body" let-tenant>
          <tr>
            <td class="font-medium">{{ tenant.name }}</td>
            <td>
              <span
                class="rounded-full px-2 py-0.5 text-xs"
                [class]="
                  tenant.status === 'active'
                    ? 'bg-green-100 text-green-700'
                    : 'bg-red-100 text-red-700'
                "
              >
                {{ tenant.status === 'active' ? 'Active' : 'Suspendue' }}
              </span>
            </td>
            <td>{{ tenant.created_at | date: 'dd/MM/yyyy' }}</td>
            <td class="text-right">
              @if (tenant.status === 'active') {
                <button class="text-red-600 text-sm hover:underline" (click)="suspend(tenant)">
                  Suspendre
                </button>
              } @else {
                <button class="text-green-600 text-sm hover:underline" (click)="activate(tenant)">
                  Réactiver
                </button>
              }
            </td>
          </tr>
        </ng-template>
      </p-table>
    </div>
  `
})
export class TenantsComponent implements OnInit {
  private readonly api = inject(ApiService);
  readonly tenants = signal<TenantSummary[]>([]);

  ngOnInit(): void {
    this.load();
  }

  load(): void {
    this.api
      .get<TenantSummary[]>('/superadmin/tenants', { per_page: 100 })
      .subscribe((t) => this.tenants.set(t));
  }

  suspend(tenant: TenantSummary): void {
    const reason = prompt('Motif de suspension ?');
    if (!reason) return;
    this.api
      .post(`/superadmin/tenants/${tenant.id}/suspend`, { reason })
      .subscribe(() => this.load());
  }

  activate(tenant: TenantSummary): void {
    this.api.post(`/superadmin/tenants/${tenant.id}/activate`, {}).subscribe(() => this.load());
  }
}
