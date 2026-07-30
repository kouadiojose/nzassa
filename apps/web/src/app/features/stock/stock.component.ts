import { Component, OnInit, inject, signal } from '@angular/core';
import { DecimalPipe } from '@angular/common';
import { TableModule } from 'primeng/table';

import { ApiService } from '../../core/api.service';
import { Product, StockLevel } from '../../core/api.types';

@Component({
  selector: 'nz-stock',
  standalone: true,
  imports: [DecimalPipe, TableModule],
  template: `
    <div class="flex items-center justify-between mb-4">
      <h2 class="text-xl font-bold">Stock</h2>
      <label class="text-sm flex items-center gap-2">
        <input type="checkbox" (change)="toggleLowStock($any($event.target).checked)" />
        Stock faible uniquement
      </label>
    </div>
    <div class="nz-card">
      <p-table [value]="rows()" styleClass="p-datatable-sm">
        <ng-template pTemplate="header">
          <tr>
            <th>Produit</th>
            <th class="text-right">Quantité</th>
            <th class="text-right">Seuil</th>
          </tr>
        </ng-template>
        <ng-template pTemplate="body" let-row>
          <tr>
            <td>{{ row.name }}</td>
            <td class="text-right font-medium" [class.text-red-600]="row.low">
              {{ +row.quantity | number }}
            </td>
            <td class="text-right text-gray-400">{{ +row.threshold | number }}</td>
          </tr>
        </ng-template>
      </p-table>
    </div>
  `
})
export class StockComponent implements OnInit {
  private readonly api = inject(ApiService);
  readonly rows = signal<{ name: string; quantity: string; threshold: string; low: boolean }[]>([]);

  ngOnInit(): void {
    this.load(false);
  }

  toggleLowStock(lowOnly: boolean): void {
    this.load(lowOnly);
  }

  load(lowOnly: boolean): void {
    this.api.get<Product[]>('/catalog/products', { per_page: 200 }).subscribe((products) => {
      const byId = new Map(products.map((p) => [p.id, p]));
      this.api
        .get<StockLevel[]>('/stock/levels', { per_page: 200, low_stock: lowOnly })
        .subscribe((levels) => {
          this.rows.set(
            levels.map((level) => {
              const product = byId.get(level.product_id);
              return {
                name: product?.name ?? level.product_id,
                quantity: level.quantity,
                threshold: product?.low_stock_threshold ?? '0',
                low: product ? Number(level.quantity) <= Number(product.low_stock_threshold) : false
              };
            })
          );
        });
    });
  }
}
