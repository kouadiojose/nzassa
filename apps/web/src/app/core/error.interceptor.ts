import { HttpErrorResponse, HttpInterceptorFn } from '@angular/common/http';
import { inject } from '@angular/core';
import { Router } from '@angular/router';
import { catchError, switchMap, throwError, from } from 'rxjs';

import { AuthService } from './auth.service';

/** Rafraîchit le token sur 401 (une tentative), sinon redirige vers la connexion. */
export const errorInterceptor: HttpInterceptorFn = (req, next) => {
  const auth = inject(AuthService);
  const router = inject(Router);

  return next(req).pipe(
    catchError((error: HttpErrorResponse) => {
      const isAuthCall = req.url.includes('/auth/login') || req.url.includes('/auth/refresh');
      if (error.status === 401 && !isAuthCall && !req.headers.has('X-Retried')) {
        return from(auth.refresh()).pipe(
          switchMap((refreshed) => {
            if (!refreshed) {
              void router.navigate(['/auth/login']);
              return throwError(() => error);
            }
            const retried = req.clone({
              setHeaders: {
                Authorization: `Bearer ${auth.accessToken}`,
                'X-Retried': '1'
              }
            });
            return next(retried);
          })
        );
      }
      return throwError(() => error);
    })
  );
};
