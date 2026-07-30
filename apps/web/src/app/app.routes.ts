import { Routes } from '@angular/router';

import { authGuard, superadminGuard } from './core/guards';

export const routes: Routes = [
  { path: '', pathMatch: 'full', redirectTo: 'app/dashboard' },
  {
    path: 'auth',
    children: [
      {
        path: 'login',
        loadComponent: () => import('./features/auth/login.component').then((m) => m.LoginComponent)
      },
      {
        path: 'register',
        loadComponent: () =>
          import('./features/auth/register.component').then((m) => m.RegisterComponent)
      }
    ]
  },
  {
    path: 'app',
    canActivate: [authGuard],
    loadComponent: () => import('./layout/shell.component').then((m) => m.ShellComponent),
    children: [
      { path: '', pathMatch: 'full', redirectTo: 'dashboard' },
      {
        path: 'dashboard',
        loadComponent: () =>
          import('./features/dashboard/dashboard.component').then((m) => m.DashboardComponent)
      },
      {
        path: 'sales',
        loadComponent: () =>
          import('./features/sales/sales-list.component').then((m) => m.SalesListComponent)
      },
      {
        path: 'sales/new',
        loadComponent: () =>
          import('./features/sales/sale-create.component').then((m) => m.SaleCreateComponent)
      },
      {
        path: 'products',
        loadComponent: () =>
          import('./features/products/products.component').then((m) => m.ProductsComponent)
      },
      {
        path: 'customers',
        loadComponent: () =>
          import('./features/customers/customers.component').then((m) => m.CustomersComponent)
      },
      {
        path: 'stock',
        loadComponent: () =>
          import('./features/stock/stock.component').then((m) => m.StockComponent)
      },
      {
        path: 'expenses',
        loadComponent: () =>
          import('./features/expenses/expenses.component').then((m) => m.ExpensesComponent)
      }
    ]
  },
  {
    path: 'admin',
    canActivate: [superadminGuard],
    loadComponent: () => import('./layout/shell.component').then((m) => m.ShellComponent),
    children: [
      { path: '', pathMatch: 'full', redirectTo: 'dashboard' },
      {
        path: 'dashboard',
        loadComponent: () =>
          import('./features/superadmin/admin-dashboard.component').then(
            (m) => m.AdminDashboardComponent
          )
      },
      {
        path: 'tenants',
        loadComponent: () =>
          import('./features/superadmin/tenants.component').then((m) => m.TenantsComponent)
      }
    ]
  },
  { path: '**', redirectTo: 'app/dashboard' }
];
