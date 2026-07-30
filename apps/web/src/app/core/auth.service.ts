import { HttpClient } from '@angular/common/http';
import { Injectable, computed, inject, signal } from '@angular/core';
import { Router } from '@angular/router';
import { firstValueFrom } from 'rxjs';

import { ApiResponse, AuthResult, TokenPair, User } from './api.types';

const ACCESS_KEY = 'nz_access';
const REFRESH_KEY = 'nz_refresh';
const USER_KEY = 'nz_user';
const PERMS_KEY = 'nz_perms';

@Injectable({ providedIn: 'root' })
export class AuthService {
  private readonly http = inject(HttpClient);
  private readonly router = inject(Router);

  readonly user = signal<User | null>(this.restore<User>(USER_KEY));
  readonly permissions = signal<string[]>(this.restore<string[]>(PERMS_KEY) ?? []);
  readonly isAuthenticated = computed(() => this.user() !== null);
  readonly isSuperadmin = computed(() => this.user()?.is_superadmin ?? false);

  get accessToken(): string | null {
    return localStorage.getItem(ACCESS_KEY);
  }

  hasPermission(permission: string): boolean {
    const perms = this.permissions();
    return this.isSuperadmin() || perms.includes('*') || perms.includes(permission);
  }

  async login(email: string, password: string): Promise<void> {
    const resp = await firstValueFrom(
      this.http.post<ApiResponse<AuthResult>>('/api/v1/auth/login', { email, password })
    );
    this.storeSession(resp.data.user, resp.data.tokens, resp.data.permissions);
  }

  async register(payload: Record<string, unknown>): Promise<void> {
    const resp = await firstValueFrom(
      this.http.post<ApiResponse<{ user: User; tokens: TokenPair }>>(
        '/api/v1/auth/register',
        payload
      )
    );
    this.storeSession(resp.data.user, resp.data.tokens, ['*']);
  }

  async refresh(): Promise<boolean> {
    const refreshToken = localStorage.getItem(REFRESH_KEY);
    if (!refreshToken) return false;
    try {
      const resp = await firstValueFrom(
        this.http.post<ApiResponse<TokenPair>>('/api/v1/auth/refresh', {
          refresh_token: refreshToken
        })
      );
      localStorage.setItem(ACCESS_KEY, resp.data.access_token);
      localStorage.setItem(REFRESH_KEY, resp.data.refresh_token);
      return true;
    } catch {
      this.clearSession();
      return false;
    }
  }

  async logout(): Promise<void> {
    const refreshToken = localStorage.getItem(REFRESH_KEY);
    try {
      await firstValueFrom(
        this.http.post('/api/v1/auth/logout', { refresh_token: refreshToken })
      );
    } catch {
      // La session locale est purgée quoi qu'il arrive.
    }
    this.clearSession();
    await this.router.navigate(['/auth/login']);
  }

  private storeSession(user: User, tokens: TokenPair, permissions: string[]): void {
    localStorage.setItem(ACCESS_KEY, tokens.access_token);
    localStorage.setItem(REFRESH_KEY, tokens.refresh_token);
    localStorage.setItem(USER_KEY, JSON.stringify(user));
    localStorage.setItem(PERMS_KEY, JSON.stringify(permissions));
    this.user.set(user);
    this.permissions.set(permissions);
  }

  clearSession(): void {
    localStorage.removeItem(ACCESS_KEY);
    localStorage.removeItem(REFRESH_KEY);
    localStorage.removeItem(USER_KEY);
    localStorage.removeItem(PERMS_KEY);
    this.user.set(null);
    this.permissions.set([]);
  }

  private restore<T>(key: string): T | null {
    try {
      const raw = localStorage.getItem(key);
      return raw ? (JSON.parse(raw) as T) : null;
    } catch {
      return null;
    }
  }
}
