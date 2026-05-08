import type { ComponentType, ReactNode } from "react";

export type P0PageId =
  | "city"
  | "risk"
  | "data"
  | "evidence"
  | "mainline"
  | "worldline"
  | "council"
  | "brief"
  | "memory"
  | "library"
  | "config";

export type P0ActionId =
  | "select-theme"
  | "capture-data"
  | "review-evidence"
  | "reject-evidence"
  | "confirm-risk-factor"
  | "confirm-mainline"
  | "generate-worldline"
  | "run-council"
  | "confirm-brief"
  | "update-task";

export type P0PageTone = "blue" | "green" | "amber" | "red" | "violet" | "cyan" | "gray";

export type P0Metric = {
  id: string;
  label: string;
  value: string;
  helper?: string;
  tone?: P0PageTone;
};

export type P0Tag = {
  id: string;
  label: string;
  tone?: P0PageTone;
};

export type P0TableColumn = {
  key: string;
  label: string;
  width?: string;
};

export type P0TableRow = {
  id: string;
  title?: string;
  cells: Record<string, ReactNode>;
  tone?: P0PageTone;
  action?: P0PageAction;
};

export type P0PageAction = {
  id: P0ActionId;
  label: string;
  targetId?: string;
  variant?: "primary" | "secondary" | "danger";
  disabled?: boolean;
  reason?: string;
};

export type P0EvidenceItem = {
  id: string;
  title: string;
  source: string;
  status: string;
  credibility?: string;
  sensitivity?: string;
  excerpt: string;
  tags?: P0Tag[];
  actions?: P0PageAction[];
};

export type P0SubjectOutput = {
  id: string;
  role: string;
  stance: string;
  reaction: string;
  uncertainty?: string;
  evidenceRefs?: string[];
  blockedClaims?: string[];
  deltas?: Array<{ label: string; value: string; tone?: P0PageTone }>;
};

export type P0TimelineItem = {
  id: string;
  label: string;
  status: "done" | "active" | "pending";
  helper?: string;
};

export type P0BranchItem = {
  id: string;
  title: string;
  branch: string;
  probability: number;
  risk: number;
  status: string;
  summary?: string;
  action?: P0PageAction;
};

export type P0Section = {
  id: string;
  title: string;
  eyebrow?: string;
  helper?: string;
  tone?: P0PageTone;
  metrics?: P0Metric[];
  tags?: P0Tag[];
  body?: ReactNode;
  table?: {
    columns: P0TableColumn[];
    rows: P0TableRow[];
  };
  items?: Array<{
    id: string;
    title: string;
    helper?: string;
    value?: string;
    status?: string;
    tone?: P0PageTone;
    tags?: P0Tag[];
    action?: P0PageAction;
  }>;
  evidence?: P0EvidenceItem[];
  subjects?: P0SubjectOutput[];
  timeline?: P0TimelineItem[];
  branches?: P0BranchItem[];
  actions?: P0PageAction[];
};

export type P0PageViewModel = {
  page: P0PageId;
  caseId: string;
  title: string;
  subtitle?: string;
  scenarioLabel?: string;
  updatedAt?: string;
  primaryAction?: P0PageAction;
  metrics?: P0Metric[];
  sections: P0Section[];
  nav?: Array<{ page: P0PageId; label: string; helper?: string }>;
};

export type P0PageActionRunner = (action: P0PageAction) => void | Promise<void>;

export type P0PageRendererProps = {
  view: P0PageViewModel;
  onAction?: P0PageActionRunner;
  isActionPending?: (action: P0PageAction) => boolean;
  className?: string;
  iconForPage?: Partial<Record<P0PageId, ComponentType<{ size?: number }>>>;
};
