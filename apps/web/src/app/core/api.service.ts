import { HttpClient, HttpParams } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable, map } from 'rxjs';

import { ApiResponse } from './api.types';

/** Client API minimal : déballe l'enveloppe standard {success, data, meta}. */
@Injectable({ providedIn: 'root' })
export class ApiService {
  private readonly http = inject(HttpClient);

  get<T>(path: string, params?: Record<string, string | number | boolean>): Observable<T> {
    return this.http
      .get<ApiResponse<T>>(`/api/v1${path}`, { params: this.toParams(params) })
      .pipe(map((r) => r.data));
  }

  getWithMeta<T>(
    path: string,
    params?: Record<string, string | number | boolean>
  ): Observable<ApiResponse<T>> {
    return this.http.get<ApiResponse<T>>(`/api/v1${path}`, { params: this.toParams(params) });
  }

  post<T>(path: string, body: unknown): Observable<T> {
    return this.http.post<ApiResponse<T>>(`/api/v1${path}`, body).pipe(map((r) => r.data));
  }

  patch<T>(path: string, body: unknown): Observable<T> {
    return this.http.patch<ApiResponse<T>>(`/api/v1${path}`, body).pipe(map((r) => r.data));
  }

  put<T>(path: string, body: unknown): Observable<T> {
    return this.http.put<ApiResponse<T>>(`/api/v1${path}`, body).pipe(map((r) => r.data));
  }

  private toParams(params?: Record<string, string | number | boolean>): HttpParams | undefined {
    if (!params) return undefined;
    let httpParams = new HttpParams();
    for (const [key, value] of Object.entries(params)) {
      httpParams = httpParams.set(key, String(value));
    }
    return httpParams;
  }
}
