import React from 'react';
import { HierarchicalPanchayatSelector, HierarchicalPanchayatSelectorProps } from './HierarchicalPanchayatSelector';
import { PanchayatItem } from '../types';

export interface DemoPanchayatSelectorProps extends Partial<HierarchicalPanchayatSelectorProps> {
  onSelectPanchayat: (panchayat: PanchayatItem) => void;
  selectedPanchayatId?: number | null;
  className?: string;
}

/**
 * Universal Hierarchical Panchayat Selector.
 * 
 * Implements District → Block → Panchayat cascading hierarchy
 * backed by Phase 3 database APIs.
 */
export const DemoPanchayatSelector: React.FC<DemoPanchayatSelectorProps> = (props) => {
  return <HierarchicalPanchayatSelector {...props} />;
};
