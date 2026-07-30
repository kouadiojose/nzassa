import { Component, OnInit, inject, signal } from '@angular/core';
import { DatePipe, DecimalPipe } from '@angular/common';
import { RouterLink } from '@angular/router';
import { TableModule } from 'primeng/table';

import { ApiService } from '../../core/api.service';
import { Sale } from '../../core/api.types';

const STATUS_LABELS: Record<string, string> = {
  draft: 'Brouillon',
  completed: 'Validée',
  cancelled: 'Annulée',
  refunded: 'Remboursée',
  partially_refunded: 'Remb. partiel'
};

@Component({
  selector: 'nz-sales-list',
  standalone: true,
  imports: [DecimalPipe, DatePipe, RouterLink, TableModule],
  template: `
    <div class="flex items-center justify-between mb-4">
      <h2 class="text-xl font-bold">Ventes</h2>
      <a routerLink="/app/sales/new" class="nz-btn-primary">+ Nouvelle vente</a>
    </div>
    <div class="nz-card">
      <p-table [value]="sales()" styleClass="p-datatable-sm">
        <ng-template pTemplate="header">
          <tr>
            <th>Numéro</th>
            <th>Date</th>
            <th>Statut</th>
            <th class="text-right">Total</th>
            <th class="text-right">Payé</th>
            <th class="text-right">Reste dû</th>
          </tr>
        </ng-template>
        <ng-template pTemplate="body" let-sale>
          <tr>
            <td class="font-medium">{{ sale.number }}</td>
            <td>{{ sale.sold_at | date: 'dd/MM/yyyy HH:mm' }}</td>
            <td>
              <span
                class="rounded-full px-2 py-0.5 text-xs"
                [class]="
                  sale.status === 'completed'
                    ? 'bg-green-100 text-green-700'
                    : sale.status === 'cancelled'
                      ? 'bg-red-100 text-red-700'
                      : 'bg-gray-100 text-gray-600'
                "
              >
                {{ statusLabel(sale.status) }}
              </span>
            </td>
            <td class="text-right">{{ +sale.total | number }} F</td>
            <td class="text-right text-green-700">{{ +sale.amount_paid | number }} F</td>
            <td class="text-right" [class.text-amber-600]="+sale.amount_due > 0">
              {{ +sale.amount_due | number }} F
            </td>
          </tr>
        </ng-template>
      </p-table>
    </div>
  `
})
export class SalesListComponent implements OnInit {
  private readonly api = inject(ApiService);
  readonly sales = signal<Sale[]>([]);

  ngOnInit(): void {
    this.api.get<Sale[]>('/sales', { per_page: 50 }).subscribe((s) => this.sales.set(s));
  }

  statusLabel(status: string): string {
    return STATUS_LABELS[status] ?? status;
  }
}
