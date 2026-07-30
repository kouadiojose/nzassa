import { Component, inject, signal } from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { Router, RouterLink } from '@angular/router';

import { AuthService } from '../../core/auth.service';

@Component({
  selector: 'nz-login',
  standalone: true,
  imports: [ReactiveFormsModule, RouterLink],
  template: `
    <div class="min-h-screen flex items-center justify-center bg-nzassa-50">
      <div class="nz-card w-full max-w-md">
        <h1 class="text-2xl font-bold text-nzassa-900">N'Zassa Business</h1>
        <p class="text-gray-500 mb-6">Connectez-vous à votre espace</p>

        @if (error()) {
          <p class="mb-4 rounded-lg bg-red-50 text-red-700 px-3 py-2 text-sm">{{ error() }}</p>
        }

        <form [formGroup]="form" (ngSubmit)="submit()" class="space-y-4">
          <div>
            <label class="nz-label" for="email">Email</label>
            <input id="email" type="email" class="nz-input" formControlName="email" />
          </div>
          <div>
            <label class="nz-label" for="password">Mot de passe</label>
            <input id="password" type="password" class="nz-input" formControlName="password" />
          </div>
          <button type="submit" class="nz-btn-primary w-full" [disabled]="form.invalid || loading()">
            {{ loading() ? 'Connexion…' : 'Se connecter' }}
          </button>
        </form>

        <p class="mt-4 text-sm text-gray-500">
          Pas encore de compte ?
          <a routerLink="/auth/register" class="text-nzassa-600 font-medium">Créer mon entreprise</a>
        </p>
      </div>
    </div>
  `
})
export class LoginComponent {
  private readonly fb = inject(FormBuilder);
  private readonly auth = inject(AuthService);
  private readonly router = inject(Router);

  readonly loading = signal(false);
  readonly error = signal<string | null>(null);

  readonly form = this.fb.nonNullable.group({
    email: ['', [Validators.required, Validators.email]],
    password: ['', [Validators.required, Validators.minLength(8)]]
  });

  async submit(): Promise<void> {
    if (this.form.invalid) return;
    this.loading.set(true);
    this.error.set(null);
    try {
      const { email, password } = this.form.getRawValue();
      await this.auth.login(email, password);
      await this.router.navigate([this.auth.isSuperadmin() ? '/admin' : '/app/dashboard']);
    } catch (err: unknown) {
      const message =
        (err as { error?: { message?: string } })?.error?.message ?? 'Connexion impossible';
      this.error.set(message);
    } finally {
      this.loading.set(false);
    }
  }
}
