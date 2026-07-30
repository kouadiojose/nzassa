import { Component, OnInit, inject, signal } from '@angular/core';
import { DecimalPipe } from '@angular/common';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { TableModule } from 'primeng/table';

import { ApiService } from '../../core/api.service';
import { AuthService } from '../../core/auth.service';
import { Product } from '../../core/api.types';

@Component({
  selector: 'nz-products',
  standalone: true,
  imports: [DecimalPipe, ReactiveFormsModule, TableModule],
  template: `
    <div class="flex items-center justify-between mb-4">
      <h2 class="text-xl font-bold">Produits</h2>
      @if (auth.hasPermission('products.create')) {
        <button class="nz-btn-primary" (click)="showForm.set(!showForm())">
          {{ showForm() ? 'Fermer' : '+ Nouveau produit' }}
        </button>
      }
    </div>

    @if (showForm()) {
      <form [formGroup]="form" (ngSubmit)="create()" class="nz-card mb-4 grid grid-cols-1 md:grid-cols-4 gap-3">
        <div class="md:col-span-2">
          <label class="nz-label" for="name">Nom</label>
          <input id="name" class="nz-input" formControlName="name" />
        </div>
        <div>
          <label class="nz-label" for="selling_price">Prix de vente</label>
          <input id="selling_price" type="number" class="nz-input" formControlName="selling_price" />
        </div>
        <div>
          <label class="nz-label" for="purchase_price">Prix d'achat</label>
          <input id="purchase_price" type="number" class="nz-input" formControlName="purchase_price" />
        </div>
        <div>
          <label class="nz-label" for="barcode">Code-barres</label>
          <input id="barcode" class="nz-input" formControlName="barcode" />
        </div>
        <div class="flex items-end">
          <button type="submit" class="nz-btn-primary" [disabled]="form.invalid">Créer</button>
        </div>
      </form>
    }

    <div class="nz-card">
      <input
        class="nz-input mb-3 max-w-sm"
        placeholder="Rechercher un produit…"
        (input)="search($any($event.target).value)"
      />
      <p-table [value]="products()" [rows]="20" styleClass="p-datatable-sm">
        <ng-template pTemplate="header">
          <tr>
            <th>Nom</th>
            <th>SKU</th>
            <th class="text-right">Prix vente</th>
            <th class="text-right">Prix achat</th>
          </tr>
        </ng-template>
        <ng-template pTemplate="body" let-product>
          <tr>
            <td>{{ product.name }}</td>
            <td class="text-gray-500">{{ product.sku }}</td>
            <td class="text-right">{{ +product.selling_price | number }} F</td>
            <td class="text-right text-gray-500">{{ +product.purchase_price | number }} F</td>
          </tr>
        </ng-template>
      </p-table>
    </div>
  `
})
export class ProductsComponent implements OnInit {
  private readonly api = inject(ApiService);
  private readonly fb = inject(FormBuilder);
  readonly auth = inject(AuthService);

  readonly products = signal<Product[]>([]);
  readonly showForm = signal(false);

  readonly form = this.fb.nonNullable.group({
    name: ['', [Validators.required, Validators.minLength(1)]],
    selling_price: ['', Validators.required],
    purchase_price: ['0'],
    barcode: ['']
  });

  ngOnInit(): void {
    this.load();
  }

  load(searchTerm = ''): void {
    const params: Record<string, string> = { per_page: '100' };
    if (searchTerm) params['search'] = searchTerm;
    this.api.get<Product[]>('/catalog/products', params).subscribe((p) => this.products.set(p));
  }

  search(term: string): void {
    this.load(term);
  }

  create(): void {
    const value = this.form.getRawValue();
    this.api
      .post<Product>('/catalog/products', {
        name: value.name,
        selling_price: String(value.selling_price),
        purchase_price: String(value.purchase_price || 0),
        barcode: value.barcode || null
      })
      .subscribe(() => {
        this.form.reset({ name: '', selling_price: '', purchase_price: '0', barcode: '' });
        this.showForm.set(false);
        this.load();
      });
  }
}
