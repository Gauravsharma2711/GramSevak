export interface PanchayatItem {
  panchayat_id: number;
  lgd_code: number;
  panchayat_name: string;
  block_name: string;
  district_name: string;
  latitude: number;
  longitude: number;
  elevation_m: number;
}

export interface PanchayatPagination {
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
  items: PanchayatItem[];
}

export interface DistrictItem {
  id: number;
  name: string;
  code?: string | null;
  state?: string;
}

export interface DistrictPagination {
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
  items: DistrictItem[];
}

export interface BlockItem {
  id: number;
  district_id: number;
  name: string;
  code?: string | null;
}

export interface BlockPagination {
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
  items: BlockItem[];
}

export interface BlockPanchayatItem {
  id: number;
  lgd_code: number;
  name: string;
  block_id: number;
  district_id: number;
  latitude?: number;
  longitude?: number;
  elevation_m?: number;
  panchayat_id?: number;
  panchayat_name?: string;
}

export interface BlockPanchayatPagination {
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
  items: BlockPanchayatItem[];
}

export interface AdvisoryItem {
  id: number;
  panchayat_id: number;
  forecast_id: number;
  forecast_date: string;
  rainfall_mm: number;
  rainfall_category: string;
  severity: 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL';
  advisory_title: string;
  advisory_text: string;
  status: 'DRAFT' | 'NEEDS_REVIEW' | 'EDITED' | 'APPROVED' | 'REJECTED';
  version?: number;
  advisory_source?: string;
  validation_status?: string;
  validation_report?: Record<string, any> | null;
  original_content?: Record<string, any> | null;
  edited_content?: Record<string, any> | null;
  approved_content?: Record<string, any> | null;
  rejection_reason?: string | null;
  updated_at?: string;
  rule_id?: string;
  rule_version?: string;
  officer_id?: string | null;
  officer_comment?: string | null;
  approved_at?: string | null;
  created_at?: string;
  // Spatial & forecast metadata resolved for detail view
  panchayat_name?: string;
  block_name?: string;
  district_name?: string;
  elevation_m?: number;
  latitude?: number;
  longitude?: number;
  block_forecast_mm?: number;
  actual_observed_rainfall_mm?: number | null;
  forecast_issue_date?: string;
  model_name?: string;
  model_version?: string;
}

export interface DownscaledForecastDetail {
  id: number;
  panchayat_id: number;
  panchayat_name: string;
  block_name: string;
  district_name: string;
  forecast_date: string;
  forecast_issue_date: string;
  lead_days: number;
  block_forecast_rainfall_mm: number;
  downscaled_rainfall_mm: number;
  model_name: string;
  model_version: string;
  confidence?: number | null;
}

export interface OfficerApprovePayload {
  officer_id: string;
  officer_comment?: string;
  version?: number;
}

export interface OfficerRejectPayload {
  officer_id: string;
  reason?: string;
  officer_comment?: string;
  version?: number;
}

export interface OfficerEditPayload {
  officer_id: string;
  advisory_title: string;
  advisory_text: string;
  severity?: 'LOW' | 'MODERATE' | 'HIGH' | 'CRITICAL';
  officer_comment?: string;
  version?: number;
}

export interface AdvisoryAuditLogItem {
  id: number;
  advisory_id: number;
  action: string;
  officer_id?: string | null;
  previous_status?: string | null;
  new_status?: string | null;
  version: number;
  reason?: string | null;
  details?: Record<string, any> | null;
  created_at: string;
}

export interface GenerateForecastPayload {
  panchayat_id: number;
  forecast_date: string;
  forecast_issue_date: string;
}
