import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { ApiService } from '../api';

describe('ApiService - Scalable Hierarchy Endpoints', () => {
  const originalFetch = global.fetch;

  beforeEach(() => {
    vi.restoreAllMocks();
  });

  afterEach(() => {
    global.fetch = originalFetch;
  });

  it('getDistricts sends correct parameters and handles paginated response', async () => {
    const mockResponse = {
      total: 2,
      page: 1,
      page_size: 20,
      total_pages: 1,
      items: [
        { id: 1, name: 'Nashik', code: 'NSK', state: 'Maharashtra' },
        { id: 4, name: 'Pune', code: 'PUN', state: 'Maharashtra' },
      ],
    };

    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => mockResponse,
    });

    const res = await ApiService.getDistricts('Nash', 1, 10);

    expect(global.fetch).toHaveBeenCalledWith(
      expect.stringContaining('/districts?search=Nash&page=1&page_size=10'),
      expect.objectContaining({ method: 'GET' })
    );
    expect(res.total).toBe(2);
    expect(res.items.length).toBe(2);
    expect(res.items[0].name).toBe('Nashik');
    expect(res.items[1].name).toBe('Pune');
  });

  it('getDistrictBlocks sends district_id, search and pagination', async () => {
    const mockResponse = {
      total: 1,
      page: 1,
      page_size: 20,
      total_pages: 1,
      items: [{ id: 1, district_id: 1, name: 'Baglan', code: 'BGL' }],
    };

    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => mockResponse,
    });

    const res = await ApiService.getDistrictBlocks(1, 'Bag', 1, 20);

    expect(global.fetch).toHaveBeenCalledWith(
      expect.stringContaining('/districts/1/blocks?search=Bag&page=1&page_size=20'),
      expect.objectContaining({ method: 'GET' })
    );
    expect(res.items[0].name).toBe('Baglan');
  });

  it('getBlockPanchayats sends block_id, search and pagination', async () => {
    const mockResponse = {
      total: 50,
      page: 1,
      page_size: 50,
      total_pages: 1,
      items: [
        {
          id: 101,
          lgd_code: 187123,
          name: 'Abhona',
          block_id: 1,
          district_id: 1,
          latitude: 20.63,
          longitude: 74.12,
          elevation_m: 550,
        },
      ],
    };

    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => mockResponse,
    });

    const res = await ApiService.getBlockPanchayats(1, 'Abh', 1, 50);

    expect(global.fetch).toHaveBeenCalledWith(
      expect.stringContaining('/blocks/1/panchayats?search=Abh&page=1&page_size=50'),
      expect.objectContaining({ method: 'GET' })
    );
    expect(res.items[0].name).toBe('Abhona');
    expect(res.items[0].lgd_code).toBe(187123);
  });

  it('getPanchayatById returns single panchayat detail', async () => {
    const mockPanchayat = {
      id: 101,
      panchayat_id: 101,
      lgd_code: 187123,
      name: 'Abhona',
      panchayat_name: 'Abhona',
      block_name: 'Baglan',
      district_name: 'Nashik',
      latitude: 20.63,
      longitude: 74.12,
      elevation_m: 550,
    };

    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => mockPanchayat,
    });

    const res = await ApiService.getPanchayatById(101);

    expect(global.fetch).toHaveBeenCalledWith(
      expect.stringContaining('/panchayats/101'),
      expect.objectContaining({ method: 'GET' })
    );
    expect(res.panchayat_name).toBe('Abhona');
  });

  it('propagates HTTP error when backend fails', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 404,
      statusText: 'Not Found',
      json: async () => ({ detail: 'District not found' }),
    });

    await expect(ApiService.getDistrictBlocks(999)).rejects.toThrow('District not found');
  });
});
