/**
 * GramSevak Officer Dashboard - Centralized API Service Client
 * 
 * Provides typed, resilient communication with the FastAPI backend.
 * Features:
 * - Configurable base URL via Vite environment (VITE_API_BASE_URL)
 * - Centralized timeout (AbortController) and error handling
 * - Clean response typing and graceful missing-field mitigation
 * - Zero secrets or direct database service-role keys in frontend
 */

import {
  PanchayatItem,
  PanchayatPagination,
  DistrictItem,
  BlockItem,
  BlockPanchayatItem,
  BlockPanchayatPagination,
  AdvisoryItem,
  OfficerApprovePayload,
  OfficerRejectPayload,
  GenerateForecastPayload,
  DownscaledForecastDetail,
} from '../types';
import { MOCK_PANCHAYATS, INITIAL_MOCK_ADVISORIES } from './mockData';

// Base API URL from Vite environment or fallback default
const RAW_API_BASE_URL =
  (import.meta as any).env?.VITE_API_BASE_URL || 'https://gramseva-0etv.onrender.com/api/v1';
const API_BASE_URL = RAW_API_BASE_URL.replace(/\/+$/, '');

// Default timeout in milliseconds for API operations (accommodates cloud cold-start latency)
const DEFAULT_TIMEOUT_MS = 15000;

// In-memory fallback state for resilience during network glitches
let localAdvisories: AdvisoryItem[] = [...INITIAL_MOCK_ADVISORIES];

export class ApiService {
  public static readonly baseUrl = API_BASE_URL;

  /**
   * Helper method for performing fetch with timeout, error extraction, and fallback
   */
  private static async request<T>(
    endpoint: string,
    options: RequestInit = {},
    fallbackFn?: () => T | Promise<T>,
    timeoutMs: number = DEFAULT_TIMEOUT_MS
  ): Promise<T> {
    const url = `${this.baseUrl}${endpoint}`;
    let isNetworkError = false;

    try {
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), timeoutMs);

      const response = await fetch(url, {
        ...options,
        signal: controller.signal,
        headers: {
          'Content-Type': 'application/json',
          Accept: 'application/json',
          ...(options.headers || {}),
        },
      });

      clearTimeout(timeoutId);

      if (!response.ok) {
        let errorDetail = `HTTP ${response.status}: ${response.statusText}`;
        try {
          const errData = await response.json();
          if (errData?.detail) {
            if (typeof errData.detail === 'string') {
              errorDetail = errData.detail;
            } else if (Array.isArray(errData.detail)) {
              errorDetail = errData.detail.map((d: any) => d.msg || JSON.stringify(d)).join('; ');
            } else {
              errorDetail = JSON.stringify(errData.detail);
            }
          }
        } catch {
          // Ignore JSON parse error on non-JSON error response
        }
        throw new Error(errorDetail);
      }

      return (await response.json()) as T;
    } catch (err: any) {
      if (
        err?.name === 'AbortError' ||
        err?.message?.includes('Failed to fetch') ||
        err?.message?.includes('NetworkError') ||
        err?.message?.includes('network')
      ) {
        isNetworkError = true;
      }

      if (isNetworkError && fallbackFn) {
        console.warn(
          `[API Client] Endpoint ${endpoint} offline or timed out (${err.message}). Using local fallback store.`
        );
        return fallbackFn();
      }

      // If backend was reached and returned HTTP error, propagate real error
      throw err;
    }
  }

  // ==========================================
  // 1. PANCHAYAT ENDPOINTS
  // ==========================================

  /**
   * List Panchayats with optional block filter and search query (GET /api/v1/panchayats)
   */
  static async getPanchayats(
    blockName?: string,
    search?: string,
    page: number = 1,
    pageSize: number = 50
  ): Promise<PanchayatPagination> {
    const params = new URLSearchParams();
    if (blockName) params.append('block_name', blockName);
    if (search) params.append('search', search);
    params.append('page', String(page));
    params.append('page_size', String(pageSize));

    return this.request<PanchayatPagination>(
      `/panchayats?${params.toString()}`,
      { method: 'GET' },
      () => {
        let filtered = [...MOCK_PANCHAYATS];
        if (blockName) {
          filtered = filtered.filter(
            (p) => p.block_name.toLowerCase() === blockName.toLowerCase()
          );
        }
        if (search) {
          const s = search.toLowerCase();
          filtered = filtered.filter(
            (p) =>
              p.panchayat_name.toLowerCase().includes(s) ||
              p.block_name.toLowerCase().includes(s) ||
              String(p.panchayat_id).includes(s) ||
              String(p.lgd_code).includes(s)
          );
        }
        const total = filtered.length;
        const total_pages = Math.ceil(total / pageSize);
        const offset = (page - 1) * pageSize;
        const items = filtered.slice(offset, offset + pageSize);
        return { total, page, page_size: pageSize, total_pages, items };
      }
    );
  }

  /**
   * Retrieve single Panchayat details by ID (GET /api/v1/panchayats/{panchayat_id})
   */
  static async getPanchayatById(panchayatId: number): Promise<PanchayatItem> {
    return this.request<PanchayatItem>(
      `/panchayats/${panchayatId}`,
      { method: 'GET' },
      () => {
        const found = MOCK_PANCHAYATS.find((p) => p.panchayat_id === panchayatId);
        if (!found) {
          throw new Error(`Panchayat with ID ${panchayatId} not found.`);
        }
        return found;
      }
    );
  }

  /**
   * List all administrative Districts (GET /api/v1/districts)
   */
  static async getDistricts(): Promise<DistrictItem[]> {
    return this.request<DistrictItem[]>(
      '/districts',
      { method: 'GET' },
      () => [
        { id: 1, name: 'Nashik', state: 'Maharashtra' },
        { id: 4, name: 'Pune', state: 'Maharashtra' },
      ]
    );
  }

  /**
   * List blocks for a specific District (GET /api/v1/districts/{district_id}/blocks)
   */
  static async getDistrictBlocks(districtId: number): Promise<BlockItem[]> {
    return this.request<BlockItem[]>(
      `/districts/${districtId}/blocks`,
      { method: 'GET' },
      () => [
        { id: 1, district_id: districtId, name: 'Baglan' },
        { id: 2, district_id: districtId, name: 'Dindori' },
        { id: 3, district_id: districtId, name: 'Surgana' },
        { id: 4, district_id: districtId, name: 'Igatpuri' },
        { id: 5, district_id: districtId, name: 'Kalwan' },
        { id: 6, district_id: districtId, name: 'Niphad' },
        { id: 7, district_id: districtId, name: 'Sinnar' },
      ]
    );
  }

  /**
   * List Panchayats for a specific block with pagination & search (GET /api/v1/blocks/{block_id}/panchayats)
   */
  static async getBlockPanchayats(
    blockId: number,
    search?: string,
    page: number = 1,
    pageSize: number = 50
  ): Promise<BlockPanchayatPagination> {
    const params = new URLSearchParams();
    if (search) params.append('search', search);
    params.append('page', String(page));
    params.append('page_size', String(pageSize));

    return this.request<BlockPanchayatPagination>(
      `/blocks/${blockId}/panchayats?${params.toString()}`,
      { method: 'GET' },
      () => {
        const filtered = MOCK_PANCHAYATS.map((p) => ({
          id: p.panchayat_id,
          lgd_code: p.lgd_code,
          name: p.panchayat_name,
          block_id: blockId,
          district_id: 1,
          latitude: p.latitude,
          longitude: p.longitude,
          elevation_m: p.elevation_m,
          panchayat_id: p.panchayat_id,
          panchayat_name: p.panchayat_name,
        }));
        return {
          total: filtered.length,
          page,
          page_size: pageSize,
          total_pages: 1,
          items: filtered,
        };
      }
    );
  }

  // ==========================================
  // 2. FORECAST ENDPOINTS
  // ==========================================

  /**
   * Retrieve stored downscaled forecast for a Panchayat (GET /api/v1/forecast/panchayat/{panchayat_id})
   */
  static async getPanchayatForecast(
    panchayatId: number,
    forecastDate?: string
  ): Promise<DownscaledForecastDetail> {
    const params = new URLSearchParams();
    if (forecastDate) params.append('forecast_date', forecastDate);
    const queryStr = params.toString() ? `?${params.toString()}` : '';

    return this.request<DownscaledForecastDetail>(
      `/forecast/panchayat/${panchayatId}${queryStr}`,
      { method: 'GET' },
      () => {
        const p = MOCK_PANCHAYATS.find((x) => x.panchayat_id === panchayatId) || MOCK_PANCHAYATS[0];
        return {
          id: panchayatId,
          panchayat_id: p.panchayat_id,
          panchayat_name: p.panchayat_name,
          block_name: p.block_name,
          district_name: p.district_name,
          forecast_date: forecastDate || '2026-09-09',
          forecast_issue_date: '2026-09-08',
          lead_days: 1,
          block_forecast_rainfall_mm: 18.5,
          downscaled_rainfall_mm: 26.4,
          model_name: 'XGBoost Regressor',
          model_version: 'v1.0.0',
          confidence: null,
        };
      }
    );
  }

  /**
   * Trigger on-demand ML Downscaling inference for a Panchayat (POST /api/v1/forecast/generate)
   */
  static async generateForecast(
    payload: GenerateForecastPayload
  ): Promise<DownscaledForecastDetail> {
    return this.request<DownscaledForecastDetail>(
      `/forecast/generate`,
      {
        method: 'POST',
        body: JSON.stringify(payload),
      },
      () => {
        const p =
          MOCK_PANCHAYATS.find((x) => x.panchayat_id === payload.panchayat_id) ||
          MOCK_PANCHAYATS[0];
        return {
          id: Math.floor(Math.random() * 9000) + 1000,
          panchayat_id: p.panchayat_id,
          panchayat_name: p.panchayat_name,
          block_name: p.block_name,
          district_name: p.district_name,
          forecast_date: payload.forecast_date,
          forecast_issue_date: payload.forecast_issue_date,
          lead_days: 1,
          block_forecast_rainfall_mm: 18.5,
          downscaled_rainfall_mm: 26.4,
          model_name: 'XGBoost Regressor',
          model_version: 'v1.0.0',
          confidence: null,
        };
      }
    );
  }

  // ==========================================
  // 3. ADVISORY & OFFICER REVIEW ENDPOINTS
  // ==========================================

  /**
   * List advisories for extension officer review (GET /api/v1/officer/advisories)
   */
  static async getOfficerAdvisories(
    status?: 'DRAFT' | 'APPROVED' | 'REJECTED',
    panchayatId?: number,
    forecastDate?: string,
    limit: number = 100,
    offset: number = 0
  ): Promise<AdvisoryItem[]> {
    const params = new URLSearchParams();
    if (status) params.append('status', status);
    if (panchayatId) params.append('panchayat_id', String(panchayatId));
    if (forecastDate) params.append('forecast_date', forecastDate);
    params.append('limit', String(limit));
    params.append('offset', String(offset));

    const advisories = await this.request<AdvisoryItem[]>(
      `/officer/advisories?${params.toString()}`,
      { method: 'GET' },
      () => {
        let results = [...localAdvisories];
        if (status) {
          results = results.filter((a) => a.status === status);
        }
        if (panchayatId) {
          results = results.filter((a) => a.panchayat_id === panchayatId);
        }
        if (forecastDate) {
          results = results.filter((a) => a.forecast_date === forecastDate);
        }
        return results;
      }
    );

    // Sanitize and ensure spatial metadata presence
    return advisories.map((item) => {
      const p = MOCK_PANCHAYATS.find((x) => x.panchayat_id === item.panchayat_id);
      return {
        ...item,
        panchayat_name: item.panchayat_name || p?.panchayat_name || `Panchayat ${item.panchayat_id}`,
        block_name: item.block_name || p?.block_name || 'Baglan',
        district_name: item.district_name || p?.district_name || 'Nashik',
        elevation_m: item.elevation_m ?? p?.elevation_m ?? 550,
        latitude: item.latitude ?? p?.latitude ?? 20.6385,
        longitude: item.longitude ?? p?.longitude ?? 74.1201,
        block_forecast_mm: item.block_forecast_mm ?? 18.5,
      };
    });
  }

  /**
   * Retrieve single advisory detail (GET /api/v1/officer/advisories/{advisory_id})
   */
  static async getOfficerAdvisoryDetail(advisoryId: number): Promise<AdvisoryItem> {
    const item = await this.request<AdvisoryItem>(
      `/officer/advisories/${advisoryId}`,
      { method: 'GET' },
      () => {
        const found = localAdvisories.find((a) => a.id === advisoryId);
        if (!found) {
          throw new Error(`Advisory with ID ${advisoryId} not found.`);
        }
        return found;
      }
    );

    // Ensure spatial metadata
    const p = MOCK_PANCHAYATS.find((x) => x.panchayat_id === item.panchayat_id);
    return {
      ...item,
      panchayat_name: item.panchayat_name || p?.panchayat_name || `Panchayat ${item.panchayat_id}`,
      block_name: item.block_name || p?.block_name || 'Baglan',
      district_name: item.district_name || p?.district_name || 'Nashik',
      elevation_m: item.elevation_m ?? p?.elevation_m ?? 550,
      latitude: item.latitude ?? p?.latitude ?? 20.6385,
      longitude: item.longitude ?? p?.longitude ?? 74.1201,
      block_forecast_mm: item.block_forecast_mm ?? 18.5,
    };
  }

  /**
   * Approve a DRAFT advisory (POST /api/v1/officer/advisories/{advisory_id}/approve)
   */
  static async approveAdvisory(
    advisoryId: number,
    payload: OfficerApprovePayload
  ): Promise<AdvisoryItem> {
    const updated = await this.request<AdvisoryItem>(
      `/officer/advisories/${advisoryId}/approve`,
      {
        method: 'POST',
        body: JSON.stringify(payload),
      },
      () => {
        const index = localAdvisories.findIndex((a) => a.id === advisoryId);
        if (index === -1) throw new Error(`Advisory ${advisoryId} not found.`);
        localAdvisories[index] = {
          ...localAdvisories[index],
          status: 'APPROVED',
          officer_id: payload.officer_id,
          officer_comment: payload.officer_comment || null,
          approved_at: new Date().toISOString(),
        };
        return localAdvisories[index];
      }
    );

    return updated;
  }

  /**
   * Reject a DRAFT advisory (POST /api/v1/officer/advisories/{advisory_id}/reject)
   */
  static async rejectAdvisory(
    advisoryId: number,
    payload: OfficerRejectPayload
  ): Promise<AdvisoryItem> {
    const updated = await this.request<AdvisoryItem>(
      `/officer/advisories/${advisoryId}/reject`,
      {
        method: 'POST',
        body: JSON.stringify(payload),
      },
      () => {
        const index = localAdvisories.findIndex((a) => a.id === advisoryId);
        if (index === -1) throw new Error(`Advisory ${advisoryId} not found.`);
        localAdvisories[index] = {
          ...localAdvisories[index],
          status: 'REJECTED',
          officer_id: payload.officer_id,
          officer_comment: payload.officer_comment || null,
        };
        return localAdvisories[index];
      }
    );

    return updated;
  }
}
