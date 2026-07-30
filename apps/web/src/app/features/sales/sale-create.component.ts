import { Component, OnInit, computed, inject, signal } from '@angular/core';
import { DecimalPipe } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { Router } from '@angular/router';

import { ApiService } from '../../core/api.service';
import { Branch, Customer, Product, Sale } from '../../core/api.types';

interface CartLine {
  product: Product;
  quantity: number;
}

const PAYMENT_METHODS = [
  { code: 'cash', label: 'Espèces' },
  { code: 'wave', label: 'Wave' },
  { code: 'orange_money', label: 'Orange Money' },
  { code: 'mtn_money', label: 'MTN Money' },
  { code: 'moov_money', label: 'Moov Money' },
  { code: 'card', label: 'Carte' },
  { code: 'bank_transfer', label: 'Virement' }
];

@Component({
  selector: 'nz-sale-create',
  standalone: true,
  imports: [DecimalPipe, FormsModule],
  template: `
    <h2 class="text-xl font-bold mb-4">Nouvelle vente</h2>
    @if (error()) {
      <p class="mb-4 rounded-lg bg-red-50 text-red-700 px-3 py-2 text-sm">{{ error() }}</p>
    }
    <div class="grid grid-cols-1 lg:grid-cols-3 gap-4">
      <div class="lg:col-span-2 nz-card">
        <input
          class="nz-input mb-3"
          placeholder="Rechercher un produit (nom, code-barres)…"
          [ngModel]="searchTerm()"
          (ngModelChange)="search($event)"
        />
        <div class="grid grid-cols-2 md:grid-cols-3 gap-2">
          @for (product of products(); track product.id) {
            <button
              class="border border-gray-200 rounded-lg p-3 text-left hover:border-nzassa-500 hover:bg-nzassa-50"
              (click)="addToCart(product)"
            >
              <p class="font-medium text-sm truncate">{{ product.name }}</p>
              <p class="text-nzassa-700 font-bold">{{ +product.selling_price | number }} F</p>
            </button>
          }
        </div>
      </div>

      <div class="nz-card space-y-3">
        <h3 class="font-semibold">Panier</h3>
        <div>
          <label class="nz-label" for="branch">Point de vente</label>
          <select id="branch" class="nz-input" [(ngModel)]="branchId">
            @for (branch of branches(); track branch.id) {
              <option [value]="branch.id">{{ branch.name }}</option>
            }
          </select>
        </div>
        <div>
          <label class="nz-label" for="customer">Client (facultatif)</label>
          <select id="customer" class="nz-input" [(ngModel)]="customerId">
            <option value="">— Aucun —</option>
            @for (customer of customers(); track customer.id) {
              <option [value]="customer.id">
                {{ customer.first_name }} {{ customer.last_name }}
              </option>
            }
          </select>
        </div>

        @for (line of cart(); track line.product.id) {
          <div class="flex items-center gap-2 border-b border-gray-100 pb-2">
            <span class="flex-1 text-sm truncate">{{ line.product.name }}</span>
            <input
              type="number"
              min="1"
              class="nz-input !w-16 !px-2"
              [ngModel]="line.quantity"
              (ngModelChange)="setQuantity(line, $event)"
            />
            <span class="text-sm w-20 text-right">
              {{ +line.product.selling_price * line.quantity | number }} F
            </span>
            <button class="text-red-500" (click)="remove(line)">✕</button>
          </div>
        } @empty {
          <p class="text-sm text-gray-400">Aucun article — cliquez sur un produit.</p>
        }

        <p class="text-lg font-bold text-right">Total : {{ total() | number }} F</p>

        <div>
          <label class="nz-label" for="method">Moyen de paiement</label>
          <select id="method" class="nz-input" [(ngModel)]="paymentMethod">
            @for (method of paymentMethods; track method.code) {
              <option [value]="method.code">{{ method.label }}</option>
            }
          </select>
        </div>
        <div>
          <label class="nz-label" for="amount">Montant payé</label>
          <input id="amount" type="number" class="nz-input" [(ngModel)]="amountPaid" />
          <p class="text-xs text-gray-500 mt-1">
            Un montant inférieur au total crée une vente à crédit (client requis).
          </p>
        </div>
        <button
          class="nz-btn-primary w-full"
          [disabled]="cart().length === 0 || saving()"
          (click)="submit()"
        >
          {{ saving() ? 'Enregistrement…' : 'Valider la vente' }}
        </button>
      </div>
    </div>
  `
})
export class SaleCreateComponent implements OnInit {
  private readonly api = inject(ApiService);
  private readonly router = inject(Router);

  readonly products = signal<Product[]>([]);
  readonly branches = signal<Branch[]>([]);
  readonly customers = signal<Customer[]>([]);
  readonly cart = signal<CartLine[]>([]);
  readonly searchTerm = signal('');
  readonly saving = signal(false);
  readonly error = signal<string | null>(null);

  branchId = '';
  customerId = '';
  paymentMethod = 'cash';
  amountPaid = 0;

  readonly paymentMethods = PAYMENT_METHODS;

  readonly total = computed(() =>
    this.cart().reduce((sum, line) => sum + Number(line.product.selling_price) * line.quantity, 0)
  );

  ngOnInit(): void {
    this.loadProducts();
    this.api.get<Branch[]>('/business/branches').subscribe((branches) => {
      this.branches.set(branches);
      if (branches.length) this.branchId = branches[0].id;
    });
    this.api
      .get<Customer[]>('/customers', { per_page: 100 })
      .subscribe((customers) => this.customers.set(customers));
  }

  loadProducts(term = ''): void {
    const params: Record<string, string> = { per_page: '30' };
    if (term) params['search'] = term;
    this.api.get<Product[]>('/catalog/products', params).subscribe((p) => this.products.set(p));
  }

  search(term: string): void {
    this.searchTerm.set(term);
    this.loadProducts(term);
  }

  addToCart(product: Product): void {
    const lines = [...this.cart()];
    const existing = lines.find((l) => l.product.id === product.id);
    if (existing) existing.quantity += 1;
    else lines.push({ product, quantity: 1 });
    this.cart.set(lines);
    this.amountPaid = this.total();
  }

  setQuantity(line: CartLine, quantity: number): void {
    line.quantity = Math.max(1, Number(quantity) || 1);
    this.cart.set([...this.cart()]);
    this.amountPaid = this.total();
  }

  remove(line: CartLine): void {
    this.cart.set(this.cart().filter((l) => l !== line));
    this.amountPaid = this.total();
  }

  submit(): void {
    this.saving.set(true);
    this.error.set(null);
    const payments =
      this.amountPaid > 0
        ? [{ method: this.paymentMethod, amount: String(this.amountPaid) }]
        : [];
    this.api
      .post<Sale>('/sales', {
        branch_id: this.branchId,
        customer_id: this.customerId || null,
        items: this.cart().map((line) => ({
          item_type: 'product',
          product_id: line.product.id,
          quantity: String(line.quantity)
        })),
        payments
      })
      .subscribe({
        next: () => void this.router.navigate(['/app/sales']),
        error: (err) => {
          this.saving.set(false);
          this.error.set(err?.error?.message ?? 'Erreur lors de la vente');
        }
      });
  }
}
