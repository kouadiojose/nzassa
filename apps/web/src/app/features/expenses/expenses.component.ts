import { Component, OnInit, inject, signal } from '@angular/core';
import { DatePipe, DecimalPipe } from '@angular/common';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { TableModule } from 'primeng/table';

import { ApiService } from '../../core/api.service';
import { AuthService } from '../../core/auth.service';
import { Branch } from '../../core/api.types';

interface Expense {
  id: string;
  label: string;
  amount: string;
  expense_date: string;
  payment_method: string;
  status: string;
}

@Component({
  selector: 'nz-expenses',
  standalone: true,
  imports: [DecimalPipe, DatePipe, ReactiveFormsModule, TableModule],
  template: `
    <div class="flex items-center justify-between mb-4">
      <h2 class="text-xl font-bold">Dépenses</h2>
      @if (auth.hasPermission('expenses.create')) {
        <button class="nz-btn-primary" (click)="showForm.set(!showForm())">
          {{ showForm() ? 'Fermer' : '+ Nouvelle dépense' }}
        </button>
      }
    </div>

    @if (showForm()) {
      <form [formGroup]="form" (ngSubmit)="create()" class="nz-card mb-4 grid grid-cols-1 md:grid-cols-4 gap-3">
        <div>
          <label class="nz-label" for="label">Libellé</label>
          <input id="label" class="nz-input" formControlName="label" />
        </div>
        <div>
          <label class="nz-label" for="amount">Montant</label>
          <input id="amount" type="number" class="nz-input" formControlName="amount" />
        </div>
        <div>
          <label class="nz-label" for="expense_date">Date</label>
          <input id="expense_date" type="date" class="nz-input" formControlName="expense_date" />
        </div>
        <div class="flex items-end">
          <button type="submit" class="nz-btn-primary" [disabled]="form.invalid">Enregistrer</button>
        </div>
      </form>
    }

    <div class="nz-card">
      <p-table [value]="expenses()" styleClass="p-datatable-sm">
        <ng-template pTemplate="header">
          <tr>
            <th>Libellé</th>
            <th>Date</th>
            <th>Moyen</th>
            <th>Statut</th>
            <th class="text-right">Montant</th>
          </tr>
        </ng-template>
        <ng-template pTemplate="body" let-expense>
          <tr>
            <td class="font-medium">{{ expense.label }}</td>
            <td>{{ expense.expense_date | date: 'dd/MM/yyyy' }}</td>
            <td class="text-gray-500">{{ expense.payment_method }}</td>
            <td>{{ expense.status }}</td>
            <td class="text-right">{{ +expense.amount | number }} F</td>
          </tr>
        </ng-template>
      </p-table>
    </div>
  `
})
export class ExpensesComponent implements OnInit {
  private readonly api = inject(ApiService);
  private readonly fb = inject(FormBuilder);
  readonly auth = inject(AuthService);

  readonly expenses = signal<Expense[]>([]);
  readonly showForm = signal(false);
  private branchId = '';

  readonly form = this.fb.nonNullable.group({
    label: ['', Validators.required],
    amount: ['', Validators.required],
    expense_date: [new Date().toISOString().slice(0, 10), Validators.required]
  });

  ngOnInit(): void {
    this.api.get<Branch[]>('/business/branches').subscribe((branches) => {
      if (branches.length) this.branchId = branches[0].id;
    });
    this.load();
  }

  load(): void {
    this.api
      .get<Expense[]>('/expenses', { per_page: 100 })
      .subscribe((e) => this.expenses.set(e));
  }

  create(): void {
    const value = this.form.getRawValue();
    this.api
      .post('/expenses', {
        branch_id: this.branchId,
        label: value.label,
        amount: String(value.amount),
        expense_date: value.expense_date,
        payment_method: 'cash'
      })
      .subscribe(() => {
        this.form.reset({
          label: '',
          amount: '',
          expense_date: new Date().toISOString().slice(0, 10)
        });
        this.showForm.set(false);
        this.load();
      });
  }
}
