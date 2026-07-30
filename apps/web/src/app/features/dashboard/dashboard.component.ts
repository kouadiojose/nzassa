import { Component, OnInit, inject, signal } from '@angular/core';
import { DecimalPipe } from '@angular/common';

import { ApiService } from '../../core/api.service';
import { DashboardData } from '../../core/api.types';

@Component({
  selector: 'nz-dashboard',
  standalone: true,
  imports: [DecimalPipe],
  template: `
    <h2 class="text-xl font-bold mb-4">Tableau de bord</h2>
    @if (data(); as d) {
      <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div class="nz-card">
          <p class="text-sm text-gray-500">Chiffre d'affaires (30 j)</p>
          <p class="text-2xl font-bold text-nzassa-700">{{ +d.revenue | number }} F</p>
          <p class="text-xs text-gray-400">{{ d.sales_count }} ventes</p>
        </div>
        <div class="nz-card">
          <p class="text-sm text-gray-500">Dépenses</p>
          <p class="text-2xl font-bold">{{ +d.expenses | number }} F</p>
        </div>
        <div class="nz-card">
          <p class="text-sm text-gray-500">Bénéfice estimé</p>
          <p class="text-2xl font-bold text-green-700">{{ +d.estimated_profit | number }} F</p>
          <p class="text-xs text-gray-400">Marge brute : {{ +d.gross_margin | number }} F</p>
        </div>
        <div class="nz-card">
          <p class="text-sm text-gray-500">Créances clients</p>
          <p class="text-2xl font-bold text-amber-600">{{ +d.open_debts | number }} F</p>
        </div>
        <div class="nz-card">
          <p class="text-sm text-gray-500">Valeur du stock</p>
          <p class="text-2xl font-bold">{{ +d.stock_value | number }} F</p>
        </div>
        <div class="nz-card">
          <p class="text-sm text-gray-500">Produits en stock faible</p>
          <p class="text-2xl font-bold" [class.text-red-600]="d.low_stock_count > 0">
            {{ d.low_stock_count }}
          </p>
        </div>
      </div>
    } @else {
      <p class="text-gray-500">Chargement…</p>
    }
  `
})
export class DashboardComponent implements OnInit {
  private readonly api = inject(ApiService);
  readonly data = signal<DashboardData | null>(null);

  ngOnInit(): void {
    this.api.get<DashboardData>('/reports/dashboard').subscribe((d) => this.data.set(d));
  }
}
