import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent, waitFor, act } from '@testing-library/react';
import { HierarchicalPanchayatSelector } from '../HierarchicalPanchayatSelector';
import { ApiService } from '../../services/api';

describe('HierarchicalPanchayatSelector Component', () => {
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

  const mockBlocksNashik = {
    total: 2,
    page: 1,
    page_size: 20,
    total_pages: 1,
    items: [
      { id: 10, district_id: 1, name: 'Baglan', code: 'BGL' },
      { id: 11, district_id: 1, name: 'Dindori', code: 'DIN' },
    ],
  };

  const mockBlocksPune = {
    total: 1,
    page: 1,
    page_size: 20,
    total_pages: 1,
    items: [
      { id: 20, district_id: 4, name: 'Haveli', code: 'HAV' },
    ],
  };

  const mockPanchayatsBaglan = {
    total: 2,
    page: 1,
    page_size: 50,
    total_pages: 1,
    items: [
      {
        id: 101,
        lgd_code: 187123,
        name: 'Abhona',
        block_id: 10,
        district_id: 1,
        latitude: 20.63,
        longitude: 74.12,
        elevation_m: 550,
      },
      {
        id: 102,
        lgd_code: 187124,
        name: 'Ajmer Saundane',
        block_id: 10,
        district_id: 1,
        latitude: 20.65,
        longitude: 74.15,
        elevation_m: 560,
      },
    ],
  };

  beforeEach(() => {
    vi.restoreAllMocks();
    vi.spyOn(ApiService, 'getDistricts').mockResolvedValue(mockDistricts);
    vi.spyOn(ApiService, 'getDistrictBlocks').mockImplementation(async (distId) => {
      if (distId === 1) return mockBlocksNashik;
      if (distId === 4) return mockBlocksPune;
      return { total: 0, page: 1, page_size: 20, total_pages: 0, items: [] };
    });
    vi.spyOn(ApiService, 'getBlockPanchayats').mockResolvedValue(mockPanchayatsBaglan);
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  // =========================================================================
  // 1. DISTRICT SUITE
  // =========================================================================
  describe('District Selection', () => {
    it('loads and displays districts from backend API', async () => {
      render(<HierarchicalPanchayatSelector onSelectPanchayat={vi.fn()} />);

      // Open selector dropdown
      const triggerBtn = screen.getByRole('button', { name: /Administrative Scope/i });
      fireEvent.click(triggerBtn);

      // Verify district options appear
      await waitFor(() => {
        expect(screen.getByText('Nashik District')).toBeInTheDocument();
        expect(screen.getByText('Pune District')).toBeInTheDocument();
      });
      expect(ApiService.getDistricts).toHaveBeenCalled();
    });

    it('displays district error state with retry button on failure', async () => {
      vi.spyOn(ApiService, 'getDistricts').mockRejectedValueOnce(new Error('Network failure'));

      render(<HierarchicalPanchayatSelector onSelectPanchayat={vi.fn()} />);

      const triggerBtn = screen.getByRole('button', { name: /Administrative Scope/i });
      fireEvent.click(triggerBtn);

      await waitFor(() => {
        expect(screen.getByText(/Network failure/i)).toBeInTheDocument();
        expect(screen.getByRole('button', { name: /Retry/i })).toBeInTheDocument();
      });
    });

    it('displays empty district state when query returns zero records', async () => {
      vi.spyOn(ApiService, 'getDistricts').mockResolvedValueOnce({
        total: 0,
        page: 1,
        page_size: 20,
        total_pages: 0,
        items: [],
      });

      render(<HierarchicalPanchayatSelector onSelectPanchayat={vi.fn()} />);

      const triggerBtn = screen.getByRole('button', { name: /Administrative Scope/i });
      fireEvent.click(triggerBtn);

      await waitFor(() => {
        expect(screen.getByText(/No administrative districts found/i)).toBeInTheDocument();
      });
    });

    it('supports server-side district search input', async () => {
      render(<HierarchicalPanchayatSelector onSelectPanchayat={vi.fn()} />);

      const triggerBtn = screen.getByRole('button', { name: /Administrative Scope/i });
      fireEvent.click(triggerBtn);

      await waitFor(() => {
        expect(screen.getByPlaceholderText(/Search districts by name/i)).toBeInTheDocument();
      });

      const searchInput = screen.getByPlaceholderText(/Search districts by name/i);
      fireEvent.change(searchInput, { target: { value: 'Pun' } });

      await waitFor(() => {
        expect(ApiService.getDistricts).toHaveBeenCalledWith('Pun', 1, 20);
      });
    });

    it('renders district pagination controls when total_pages > 1', async () => {
      vi.spyOn(ApiService, 'getDistricts').mockResolvedValue({
        total: 40,
        page: 1,
        page_size: 20,
        total_pages: 2,
        items: mockDistricts.items,
      });

      render(<HierarchicalPanchayatSelector onSelectPanchayat={vi.fn()} />);

      const triggerBtn = screen.getByRole('button', { name: /Administrative Scope/i });
      fireEvent.click(triggerBtn);

      await waitFor(() => {
        expect(screen.getByText(/Page 1 of 2/i)).toBeInTheDocument();
        expect(screen.getByRole('button', { name: /Next district page/i })).toBeInTheDocument();
      });

      fireEvent.click(screen.getByRole('button', { name: /Next district page/i }));

      await waitFor(() => {
        expect(ApiService.getDistricts).toHaveBeenCalledWith(undefined, 2, 20);
      });
    });
  });

  // =========================================================================
  // 2. BLOCK SUITE
  // =========================================================================
  describe('Block Selection', () => {
    it('loads blocks after selecting a district and transitions to block step', async () => {
      const onDistrictChange = vi.fn();
      render(
        <HierarchicalPanchayatSelector
          onSelectPanchayat={vi.fn()}
          onDistrictChange={onDistrictChange}
        />
      );

      const triggerBtn = screen.getByRole('button', { name: /Administrative Scope/i });
      fireEvent.click(triggerBtn);

      await waitFor(() => {
        expect(screen.getByText('Nashik District')).toBeInTheDocument();
      });

      // Select Nashik
      fireEvent.click(screen.getByText('Nashik District'));

      expect(onDistrictChange).toHaveBeenCalledWith(1, 'Nashik');

      // Verify transitioned to block step and blocks are displayed
      await waitFor(() => {
        expect(screen.getByText('Baglan')).toBeInTheDocument();
        expect(screen.getByText('Dindori')).toBeInTheDocument();
      });
      expect(ApiService.getDistrictBlocks).toHaveBeenCalledWith(1, undefined, 1, 20);
    });

    it('resets block and panchayat state when district changes', async () => {
      const onBlockChange = vi.fn();
      render(
        <HierarchicalPanchayatSelector
          onSelectPanchayat={vi.fn()}
          selectedDistrictId={1}
          selectedBlockId={10}
          onBlockChange={onBlockChange}
        />
      );

      const triggerBtn = screen.getByRole('button', { name: /Administrative Scope/i });
      fireEvent.click(triggerBtn);

      // Navigate back to district step
      await waitFor(() => {
        expect(screen.getByRole('button', { name: /Step 1: Select District/i })).toBeInTheDocument();
      });
      fireEvent.click(screen.getByRole('button', { name: /Step 1: Select District/i }));

      // Select Pune District
      await waitFor(() => {
        expect(screen.getByText('Pune District')).toBeInTheDocument();
      });
      fireEvent.click(screen.getByText('Pune District'));

      // Check onBlockChange was reset to null
      expect(onBlockChange).toHaveBeenCalledWith(null, null);

      // Verify Haveli block loads from Pune
      await waitFor(() => {
        expect(screen.getByText('Haveli')).toBeInTheDocument();
      });
      expect(screen.queryByText('Baglan')).not.toBeInTheDocument();
    });

    it('stale block request cannot overwrite current district data (race condition safety)', async () => {
      let resolveFirstDistrict: (val: any) => void;
      const delayedFirstDistrictPromise = new Promise((resolve) => {
        resolveFirstDistrict = resolve;
      });

      vi.spyOn(ApiService, 'getDistrictBlocks').mockImplementation(async (distId) => {
        if (distId === 1) {
          // Slow response for District 1
          await delayedFirstDistrictPromise;
          return mockBlocksNashik;
        }
        if (distId === 4) {
          // Fast response for District 4
          return mockBlocksPune;
        }
        return { total: 0, page: 1, page_size: 20, total_pages: 0, items: [] };
      });

      render(<HierarchicalPanchayatSelector onSelectPanchayat={vi.fn()} />);

      const triggerBtn = screen.getByRole('button', { name: /Administrative Scope/i });
      fireEvent.click(triggerBtn);

      await waitFor(() => screen.getByText('Nashik District'));

      // Trigger selection of Nashik (slow)
      fireEvent.click(screen.getByText('Nashik District'));

      // Immediately switch back to district step and pick Pune (fast)
      fireEvent.click(screen.getByRole('button', { name: /Step 1: Select District/i }));
      await waitFor(() => screen.getByText('Pune District'));
      fireEvent.click(screen.getByText('Pune District'));

      // Wait for Pune blocks to appear
      await waitFor(() => {
        expect(screen.getByText('Haveli')).toBeInTheDocument();
      });

      // Now resolve the stale District 1 request
      await act(async () => {
        resolveFirstDistrict!(mockBlocksNashik);
      });

      // Verify Pune blocks remain visible and stale Nashik blocks did NOT overwrite state
      expect(screen.getByText('Haveli')).toBeInTheDocument();
      expect(screen.queryByText('Baglan')).not.toBeInTheDocument();
    });
  });

  // =========================================================================
  // 3. PANCHAYAT SUITE
  // =========================================================================
  describe('Panchayat Selection', () => {
    it('loads Panchayats after selecting a block and transitions to panchayat step', async () => {
      render(
        <HierarchicalPanchayatSelector
          onSelectPanchayat={vi.fn()}
          selectedDistrictId={1}
        />
      );

      const triggerBtn = screen.getByRole('button', { name: /Administrative Scope/i });
      fireEvent.click(triggerBtn);

      // Click Baglan block
      await waitFor(() => {
        expect(screen.getByText('Baglan')).toBeInTheDocument();
      });
      fireEvent.click(screen.getByText('Baglan'));

      // Verify Panchayats load
      await waitFor(() => {
        expect(screen.getByText('Abhona')).toBeInTheDocument();
        expect(screen.getByText('Ajmer Saundane')).toBeInTheDocument();
      });
      expect(ApiService.getBlockPanchayats).toHaveBeenCalledWith(10, undefined, 1, 50);
    });

    it('supports server-side search by Panchayat name and LGD code', async () => {
      render(
        <HierarchicalPanchayatSelector
          onSelectPanchayat={vi.fn()}
          selectedDistrictId={1}
          selectedBlockId={10}
        />
      );

      const triggerBtn = screen.getByRole('button', { name: /Administrative Scope/i });
      fireEvent.click(triggerBtn);

      await waitFor(() => {
        expect(screen.getByPlaceholderText(/Search Baglan Panchayats or LGD/i)).toBeInTheDocument();
      });

      const searchInput = screen.getByPlaceholderText(/Search Baglan Panchayats or LGD/i);
      fireEvent.change(searchInput, { target: { value: 'Abh' } });

      await waitFor(() => {
        expect(ApiService.getBlockPanchayats).toHaveBeenCalledWith(10, 'Abh', 1, 50);
      });
    });

    it('calls onSelectPanchayat with complete payload and closes dropdown', async () => {
      const onSelectPanchayat = vi.fn();
      render(
        <HierarchicalPanchayatSelector
          onSelectPanchayat={onSelectPanchayat}
          selectedDistrictId={1}
          selectedBlockId={10}
        />
      );

      const triggerBtn = screen.getByRole('button', { name: /Administrative Scope/i });
      fireEvent.click(triggerBtn);

      await waitFor(() => {
        expect(screen.getByText('Abhona')).toBeInTheDocument();
      });

      // Click Abhona
      fireEvent.click(screen.getByText('Abhona'));

      expect(onSelectPanchayat).toHaveBeenCalledWith(
        expect.objectContaining({
          panchayat_id: 101,
          panchayat_name: 'Abhona',
          lgd_code: 187123,
          latitude: 20.63,
          longitude: 74.12,
          elevation_m: 550,
        })
      );

      // Verify dropdown closed
      expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    });

    it('stale panchayat search request cannot overwrite current search results', async () => {
      let resolveFirstSearch: (val: any) => void;
      const slowFirstSearch = new Promise((resolve) => {
        resolveFirstSearch = resolve;
      });

      vi.spyOn(ApiService, 'getBlockPanchayats').mockImplementation(async (_blockId, search) => {
        if (search === 'slow') {
          await slowFirstSearch;
          return {
            total: 1,
            page: 1,
            page_size: 50,
            total_pages: 1,
            items: [{ id: 999, lgd_code: 999999, name: 'Stale Panchayat', block_id: 10, district_id: 1 }],
          };
        }
        return mockPanchayatsBaglan;
      });

      render(
        <HierarchicalPanchayatSelector
          onSelectPanchayat={vi.fn()}
          selectedDistrictId={1}
          selectedBlockId={10}
        />
      );

      const triggerBtn = screen.getByRole('button', { name: /Administrative Scope/i });
      fireEvent.click(triggerBtn);

      await waitFor(() => screen.getByPlaceholderText(/Search Baglan Panchayats/i));
      const searchInput = screen.getByPlaceholderText(/Search Baglan Panchayats/i);

      // Fire slow search
      fireEvent.change(searchInput, { target: { value: 'slow' } });

      // Immediately change to quick search
      fireEvent.change(searchInput, { target: { value: 'quick' } });

      await waitFor(() => {
        expect(screen.getByText('Abhona')).toBeInTheDocument();
      });

      // Now resolve slow search
      await act(async () => {
        resolveFirstSearch!(null);
      });

      // Confirm stale result did NOT replace 'Abhona'
      expect(screen.queryByText('Stale Panchayat')).not.toBeInTheDocument();
      expect(screen.getByText('Abhona')).toBeInTheDocument();
    });
  });
});
