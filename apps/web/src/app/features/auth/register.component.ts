import { Component, inject, signal } from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { Router, RouterLink } from '@angular/router';

import { AuthService } from '../../core/auth.service';

@Component({
  selector: 'nz-register',
  standalone: true,
  imports: [ReactiveFormsModule, RouterLink],
  template: `
    <div class="min-h-screen flex items-center justify-center bg-nzassa-50 py-8">
      <div class="nz-card w-full max-w-lg">
        <h1 class="text-2xl font-bold text-nzassa-900">Créer mon entreprise</h1>
        <p class="text-gray-500 mb-6">14 jours d'essai gratuit, sans carte bancaire.</p>

        @if (error()) {
          <p class="mb-4 rounded-lg bg-red-50 text-red-700 px-3 py-2 text-sm">{{ error() }}</p>
        }

        <form [formGroup]="form" (ngSubmit)="submit()" class="space-y-4">
          <div>
            <label class="nz-label" for="business_name">Nom de l'entreprise</label>
            <input id="business_name" class="nz-input" formControlName="business_name" />
          </div>
          <div class="grid grid-cols-2 gap-4">
            <div>
              <label class="nz-label" for="first_name">Prénom</label>
              <input id="first_name" class="nz-input" formControlName="first_name" />
            </div>
            <div>
              <label class="nz-label" for="last_name">Nom</label>
              <input id="last_name" class="nz-input" formControlName="last_name" />
            </div>
          </div>
          <div>
            <label class="nz-label" for="industry">Secteur d'activité</label>
            <select id="industry" class="nz-input" formControlName="industry">
              <option value="beauty">Institut de beauté</option>
              <option value="hair">Salon de coiffure</option>
              <option value="cosmetics">Boutique cosmétiques</option>
              <option value="retail">Commerce</option>
              <option value="services">Prestations de services</option>
              <option value="other">Autre</option>
            </select>
          </div>
          <div>
            <label class="nz-label" for="email">Email</label>
            <input id="email" type="email" class="nz-input" formControlName="email" />
          </div>
          <div>
            <label class="nz-label" for="phone">Téléphone</label>
            <input id="phone" class="nz-input" formControlName="phone" placeholder="+225…" />
          </div>
          <div>
            <label class="nz-label" for="password">Mot de passe</label>
            <input id="password" type="password" class="nz-input" formControlName="password" />
          </div>
          <button type="submit" class="nz-btn-primary w-full" [disabled]="form.invalid || loading()">
            {{ loading() ? 'Création…' : 'Créer mon compte' }}
          </button>
        </form>

        <p class="mt-4 text-sm text-gray-500">
          Déjà inscrit ?
          <a routerLink="/auth/login" class="text-nzassa-600 font-medium">Se connecter</a>
        </p>
      </div>
    </div>
  `
})
export class RegisterComponent {
  private readonly fb = inject(FormBuilder);
  private readonly auth = inject(AuthService);
  private readonly router = inject(Router);

  readonly loading = signal(false);
  readonly error = signal<string | null>(null);

  readonly form = this.fb.nonNullable.group({
    business_name: ['', [Validators.required, Validators.minLength(2)]],
    first_name: ['', Validators.required],
    last_name: ['', Validators.required],
    industry: ['beauty', Validators.required],
    email: ['', [Validators.required, Validators.email]],
    phone: [''],
    password: ['', [Validators.required, Validators.minLength(8)]]
  });

  async submit(): Promise<void> {
    if (this.form.invalid) return;
    this.loading.set(true);
    this.error.set(null);
    try {
      await this.auth.register(this.form.getRawValue());
      await this.router.navigate(['/app/dashboard']);
    } catch (err: unknown) {
      const message =
        (err as { error?: { message?: string } })?.error?.message ?? 'Inscription impossible';
      this.error.set(message);
    } finally {
      this.loading.set(false);
    }
  }
}
