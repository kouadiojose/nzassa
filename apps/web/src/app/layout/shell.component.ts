import { Component, inject } from '@angular/core';
import { RouterLink, RouterLinkActive, RouterOutlet } from '@angular/router';

import { AuthService } from '../core/auth.service';

@Component({
  selector: 'nz-shell',
  standalone: true,
  imports: [RouterOutlet, RouterLink, RouterLinkActive],
  template: `
    <div class="min-h-screen flex">
      <aside class="w-60 bg-nzassa-900 text-white flex flex-col">
        <div class="p-4 border-b border-white/10">
          <h1 class="text-lg font-bold">N'Zassa Business</h1>
          <p class="text-xs text-white/60">Gérez. Vendez. Grandissez.</p>
        </div>
        <nav class="flex-1 p-2 space-y-1 text-sm">
          @if (!auth.isSuperadmin()) {
            @for (item of menu; track item.path) {
              <a
                [routerLink]="item.path"
                routerLinkActive="bg-white/15"
                class="flex items-center gap-2 rounded-lg px-3 py-2 hover:bg-white/10"
              >
                <i class="pi" [class]="item.icon"></i>
                {{ item.label }}
              </a>
            }
          } @else {
            @for (item of adminMenu; track item.path) {
              <a
                [routerLink]="item.path"
                routerLinkActive="bg-white/15"
                class="flex items-center gap-2 rounded-lg px-3 py-2 hover:bg-white/10"
              >
                <i class="pi" [class]="item.icon"></i>
                {{ item.label }}
              </a>
            }
          }
        </nav>
        <div class="p-3 border-t border-white/10 text-sm">
          <p class="truncate text-white/80">{{ auth.user()?.email }}</p>
          <button class="mt-2 text-white/60 hover:text-white" (click)="logout()">
            <i class="pi pi-sign-out mr-1"></i>Déconnexion
          </button>
        </div>
      </aside>
      <main class="flex-1 p-6 overflow-auto">
        <router-outlet />
      </main>
    </div>
  `
})
export class ShellComponent {
  readonly auth = inject(AuthService);

  readonly menu = [
    { path: '/app/dashboard', label: 'Tableau de bord', icon: 'pi-chart-line' },
    { path: '/app/sales', label: 'Ventes', icon: 'pi-shopping-cart' },
    { path: '/app/products', label: 'Produits', icon: 'pi-box' },
    { path: '/app/stock', label: 'Stock', icon: 'pi-database' },
    { path: '/app/customers', label: 'Clients', icon: 'pi-users' },
    { path: '/app/expenses', label: 'Dépenses', icon: 'pi-wallet' }
  ];

  readonly adminMenu = [
    { path: '/admin/dashboard', label: 'Vue globale', icon: 'pi-globe' },
    { path: '/admin/tenants', label: 'Entreprises', icon: 'pi-building' }
  ];

  logout(): void {
    void this.auth.logout();
  }
}
