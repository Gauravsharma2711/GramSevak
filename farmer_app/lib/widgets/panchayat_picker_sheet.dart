import 'dart:async';
import 'package:flutter/material.dart';
import '../models/panchayat_item.dart';
import '../models/hierarchy_models.dart';
import '../repositories/farmer_repository.dart';
import '../theme/app_theme.dart';
import '../l10n/app_localizations.dart';

enum PickerStep { district, block, panchayat }

/// Hierarchical District → Block → Panchayat Picker Sheet for Farmer App.
///
/// Follows Universal Farmer Product Design System:
/// - Step-by-step administrative hierarchy navigation
/// - Server-side search & bounded pagination
/// - Strict parent-child dependency reset
/// - Stale asynchronous response protection
/// - Accessible touch targets >= 48px
/// - Clear loading, empty, and retryable error states
class PanchayatPickerSheet extends StatefulWidget {
  final List<PanchayatItem>? panchayats;
  final int? selectedPanchayatId;
  final DistrictItem? initialDistrict;
  final BlockItem? initialBlock;
  final Function(PanchayatItem) onSelect;
  final FarmerRepository? repository;

  const PanchayatPickerSheet({
    super.key,
    this.panchayats,
    this.selectedPanchayatId,
    this.initialDistrict,
    this.initialBlock,
    required this.onSelect,
    this.repository,
  });

  @override
  State<PanchayatPickerSheet> createState() => _PanchayatPickerSheetState();
}

class _PanchayatPickerSheetState extends State<PanchayatPickerSheet> {
  late final FarmerRepository _repo;

  PickerStep _step = PickerStep.district;

  // Selected State
  DistrictItem? _selectedDistrict;
  BlockItem? _selectedBlock;
  PanchayatItem? _selectedPanchayat;

  // Step 1: District State
  List<DistrictItem> _districts = [];
  int _districtPage = 1;
  int _districtTotalPages = 1;
  int _districtTotal = 0;
  String _districtSearch = '';
  bool _loadingDistricts = false;
  String? _districtError;
  int _districtReqId = 0;

  // Step 2: Block State
  List<BlockItem> _blocks = [];
  int _blockPage = 1;
  int _blockTotalPages = 1;
  int _blockTotal = 0;
  String _blockSearch = '';
  bool _loadingBlocks = false;
  String? _blockError;
  int _blockReqId = 0;

  // Step 3: Panchayat State
  List<PanchayatItem> _panchayats = [];
  int _panchayatPage = 1;
  int _panchayatTotalPages = 1;
  int _panchayatTotal = 0;
  String _panchayatSearch = '';
  bool _loadingPanchayats = false;
  String? _panchayatError;
  int _panchayatReqId = 0;

  // Search Controller & Debounce
  final TextEditingController _searchController = TextEditingController();
  Timer? _debounceTimer;

  @override
  void initState() {
    super.initState();
    _repo = widget.repository ?? FarmerRepository();

    if (widget.initialDistrict != null) {
      _selectedDistrict = widget.initialDistrict;
      if (widget.initialBlock != null) {
        _selectedBlock = widget.initialBlock;
        _step = PickerStep.panchayat;
        _loadPanchayats();
      } else {
        _step = PickerStep.block;
        _loadBlocks();
      }
    } else {
      _step = PickerStep.district;
      _loadDistricts();
    }
  }

  @override
  void dispose() {
    _debounceTimer?.cancel();
    _searchController.dispose();
    super.dispose();
  }

  // --- API CALLS WITH RACE-CONDITION SAFETY ---

  Future<void> _loadDistricts() async {
    final reqId = ++_districtReqId;
    setState(() {
      _loadingDistricts = true;
      _districtError = null;
    });

    try {
      final res = await _repo.getDistricts(
        page: _districtPage,
        pageSize: 20,
        search:
            _districtSearch.trim().isNotEmpty ? _districtSearch.trim() : null,
      );

      if (!mounted || reqId != _districtReqId) return;

      setState(() {
        _districts = res.items;
        _districtTotal = res.total;
        _districtTotalPages = res.totalPages;
        _loadingDistricts = false;
      });
    } catch (_) {
      if (!mounted || reqId != _districtReqId) return;
      setState(() {
        _districtError = 'Unable to load districts.';
        _loadingDistricts = false;
      });
    }
  }

  Future<void> _loadBlocks() async {
    if (_selectedDistrict == null) return;
    final districtId = _selectedDistrict!.id;
    final reqId = ++_blockReqId;

    setState(() {
      _loadingBlocks = true;
      _blockError = null;
    });

    try {
      final res = await _repo.getDistrictBlocks(
        districtId,
        page: _blockPage,
        pageSize: 20,
        search: _blockSearch.trim().isNotEmpty ? _blockSearch.trim() : null,
      );

      if (!mounted || reqId != _blockReqId) return;

      setState(() {
        _blocks = res.items;
        _blockTotal = res.total;
        _blockTotalPages = res.totalPages;
        _loadingBlocks = false;
      });
    } catch (_) {
      if (!mounted || reqId != _blockReqId) return;
      setState(() {
        _blockError = 'Unable to load blocks for ${_selectedDistrict!.name}.';
        _loadingBlocks = false;
      });
    }
  }

  Future<void> _loadPanchayats() async {
    if (_selectedBlock == null) return;
    final blockId = _selectedBlock!.id;
    final reqId = ++_panchayatReqId;

    setState(() {
      _loadingPanchayats = true;
      _panchayatError = null;
    });

    try {
      final res = await _repo.getBlockPanchayats(
        blockId,
        page: _panchayatPage,
        pageSize: 50,
        search:
            _panchayatSearch.trim().isNotEmpty ? _panchayatSearch.trim() : null,
        blockName: _selectedBlock!.name,
        districtName: _selectedDistrict?.name,
      );

      if (!mounted || reqId != _panchayatReqId) return;

      setState(() {
        _panchayats = res.items;
        _panchayatTotal = res.total;
        _panchayatTotalPages = res.totalPages;
        _loadingPanchayats = false;
      });
    } catch (_) {
      if (!mounted || reqId != _panchayatReqId) return;
      setState(() {
        _panchayatError =
            'Unable to load Panchayats for ${_selectedBlock!.name}.';
        _loadingPanchayats = false;
      });
    }
  }

  // --- SELECTION HANDLERS WITH DEPENDENCY INVALIDATION ---

  void _onSelectDistrict(DistrictItem district) {
    setState(() {
      _selectedDistrict = district;
      _selectedBlock = null;
      _selectedPanchayat = null;
      _blocks = [];
      _panchayats = [];
      _blockPage = 1;
      _blockSearch = '';
      _panchayatPage = 1;
      _panchayatSearch = '';
      _step = PickerStep.block;
      _searchController.clear();
    });
    _loadBlocks();
  }

  void _onSelectBlock(BlockItem block) {
    setState(() {
      _selectedBlock = block;
      _selectedPanchayat = null;
      _panchayats = [];
      _panchayatPage = 1;
      _panchayatSearch = '';
      _step = PickerStep.panchayat;
      _searchController.clear();
    });
    _loadPanchayats();
  }

  void _onSelectPanchayat(PanchayatItem panchayat) {
    setState(() {
      _selectedPanchayat = panchayat;
    });
    widget.onSelect(panchayat);
    Navigator.of(context).pop();
  }

  // --- SEARCH DEBOUNCE ---

  void _onSearchChanged(String query) {
    _debounceTimer?.cancel();
    _debounceTimer = Timer(const Duration(milliseconds: 250), () {
      if (!mounted) return;
      switch (_step) {
        case PickerStep.district:
          _districtSearch = query;
          _districtPage = 1;
          _loadDistricts();
          break;
        case PickerStep.block:
          _blockSearch = query;
          _blockPage = 1;
          _loadBlocks();
          break;
        case PickerStep.panchayat:
          _panchayatSearch = query;
          _panchayatPage = 1;
          _loadPanchayats();
          break;
      }
    });
  }

  void _switchStep(PickerStep target) {
    if (target == PickerStep.block && _selectedDistrict == null) return;
    if (target == PickerStep.panchayat && _selectedBlock == null) return;

    _debounceTimer?.cancel();
    setState(() {
      _step = target;
      switch (target) {
        case PickerStep.district:
          _searchController.text = _districtSearch;
          if (_districts.isEmpty && !_loadingDistricts) _loadDistricts();
          break;
        case PickerStep.block:
          _searchController.text = _blockSearch;
          if (_blocks.isEmpty && !_loadingBlocks) _loadBlocks();
          break;
        case PickerStep.panchayat:
          _searchController.text = _panchayatSearch;
          if (_panchayats.isEmpty && !_loadingPanchayats) _loadPanchayats();
          break;
      }
    });
  }

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);

    return Material(
      color: AppColors.surface,
      borderRadius: const BorderRadius.vertical(top: Radius.circular(24)),
      child: Container(
        decoration: const BoxDecoration(
          borderRadius: BorderRadius.vertical(top: Radius.circular(24)),
        ),
        padding: EdgeInsets.fromLTRB(
          16,
          12,
          16,
          24 + MediaQuery.of(context).viewInsets.bottom,
        ),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // Drag handle
            Center(
              child: Container(
                width: 44,
                height: 4,
                decoration: BoxDecoration(
                  color: AppColors.ink300,
                  borderRadius: BorderRadius.circular(999),
                ),
              ),
            ),
            const SizedBox(height: 12),

            // Header
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                Text(
                  l10n.selectVillage,
                  style: const TextStyle(
                    fontSize: 18,
                    fontWeight: FontWeight.w700,
                    color: AppColors.ink900,
                  ),
                ),
                if (_selectedDistrict != null)
                  Container(
                    padding:
                        const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                    decoration: BoxDecoration(
                      color: AppColors.primary050,
                      borderRadius: BorderRadius.circular(999),
                      border: Border.all(color: AppColors.primary100),
                    ),
                    child: Row(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        const Icon(Icons.location_on,
                            size: 12, color: AppColors.primary700),
                        const SizedBox(width: 4),
                        Text(
                          _selectedDistrict!.name,
                          style: const TextStyle(
                            fontSize: 11,
                            fontWeight: FontWeight.w700,
                            color: AppColors.primary700,
                          ),
                        ),
                      ],
                    ),
                  ),
              ],
            ),
            const SizedBox(height: 10),

            // Breadcrumb Stepper Navigation
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
              decoration: BoxDecoration(
                color: AppColors.surfaceSubtle,
                borderRadius: BorderRadius.circular(8),
                border: Border.all(color: const Color(0xFFE5EAE7)),
              ),
              child: Row(
                children: [
                  // Step 1: District
                  Semantics(
                    button: true,
                    label: 'Step 1: District',
                    child: InkWell(
                      onTap: () => _switchStep(PickerStep.district),
                      borderRadius: BorderRadius.circular(4),
                      child: Padding(
                        padding: const EdgeInsets.symmetric(
                            horizontal: 4, vertical: 4),
                        child: Text(
                          '1. ${_selectedDistrict?.name ?? 'District'}',
                          style: TextStyle(
                            fontSize: 12,
                            fontWeight: _step == PickerStep.district
                                ? FontWeight.w700
                                : FontWeight.w500,
                            color: _step == PickerStep.district
                                ? AppColors.primary700
                                : AppColors.ink700,
                            decoration: _step == PickerStep.district
                                ? TextDecoration.underline
                                : null,
                          ),
                        ),
                      ),
                    ),
                  ),
                  const Icon(Icons.chevron_right,
                      size: 14, color: AppColors.ink300),

                  // Step 2: Block
                  Semantics(
                    button: true,
                    label: 'Step 2: Block',
                    child: InkWell(
                      onTap: _selectedDistrict != null
                          ? () => _switchStep(PickerStep.block)
                          : null,
                      borderRadius: BorderRadius.circular(4),
                      child: Padding(
                        padding: const EdgeInsets.symmetric(
                            horizontal: 4, vertical: 4),
                        child: Text(
                          '2. ${_selectedBlock?.name ?? 'Block'}',
                          style: TextStyle(
                            fontSize: 12,
                            fontWeight: _step == PickerStep.block
                                ? FontWeight.w700
                                : FontWeight.w500,
                            color: _selectedDistrict == null
                                ? AppColors.ink300
                                : (_step == PickerStep.block
                                    ? AppColors.primary700
                                    : AppColors.ink700),
                            decoration: _step == PickerStep.block
                                ? TextDecoration.underline
                                : null,
                          ),
                        ),
                      ),
                    ),
                  ),
                  const Icon(Icons.chevron_right,
                      size: 14, color: AppColors.ink300),

                  // Step 3: Panchayat
                  Semantics(
                    button: true,
                    label: 'Step 3: Gram Panchayat',
                    child: InkWell(
                      onTap: _selectedBlock != null
                          ? () => _switchStep(PickerStep.panchayat)
                          : null,
                      borderRadius: BorderRadius.circular(4),
                      child: Padding(
                        padding: const EdgeInsets.symmetric(
                            horizontal: 4, vertical: 4),
                        child: Text(
                          '3. ${_selectedPanchayat?.panchayatName ?? 'Village'}',
                          style: TextStyle(
                            fontSize: 12,
                            fontWeight: _step == PickerStep.panchayat
                                ? FontWeight.w700
                                : FontWeight.w500,
                            color: _selectedBlock == null
                                ? AppColors.ink300
                                : (_step == PickerStep.panchayat
                                    ? AppColors.primary700
                                    : AppColors.ink700),
                            decoration: _step == PickerStep.panchayat
                                ? TextDecoration.underline
                                : null,
                          ),
                        ),
                      ),
                    ),
                  ),
                ],
              ),
            ),
            const SizedBox(height: 12),

            // Search Field
            TextField(
              controller: _searchController,
              onChanged: _onSearchChanged,
              decoration: InputDecoration(
                hintText: _step == PickerStep.district
                    ? 'Search District...'
                    : (_step == PickerStep.block
                        ? 'Search Blocks in ${_selectedDistrict?.name ?? ''}...'
                        : 'Search Villages in ${_selectedBlock?.name ?? ''}...'),
                prefixIcon:
                    const Icon(Icons.search, color: AppColors.ink500, size: 20),
                suffixIcon: (_step == PickerStep.district &&
                            _loadingDistricts) ||
                        (_step == PickerStep.block && _loadingBlocks) ||
                        (_step == PickerStep.panchayat && _loadingPanchayats)
                    ? const Padding(
                        padding: EdgeInsets.all(12.0),
                        child: SizedBox(
                          width: 14,
                          height: 14,
                          child: CircularProgressIndicator(
                              strokeWidth: 2, color: AppColors.primary500),
                        ),
                      )
                    : null,
                filled: true,
                fillColor: AppColors.surfaceSubtle,
                contentPadding:
                    const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
                border: OutlineInputBorder(
                  borderRadius: BorderRadius.circular(12),
                  borderSide: const BorderSide(color: Color(0xFFE5EAE7)),
                ),
                enabledBorder: OutlineInputBorder(
                  borderRadius: BorderRadius.circular(12),
                  borderSide: const BorderSide(color: Color(0xFFE5EAE7)),
                ),
                focusedBorder: OutlineInputBorder(
                  borderRadius: BorderRadius.circular(12),
                  borderSide: const BorderSide(color: AppColors.primary500),
                ),
              ),
            ),
            const SizedBox(height: 10),

            // CONTENT ACCORDING TO STEP
            if (_step == PickerStep.district) _buildDistrictStep(context),
            if (_step == PickerStep.block) _buildBlockStep(context),
            if (_step == PickerStep.panchayat) _buildPanchayatStep(context),
          ],
        ),
      ),
    );
  }

  // --- STEP 1: DISTRICT WIDGET ---

  Widget _buildDistrictStep(BuildContext context) {
    if (_loadingDistricts) {
      return const Center(
        child: Padding(
          padding: EdgeInsets.all(32),
          child: CircularProgressIndicator(color: AppColors.primary500),
        ),
      );
    }

    if (_districtError != null) {
      return Center(
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: Column(
            children: [
              Text(_districtError!,
                  style: const TextStyle(
                      color: AppColors.danger600, fontSize: 13)),
              const SizedBox(height: 8),
              ElevatedButton(
                onPressed: _loadDistricts,
                style: ElevatedButton.styleFrom(
                  minimumSize: const Size(120, 48),
                ),
                child: const Text('Retry'),
              ),
            ],
          ),
        ),
      );
    }

    if (_districts.isEmpty) {
      return Center(
        child: Padding(
          padding: const EdgeInsets.all(24.0),
          child: Text(
            _districtSearch.isNotEmpty
                ? 'No districts found matching "$_districtSearch".'
                : 'No districts found.',
            style: const TextStyle(fontSize: 13, color: AppColors.ink500),
          ),
        ),
      );
    }

    return Column(
      mainAxisSize: MainAxisSize.min,
      children: [
        ConstrainedBox(
          constraints: BoxConstraints(
              maxHeight: MediaQuery.of(context).size.height * 0.38),
          child: ListView.separated(
            shrinkWrap: true,
            itemCount: _districts.length,
            separatorBuilder: (_, __) => const SizedBox(height: 8),
            itemBuilder: (ctx, idx) {
              final d = _districts[idx];
              final isSelected = d.id == _selectedDistrict?.id;
              return InkWell(
                onTap: () => _onSelectDistrict(d),
                borderRadius: BorderRadius.circular(10),
                child: Container(
                  constraints: const BoxConstraints(minHeight: 48),
                  padding:
                      const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
                  decoration: BoxDecoration(
                    color:
                        isSelected ? AppColors.primary050 : AppColors.surface,
                    borderRadius: BorderRadius.circular(10),
                    border: Border.all(
                      color: isSelected
                          ? AppColors.primary500
                          : const Color(0xFFE5EAE7),
                      width: isSelected ? 1.5 : 1.0,
                    ),
                  ),
                  child: Row(
                    mainAxisAlignment: MainAxisAlignment.spaceBetween,
                    children: [
                      Text(
                        '${d.name} District',
                        style: TextStyle(
                          fontSize: 14,
                          fontWeight:
                              isSelected ? FontWeight.w700 : FontWeight.w600,
                          color: isSelected
                              ? AppColors.primary700
                              : AppColors.ink900,
                        ),
                      ),
                      const Icon(Icons.chevron_right,
                          size: 18, color: AppColors.ink500),
                    ],
                  ),
                ),
              );
            },
          ),
        ),
        if (_districtTotalPages > 1)
          _buildPaginationBar(
            page: _districtPage,
            totalPages: _districtTotalPages,
            totalCount: _districtTotal,
            onPrev: () {
              setState(() => _districtPage--);
              _loadDistricts();
            },
            onNext: () {
              setState(() => _districtPage++);
              _loadDistricts();
            },
          ),
      ],
    );
  }

  // --- STEP 2: BLOCK WIDGET ---

  Widget _buildBlockStep(BuildContext context) {
    if (_loadingBlocks) {
      return const Center(
        child: Padding(
          padding: EdgeInsets.all(32),
          child: CircularProgressIndicator(color: AppColors.primary500),
        ),
      );
    }

    if (_blockError != null) {
      return Center(
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: Column(
            children: [
              Text(_blockError!,
                  style: const TextStyle(
                      color: AppColors.danger600, fontSize: 13)),
              const SizedBox(height: 8),
              ElevatedButton(
                onPressed: _loadBlocks,
                style: ElevatedButton.styleFrom(
                  minimumSize: const Size(120, 48),
                ),
                child: const Text('Retry'),
              ),
            ],
          ),
        ),
      );
    }

    if (_blocks.isEmpty) {
      return Center(
        child: Padding(
          padding: const EdgeInsets.all(24.0),
          child: Text(
            _blockSearch.isNotEmpty
                ? 'No blocks found matching "$_blockSearch".'
                : 'No blocks found in ${_selectedDistrict?.name ?? 'selected district'}.',
            style: const TextStyle(fontSize: 13, color: AppColors.ink500),
          ),
        ),
      );
    }

    return Column(
      mainAxisSize: MainAxisSize.min,
      children: [
        ConstrainedBox(
          constraints: BoxConstraints(
              maxHeight: MediaQuery.of(context).size.height * 0.38),
          child: GridView.builder(
            shrinkWrap: true,
            gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
              crossAxisCount: 2,
              childAspectRatio: 2.6,
              crossAxisSpacing: 8,
              mainAxisSpacing: 8,
            ),
            itemCount: _blocks.length,
            itemBuilder: (ctx, idx) {
              final b = _blocks[idx];
              final isSelected = b.id == _selectedBlock?.id;
              return InkWell(
                onTap: () => _onSelectBlock(b),
                borderRadius: BorderRadius.circular(10),
                child: Container(
                  constraints: const BoxConstraints(minHeight: 48),
                  padding:
                      const EdgeInsets.symmetric(horizontal: 10, vertical: 8),
                  decoration: BoxDecoration(
                    color:
                        isSelected ? AppColors.primary050 : AppColors.surface,
                    borderRadius: BorderRadius.circular(10),
                    border: Border.all(
                      color: isSelected
                          ? AppColors.primary500
                          : const Color(0xFFE5EAE7),
                      width: isSelected ? 1.5 : 1.0,
                    ),
                  ),
                  alignment: Alignment.center,
                  child: Text(
                    b.name,
                    style: TextStyle(
                      fontSize: 13,
                      fontWeight:
                          isSelected ? FontWeight.w700 : FontWeight.w600,
                      color:
                          isSelected ? AppColors.primary700 : AppColors.ink900,
                    ),
                    overflow: TextOverflow.ellipsis,
                  ),
                ),
              );
            },
          ),
        ),
        if (_blockTotalPages > 1)
          _buildPaginationBar(
            page: _blockPage,
            totalPages: _blockTotalPages,
            totalCount: _blockTotal,
            onPrev: () {
              setState(() => _blockPage--);
              _loadBlocks();
            },
            onNext: () {
              setState(() => _blockPage++);
              _loadBlocks();
            },
          ),
      ],
    );
  }

  // --- STEP 3: PANCHAYAT WIDGET ---

  Widget _buildPanchayatStep(BuildContext context) {
    if (_loadingPanchayats) {
      return const Center(
        child: Padding(
          padding: EdgeInsets.all(32),
          child: CircularProgressIndicator(color: AppColors.primary500),
        ),
      );
    }

    if (_panchayatError != null) {
      return Center(
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: Column(
            children: [
              Text(_panchayatError!,
                  style: const TextStyle(
                      color: AppColors.danger600, fontSize: 13)),
              const SizedBox(height: 8),
              ElevatedButton(
                onPressed: _loadPanchayats,
                style: ElevatedButton.styleFrom(
                  minimumSize: const Size(120, 48),
                ),
                child: const Text('Retry'),
              ),
            ],
          ),
        ),
      );
    }

    if (_panchayats.isEmpty) {
      return Center(
        child: Padding(
          padding: const EdgeInsets.all(24.0),
          child: Text(
            _panchayatSearch.isNotEmpty
                ? 'No villages found matching "$_panchayatSearch".'
                : 'No villages found in ${_selectedBlock?.name ?? 'this block'}.',
            style: const TextStyle(fontSize: 13, color: AppColors.ink500),
          ),
        ),
      );
    }

    return Column(
      mainAxisSize: MainAxisSize.min,
      children: [
        ConstrainedBox(
          constraints: BoxConstraints(
              maxHeight: MediaQuery.of(context).size.height * 0.38),
          child: ListView.separated(
            shrinkWrap: true,
            itemCount: _panchayats.length,
            separatorBuilder: (_, __) =>
                const Divider(color: Color(0xFFF0F4F1), height: 1),
            itemBuilder: (ctx, idx) {
              final p = _panchayats[idx];
              final isSelected = p.panchayatId == widget.selectedPanchayatId ||
                  p.panchayatId == _selectedPanchayat?.panchayatId;
              return Material(
                color: Colors.transparent,
                child: ListTile(
                  minLeadingWidth: 0,
                  contentPadding:
                      const EdgeInsets.symmetric(horizontal: 4, vertical: 4),
                  leading: Container(
                    width: 36,
                    height: 36,
                    decoration: BoxDecoration(
                      color: isSelected
                          ? AppColors.primary100
                          : AppColors.surfaceSubtle,
                      borderRadius: BorderRadius.circular(8),
                    ),
                    child: Icon(
                      Icons.location_on_outlined,
                      color:
                          isSelected ? AppColors.primary700 : AppColors.ink500,
                      size: 18,
                    ),
                  ),
                  title: Row(
                    children: [
                      Flexible(
                        child: Text(
                          p.panchayatName,
                          style: TextStyle(
                            fontSize: 14,
                            fontWeight:
                                isSelected ? FontWeight.w700 : FontWeight.w600,
                            color: isSelected
                                ? AppColors.primary700
                                : AppColors.ink900,
                          ),
                          overflow: TextOverflow.ellipsis,
                        ),
                      ),
                      const SizedBox(width: 6),
                      Container(
                        padding: const EdgeInsets.symmetric(
                            horizontal: 5, vertical: 1),
                        decoration: BoxDecoration(
                          color: AppColors.ink100,
                          borderRadius: BorderRadius.circular(4),
                        ),
                        child: Text(
                          'LGD ${p.lgdCode}',
                          style: const TextStyle(
                              fontSize: 10,
                              color: AppColors.ink700,
                              fontWeight: FontWeight.w600),
                        ),
                      ),
                    ],
                  ),
                  subtitle: Text(
                    '${p.blockName} Block • ${p.districtName} • ${p.elevationM.round()}m',
                    style:
                        const TextStyle(fontSize: 12, color: AppColors.ink500),
                  ),
                  trailing: isSelected
                      ? const Icon(Icons.check_circle,
                          color: AppColors.primary600, size: 20)
                      : const Icon(Icons.chevron_right,
                          color: AppColors.ink300, size: 18),
                  onTap: () => _onSelectPanchayat(p),
                ),
              );
            },
          ),
        ),
        if (_panchayatTotalPages > 1)
          _buildPaginationBar(
            page: _panchayatPage,
            totalPages: _panchayatTotalPages,
            totalCount: _panchayatTotal,
            onPrev: () {
              setState(() => _panchayatPage--);
              _loadPanchayats();
            },
            onNext: () {
              setState(() => _panchayatPage++);
              _loadPanchayats();
            },
          ),
      ],
    );
  }

  // --- REUSABLE PAGINATION BAR ---

  Widget _buildPaginationBar({
    required int page,
    required int totalPages,
    required int totalCount,
    required VoidCallback onPrev,
    required VoidCallback onNext,
  }) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 8),
      margin: const EdgeInsets.only(top: 8),
      decoration: BoxDecoration(
        color: AppColors.surfaceSubtle,
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: const Color(0xFFE5EAE7)),
      ),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          Text(
            'Page $page of $totalPages ($totalCount total)',
            style: const TextStyle(
                fontSize: 12,
                fontWeight: FontWeight.w600,
                color: AppColors.ink700),
          ),
          Row(
            children: [
              Semantics(
                button: true,
                label: 'Previous Page',
                child: TextButton(
                  onPressed: page > 1 ? onPrev : null,
                  style: TextButton.styleFrom(
                    minimumSize: const Size(48, 36),
                    padding: const EdgeInsets.symmetric(horizontal: 8),
                  ),
                  child: const Text('Prev',
                      style: TextStyle(fontWeight: FontWeight.w700)),
                ),
              ),
              const SizedBox(width: 4),
              Semantics(
                button: true,
                label: 'Next Page',
                child: TextButton(
                  onPressed: page < totalPages ? onNext : null,
                  style: TextButton.styleFrom(
                    minimumSize: const Size(48, 36),
                    padding: const EdgeInsets.symmetric(horizontal: 8),
                  ),
                  child: const Text('Next',
                      style: TextStyle(fontWeight: FontWeight.w700)),
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }
}
