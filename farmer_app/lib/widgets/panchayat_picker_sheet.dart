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
/// - Glanceable, step-by-step administrative hierarchy navigation
/// - Server-side search & bounded pagination
/// - Touch targets >= 48px
/// - Clear loading, empty, and retryable error states
class PanchayatPickerSheet extends StatefulWidget {
  final List<PanchayatItem> panchayats;
  final int selectedPanchayatId;
  final Function(PanchayatItem) onSelect;
  final FarmerRepository? repository;

  const PanchayatPickerSheet({
    super.key,
    required this.panchayats,
    required this.selectedPanchayatId,
    required this.onSelect,
    this.repository,
  });

  @override
  State<PanchayatPickerSheet> createState() => _PanchayatPickerSheetState();
}

class _PanchayatPickerSheetState extends State<PanchayatPickerSheet> {
  late final FarmerRepository _repo;

  PickerStep _step = PickerStep.panchayat;

  // Hierarchy Data
  List<DistrictItem> _districts = [];
  List<BlockItem> _blocks = [];
  List<PanchayatItem> _panchayats = [];

  DistrictItem _selectedDistrict = DistrictItem(id: 1, name: 'Nashik', state: 'Maharashtra');
  BlockItem? _selectedBlock;
  PanchayatItem? _activePanchayat;

  // Search & Loading State
  String _searchQuery = '';
  Timer? _debounceTimer;
  bool _isLoading = false;
  String? _errorMessage;

  @override
  void initState() {
    super.initState();
    _repo = widget.repository ?? FarmerRepository();
    _panchayats = widget.panchayats;

    // Detect active panchayat if present in widget.panchayats
    for (final p in widget.panchayats) {
      if (p.panchayatId == widget.selectedPanchayatId) {
        _activePanchayat = p;
        break;
      }
    }

    _loadDistricts();
  }

  @override
  void dispose() {
    _debounceTimer?.cancel();
    super.dispose();
  }

  Future<void> _loadDistricts() async {
    setState(() {
      _isLoading = true;
      _errorMessage = null;
    });
    try {
      final list = await _repo.getDistricts();
      if (mounted) {
        setState(() {
          _districts = list;
          _isLoading = false;
        });
      }
    } catch (_) {
      if (mounted) {
        setState(() {
          _errorMessage = 'Unable to load districts.';
          _isLoading = false;
        });
      }
    }
  }

  Future<void> _loadBlocks(DistrictItem district) async {
    setState(() {
      _selectedDistrict = district;
      _selectedBlock = null;
      _isLoading = true;
      _errorMessage = null;
      _step = PickerStep.block;
    });
    try {
      final list = await _repo.getDistrictBlocks(district.id);
      if (mounted) {
        setState(() {
          _blocks = list;
          _isLoading = false;
        });
      }
    } catch (_) {
      if (mounted) {
        setState(() {
          _errorMessage = 'Unable to load blocks for ${district.name}.';
          _isLoading = false;
        });
      }
    }
  }

  Future<void> _loadPanchayats(BlockItem block, {String query = ''}) async {
    setState(() {
      _selectedBlock = block;
      _searchQuery = query;
      _isLoading = true;
      _errorMessage = null;
      _step = PickerStep.panchayat;
    });
    try {
      final list = await _repo.getBlockPanchayats(
        block.id,
        search: query.trim().isNotEmpty ? query.trim() : null,
        blockName: block.name,
        districtName: _selectedDistrict.name,
      );
      if (mounted) {
        setState(() {
          _panchayats = list;
          _isLoading = false;
        });
      }
    } catch (_) {
      if (mounted) {
        setState(() {
          _errorMessage = 'Unable to load Panchayats for ${block.name}.';
          _isLoading = false;
        });
      }
    }
  }

  void _onSearchChanged(String query) {
    _debounceTimer?.cancel();
    _debounceTimer = Timer(const Duration(milliseconds: 250), () {
      if (!mounted) return;
      if (_selectedBlock != null) {
        _loadPanchayats(_selectedBlock!, query: query);
      } else {
        // Fallback search across flat panchayats
        setState(() => _isLoading = true);
        _repo.getPanchayats(search: query.trim()).then((res) {
          if (mounted) {
            setState(() {
              _panchayats = res;
              _isLoading = false;
            });
          }
        }).catchError((_) {
          if (mounted) setState(() => _isLoading = false);
        });
      }
    });
  }

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);

    return Container(
      decoration: const BoxDecoration(
        color: AppColors.surface,
        borderRadius: BorderRadius.vertical(top: Radius.circular(24)),
      ),
      padding: const EdgeInsets.fromLTRB(16, 12, 16, 24),
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

          // Header with Hierarchy Stepper
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
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                decoration: BoxDecoration(
                  color: AppColors.primary050,
                  borderRadius: BorderRadius.circular(999),
                  border: Border.all(color: AppColors.primary100),
                ),
                child: Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    const Icon(Icons.location_on, size: 12, color: AppColors.primary700),
                    const SizedBox(width: 4),
                    Text(
                      _selectedDistrict.name,
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
          const SizedBox(height: 8),

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
                InkWell(
                  onTap: () => setState(() => _step = PickerStep.district),
                  borderRadius: BorderRadius.circular(4),
                  child: Padding(
                    padding: const EdgeInsets.symmetric(horizontal: 4, vertical: 2),
                    child: Text(
                      '1. ${_selectedDistrict.name}',
                      style: TextStyle(
                        fontSize: 12,
                        fontWeight: _step == PickerStep.district ? FontWeight.w700 : FontWeight.w500,
                        color: _step == PickerStep.district ? AppColors.primary700 : AppColors.ink700,
                        decoration: _step == PickerStep.district ? TextDecoration.underline : null,
                      ),
                    ),
                  ),
                ),
                const Icon(Icons.chevron_right, size: 14, color: AppColors.ink300),
                InkWell(
                  onTap: () {
                    if (_blocks.isEmpty) {
                      _loadBlocks(_selectedDistrict);
                    } else {
                      setState(() => _step = PickerStep.block);
                    }
                  },
                  borderRadius: BorderRadius.circular(4),
                  child: Padding(
                    padding: const EdgeInsets.symmetric(horizontal: 4, vertical: 2),
                    child: Text(
                      '2. ${_selectedBlock?.name ?? 'Block'}',
                      style: TextStyle(
                        fontSize: 12,
                        fontWeight: _step == PickerStep.block ? FontWeight.w700 : FontWeight.w500,
                        color: _step == PickerStep.block ? AppColors.primary700 : AppColors.ink700,
                        decoration: _step == PickerStep.block ? TextDecoration.underline : null,
                      ),
                    ),
                  ),
                ),
                const Icon(Icons.chevron_right, size: 14, color: AppColors.ink300),
                Padding(
                  padding: const EdgeInsets.symmetric(horizontal: 4, vertical: 2),
                  child: Text(
                    '3. Gram Panchayat',
                    style: TextStyle(
                      fontSize: 12,
                      fontWeight: _step == PickerStep.panchayat ? FontWeight.w700 : FontWeight.w500,
                      color: _step == PickerStep.panchayat ? AppColors.primary700 : AppColors.ink500,
                    ),
                  ),
                ),
              ],
            ),
          ),
          const SizedBox(height: 12),

          // STEP 1: DISTRICT SELECTION
          if (_step == PickerStep.district) ...[
            const Text(
              'Select Administrative District:',
              style: TextStyle(fontSize: 13, fontWeight: FontWeight.w600, color: AppColors.ink900),
            ),
            const SizedBox(height: 8),
            if (_isLoading)
              const Center(child: Padding(padding: EdgeInsets.all(24), child: CircularProgressIndicator(color: AppColors.primary500)))
            else if (_errorMessage != null)
              Center(
                child: Padding(
                  padding: const EdgeInsets.all(16),
                  child: Column(
                    children: [
                      Text(_errorMessage!, style: const TextStyle(color: AppColors.danger600, fontSize: 13)),
                      TextButton(onPressed: _loadDistricts, child: const Text('Retry')),
                    ],
                  ),
                ),
              )
            else
              ConstrainedBox(
                constraints: BoxConstraints(maxHeight: MediaQuery.of(context).size.height * 0.40),
                child: ListView.separated(
                  shrinkWrap: true,
                  itemCount: _districts.length,
                  separatorBuilder: (_, __) => const SizedBox(height: 8),
                  itemBuilder: (ctx, idx) {
                    final d = _districts[idx];
                    final isSelected = d.id == _selectedDistrict.id;
                    return InkWell(
                      onTap: () => _loadBlocks(d),
                      borderRadius: BorderRadius.circular(10),
                      child: Container(
                        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
                        decoration: BoxDecoration(
                          color: isSelected ? AppColors.primary050 : AppColors.surface,
                          borderRadius: BorderRadius.circular(10),
                          border: Border.all(
                            color: isSelected ? AppColors.primary500 : const Color(0xFFE5EAE7),
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
                                fontWeight: isSelected ? FontWeight.w700 : FontWeight.w600,
                                color: isSelected ? AppColors.primary700 : AppColors.ink900,
                              ),
                            ),
                            const Icon(Icons.chevron_right, size: 18, color: AppColors.ink500),
                          ],
                        ),
                      ),
                    );
                  },
                ),
              ),
          ],

          // STEP 2: BLOCK SELECTION
          if (_step == PickerStep.block) ...[
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                Text(
                  'Blocks in ${_selectedDistrict.name} (${_blocks.length}):',
                  style: const TextStyle(fontSize: 13, fontWeight: FontWeight.w600, color: AppColors.ink900),
                ),
                TextButton(
                  onPressed: () => setState(() => _step = PickerStep.district),
                  child: const Text('Change District', style: TextStyle(fontSize: 11, color: AppColors.primary700)),
                ),
              ],
            ),
            const SizedBox(height: 6),
            if (_isLoading)
              const Center(child: Padding(padding: EdgeInsets.all(24), child: CircularProgressIndicator(color: AppColors.primary500)))
            else if (_errorMessage != null)
              Center(
                child: Padding(
                  padding: const EdgeInsets.all(16),
                  child: Column(
                    children: [
                      Text(_errorMessage!, style: const TextStyle(color: AppColors.danger600, fontSize: 13)),
                      TextButton(onPressed: () => _loadBlocks(_selectedDistrict), child: const Text('Retry')),
                    ],
                  ),
                ),
              )
            else
              ConstrainedBox(
                constraints: BoxConstraints(maxHeight: MediaQuery.of(context).size.height * 0.40),
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
                      onTap: () => _loadPanchayats(b),
                      borderRadius: BorderRadius.circular(10),
                      child: Container(
                        padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 8),
                        decoration: BoxDecoration(
                          color: isSelected ? AppColors.primary050 : AppColors.surface,
                          borderRadius: BorderRadius.circular(10),
                          border: Border.all(
                            color: isSelected ? AppColors.primary500 : const Color(0xFFE5EAE7),
                            width: isSelected ? 1.5 : 1.0,
                          ),
                        ),
                        alignment: Alignment.center,
                        child: Text(
                          b.name,
                          style: TextStyle(
                            fontSize: 13,
                            fontWeight: isSelected ? FontWeight.w700 : FontWeight.w600,
                            color: isSelected ? AppColors.primary700 : AppColors.ink900,
                          ),
                        ),
                      ),
                    );
                  },
                ),
              ),
          ],

          // STEP 3: PANCHAYAT SELECTION
          if (_step == PickerStep.panchayat) ...[
            // Search Field
            TextField(
              onChanged: _onSearchChanged,
              decoration: InputDecoration(
                hintText: _selectedBlock != null
                    ? 'Search ${_selectedBlock!.name} Panchayats...'
                    : l10n.searchVillage,
                prefixIcon: const Icon(Icons.search, color: AppColors.ink500, size: 20),
                suffixIcon: _isLoading
                    ? const Padding(
                        padding: EdgeInsets.all(12.0),
                        child: SizedBox(
                          width: 14,
                          height: 14,
                          child: CircularProgressIndicator(strokeWidth: 2, color: AppColors.primary500),
                        ),
                      )
                    : null,
                filled: true,
                fillColor: AppColors.surfaceSubtle,
                contentPadding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
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

            // Panchayat List View
            ConstrainedBox(
              constraints: BoxConstraints(
                maxHeight: MediaQuery.of(context).size.height * 0.40,
              ),
              child: _panchayats.isEmpty && !_isLoading
                  ? Center(
                      child: Padding(
                        padding: const EdgeInsets.all(24.0),
                        child: Text(
                          _searchQuery.isNotEmpty
                              ? 'No Panchayats match "$_searchQuery".'
                              : 'No Panchayats found in this block.',
                          style: const TextStyle(fontSize: 13, color: AppColors.ink500),
                        ),
                      ),
                    )
                  : ListView.separated(
                      shrinkWrap: true,
                      itemCount: _panchayats.length,
                      separatorBuilder: (_, __) => const Divider(color: Color(0xFFF0F4F1), height: 1),
                      itemBuilder: (ctx, idx) {
                        final p = _panchayats[idx];
                        final isSelected = p.panchayatId == widget.selectedPanchayatId;
                        return ListTile(
                          minLeadingWidth: 0,
                          contentPadding: const EdgeInsets.symmetric(horizontal: 4, vertical: 4),
                          leading: Container(
                            width: 36,
                            height: 36,
                            decoration: BoxDecoration(
                              color: isSelected ? AppColors.primary100 : AppColors.surfaceSubtle,
                              borderRadius: BorderRadius.circular(8),
                            ),
                            child: Icon(
                              Icons.location_on_outlined,
                              color: isSelected ? AppColors.primary700 : AppColors.ink500,
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
                                    fontWeight: isSelected ? FontWeight.w700 : FontWeight.w600,
                                    color: isSelected ? AppColors.primary700 : AppColors.ink900,
                                  ),
                                  overflow: TextOverflow.ellipsis,
                                ),
                              ),
                              const SizedBox(width: 6),
                              Container(
                                padding: const EdgeInsets.symmetric(horizontal: 5, vertical: 1),
                                decoration: BoxDecoration(
                                  color: AppColors.ink100,
                                  borderRadius: BorderRadius.circular(4),
                                ),
                                child: Text(
                                  'LGD ${p.lgdCode}',
                                  style: const TextStyle(fontSize: 10, color: AppColors.ink700, fontWeight: FontWeight.w600),
                                ),
                              ),
                            ],
                          ),
                          subtitle: Text(
                            '${p.blockName} Block • ${p.districtName} • ${p.elevationM.round()}m',
                            style: const TextStyle(fontSize: 12, color: AppColors.ink500),
                          ),
                          trailing: isSelected
                              ? const Icon(Icons.check_circle, color: AppColors.primary600, size: 20)
                              : const Icon(Icons.chevron_right, color: AppColors.ink300, size: 18),
                          onTap: () {
                            widget.onSelect(p);
                            Navigator.pop(context);
                          },
                        );
                      },
                    ),
            ),
          ],
        ],
      ),
    );
  }
}
