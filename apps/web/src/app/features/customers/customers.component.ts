import { Component, OnInit, inject, signal } from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { TableModule } from 'primeng/table';

import { ApiService } from '../../core/api.service';
import { AuthService } from '../../core/auth.service';
import { Customer } from '../../core/api.types';

@Component({
  selector: 'nz-customers',
  standalone: true,
  imports: [ReactiveFormsModule, TableModule],
  template: `
    <div class="flex items-center justify-between mb-4">
      <h2 class="text-xl font-bold">Clients</h2>
      @if (auth.hasPermission('customers.create')) {
        <button class="nz-btn-primary" (click)="showForm.set(!showForm())">
          {{ showForm() ? 'Fermer' : '+ Nouveau client' }}
        </button>
      }
    </div>

    @if (showForm()) {
      <form [formGroup]="form" (ngSubmit)="create()" class="nz-card mb-4 grid grid-cols-1 md:grid-cols-4 gap-3">
        <div>
          <label class="nz-label" for="first_name">Prénom</label>
          <input id="first_name" class="nz-input" formControlName="first_name" />
        </div>
        <div>
          <label class="nz-label" for="last_name">Nom</label>
          <input id="last_name" class="nz-input" formControlName="last_name" />
        </div>
        <div>
          <label class="nz-label" for="phone">Téléphone</label>
          <input id="phone" class="nz-input" formControlName="phone" placeholder="+225…" />
        </div>
        <div class="flex items-end">
          <button type="submit" class="nz-btn-primary" [disabled]="form.invalid">Créer</button>
        </div>
      </form>
    }

    <div class="nz-card">
      <input
        class="nz-input mb-3 max-w-sm"
        placeholder="Rechercher (nom, téléphone)…"
        (input)="search($any($event.target).value)"
      />
      <p-table [value]="customers()" styleClass="p-datatable-sm">
        <ng-template pTemplate="header">
          <tr>
            <th>Nom</th>
            <th>Téléphone</th>
            <th>Email</th>
          </tr>
        </ng-template>
        <ng-template pTemplate="body" let-customer>
          <tr>
            <td class="font-medium">{{ customer.first_name }} {{ customer.last_name }}</td>
            <td>{{ customer.phone }}</td>
            <td class="text-gray-500">{{ customer.email }}</td>
          </tr>
        </ng-template>
      </p-table>
    </div>
  `
})
export class CustomersComponent implements OnInit {
  private readonly api = inject(ApiService);
  private readonly fb = inject(FormBuilder);
  readonly auth = inject(AuthService);

  readonly customers = signal<Customer[]>([]);
  readonly showForm = signal(false);

  readonly form = this.fb.nonNullable.group({
    first_name: ['', Validators.required],
    last_name: [''],
    phone: ['']
  });

  ngOnInit(): void {
    this.load();
  }

  load(term = ''): void {
    const params: Record<string, string> = { per_page: '100' };
    if (term) params['search'] = term;
    this.api.get<Customer[]>('/customers', params).subscribe((c) => this.customers.set(c));
  }

  search(term: string): void {
    this.load(term);
  }

  create(): void {
    const value = this.form.getRawValue();
    this.api
      .post<Customer>('/customers', {
        first_name: value.first_name,
        last_name: value.last_name || null,
        phone: value.phone || null
      })
      .subscribe(() => {
        this.form.reset();
        this.showForm.set(false);
        this.load();
      });
  }
}
