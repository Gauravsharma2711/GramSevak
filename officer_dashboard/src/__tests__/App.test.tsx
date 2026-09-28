import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { App } from '../App';
import { ApiService } from '../services/api';

describe('App - Hierarchy & Forecast Integration', () => {
  const mockDistricts = {
    total: 2,
    page: 1,
    page_size: 20,
    total_pages: 1,
    items: [
      { id: 1, name: 'Nashik', code: 'NSK', state: 'Maharashtra' },
      { id: 4, name: 'Pune', code: 'PUN', state: 'Maharashtra' },
    ],
  };

  const mockBlocks = {
    total: 1,
    page: 1,
    page_size: 20,
    total_pages: 1,
    items: [{ id: 10, district_id: 1, name: 'Baglan', code: 'BGL' }],
  };

  const mockPanchayats = {
    total: 1,
    page: 1,
    page_size: 50,
    total_pages: 1,
    items: [
      {
        id: 101,
        panchayat_id: 101,
        lgd_code: 187123,
        name: 'Abhona',
        panchayat_name: 'Abhona',
        block_id: 10,
        block_name: 'Baglan',
        district_id: 1,
        district_name: 'Nashik',
        latitude: 20.6385,
        longitude: 74.1201,
        elevation_m: 550,
      },
    ],
  };

  const mockAdvisories = [
    {
      id: 1,
      panchayat_id: 101,
      forecast_id: 2001,
      forecast_date: '2026-09-09',
      rainfall_mm: 24.5,
      rainfall_category: 'MODERATE',
      severity: 'MEDIUM' as const,
      advisory_title: 'Spray Schedule Advisory',
      advisory_text: 'Postpone pesticide application due to downscaled rainfall.',
      status: 'DRAFT' as const,
      panchayat_name: 'Abhona',
      block_name: 'Baglan',
      district_name: 'Nashik',
    },
  ];

  beforeEach(() => {
    vi.restoreAllMocks();
    vi.spyOn(ApiService, 'getDistricts').mockResolvedValue(mockDistricts);
    vi.spyOn(ApiService, 'getDistrictBlocks').mockResolvedValue(mockBlocks);
    vi.spyOn(ApiService, 'getBlockPanchayats').mockResolvedValue(mockPanchayats as any);
    vi.spyOn(ApiService, 'getPanchayats').mockResolvedValue(mockPanchayats as any);
    vi.spyOn(ApiService, 'getOfficerAdvisories').mockResolvedValue(mockAdvisories);
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  it('initializes dashboard jurisdiction dynamically from backend districts API', async () => {
    render(<App />);

    await waitFor(() => {
      // Check MetricCard displays active district from API
      expect(screen.getByText('Active District')).toBeInTheDocument();
      expect(screen.getByText('Nashik')).toBeInTheDocument();
    });
  });

  it('updates dashboard context when a Panchayat is selected via hierarchy selector', async () => {
    render(<App />);

    await waitFor(() => {
      expect(screen.getByText('Active District')).toBeInTheDocument();
    });

    // Open hierarchy dropdown
    const triggerBtn = screen.getByRole('button', { name: /Administrative Scope/i });
    fireEvent.click(triggerBtn);

    // Click Baglan Block
    await waitFor(() => {
      expect(screen.getByText('Baglan')).toBeInTheDocument();
    });
    fireEvent.click(screen.getByText('Baglan'));

    // Click Abhona Panchayat
    await waitFor(() => {
      expect(screen.getByText('Abhona')).toBeInTheDocument();
    });
    fireEvent.click(screen.getByText('Abhona'));

    // Verify toast notification indicates live Panchayat loaded
    await waitFor(() => {
      expect(screen.getByText(/Loaded live Panchayat: Abhona/i)).toBeInTheDocument();
    });

    // Verify trigger reflects the newly selected Panchayat
    expect(triggerBtn).toHaveTextContent(/Abhona/i);
  });

  it('switching tabs to Directory and Audit maintains dashboard state', async () => {
    render(<App />);

    await waitFor(() => {
      expect(screen.getByText('Active District')).toBeInTheDocument();
    });

    // Switch to Panchayat Directory tab via sidebar
    const directoryNavBtn = screen.getByRole('button', { name: /Panchayat Directory/i });
    fireEvent.click(directoryNavBtn);

    await waitFor(() => {
      expect(screen.getByText(/Panchayat Geospatial Registry/i)).toBeInTheDocument();
    });

    // Switch to Audit Trail tab via sidebar
    const auditNavBtn = screen.getByRole('button', { name: /Approval Audit Log/i });
    fireEvent.click(auditNavBtn);

    await waitFor(() => {
      expect(screen.getByRole('heading', { name: /Historical Approval Audit Trail/i })).toBeInTheDocument();
    });
  });
});
