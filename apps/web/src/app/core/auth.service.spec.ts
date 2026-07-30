import { TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { provideRouter } from '@angular/router';

import { AuthService } from './auth.service';

describe('AuthService', () => {
  let service: AuthService;
  let http: HttpTestingController;

  beforeEach(() => {
    localStorage.clear();
    TestBed.configureTestingModule({
      providers: [provideHttpClient(), provideHttpClientTesting(), provideRouter([])]
    });
    service = TestBed.inject(AuthService);
    http = TestBed.inject(HttpTestingController);
  });

  afterEach(() => {
    http.verify();
    localStorage.clear();
  });

  it('démarre non authentifié', () => {
    expect(service.isAuthenticated()).toBeFalse();
  });

  it('stocke la session après connexion', async () => {
    const promise = service.login('awa@test.ci', 'MotDePasse#2026');
    const req = http.expectOne('/api/v1/auth/login');
    expect(req.request.method).toBe('POST');
    req.flush({
      success: true,
      message: 'ok',
      data: {
        user: {
          id: 'u1',
          tenant_id: 't1',
          email: 'awa@test.ci',
          phone: null,
          first_name: 'Awa',
          last_name: 'Koné',
          is_active: true,
          is_superadmin: false
        },
        tokens: {
          access_token: 'access',
          refresh_token: 'refresh',
          token_type: 'bearer',
          expires_in: 900
        },
        permissions: ['*']
      },
      meta: {}
    });
    await promise;
    expect(service.isAuthenticated()).toBeTrue();
    expect(service.hasPermission('sales.create')).toBeTrue();
    expect(service.accessToken).toBe('access');
  });

  it('hasPermission respecte les permissions précises', async () => {
    const promise = service.login('vendeur@test.ci', 'MotDePasse#2026');
    const req = http.expectOne('/api/v1/auth/login');
    req.flush({
      success: true,
      message: 'ok',
      data: {
        user: {
          id: 'u2',
          tenant_id: 't1',
          email: 'vendeur@test.ci',
          phone: null,
          first_name: 'Moussa',
          last_name: 'Koffi',
          is_active: true,
          is_superadmin: false
        },
        tokens: {
          access_token: 'a',
          refresh_token: 'r',
          token_type: 'bearer',
          expires_in: 900
        },
        permissions: ['sales.create', 'products.read']
      },
      meta: {}
    });
    await promise;
    expect(service.hasPermission('sales.create')).toBeTrue();
    expect(service.hasPermission('products.create')).toBeFalse();
  });
});
